from types import SimpleNamespace

import pytest

from app import nodes


def noul(p: float) -> SimpleNamespace:
    return SimpleNamespace(noul=p)


def answers(
    *, request: float = 0.99, fits: float = 0.99, blocked: float = 0.1, reach: int = 0,
    diagnose: float = 0.1, vague: float = 0.05, category: str = "password", intent: str = "request_action",
) -> dict[str, SimpleNamespace]:
    probs = {i: (0.98 if i == reach else 0.01) for i in range(3)}
    return {
        "is_request": noul(request),
        "category": SimpleNamespace(choice=category, probabilities={category: 0.95}),
        "intent": SimpleNamespace(choice=intent, probabilities={intent: 0.9}),
        "category_fits": noul(fits),
        "fully_blocked": noul(blocked),
        "reach": SimpleNamespace(probabilities=probs),
        "needs_diagnosis": noul(diagnose),
        "too_vague": noul(vague),
    }


# --- input guardrail ---


@pytest.mark.parametrize(
    ("top", "verdict"),
    [(0.03, "proceed"), (0.29, "proceed"), (0.30, "hold"), (0.69, "hold"), (0.70, "block"), (0.99, "block")],
)
def test_guardrail_verdict_bands(top: float, verdict: str) -> None:
    assert nodes.guardrail_verdict({"prompt_injection": 0.02, "jailbreak": top}) == verdict


def test_guardrail_uses_the_higher_score() -> None:
    assert nodes.guardrail_verdict({"prompt_injection": 0.8, "jailbreak": 0.1}) == "block"


# --- understanding: thresholds ---


@pytest.mark.parametrize(("p", "value"), [(0.49, "conversation"), (0.50, "request")])
def test_request_detection_threshold(p: float, value: str) -> None:
    assert nodes.understanding_from(answers(request=p))["request"]["value"] == value


@pytest.mark.parametrize(("p", "value"), [(0.59, "other"), (0.60, "password")])
def test_category_falls_back_to_other(p: float, value: str) -> None:
    assert nodes.understanding_from(answers(fits=p))["category"]["value"] == value


@pytest.mark.parametrize(
    ("p", "effort"),
    [(0.29, "quick_fix"), (0.30, "standard"), (0.69, "standard"), (0.70, "needs_investigation")],
)
def test_effort_bands(p: float, effort: str) -> None:
    assert nodes.understanding_from(answers(diagnose=p))["effort"]["value"] == effort


@pytest.mark.parametrize(("p", "value"), [(0.39, "working"), (0.40, "blocked")])
def test_work_stoppage_threshold(p: float, value: str) -> None:
    assert nodes.understanding_from(answers(blocked=p))["work_stoppage"]["value"] == value


# --- understanding: impact matrix ---


@pytest.mark.parametrize(
    ("reach", "blocked", "impact"),
    [(0, 0.1, "low"), (0, 0.9, "medium"), (1, 0.1, "medium"), (1, 0.9, "high"), (2, 0.1, "high"), (2, 0.9, "critical")],
)
def test_impact_matrix(reach: int, blocked: float, impact: str) -> None:
    assert nodes.understanding_from(answers(reach=reach, blocked=blocked))["impact"] == impact


# --- understanding: first match wins ---


def test_conversation_goes_to_a_greeting_reply() -> None:
    u = nodes.understanding_from(answers(request=0.05))
    assert (u["path"], u["reply_kind"]) == ("reply", "greeting")


def test_security_goes_to_a_specialist() -> None:
    assert nodes.understanding_from(answers(category="security"))["path"] == "specialist"


def test_vague_request_gets_a_clarifying_reply() -> None:
    u = nodes.understanding_from(answers(vague=0.9))
    assert (u["path"], u["reply_kind"]) == ("reply", "clarify")


def test_clear_request_is_handled() -> None:
    assert nodes.understanding_from(answers())["path"] == "handle"


def test_conversation_beats_security() -> None:
    assert nodes.understanding_from(answers(request=0.1, category="security"))["path"] == "reply"


def test_security_beats_vague() -> None:
    assert nodes.understanding_from(answers(category="security", vague=0.9))["path"] == "specialist"
