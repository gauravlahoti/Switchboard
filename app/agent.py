# ruff: noqa
from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.workflow import Workflow, node

from app import jev, nodes, questions, tiers
from app.nodes import (
    ClarificationQuestion,
    ToolCallPlan,
    TriageContext,
    escalate,
    execute_tool,
    intake,
    policy_router,
    prep_reply,
)


_TIER_LLM_INSTRUCTION = """\
You are an IT service desk tool call planner.

Input is a JSON object with:
- ticket: the user's IT support request (text, requester_name, requester_email)
- triage: Jev's typed assessment with tool_choice (recommended tool) and complexity (0-1)

Produce a ToolCallPlan:
- tool_name: use triage.tool_choice exactly as given (do not change it)
- arguments: extracted from ticket.text only. Do not invent values not stated in the ticket.
- reasoning: one sentence explaining the argument choices

Available tools and required arguments:
  search_kb(query: str)
  lookup_user(identifier: str)
  create_ticket(requester_id: str, title: str, priority: str)
  reset_password(user_id: str)
  query_logs(service: str | None, level: str | None, limit: int)
  restart_service -- DISABLED in sprint 1, never plan this
  grant_access    -- DISABLED in sprint 1, never plan this
"""

_CLARIFY_LLM_INSTRUCTION = """\
You are an IT service desk agent. The user's ticket is unclear or missing key information.
Ask ONE focused, specific question to get what you need. Be brief. Output only the question.
"""

_REPLY_LLM_INSTRUCTION = """\
You are an IT service desk agent writing the final reply to a user. No jargon. No em-dashes. Short sentences.

You receive a ReplyContext with:
- ticket_text: the user's original message
- action_taken: tool_success | tool_error | clarify | escalate | unknown
- result_summary: what the tool returned or the error message
- ask_question: a clarifying question (only when action_taken is clarify)
- is_escalated: true when escalated to the security team

Reply rules:
- tool_success: confirm what was done and what the user should do next
- tool_error: explain there was a problem and suggest they contact IT support directly
- clarify: present ask_question naturally as part of your reply
- escalate: reassure the user their concern was passed to the security team
"""


async def jev_triage(node_input: nodes.Ticket) -> Event:
    state = questions.triage_state(
        node_input.text, node_input.requester_name, node_input.requester_email
    )
    answers = await jev.ask_jev("triage", questions.TRIAGE_QUESTIONS, state)
    triage_ctx = nodes.parse_triage(answers, node_input)
    return Event(
        output=triage_ctx,
        state={"triage_ctx": triage_ctx.model_dump()},
    )


@node(rerun_on_resume=True)
async def tier_llm_node(ctx: Context, node_input: TriageContext) -> ToolCallPlan:
    # Code selects the model tier from Jev's complexity Noul — Jev judges, code decides
    model_id = tiers.model_for_complexity(node_input.triage.complexity)
    dynamic_agent = LlmAgent(
        name="tier_llm",
        model=model_id,
        instruction=_TIER_LLM_INSTRUCTION,
        output_schema=ToolCallPlan,
    )
    result = await ctx.run_node(dynamic_agent, node_input=node_input.model_dump())
    return ToolCallPlan(**result)


clarify_llm = LlmAgent(
    name="clarify_llm",
    model=tiers.TIER_SMALL,
    instruction=_CLARIFY_LLM_INSTRUCTION,
    output_schema=ClarificationQuestion,
    output_key="clarification",
)

reply_llm = LlmAgent(
    name="reply_llm",
    model=tiers.TIER_SMALL,
    instruction=_REPLY_LLM_INSTRUCTION,
)

root_agent = Workflow(
    # Keep name in sync with agents-cli-manifest.yaml create_params.root_agent_name
    name="desk",
    edges=[
        ("START", intake),
        (intake, jev_triage),
        (jev_triage, policy_router),
        # RoutingMap: policy_router emits Event(route=X); dict maps X -> target node
        (policy_router, {"security": escalate, "action": tier_llm_node, "clarify": clarify_llm}),
        (tier_llm_node, execute_tool),
        (execute_tool, prep_reply),
        (escalate, prep_reply),
        (clarify_llm, prep_reply),
        (prep_reply, reply_llm),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
