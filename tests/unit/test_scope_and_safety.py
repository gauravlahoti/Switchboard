import asyncio
from types import SimpleNamespace

import pytest

from app import approvals, harness, identity, nodes, safety
from app.nodes import Ticket


def calm(**over: float) -> dict[str, float]:
    base = {"privileged": 0.05, "requester_verified": 0.95, "matches_attack_pattern": 0.03}
    return {**base, **over}


# --- scope check in the input guardrail ---


@pytest.mark.parametrize(
    ("scores", "verdict"),
    [
        ({"prompt_injection": 0.02, "jailbreak": 0.02, "off_topic": 0.97}, "decline"),
        ({"prompt_injection": 0.02, "jailbreak": 0.02, "off_topic": 0.59}, "proceed"),
        ({"prompt_injection": 0.02, "jailbreak": 0.02, "off_topic": 0.02}, "proceed"),
        ({"prompt_injection": 0.80, "jailbreak": 0.02, "off_topic": 0.99}, "block"),
        ({"prompt_injection": 0.40, "jailbreak": 0.02, "off_topic": 0.99}, "hold"),
    ],
)
def test_scope_is_judged_after_attacks(scores: dict[str, float], verdict: str) -> None:
    assert nodes.guardrail_verdict(scores) == verdict


def _ticket(verdict: str) -> Ticket:
    who = identity.resolve("user_a").model_dump()
    return Ticket(text="I need a food recipe", requester=who, guardrail={"verdict": verdict})


def test_decline_is_polite_personal_and_free_of_model_calls() -> None:
    text = nodes.block_request(_ticket("decline")).output
    assert text.startswith("Carol, that is outside what the IT service desk can help with.")
    assert "Next step:" in text and "—" not in text


def test_a_blocked_attack_keeps_its_own_message() -> None:
    assert "cannot be acted on" in nodes.block_request(_ticket("block")).output


# --- safety table ---


def test_account_changes_always_go_to_a_person() -> None:
    v = safety.decide("reset_password", calm())
    assert v.outcome == "approve" and "always" in v.rule


def test_a_calm_ticket_runs_without_asking() -> None:
    assert safety.decide("create_ticket", calm()).outcome == "auto"


@pytest.mark.parametrize(
    "over", [{"privileged": 0.6}, {"requester_verified": 0.3}, {"matches_attack_pattern": 0.4}]
)
def test_signals_send_a_ticket_to_a_person(over: dict[str, float]) -> None:
    assert safety.decide("create_ticket", calm(**over)).outcome == "approve"


def test_a_tool_the_code_cannot_vouch_for_goes_to_a_person() -> None:
    assert safety.decide("restart_service", calm()).outcome == "approve"


def test_an_attack_pattern_is_refused_outright() -> None:
    assert safety.decide("reset_password", calm(matches_attack_pattern=0.85)).outcome == "deny"


def test_the_action_is_described_with_a_masked_address() -> None:
    who = identity.resolve("user_a")
    text = safety.describe("reset_password", {}, who)
    assert "c***@acme.corp" in text and "carol@" not in text


# --- approvals ---


def test_an_approver_unblocks_the_waiting_call() -> None:
    async def go() -> tuple[str, int, str | None]:
        approvals.attach("r1", lambda ev: asyncio.sleep(0))
        waiting = asyncio.create_task(approvals.ask("r1", "a1", 5, ["manager"]))
        await asyncio.sleep(0.05)
        assert approvals.decide("r1", "a1", True, "manager")
        return await waiting

    outcome, waited, by = asyncio.run(go())
    assert outcome == "approved" and waited >= 0 and by == "manager"


def test_a_decline_and_a_silence_both_fail_closed() -> None:
    async def go() -> list[str]:
        approvals.attach("r2", lambda ev: asyncio.sleep(0))
        first = asyncio.create_task(approvals.ask("r2", "a1", 5, ["manager"]))
        await asyncio.sleep(0.05)
        approvals.decide("r2", "a1", False, "manager")
        return [
            (await first)[0],
            (await approvals.ask("r2", "a2", 0.05, ["manager"]))[0],
            (await approvals.ask("nope", "a3", 1, ["manager"]))[0],
        ]

    assert asyncio.run(go()) == ["declined", "timeout", "unreachable"]


def test_nothing_is_waiting_for_an_unknown_approval() -> None:
    assert approvals.decide("ghost", "x", True, "manager") is False


# --- the gate inside the agent's tool loop ---


def _guard_for(profile: str = "user_a") -> harness.RunGuard:
    who = identity.resolve(profile)
    plan = harness.Plan(
        "lite", "m", "Lite", 0, ("reset_password", "create_ticket", "search_kb"), (), (),
    )
    return harness.RunGuard(plan, "run-g", who.profile, who, "I am locked out")


def _stub_assess(monkeypatch: pytest.MonkeyPatch, outcome: str) -> None:
    async def fake(tool, args, requester, text):
        verdict = safety.Verdict(outcome, "test rule", calm())
        return verdict, {"calls": 1, "input_tokens": 100, "cost_usd": 0.0}, {"answers": {}}, "Unlock the account"

    monkeypatch.setattr(safety, "assess", fake)


