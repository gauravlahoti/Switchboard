from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.models.llm_response import LlmResponse
from google.adk.skills import load_skills_from_dir
from google.adk.skills.models import Skill
from google.adk.tools.skill_toolset import SkillDiscoveryMode, SkillToolset
from google.genai import types

from app import approvals, audit, safety
from app.identity import Requester, approvers_for, policy
from app.tools import ALL_TOOLS, WRITE_TOOLS, ToolContext, build_tools, err

SKILLS_DIR = Path(__file__).parent / "skills"
STYLE_SKILL = "reply-style"
SKILL_TOOL_NAMES = frozenset(
    {"list_skills", "load_skill", "load_skill_resource", "run_skill_script", "unload_skill", "search_skills"}
)
HANDOFF_TEXT = (
    "I could not finish this within my limits, so I have stopped here. "
    "Please contact the IT helpdesk on x5500 and mention this request."
)

HANDLE_INSTRUCTION = """\
You are Reflex, the IT service desk agent. You are helping {label}, {title}. Address them as {first}. Their own user id is {user_id}.

The fast classifier already assessed this request. Treat these as given and do not re-derive them:
- category: {category}
- intent: {intent}
- business impact: {impact}
- effort: {effort}
- reach: {reach}
- work stoppage: {blocked}

Your tools for this request: {tools}. They were picked because they help with it. Use only these.

How to work:
1. Load the one skill that fits the request before you use any other tool.
2. Follow the skill, but skip any step that needs a tool you were not given. Skip it silently.
3. If the person asks for something you cannot do for them, say so in plain words and what they can do instead. Open a ticket only if create_ticket is one of your tools.
4. Write the final message the person reads in the reply style below.
"""

PERSON_LINE = "The person you are writing to is {label}, {title}. Address them as {first}."

REPLY_INSTRUCTIONS = {
    "greeting": (
        "You are Reflex, the IT service desk assistant. The message is a greeting, thanks, or something that "
        "is not an IT request. Reply using the matching example from the reply style below."
    ),
    "clarify": (
        "You are Reflex, the IT service desk assistant. The message is too vague to act on. Ask ONE specific "
        "question that would let you start, such as which app or device, what exactly happens, or any error "
        "text. Do not offer solutions."
    ),
}

STYLE_SUFFIX = "\n\nReply style. Apply it to the message the person reads:\n\n{style}\n"


@lru_cache(maxsize=1)
def style_guide() -> str:
    """The reply-style skill, always applied. Task skills are loaded on demand, this one never is."""
    return next(s for s in _skills() if s.name == STYLE_SKILL).instructions.strip()


@lru_cache(maxsize=1)
def _skills() -> tuple[Skill, ...]:
    return tuple(load_skills_from_dir(SKILLS_DIR))


def tier_config(tier: str) -> dict[str, Any]:
    return policy()["tiers"][tier]


@lru_cache(maxsize=None)
def _model(tier: str) -> Gemini:
    """One model object per tier, so every request reuses the same authenticated client."""
    return Gemini(model=tier_config(tier)["model"])


async def warm_up() -> None:
    """Open each tier's connection once at start so the first person does not wait for it."""
    cfg = types.GenerateContentConfig(max_output_tokens=16, thinking_config=types.ThinkingConfig(thinking_budget=0))
    for tier in policy()["tiers"]:
        model = _model(tier)
        try:
            await model.api_client.aio.models.generate_content(model=model.model, contents="ok", config=cfg)
        except Exception:  # noqa: BLE001
            continue


def _today() -> date:
    return date.today()


def cost_usd(tier: str, input_tokens: int, output_tokens: int) -> float | None:
    """Cost of one call from the tier's price list in policy.toml. None when no price applies."""
    for entry in tier_config(tier).get("prices", []):
        if "until" in entry and _today() > date.fromisoformat(entry["until"]):
            continue
        if "max_prompt_tokens" in entry and input_tokens > entry["max_prompt_tokens"]:
            continue
        return (input_tokens * entry["input_per_mtok"] + output_tokens * entry["output_per_mtok"]) / 1_000_000
    return None


@dataclass(frozen=True)
class Plan:
    tier: str
    model: str
    label: str
    thinking_budget: int
    tools: tuple[str, ...]
    hidden: tuple[tuple[str, str], ...]
    skills: tuple[str, ...]
    why: str = ""
    fits: tuple[tuple[str, float], ...] = ()
    tier_p: float = 0.0

    @classmethod
    def from_summary(cls, d: dict[str, Any]) -> "Plan":
        cfg = tier_config(d["tier"])
        return cls(
            d["tier"], cfg["model"], cfg["label"], cfg["thinking_budget"], tuple(d["tools"]),
            tuple((h["tool"], h["why"]) for h in d["hidden"]), tuple(d["skills"]), d.get("why", ""),
            tuple(d.get("fits", {}).items()), d.get("tier_p", 0.0),
        )

    def summary(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "label": self.label,
            "model": self.model,
            "tools": list(self.tools),
            "hidden": [{"tool": t, "why": why} for t, why in self.hidden],
            "skills": list(self.skills),
            "why": self.why,
            "fits": dict(self.fits),
            "tier_p": self.tier_p,
        }


