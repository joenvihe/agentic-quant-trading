import math

import pytest

from risk import (
    RiskEngineError,
    RiskLimits,
    calculate_realized_volatility,
    evaluate_risk,
)


def test_strategy_exposure_is_approved_within_limits() -> None:
    decision = evaluate_risk(
        0.15,
        0.10,
        RiskLimits(max_position_weight=0.20, max_portfolio_exposure=0.50),
    )

    assert decision.approved_weight == 0.15
    assert decision.accepted
    assert decision.reasons == ("APPROVED_WITHIN_LIMITS",)


def test_maximum_position_weight_reduces_requested_weight() -> None:
    decision = evaluate_risk(
        0.40,
        0,
        RiskLimits(max_position_weight=0.20, max_portfolio_exposure=1),
    )

    assert decision.approved_weight == 0.20
    assert decision.accepted
    assert "REDUCED_BY_MAX_POSITION_WEIGHT" in decision.reasons


def test_maximum_portfolio_exposure_reduces_or_rejects_position() -> None:
    limits = RiskLimits(max_position_weight=0.50, max_portfolio_exposure=0.60)
    reduced = evaluate_risk(0.40, 0.30, limits)
    rejected = evaluate_risk(0.40, 0.60, limits)

    assert reduced.approved_weight == pytest.approx(0.30)
    assert "REDUCED_BY_MAX_PORTFOLIO_EXPOSURE" in reduced.reasons
    assert rejected.approved_weight == 0
    assert not rejected.accepted


def test_volatility_target_reduces_exposure_and_missing_volatility_fails_closed() -> None:
    limits = RiskLimits(
        max_position_weight=1,
        max_portfolio_exposure=1,
        target_volatility=0.10,
    )
    reduced = evaluate_risk(
        0.80, 0.0, limits, realized_volatility=0.20
    )
    unavailable = evaluate_risk(0.80, 0.0, limits)

    assert reduced.approved_weight == pytest.approx(0.40)
    assert "REDUCED_BY_VOLATILITY_TARGET" in reduced.reasons
    assert unavailable.approved_weight == 0
    assert not unavailable.accepted
    assert "REJECTED_VOLATILITY_UNAVAILABLE" in unavailable.reasons


def test_drawdown_circuit_breaker_blocks_exposure() -> None:
    decision = evaluate_risk(
        0.10,
        0.0,
        RiskLimits(max_drawdown=0.20),
        current_drawdown=0.20,
    )

    assert decision.approved_weight == 0
    assert not decision.accepted
    assert decision.reasons == ("REJECTED_MAX_DRAWDOWN_CIRCUIT_BREAKER",)


@pytest.mark.parametrize(
    "limits",
    [
        {"max_position_weight": -0.1},
        {"max_portfolio_exposure": 1.1},
        {"max_drawdown": 0.0},
        {"target_volatility": 0.0},
        {"max_position_weight": math.nan},
    ],
)
def test_invalid_risk_limits_are_rejected(limits: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        RiskLimits(**limits)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"requested_weight": 1.1}, "requested_weight"),
        ({"current_exposure": -0.1}, "current_exposure"),
        ({"realized_volatility": math.nan}, "realized_volatility"),
        ({"current_drawdown": 1.1}, "current_drawdown"),
    ],
)
def test_invalid_risk_inputs_are_rejected(
    kwargs: dict[str, float], message: str
) -> None:
    arguments = {
        "requested_weight": 0.1,
        "current_exposure": 0.0,
        "limits": RiskLimits(),
    }
    arguments.update(kwargs)
    with pytest.raises(RiskEngineError, match=message):
        evaluate_risk(**arguments)


def test_risk_decisions_are_deterministic() -> None:
    arguments = {
        "requested_weight": 0.5,
        "current_exposure": 0.2,
        "limits": RiskLimits(target_volatility=0.1),
        "realized_volatility": 0.2,
    }

    assert evaluate_risk(**arguments) == evaluate_risk(**arguments)


def test_realized_volatility_is_annualized_and_handles_short_history() -> None:
    prices = (100.0, 101.0, 99.0, 103.0)

    volatility = calculate_realized_volatility(prices, periods_per_year=4)

    assert volatility is not None
    assert volatility > 0
    assert calculate_realized_volatility((100.0, 101.0)) is None
    with pytest.raises(ValueError, match="Prices"):
        calculate_realized_volatility((100.0, 0.0, 101.0))