def _run_gate(
    outcome: str, decision: bool | None, monkeypatch: pytest.MonkeyPatch, by: str = "manager", who: str = "user_a"
) -> tuple[object, list[dict]]:
    _stub_assess(monkeypatch, outcome)
    seen: list[dict] = []

    async def go() -> object:
        async def emit(ev: dict) -> None:
            seen.append(ev)

        approvals.attach("run-g", emit)
        call = asyncio.create_task(_guard_for(who).before_tool(SimpleNamespace(name="reset_password"), {}, None))
        if decision is not None:
            while not any(e["type"] == "safety" for e in seen):
                await asyncio.sleep(0.01)
            approvals.decide("run-g", next(e["id"] for e in seen if e["type"] == "safety"), decision, by)
        return await call

    return asyncio.run(go()), seen


def test_gate_lets_a_calm_action_run(monkeypatch: pytest.MonkeyPatch) -> None:
    result, seen = _run_gate("auto", None, monkeypatch)
    assert result is None and [e["type"] for e in seen] == ["safety", "usage"]


def test_gate_refuses_without_asking(monkeypatch: pytest.MonkeyPatch) -> None:
    result, seen = _run_gate("deny", None, monkeypatch)
    assert result["code"] == "refused" and not any(e["type"] == "approval_result" for e in seen)


def test_gate_runs_the_action_once_a_person_approves(monkeypatch: pytest.MonkeyPatch) -> None:
    result, seen = _run_gate("approve", True, monkeypatch)
    assert result is None and seen[-1]["decision"] == "approved"


def test_gate_stops_the_action_when_a_person_declines(monkeypatch: pytest.MonkeyPatch) -> None:
    result, seen = _run_gate("approve", False, monkeypatch)
    assert result["code"] == "not_approved" and "Nothing was changed" in result["message"]


def test_gate_fails_closed_when_the_safety_check_breaks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(safety, "assess", boom)
    result = asyncio.run(_guard_for().before_tool(SimpleNamespace(name="reset_password"), {}, None))
    assert result["code"] == "safety_unavailable"


def test_read_tools_skip_the_safety_check(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_assess(monkeypatch, "deny")
    assert asyncio.run(_guard_for().before_tool(SimpleNamespace(name="search_kb"), {"query": "vpn"}, None)) is None


# --- who may approve ---


def test_the_manager_is_an_approver_but_nobody_approves_their_own_request() -> None:
    assert [a["id"] for a in identity.approvers_for("reset_password", "user_a")] == ["manager"]
    assert identity.approvers_for("reset_password", "manager") == []
    assert identity.approvers_for("search_kb", "user_a") == []


def test_the_approver_is_in_the_directory_and_the_menu() -> None:
    john = identity.resolve("manager")
    assert john.name == "John Reyes" and john.first_name == "John"
    entry = next(p for p in identity.catalog() if p["id"] == "manager")
    assert entry["approves"] == ["create_ticket", "reset_password"]
    assert next(p for p in identity.catalog() if p["id"] == "user_a")["approves"] == []


def test_only_a_listed_approver_can_answer() -> None:
    async def go() -> tuple[bool, bool, str]:
        approvals.attach("r5", lambda ev: asyncio.sleep(0))
        waiting = asyncio.create_task(approvals.ask("r5", "a1", 5, ["manager"]))
        await asyncio.sleep(0.05)
        forged = approvals.decide("r5", "a1", True, "user_a")  # the requester answering for themselves
        stranger = approvals.may_answer("r5", "a1", "user_b")
        approvals.decide("r5", "a1", False, "manager")
        return forged, stranger, (await waiting)[0]

    assert asyncio.run(go()) == (False, False, "declined")


def test_no_eligible_approver_fails_closed_without_waiting() -> None:
    async def go() -> tuple[str, int, str | None]:
        approvals.attach("r6", lambda ev: asyncio.sleep(0))
        return await approvals.ask("r6", "a1", 30, [])

    assert asyncio.run(go()) == ("unreachable", 0, None)


def test_gate_names_the_approver_who_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    result, seen = _run_gate("approve", True, monkeypatch)
    ask = next(e for e in seen if e["type"] == "safety")
    assert ask["approvers"][0]["label"] == "John Reyes" and ask["requester"]["label"] == "Carol Wu"
    assert result is None and seen[-1]["by"]["id"] == "manager"


def test_gate_ignores_an_answer_from_the_requester(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_assess(monkeypatch, "approve")
    seen: list[dict] = []

    async def go() -> tuple[bool, object]:
        async def emit(ev: dict) -> None:
            seen.append(ev)

        approvals.attach("run-g", emit)
        call = asyncio.create_task(_guard_for().before_tool(SimpleNamespace(name="reset_password"), {}, None))
        while not any(e["type"] == "safety" for e in seen):
            await asyncio.sleep(0.01)
        aid = next(e["id"] for e in seen if e["type"] == "safety")
        accepted = approvals.decide("run-g", aid, True, "user_a")
        approvals.decide("run-g", aid, False, "manager")
        return accepted, await call

    accepted, result = asyncio.run(go())
    assert accepted is False and result["code"] == "not_approved"


def test_a_request_with_no_other_approver_is_declined_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    result, seen = _run_gate("approve", None, monkeypatch, who="manager")
    assert result["code"] == "not_approved" and seen[-1]["decision"] == "unreachable"
