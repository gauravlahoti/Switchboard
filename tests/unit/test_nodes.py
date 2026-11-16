from app.nodes import ROUTE_LABELS, TriageResult, _route_decision
from app.tiers import TIER_FRONTIER, TIER_MID, TIER_SMALL, model_for_complexity


def _triage(security_incident: float, tool_fits: float) -> TriageResult:
    return TriageResult(
        category="auth",
        urgency="high",
        complexity=0.5,
        security_incident=security_incident,
        tool_choice="reset_password",
        tool_fits=tool_fits,
        raw_jev={},
    )


# --- policy_router truth table ---


def test_security_route_clear():
    route, rule = _route_decision(_triage(0.85, 0.90))
    assert route == "security"
    assert rule == ROUTE_LABELS["security"]


def test_security_route_at_threshold():
    route, _ = _route_decision(_triage(0.71, 0.90))
    assert route == "security"


def test_clarify_route_low_tool_fits():
    route, rule = _route_decision(_triage(0.10, 0.20))
    assert route == "clarify"
    assert rule == ROUTE_LABELS["clarify"]


def test_clarify_at_threshold():
    route, _ = _route_decision(_triage(0.10, 0.29))
    assert route == "clarify"


def test_action_route_clear():
    route, rule = _route_decision(_triage(0.10, 0.90))
    assert route == "action"
    assert rule == ROUTE_LABELS["action"]


def test_action_route_mid_band_security():
    route, _ = _route_decision(_triage(0.50, 0.80))
    assert route == "action"


def test_action_route_tool_fits_at_boundary():
    # tool_fits exactly 0.3 means NOT < 0.3, so action
    route, _ = _route_decision(_triage(0.10, 0.30))
    assert route == "action"


# --- model_for_complexity tier table ---


def test_tier_small():
    assert model_for_complexity(0.0) == TIER_SMALL
    assert model_for_complexity(0.1) == TIER_SMALL
    assert model_for_complexity(0.29) == TIER_SMALL


def test_tier_mid_at_lower_boundary():
    assert model_for_complexity(0.3) == TIER_MID


def test_tier_mid_mid_range():
    assert model_for_complexity(0.5) == TIER_MID


def test_tier_mid_at_upper_boundary():
    assert model_for_complexity(0.7) == TIER_MID


def test_tier_frontier_just_above():
    assert model_for_complexity(0.71) == TIER_FRONTIER


def test_tier_frontier_high():
    assert model_for_complexity(0.9) == TIER_FRONTIER
    assert model_for_complexity(1.0) == TIER_FRONTIER