SELECT_READ_AT = 0.30  # a read tool is offered when Jev rates it at least this useful
SELECT_WRITE_AT = 0.50  # a tool that changes something needs a clear fit


def candidates(requester: Requester, understanding: dict[str, Any]) -> tuple[list[str], list[tuple[str, str]]]:
    """The hard limits, decided in code: what the person holds, and that a how-to never changes anything."""
    by_intent = policy()["routing"]["intent_tools"][understanding["intent"]["value"]]
    allowed: list[str] = []
    hidden: list[tuple[str, str]] = []
    for tool in ALL_TOOLS:
        if not requester.can_use(tool):
            hidden.append((tool, "not in your permissions"))
        elif by_intent != "all" and tool not in by_intent:
            hidden.append((tool, "a how-to question never changes anything"))
        else:
            allowed.append(tool)
    return allowed, hidden


def plan_from_selection(
    cands: list[str], hidden: list[tuple[str, str]], answers: dict[str, Any]
) -> Plan:
    """Jev picks the model and which allowed tools help. Anything outside the allowed set is never chosen."""
    fits = {tool: answers[f"use_{tool}"].noul for tool in cands}
    chosen = [t for t in cands if fits[t] >= (SELECT_WRITE_AT if t in WRITE_TOOLS else SELECT_READ_AT)] or list(cands)
    skipped = [(t, f"Jev: not needed ({round(fits[t] * 100)}% fit)") for t in cands if t not in chosen]
    tier_answer = answers["tier"]
    tier = tier_answer.choice
    cfg = tier_config(tier)
    p = tier_answer.probabilities[tier]
    why = f"Jev chose {cfg['model']} ({round(p * 100)}% sure)"
    skills = tuple(sk.name for sk in offered_skills(frozenset(chosen)))
    return Plan(
        tier, cfg["model"], cfg["label"], cfg["thinking_budget"], tuple(chosen), tuple(hidden + skipped),
        skills, why, tuple(fits.items()), p,
    )


def offered_skills(allowed: frozenset[str]) -> list[Skill]:
    """Skills trimmed to the tools this person may use. A skill with none left is not offered."""
    offered = []
    for skill in _skills():
        if skill.frontmatter.metadata.get("always_on"):
            continue
        wanted = skill.frontmatter.metadata.get("adk_additional_tools", [])
        keep = [t for t in wanted if t in allowed]
        if wanted and not keep:
            continue
        trimmed = skill.model_copy(deep=True)
        trimmed.frontmatter.metadata["adk_additional_tools"] = keep
        offered.append(trimmed)
    return offered


