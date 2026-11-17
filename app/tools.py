from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from typing import Any, Callable

from app import audit
from app.identity import ANY, SELF, Requester
from app.store import store

ALL_TOOLS = ("search_kb", "lookup_user", "reset_password", "create_ticket")
WRITE_TOOLS = frozenset({"reset_password", "create_ticket"})
QUEUES = {
    "password": "Identity and Access",
    "access": "Identity and Access",
    "hardware": "End-user Devices",
    "software": "Applications",
    "network": "Network",
    "other": "Service Desk",
}


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool may rely on. The model never supplies any of it."""

    requester: Requester
    run_id: str
    category: str
    impact: str
    allowed: frozenset[str]


def ok(data: dict[str, Any], hint: str = "") -> dict[str, Any]:
    return {"status": "ok", "data": data, **({"hint": hint} if hint else {})}


def err(code: str, message: str, hint: str = "") -> dict[str, Any]:
    return {"status": "error", "code": code, "message": message, **({"hint": hint} if hint else {})}


def mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}" if domain else "***"


def _account(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": user["id"],
        "name": user["name"],
        "department": user["department"],
        "role": user["role"],
        "email": mask_email(user["email"]),
        "mfa_enrolled": bool(user["is_mfa_enabled"]),
        "account_locked": bool(user["password_locked"]),
    }


def build_tools(ctx: ToolContext) -> dict[str, Callable[..., dict[str, Any]]]:
    """Build only the tools this requester may use for this request.

    A tool the person cannot use does not exist for the model: it is not in the schema,
    and the call gate rejects it anyway. Targets that must be the requester are bound
    here, so they are not parameters the model could change.
    """
    who = ctx.requester
    scope = who.scope

    def govern(kind: str) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
        def deco(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
                name = fn.__name__
                started = time.perf_counter()
                if name not in ctx.allowed or not who.can_use(name):
                    result = err("not_permitted", f"{name} is not available to you for this request.",
                                 "Say what you cannot do and open a ticket if create_ticket is available.")
                else:
                    try:
                        result = fn(*args, **kwargs)
                    except Exception as exc:  # noqa: BLE001
                        audit.record("tool_exception", ctx.run_id, who.profile, tool=name, error=type(exc).__name__)
                        result = err("tool_failed", f"{name} failed.", "Retry once, then open a ticket.")
                ms = round((time.perf_counter() - started) * 1000)
                result["meta"] = {"tool": name, "kind": kind, "ms": ms}
                audit.record("tool_result", ctx.run_id, who.profile, tool=name, kind=kind,
                             args=kwargs or list(args), status=result["status"], code=result.get("code"), ms=ms)
                return result

            return wrapper

        return deco

    def _open_ticket(title: str, details: str, requester_id: str) -> dict[str, Any]:
        title, details = title.strip(), details.strip()
        if not 5 <= len(title) <= 80:
            return err("bad_title", "The title must be 5 to 80 characters.", "Write a short summary of the problem.")
        if len(details) > 500:
            return err("details_too_long", "Details are limited to 500 characters.", "Shorten them.")
        target = store.get_user(requester_id)
        if target is None:
            return err("not_found", "No account matches that requester.", "Ask for the user id or work email.")
        existing = store.recent_open_ticket(target["id"], title)
        if existing:
            return ok({"ticket_id": existing["id"], "status": existing["status"], "priority": existing["priority"],
                       "queue": existing["queue"], "duplicate": True},
                      "An identical open ticket already exists, so no new one was created.")
        ticket = store.add_ticket(
            requester_id=target["id"], title=title, details=details, priority=ctx.impact,
            category=ctx.category, queue=QUEUES.get(ctx.category, "Service Desk"),
            created_by=who.user_id, run_id=ctx.run_id,
        )
        return ok({"ticket_id": ticket["id"], "status": "open", "priority": ticket["priority"],
                   "queue": ticket["queue"], "duplicate": False})

    tools: dict[str, Callable[..., dict[str, Any]]] = {}

    @govern("read")
    def search_kb(query: str) -> dict[str, Any]:
        """Search the IT knowledge base for how-to steps and troubleshooting guidance.

        Use when: the person asks how to do something, or a known problem may have a documented fix.
        Do not use: to look up people, accounts or tickets.

        Args:
            query: 2 to 8 plain keywords, for example "vpn dropping wifi".

        Returns: up to 3 articles, each with an id, a title and the full steps.
        """
        if len(query.strip()) < 3:
            return err("bad_query", "The query is too short.", "Use 2 to 8 keywords.")
        hits = store.search_kb(query)
        if not hits:
            return ok({"articles": []}, "No article matched. Try other keywords or open a ticket.")
        return ok({"articles": [{"id": h["id"], "title": h["title"], "steps": h["body"]} for h in hits]})

    tools["search_kb"] = search_kb

    if scope.get("lookup_user") == ANY:

        @govern("read")
        def lookup_user(identifier: str) -> dict[str, Any]:  # type: ignore[misc]
            """Look up any employee account by user id, work email or full name.

            Use when: you need to confirm who someone is or whether their account is locked.
            Do not use: to guess accounts. If nothing matches, ask for the user id or work email.

            Args:
                identifier: A user id such as u003, a work email, or a full name.

            Returns: name, department, role, masked email, whether MFA is enrolled and whether the
            account is locked.
            """
            user = store.get_user(identifier)
            if user is None:
                return err("not_found", "No account matches that identifier.", "Ask for the user id or work email.")
            return ok(_account(user))

    else:

        @govern("read")
        def lookup_user() -> dict[str, Any]:  # type: ignore[misc]
            """Check the status of your own account.

            Use when: you need to know whether the account is locked or MFA is enrolled before acting.
            Do not use: to look up other people. You cannot.

            Returns: name, department, role, masked email, whether MFA is enrolled and whether the
            account is locked.
            """
            user = store.get_user(who.user_id)
            return ok(_account(user)) if user else err("not_found", "Your account was not found.")

    tools["lookup_user"] = lookup_user

    @govern("write")
    def reset_password() -> dict[str, Any]:
        """Unlock your own account and email a one-time password reset link.

        Use when: the person forgot their password or is locked out, and the account is theirs.
        Do not use: for MFA problems, for other people, or for any request that is only a question.
        Check lookup_user first when it is available, so you know whether the account is locked.

        Returns: whether the account was locked, that it is now unlocked, and the masked address the
        link was sent to. The link is valid for 30 minutes. Never repeat the link or any code.
        """
        user = store.get_user(who.user_id)
        if user is None:
            return err("not_found", "Your account was not found.")
        if not user["is_mfa_enabled"]:
            return err("mfa_required", "MFA is not enrolled, so a reset cannot be verified.",
                       "Open a ticket for Identity and Access.")
        was_locked = store.unlock_account(user["id"])
        return ok({"was_locked": was_locked, "account_unlocked": True,
                   "reset_link_sent_to": mask_email(user["email"]), "link_valid_minutes": 30})

    tools["reset_password"] = reset_password

    if scope.get("create_ticket") == ANY:

        @govern("write")
        def create_ticket(title: str, details: str, requester_id: str = "") -> dict[str, Any]:  # type: ignore[misc]
            """Open a service desk ticket, for yourself or on behalf of another employee.

            Use when: the problem needs a person (hardware, access approval, an unresolved fault), or the
            requested action is not available to you.
            Do not use: when a tool already solved the problem, or only to answer a question.
            Priority and category are set from the triage. Do not describe them as your choice.

            Args:
                title: A short summary, 5 to 80 characters.
                details: What happens and what was already tried, under 500 characters.
                requester_id: The user id the ticket is for. Leave empty for yourself.

            Returns: the ticket id, status, priority and queue.
            """
            return _open_ticket(title, details, requester_id.strip() or who.user_id)

    else:

        @govern("write")
        def create_ticket(title: str, details: str) -> dict[str, Any]:  # type: ignore[misc]
            """Open a service desk ticket for yourself.

            Use when: the problem needs a person (hardware, access approval, an unresolved fault), or the
            requested action is not available to you.
            Do not use: when a tool already solved the problem, or only to answer a question.
            Priority and category are set from the triage. Do not describe them as your choice.

            Args:
                title: A short summary, 5 to 80 characters.
                details: What happens and what was already tried, under 500 characters.

            Returns: the ticket id, status, priority and queue.
            """
            return _open_ticket(title, details, who.user_id)

    tools["create_ticket"] = create_ticket
    return {name: fn for name, fn in tools.items() if name in ctx.allowed and who.can_use(name)}
