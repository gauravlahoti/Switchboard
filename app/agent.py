# ruff: noqa
from __future__ import annotations

import asyncio
import logging

from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.workflow import Workflow, node

from app import approvals, audit, harness, jev, nodes, questions
from app.identity import Requester, policy
from app.store import store
from app.nodes import Ticket, block_request, hold_review, intake, specialist_review


async def input_guardrail(node_input: Ticket) -> Event:
    # Fail closed: a failed Jev call raises and nothing downstream runs
    answers, usage, raw = await jev.ask_jev(
        "guardrail", questions.GUARDRAIL_QUESTIONS, questions.guardrail_state(node_input.text)
    )
    scores = {name: answers[name].noul for name in questions.GUARDRAIL_QUESTIONS}
    verdict = nodes.guardrail_verdict(scores)
    logging.getLogger("desk.guardrail").info("verdict=%s scores=%s", verdict, scores)
    screened = node_input.model_copy(
        update={
            "guardrail": {
                "verdict": verdict,
                "scores": scores,
                "usage": usage,
                "raw": raw,
                "thresholds": {"proceed_below": nodes.GUARD_PROCEED_BELOW, "block_at": nodes.GUARD_BLOCK_AT,
                               "off_topic_at": nodes.GUARD_OFF_TOPIC_AT},
            }
        }
    )
    who = (node_input.requester or {}).get("profile", "")
    audit.record("guardrail", node_input.run_id, who, verdict=verdict, scores=scores)
    return Event(output=screened, route=verdict, state={"guardrail": screened.guardrail})


async def understand_request(node_input: Ticket) -> Event:
    # Fail closed: a failed Jev call raises and nothing downstream runs
    answers, usage, raw = await jev.ask_jev(
        "understand", questions.UNDERSTAND_QUESTIONS, questions.understand_state(node_input.text)
    )
    understanding = nodes.understanding_from(answers)
    understanding["usage"] = usage
    understanding["raw"] = raw
    requester = Requester.model_validate(node_input.requester)
    if understanding["path"] == "reply":
        lite = harness.tier_config("lite")
        understanding["plan"] = {"tier": "lite", "label": lite["label"], "model": lite["model"]}
    audit.record(
        "understanding", node_input.run_id, requester.profile,
        path=understanding["path"], category=understanding["category"]["value"],
        intent=understanding["intent"]["value"], impact=understanding["impact"],
        effort=understanding["effort"]["value"],
    )
    understood = node_input.model_copy(update={"understanding": understanding})
    return Event(output=understood, route=understanding["path"], state={"understanding": understanding})


async def plan_work(node_input: Ticket) -> Event:
    """Jev picks the model and the tools. Code sets the hard limits first and only accepts permitted picks."""
    requester = Requester.model_validate(node_input.requester)
    understanding = node_input.understanding or {}
    cands, hidden = harness.candidates(requester, understanding)
    # Fail closed: a failed Jev call raises and nothing downstream runs
    answers, usage, raw = await jev.ask_jev(
        "select", questions.select_questions(cands), questions.select_state(node_input.text, understanding, cands, store.kb_titles())
    )
    plan = harness.plan_from_selection(cands, hidden, answers).summary()
    plan["usage"] = usage
    plan["raw"] = raw
    audit.record(
        "plan", node_input.run_id, requester.profile, picked_by="jev", tier=plan["tier"], tools=plan["tools"],
        not_chosen=[h["tool"] for h in plan["hidden"]], fits=plan["fits"],
    )
    return Event(output=node_input.model_copy(update={"plan": plan}), state={"plan": plan})


@node(rerun_on_resume=True)
async def reply_to_user(ctx: Context, node_input: Ticket) -> Event:
    kind = (node_input.understanding or {}).get("reply_kind") or "greeting"
    requester = Requester.model_validate(node_input.requester)
    result = await ctx.run_node(harness.reply_agent(kind, requester), node_input=node_input.text)
    return nodes._say(str(result).strip())


@node(rerun_on_resume=True)
async def handle_request(ctx: Context, node_input: Ticket) -> Event:
    understanding = node_input.understanding or {}
    requester = Requester.model_validate(node_input.requester)
    plan = harness.Plan.from_summary(node_input.plan or {})
    agent = harness.handle_agent(plan, requester, understanding, node_input.run_id, node_input.text)
    try:
        # Time spent waiting for a person's approval is added back, so only the agent's own work is limited
        async with asyncio.timeout(policy()["limits"]["timeout_seconds"]) as clock:
            approvals.watch(node_input.run_id, clock)
            result = await ctx.run_node(agent, node_input=node_input.text)
    except TimeoutError:
        audit.record("limit_hit", node_input.run_id, requester.profile, limit="timeout")
        return nodes._say(harness.HANDOFF_TEXT)
    return nodes._say(str(result).strip())


root_agent = Workflow(
    # Keep name in sync with agents-cli-manifest.yaml create_params.root_agent_name
    name="desk",
    edges=[
        ("START", intake),
        (intake, input_guardrail),
        (input_guardrail, {"proceed": understand_request, "hold": hold_review, "block": block_request, "decline": block_request}),
        (understand_request, {"reply": reply_to_user, "handle": plan_work, "specialist": specialist_review}),
        (plan_work, handle_request),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
