import asyncio

import pytest

from app import agent
from app.identity import resolve
from app.nodes import Ticket, understanding_from

from test_nodes import answers, SimpleNamespace


def ticket(profile: str, **kw) -> Ticket:
    u = understanding_from(answers(**kw))
    return Ticket(text="x", run_id="r1", requester=resolve(profile).model_dump(), understanding=u)


def stub_jev(monkeypatch, fits: dict[str, float] | None = None, tier: str = "lite") -> list[list[str]]:
    asked: list[list[str]] = []

    async def fake(bundle, qs, state):
        asked.append(sorted(qs))
        out = {k: SimpleNamespace(noul=(fits or {}).get(k[4:], 0.9)) for k in qs if k.startswith("use_")}
        out["tier"] = SimpleNamespace(choice=tier, probabilities={tier: 0.9})
        return out, {"calls": 1, "input_tokens": 10, "cost_usd": 1e-6}, {"model": "jev-test"}

    monkeypatch.setattr(agent.jev, "ask_jev", fake)
    return asked


def test_plan_step_asks_jev_and_records_what_it_picked(monkeypatch) -> None:
    stub_jev(monkeypatch, {"search_kb": 0.1, "create_ticket": 0.1})
    plan = asyncio.run(agent.plan_work(ticket("user_a"))).output.plan
    assert plan["tools"] == ["lookup_user", "reset_password"] and plan["tier"] == "lite"
    assert plan["usage"]["calls"] == 1 and plan["raw"]["model"] == "jev-test"
    assert plan["fits"]["reset_password"] == 0.9


def test_jev_never_sees_a_tool_user_b_does_not_hold(monkeypatch) -> None:
    asked = stub_jev(monkeypatch)
    plan = asyncio.run(agent.plan_work(ticket("user_b"))).output.plan
    assert "use_reset_password" not in asked[0] and "reset_password" not in plan["tools"]
    assert {"tool": "reset_password", "why": "not in your permissions"} in plan["hidden"]


def test_how_to_requests_get_read_only_candidates(monkeypatch) -> None:
    asked = stub_jev(monkeypatch)
    asyncio.run(agent.plan_work(ticket("user_a", intent="how_to")))
    assert asked[0] == ["tier", "use_lookup_user", "use_search_kb"]


def test_the_model_tier_is_jevs_choice(monkeypatch) -> None:
    stub_jev(monkeypatch, tier="strong")
    plan = asyncio.run(agent.plan_work(ticket("user_a"))).output.plan
    assert plan["tier"] == "strong" and plan["model"] == "gemini-3.1-pro-preview"


def test_a_failed_jev_call_stops_the_run(monkeypatch) -> None:
    async def boom(*a, **k):
        raise RuntimeError("jev down")

    monkeypatch.setattr(agent.jev, "ask_jev", boom)
    with pytest.raises(RuntimeError):
        asyncio.run(agent.plan_work(ticket("user_a")))
