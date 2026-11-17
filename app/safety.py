"""Safety gate for tools that change something.

Jev judges the proposed action with five typed questions. This module is the truth table that
turns those probabilities into one of three outcomes. Jev never decides, the table does.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import audit, jev, questions
from app.identity import Requester, policy
from app.store import store
from app.tools import mask_email


@dataclass(frozen=True)
class Verdict:
    outcome: str  # "auto", "approve" or "deny"
    rule: str
    scores: dict[str, float]


# What each tool really does, stated from the code, so the judgment does not rest on a guess
EFFECTS = {
    "reset_password": "Unlocks one employee account and emails that employee a one-time reset link. "
    "No service, database or permission changes. The employee can reset again at any time.",
    "create_ticket": "Adds one entry to the helpdesk ticket queue. It changes no system, account or permission "
    "and can be closed at any time.",
}


def settings() -> dict[str, Any]:
    return policy()["safety"]


def decide(tool: str, scores: dict[str, float]) -> Verdict:
    """First matching row wins."""
    cfg = settings()
    attack = scores["matches_attack_pattern"]
    known = cfg["tools"].get(tool, {"production": True, "reversible": False})
    if attack >= cfg["deny_at"]:
        return Verdict("deny", "Matches a social engineering pattern, so it is refused", scores)
    if tool in cfg["always_approve"]:
        return Verdict("approve", "Account changes always need a person's approval", scores)
    if known["production"] or not known["reversible"]:
        return Verdict("approve", "It touches production or cannot be undone, so a person approves it", scores)
    if scores["privileged"] >= cfg["risk_at"]:
        return Verdict("approve", "The request raises access, so a person approves it", scores)
    if scores["requester_verified"] < cfg["verified_below"]:
        return Verdict("approve", "The requester is not clearly verified, so a person approves it", scores)
    if attack >= cfg["review_at"]:
        return Verdict("approve", "Some attack signals, so a person approves it", scores)
    return Verdict("auto", "Low risk and a verified requester, so it runs", scores)


def describe(tool: str, args: dict[str, Any], requester: Requester) -> str:
    """The action in one plain sentence for the approver. Emails are masked."""
    if tool == "reset_password":
        text = f"Unlock {requester.first_name}'s account and email a one-time reset link to {mask_email(requester.email)}"
    elif tool == "create_ticket":
        target = str(args.get("requester_id") or "").strip()
        title = str(args.get("title") or "").strip()
        text = f'Open a ticket "{title}"' + (f" for {target}" if target and target != requester.user_id else "")
    else:
        text = f"Run {tool}"
    return audit.mask(text, limit=160)


def _facts(tool: str, args: dict[str, Any], requester: Requester) -> dict[str, Any]:
    """What a person would look at before approving: who is signed in and what the action touches."""
    target_id = str(args.get("requester_id") or "").strip() or requester.user_id
    target = store.get_user(target_id)
    facts: dict[str, Any] = {
        "signed_in_as": {
            "name": requester.name, "title": requester.title, "department": requester.department,
            "role": requester.role, "identity_checked_by": "company sign-in",
        },
        "acts_on": "their own account" if target_id == requester.user_id else f"another employee ({target_id})",
    }
    if tool == "reset_password" and target:
        facts["account"] = {"mfa_enrolled": bool(target["is_mfa_enabled"]), "locked": bool(target["password_locked"])}
    facts["what_it_changes"] = EFFECTS.get(tool, "Unknown")
    return facts


async def assess(tool: str, args: dict[str, Any], requester: Requester, text: str) -> tuple[Verdict, dict, dict, str]:
    """Ask Jev, then apply the table. A failed Jev call raises, and the caller must not act."""
    summary = describe(tool, args, requester)
    answers, usage, raw = await jev.ask_jev(
        "safety", questions.SAFETY_QUESTIONS,
        questions.safety_state(text, tool, summary, requester.name, _facts(tool, args, requester)),
    )
    scores = {name: answers[name].noul for name in questions.SAFETY_QUESTIONS}
    return decide(tool, scores), usage, raw, summary
