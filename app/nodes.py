from __future__ import annotations

import json
from typing import Any

from google.adk.events.event import Event
from google.genai import types
from pydantic import BaseModel

from app import identity


class Ticket(BaseModel):
    text: str
    run_id: str = ""
    requester: dict[str, Any] | None = None
    guardrail: dict[str, Any] | None = None
    understanding: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None


GUARD_PROCEED_BELOW = 0.30
GUARD_BLOCK_AT = 0.70
GUARD_OFF_TOPIC_AT = 0.60  # clearly not an IT matter: decline here, no model call
ATTACK_CHECKS = ("prompt_injection", "jailbreak")
HOLD_MESSAGE = (
    "{name}, your request is held for a specialist review before we continue.\n\n"
    "Next step: no action is needed. A specialist will follow up."
)
DECLINE_MESSAGE = (
    "{name}, that is outside what the IT service desk can help with.\n\n"
    "Next step: describe an IT issue and we will take it from there."
)
BLOCK_MESSAGE = (
    "{name}, this request cannot be acted on as written.\n\n"
    "Next step: describe the IT problem in your own words and we will take it from there."
)
SECURITY_MESSAGE = (
    "{name}, this looks like a security matter, so it has been passed to a specialist.\n\n"
    "Next step: no action is needed. A specialist will follow up."
)


def _first_name(ticket: "Ticket") -> str:
    who = ticket.requester or {}
    return (who.get("name") or who.get("label") or "Hello").split()[0]


def guardrail_verdict(scores: dict[str, float]) -> str:
    """First match wins: an attack is judged before scope, so an attack is never reported as off-topic."""
    top = max(scores[name] for name in ATTACK_CHECKS)
    if top >= GUARD_BLOCK_AT:
        return "block"
    if top >= GUARD_PROCEED_BELOW:
        return "hold"
    if scores.get("off_topic", 0.0) >= GUARD_OFF_TOPIC_AT:
        return "decline"
    return "proceed"


REQUEST_BELOW = 0.50  # below this the message is conversation, not a request
CATEGORY_FITS_AT = 0.60  # below this the category is "other"
BLOCKED_AT = 0.40
DIAGNOSE_BELOW = 0.30  # below this a standard procedure fixes it
DIAGNOSE_AT = 0.70  # at or above this it needs investigation
DETAIL_MISSING_AT = 0.50

# (reach level, fully blocked) -> business impact
IMPACT_MATRIX = {
    (0, False): "low",
    (0, True): "medium",
    (1, False): "medium",
    (1, True): "high",
    (2, False): "high",
    (2, True): "critical",
}


def understanding_from(answers: dict[str, Any]) -> dict[str, Any]:
    is_request = answers["is_request"].noul
    category = answers["category"]
    intent = answers["intent"]
    fits = answers["category_fits"].noul
    blocked = answers["fully_blocked"].noul
    diagnose = answers["needs_diagnosis"].noul
    missing = answers["too_vague"].noul
    reach_probs = {int(k): v for k, v in answers["reach"].probabilities.items()}
    reach_level = min(max(reach_probs, key=lambda k: reach_probs[k]), 2)
    is_blocked = blocked >= BLOCKED_AT

    effort = (
        "quick_fix"
        if diagnose < DIAGNOSE_BELOW
        else "needs_investigation" if diagnose >= DIAGNOSE_AT else "standard"
    )
    u: dict[str, Any] = {
        "request": {"p": is_request, "value": "request" if is_request >= REQUEST_BELOW else "conversation"},
        "category": {
            "value": category.choice if fits >= CATEGORY_FITS_AT else "other",
            "p": category.probabilities[category.choice],
            "fits": fits,
        },
        "intent": {"value": intent.choice, "p": intent.probabilities[intent.choice]},
        "work_stoppage": {"p": blocked, "value": "blocked" if is_blocked else "working"},
        "reach": {"level": reach_level, "p": reach_probs[reach_level]},
        "impact": IMPACT_MATRIX[(reach_level, is_blocked)],
        "effort": {"p": diagnose, "value": effort},
        "detail": {"p": missing, "value": "needs_question" if missing >= DETAIL_MISSING_AT else "complete"},
    }
    u["path"], u["reply_kind"], u["reason"] = understanding_path(u)
    return u


def understanding_path(u: dict[str, Any]) -> tuple[str, str, str]:
    """First match wins. Returns the path, the reply kind, and a plain reason."""
    if u["request"]["value"] == "conversation":
        return "reply", "greeting", "There is no IT request in this message."
    if u["category"]["value"] == "security":
        return "specialist", "", "Security matters go to a specialist."
    if u["detail"]["value"] == "needs_question":
        return "reply", "clarify", "Too vague to act on, so we ask first."
    return "handle", "", "A clear request with enough detail, so the resolution agent takes it."


def intake(node_input: types.Content) -> Event:
    raw = ""
    if node_input.parts:
        raw = node_input.parts[0].text or ""
    try:
        fields = json.loads(raw)
    except ValueError:
        fields = {}
    if not isinstance(fields, dict) or not isinstance(fields.get("text"), str):
        fields = {"text": raw}
    requester = identity.resolve(str(fields.get("profile") or "user_a"))
    ticket = Ticket(
        text=fields["text"][:2000],
        run_id=str(fields.get("run_id") or ""),
        requester=requester.model_dump(),
    )
    return Event(output=ticket, state={"ticket": ticket.model_dump()})


def _say(text: str) -> Event:
    return Event(output=text, content=types.Content(role="model", parts=[types.Part(text=text)]))


def hold_review(node_input: Ticket) -> Event:
    return _say(HOLD_MESSAGE.format(name=_first_name(node_input)))


def block_request(node_input: Ticket) -> Event:
    declined = (node_input.guardrail or {}).get("verdict") == "decline"
    return _say((DECLINE_MESSAGE if declined else BLOCK_MESSAGE).format(name=_first_name(node_input)))


def specialist_review(node_input: Ticket) -> Event:
    return _say(SECURITY_MESSAGE.format(name=_first_name(node_input)))