class RunGuard:
    """The permission gate and the limits for one handled request."""

    def __init__(self, plan: Plan, run_id: str, actor: str, requester: Requester | None = None, text: str = "") -> None:
        self.plan, self.run_id, self.actor = plan, run_id, actor
        self.requester, self.text = requester, text
        self.limits = policy()["limits"]
        self.model_calls = 0
        self.tool_calls = 0

    async def before_model(self, callback_context: Any, llm_request: Any) -> LlmResponse | None:
        self.model_calls += 1
        if self.model_calls > self.limits["max_model_calls"]:
            audit.record("limit_hit", self.run_id, self.actor, limit="max_model_calls")
            return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=HANDOFF_TEXT)]))
        return None

    async def before_tool(self, tool: Any, args: dict[str, Any], tool_context: Any) -> dict[str, Any] | None:
        name = tool.name
        if name in SKILL_TOOL_NAMES:
            audit.record("skill_step", self.run_id, self.actor, tool=name, args=args)
            return None
        if name not in self.plan.tools:
            audit.record("tool_denied", self.run_id, self.actor, tool=name, reason="not in plan")
            return err("not_permitted", f"{name} is not available to you for this request.",
                       "Say what you cannot do and open a ticket if create_ticket is available.")
        self.tool_calls += 1
        if self.tool_calls > self.limits["max_tool_calls"]:
            audit.record("limit_hit", self.run_id, self.actor, limit="max_tool_calls")
            return err("tool_budget", "The tool budget for this request is used up.", "Stop and summarise.")
        if self.requester is not None and name in WRITE_TOOLS:
            held = await self._safety_gate(name, args)
            if held is not None:
                return held
        audit.record("tool_call", self.run_id, self.actor, tool=name, args=args)
        return None

    async def _safety_gate(self, name: str, args: dict[str, Any]) -> dict[str, Any] | None:
        """Jev scores the action, the table decides. None means go ahead, anything else is the tool's answer."""
        try:
            verdict, usage, raw, summary = await safety.assess(name, args, self.requester, self.text)
        except Exception as exc:  # noqa: BLE001
            audit.record("safety_error", self.run_id, self.actor, tool=name, error=type(exc).__name__)
            return err("safety_unavailable", "The safety check could not run, so nothing was changed.",
                       "Say it was not done. Open a ticket if create_ticket is available.")
        cfg = safety.settings()
        approval_id = uuid.uuid4().hex[:8]
        approvers = approvers_for(name, self.requester.profile) if verdict.outcome == "approve" else []
        await approvals.emit(self.run_id, {
            "type": "safety", "id": approval_id, "tool": name, "action": summary, "outcome": verdict.outcome,
            "rule": verdict.rule, "scores": verdict.scores, "raw": raw, "timeout": cfg["approval_seconds"],
            "approvers": approvers,
            "requester": {"id": self.requester.profile, "label": self.requester.label},
            "limits": {"deny_at": cfg["deny_at"], "risk_at": cfg["risk_at"], "verified_below": cfg["verified_below"]},
            "known": cfg["tools"].get(name, {"production": True, "reversible": False}),
        })
        await approvals.emit(self.run_id, {"type": "usage", "bucket": "s1", "node": "n-handle", **usage})
        audit.record("safety", self.run_id, self.actor, tool=name, outcome=verdict.outcome, rule=verdict.rule,
                     scores=verdict.scores)
        if verdict.outcome == "auto":
            return None
        if verdict.outcome == "deny":
            return err("refused", "The safety check refused this action.",
                       "Say plainly that it cannot be done through this service desk. Do not retry it.")
        decision, waited, by = await approvals.ask(
            self.run_id, approval_id, cfg["approval_seconds"], [a["id"] for a in approvers]
        )
        who = next((a for a in approvers if a["id"] == by), None)
        await approvals.emit(self.run_id, {"type": "approval_result", "id": approval_id, "decision": decision,
                                           "waited_ms": waited, "by": who})
        audit.record("approval", self.run_id, self.actor, tool=name, decision=decision, waited_ms=waited,
                     approver=by)
        if decision == "approved":
            return None
        why = {"declined": "A person declined it.", "timeout": "No one approved it in time.",
               "unreachable": "No approver could be reached."}[decision]
        return err("not_approved", f"{why} Nothing was changed.",
                   "Say it was not done and what the person can do instead. Do not retry it.")


def _config(cfg: dict[str, Any]) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        temperature=0.2,
        thinking_config=types.ThinkingConfig(thinking_budget=cfg["thinking_budget"]),
    )


def handle_agent(plan: Plan, requester: Requester, understanding: dict[str, Any], run_id: str, text: str = "") -> LlmAgent:
    ctx = ToolContext(
        requester=requester,
        run_id=run_id,
        category=understanding["category"]["value"],
        impact=understanding["impact"],
        allowed=frozenset(plan.tools),
    )
    tools = build_tools(ctx)
    toolset = SkillToolset(
        offered_skills(ctx.allowed),
        additional_tools=list(tools.values()),
        discovery_mode=SkillDiscoveryMode.EAGER,
    )
    guard = RunGuard(plan, run_id, requester.profile, requester, text)
    instruction = HANDLE_INSTRUCTION.format(
        label=requester.label,
        title=requester.title,
        first=requester.first_name,
        user_id=requester.user_id,
        tools=", ".join(plan.tools) or "none",
        category=understanding["category"]["value"],
        intent=understanding["intent"]["value"].replace("_", " "),
        impact=understanding["impact"],
        effort=understanding["effort"]["value"].replace("_", " "),
        reach=("just them", "a team", "everyone")[understanding["reach"]["level"]],
        blocked="blocked" if understanding["work_stoppage"]["value"] == "blocked" else "can still work",
    ) + STYLE_SUFFIX.format(style=style_guide())
    return LlmAgent(
        name="handle_llm",
        model=_model(plan.tier),
        instruction=instruction,
        tools=[toolset],
        generate_content_config=_config(tier_config(plan.tier)),
        before_model_callback=guard.before_model,
        before_tool_callback=guard.before_tool,
    )


def reply_agent(kind: str, requester: Requester | None = None) -> LlmAgent:
    who = (
        PERSON_LINE.format(label=requester.label, title=requester.title, first=requester.first_name) + " "
        if requester
        else ""
    )
    return LlmAgent(
        name="reply_llm",
        model=_model("lite"),
        instruction=who + REPLY_INSTRUCTIONS[kind] + STYLE_SUFFIX.format(style=style_guide()),
        generate_content_config=_config(tier_config("lite")),
    )
