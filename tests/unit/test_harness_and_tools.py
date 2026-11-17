import asyncio
import inspect
import json
from datetime import date
from types import SimpleNamespace

import pytest

from app import audit, harness, identity, questions
from app.store import store
from app.tools import ToolContext, build_tools


def understanding(*, category: str = "password", intent: str = "request_action", impact: str = "medium") -> dict:
    return {
        "category": {"value": category},
        "intent": {"value": intent},
        "effort": {"value": "quick_fix"},
        "impact": impact,
        "reach": {"level": 0},
        "work_stoppage": {"value": "blocked"},
    }


def jev_answers(fits: dict[str, float], tier: str = "lite", p: float = 0.9) -> dict:
    out = {f"use_{tool}": SimpleNamespace(noul=v) for tool, v in fits.items()}
    out["tier"] = SimpleNamespace(choice=tier, probabilities={tier: p})
    return out


def allowed_for(profile: str, **kw) -> tuple:
    who = identity.resolve(profile)
    cands, hidden = harness.candidates(who, understanding(**kw))
    return who, cands, hidden


def tools_for(profile: str, **kw) -> dict:
    who, cands, _ = allowed_for(profile, **kw)
    ctx = ToolContext(who, "run1", kw.get("category", "password"), kw.get("impact", "medium"), frozenset(cands))
    return build_tools(ctx)


# --- identity and policy ---


def test_two_people_never_share_the_same_tools() -> None:
    a, b = identity.resolve("user_a"), identity.resolve("user_b")
    assert set(a.tools) != set(b.tools)
    assert "reset_password" in a.tools and "reset_password" not in b.tools


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(identity.UnknownProfile):
        identity.resolve("user_z")


def test_every_profile_tool_has_a_scope() -> None:
    for prof in identity.policy()["profiles"].values():
        assert set(prof["tools"]) <= set(prof["scope"])


# --- hard limits are code, the picks are Jev ---


def test_candidates_are_only_what_the_person_holds() -> None:
    _, cands, hidden = allowed_for("user_b")
    assert "reset_password" not in cands
    assert ("reset_password", "not in your permissions") in hidden


def test_how_to_questions_only_get_read_only_candidates() -> None:
    _, cands, _ = allowed_for("user_a", intent="how_to")
    assert set(cands) == {"search_kb", "lookup_user"}


def test_jev_is_only_asked_about_tools_the_person_may_use() -> None:
    _, cands, _ = allowed_for("user_b")
    qs = questions.select_questions(cands)
    assert "use_reset_password" not in qs and {"use_search_kb", "use_lookup_user", "use_create_ticket", "tier"} == set(qs)


def test_jev_picks_tools_and_model_from_the_allowed_set() -> None:
    _, cands, hidden = allowed_for("user_a")
    fits = {"search_kb": 0.1, "lookup_user": 0.9, "reset_password": 0.95, "create_ticket": 0.05}
    plan = harness.plan_from_selection(cands, hidden, jev_answers(fits, "lite"))
    assert plan.tools == ("lookup_user", "reset_password")
    assert plan.model == "gemini-3.1-flash-lite" and "gemini-3.1-flash-lite" in plan.why
    assert {t for t, why in plan.hidden if why.startswith("Jev")} == {"search_kb", "create_ticket"}


def test_read_tools_need_a_lenient_fit_and_write_tools_a_clear_one() -> None:
    _, cands, hidden = allowed_for("user_a")
    fits = {"search_kb": 0.35, "lookup_user": 0.29, "reset_password": 0.45, "create_ticket": 0.50}
    plan = harness.plan_from_selection(cands, hidden, jev_answers(fits))
    assert plan.tools == ("search_kb", "create_ticket")


def test_the_model_tier_comes_from_jev() -> None:
    _, cands, hidden = allowed_for("user_a")
    plan = harness.plan_from_selection(cands, hidden, jev_answers({t: 0.9 for t in cands}, "strong", 0.8))
    assert plan.tier == "strong" and plan.model == "gemini-3.1-pro-preview" and "80% sure" in plan.why


def test_when_jev_finds_nothing_useful_every_allowed_tool_stays() -> None:
    _, cands, hidden = allowed_for("user_a")
    plan = harness.plan_from_selection(cands, hidden, jev_answers({t: 0.1 for t in cands}))
    assert set(plan.tools) == set(cands)


