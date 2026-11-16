from __future__ import annotations

from typing import Any

from google.adk.events.event import Event
from google.genai import types
from pydantic import BaseModel
from typesafe_sdk import ScoreAnswer

from app import tools


class Ticket(BaseModel):
    text: str
    requester_name: str = ""
    requester_email: str = ""


class TriageResult(BaseModel):
    category: str
    urgency: str
    complexity: float
    security_incident: float
    tool_choice: str
    tool_fits: float
    raw_jev: dict[str, Any]


class TriageContext(BaseModel):
    ticket: Ticket
    triage: TriageResult


class ToolCallPlan(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    reasoning: str


class ToolResult(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | list[Any] | None = None
    error: str | None = None


class EscalateResult(BaseModel):
    message: str
    is_escalated: bool = True


class ClarificationQuestion(BaseModel):
    question: str


class ReplyContext(BaseModel):
    ticket_text: str
    action_taken: str
    result_summary: str
    is_escalated: bool = False
    ask_question: str | None = None


ROUTE_LABELS: dict[str, str] = {
    "security": "security_incident > 0.7",
    "clarify":  "tool_fits < 0.3",
    "action":   "action (default)",
}


def _top_score_level(answer: ScoreAnswer) -> str:
    top_idx = max(answer.probabilities, key=lambda k: answer.probabilities[k])
    val = answer.legend.get(top_idx, str(top_idx))
    return str(val) if not isinstance(val, str) else val


def parse_triage(answers: dict[str, Any], ticket: Ticket) -> TriageContext:
    return TriageContext(
        ticket=ticket,
        triage=TriageResult(
            category=answers["category"].choice,
            urgency=_top_score_level(answers["urgency"]),
            complexity=answers["complexity"].noul,
            security_incident=answers["security_incident"].noul,
            tool_choice=answers["tool_choice"].choice,
            tool_fits=answers["tool_fits"].noul,
            raw_jev={k: v.model_dump() for k, v in answers.items()},
        ),
    )


def _route_decision(triage: TriageResult) -> tuple[str, str]:
    if triage.security_incident > 0.7:
        return "security", ROUTE_LABELS["security"]
    if triage.tool_fits < 0.3:
        return "clarify", ROUTE_LABELS["clarify"]
    return "action", ROUTE_LABELS["action"]


def intake(node_input: types.Content) -> Event:
    text = ""
    if node_input.parts:
        text = (node_input.parts[0].text or "")[:2000]
    ticket = Ticket(text=text)
    return Event(output=ticket, state={"ticket": ticket.model_dump()})


def policy_router(node_input: TriageContext) -> Event:
    route, rule = _route_decision(node_input.triage)
    return Event(output=node_input, route=route, state={"rule_fired": rule})


def escalate(node_input: TriageContext) -> EscalateResult:
    return EscalateResult(
        message=(
            "This query has been flagged as a potential security incident and escalated to the"
            " security team. No tool was called."
        )
    )


def execute_tool(node_input: ToolCallPlan) -> ToolResult:
    try:
        raw = tools.call_tool(node_input.tool_name, node_input.arguments)
        return ToolResult(
            tool_name=node_input.tool_name,
            arguments=node_input.arguments,
            result=raw.get("result"),
        )
    except Exception as exc:
        return ToolResult(
            tool_name=node_input.tool_name,
            arguments=node_input.arguments,
            error=str(exc),
        )


def prep_reply(node_input: Any, ticket: dict[str, Any]) -> ReplyContext:
    ticket_text = ticket.get("text", "")
    if not isinstance(node_input, dict):
        return ReplyContext(
            ticket_text=ticket_text, action_taken="unknown", result_summary=str(node_input)
        )
    if node_input.get("is_escalated"):
        return ReplyContext(
            ticket_text=ticket_text,
            action_taken="escalate",
            result_summary=node_input.get("message", "Escalated to the security team."),
            is_escalated=True,
        )
    if "question" in node_input and "tool_name" not in node_input:
        return ReplyContext(
            ticket_text=ticket_text,
            action_taken="clarify",
            result_summary="",
            ask_question=node_input["question"],
        )
    if "tool_name" in node_input:
        if node_input.get("error"):
            return ReplyContext(
                ticket_text=ticket_text,
                action_taken="tool_error",
                result_summary=node_input["error"],
            )
        return ReplyContext(
            ticket_text=ticket_text,
            action_taken="tool_success",
            result_summary=str(node_input.get("result", "")),
        )
    return ReplyContext(
        ticket_text=ticket_text, action_taken="unknown", result_summary=str(node_input)
    )