def test_a_plan_survives_its_summary() -> None:
    _, cands, hidden = allowed_for("user_a")
    plan = harness.plan_from_selection(cands, hidden, jev_answers({t: 0.9 for t in cands}, "mid", 0.7))
    assert harness.Plan.from_summary(plan.summary()) == plan


def test_skills_are_trimmed_to_available_tools() -> None:
    offered = harness.offered_skills(frozenset({"lookup_user"}))
    assert [s.name for s in offered] == ["account-access", "device-and-requests"]
    for skill in offered:
        assert skill.frontmatter.metadata["adk_additional_tools"] == ["lookup_user"]


def test_jev_is_told_what_the_knowledge_base_covers() -> None:
    state = questions.select_state("x", understanding(), ["search_kb", "create_ticket"], store.kb_titles())
    assert "Service Outage Procedure" in state["tools_available"]["search_kb"]
    assert "Articles cover" not in state["tools_available"]["create_ticket"]


def test_reply_style_is_not_offered_as_a_task_skill() -> None:
    names = [s.name for s in harness.offered_skills(frozenset({"search_kb", "lookup_user", "reset_password", "create_ticket"}))]
    assert "reply-style" not in names and len(names) == 3


def test_one_style_guide_is_applied_to_both_gemini_steps() -> None:
    who, cands, hidden = allowed_for("user_a")
    plan = harness.plan_from_selection(cands, hidden, jev_answers({t: 0.9 for t in cands}))
    resolve = harness.handle_agent(plan, who, understanding(), "run1").instruction
    quick = harness.reply_agent("clarify").instruction
    for text in (resolve, quick):
        assert "Outcome first" in text and '"Next step:"' in text and "no em dashes" in text
    assert "{" not in harness.style_guide()


def test_the_model_is_told_never_to_mention_missing_tools() -> None:
    who, cands, hidden = allowed_for("user_b")
    fits = {tool: 0.1 for tool in cands} | {"create_ticket": 0.9}
    plan = harness.plan_from_selection(cands, hidden, jev_answers(fits))
    agent = harness.handle_agent(plan, who, understanding(), "run1")
    assert "Your tools for this request: create_ticket." in agent.instruction
    assert "Never mention tools, skills, models, probabilities or internal limits" in agent.instruction


# --- prices ---


def test_cost_uses_the_tier_price_list() -> None:
    assert harness.cost_usd("lite", 1000, 100) == pytest.approx((1000 * 0.25 + 100 * 1.50) / 1e6)


def test_mid_tier_price_steps_up_in_2027(monkeypatch) -> None:
    monkeypatch.setattr(harness, "_today", lambda: date(2026, 12, 31))
    before = harness.cost_usd("mid", 1_000_000, 1_000_000)
    monkeypatch.setattr(harness, "_today", lambda: date(2027, 1, 1))
    after = harness.cost_usd("mid", 1_000_000, 1_000_000)
    assert before == pytest.approx(0.75 + 3.75) and after == pytest.approx(1.50 + 7.50)


def test_strong_tier_price_depends_on_prompt_size() -> None:
    assert harness.cost_usd("strong", 200_000, 0) == pytest.approx(200_000 * 2.00 / 1e6)
    assert harness.cost_usd("strong", 200_001, 0) == pytest.approx(200_001 * 4.00 / 1e6)


# --- tools: binding and behaviour ---


def test_user_a_can_only_look_up_themselves() -> None:
    tools = tools_for("user_a")
    assert list(inspect.signature(tools["lookup_user"]).parameters) == []
    result = tools["lookup_user"]()
    assert result["data"]["user_id"] == "u003"
    assert result["data"]["email"] == "c***@acme.corp"


def test_user_b_can_look_up_anyone_but_cannot_reset() -> None:
    tools = tools_for("user_b")
    assert "reset_password" not in tools
    assert tools["lookup_user"]("u003")["data"]["account_locked"] is True
    assert tools["lookup_user"]("nobody")["code"] == "not_found"


def test_reset_unlocks_the_requester_and_is_repeatable() -> None:
    reset = tools_for("user_a")["reset_password"]
    first, second = reset(), reset()
    assert first["data"]["was_locked"] is True and first["data"]["account_unlocked"] is True
    assert second["data"]["was_locked"] is False
    assert store.get_user("u003")["password_locked"] == 0


def test_reset_needs_mfa() -> None:
    with store.conn() as con:
        con.execute("UPDATE users SET is_mfa_enabled=0 WHERE id='u003'")
    assert tools_for("user_a")["reset_password"]()["code"] == "mfa_required"


def test_ticket_priority_and_category_come_from_triage_not_the_model() -> None:
    create = tools_for("user_a", category="hardware", impact="high")["create_ticket"]
    out = create(title="Cracked laptop screen", details="Screen cracked overnight")
    assert out["data"]["priority"] == "high" and out["data"]["queue"] == "End-user Devices"
    row = next(t for t in _tickets() if t["id"] == out["data"]["ticket_id"])
    assert row["requester_id"] == "u003" and row["category"] == "hardware" and row["created_by"] == "u003"


def test_an_identical_ticket_is_not_opened_twice() -> None:
    create = tools_for("user_a")["create_ticket"]
    first = create(title="Cannot sign in", details="Locked out")
    second = create(title="Cannot sign in", details="Locked out")
    assert second["data"]["duplicate"] is True and second["data"]["ticket_id"] == first["data"]["ticket_id"]


def test_analyst_can_open_a_ticket_for_someone_else() -> None:
    out = tools_for("user_b")["create_ticket"](title="Laptop swap needed", details="Broken hinge", requester_id="u001")
    row = next(t for t in _tickets() if t["id"] == out["data"]["ticket_id"])
    assert row["requester_id"] == "u001" and row["created_by"] == "u004"


def test_bad_ticket_input_gives_an_actionable_error() -> None:
    out = tools_for("user_a")["create_ticket"](title="no", details="x")
    assert out["status"] == "error" and out["code"] == "bad_title" and out["hint"]


# --- call gate and limits ---


def _guard() -> harness.RunGuard:
    _, cands, hidden = allowed_for("user_b")
    plan = harness.plan_from_selection(cands, hidden, jev_answers({t: 0.9 for t in cands}))
    return harness.RunGuard(plan, "run1", "user_b")


def test_gate_rejects_a_tool_outside_the_plan() -> None:
    denied = asyncio.run(_guard().before_tool(SimpleNamespace(name="reset_password"), {}, None))
    assert denied["code"] == "not_permitted"


def test_gate_lets_skill_tools_and_allowed_tools_through() -> None:
    g = _guard()
    assert asyncio.run(g.before_tool(SimpleNamespace(name="load_skill"), {"skill_name": "x"}, None)) is None
    assert asyncio.run(g.before_tool(SimpleNamespace(name="search_kb"), {"query": "vpn"}, None)) is None


def test_tool_budget_is_enforced() -> None:
    g = _guard()
    limit = g.limits["max_tool_calls"]
    results = [asyncio.run(g.before_tool(SimpleNamespace(name="search_kb"), {}, None)) for _ in range(limit + 1)]
    assert results[:limit] == [None] * limit and results[-1]["code"] == "tool_budget"


def test_model_budget_hands_off_instead_of_looping() -> None:
    g = _guard()
    for _ in range(g.limits["max_model_calls"]):
        assert asyncio.run(g.before_model(None, None)) is None
    assert asyncio.run(g.before_model(None, None)) is not None


# --- audit trail ---


def test_audit_masks_emails_and_long_numbers(isolated) -> None:
    audit.record("test", "run1", "user_a", note="mail carol@acme.corp card 4111111111111111")
    line = json.loads(isolated.read_text(encoding="utf-8").splitlines()[0])
    assert "carol@acme.corp" not in line["note"] and "4111111111111111" not in line["note"]
    assert line["actor"] == "user_a" and line["run_id"] == "run1"


def test_every_tool_call_is_audited(isolated) -> None:
    tools_for("user_a")["lookup_user"]()
    events = [json.loads(x) for x in isolated.read_text(encoding="utf-8").splitlines()]
    assert any(e["event"] == "tool_result" and e["tool"] == "lookup_user" for e in events)


def _tickets() -> list[dict]:
    with store.conn() as con:
        return [dict(r) for r in con.execute("SELECT * FROM tickets").fetchall()]
