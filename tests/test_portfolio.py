import math
from types import SimpleNamespace

import pytest

import portfolio.optimizer as optimizer_module
from portfolio import (
    EqualWeightAllocator,
    MaximumSharpeOptimizer,
    PortfolioConstraints,
    estimate_covariance,
)


def test_equal_weight_allocation_is_fully_invested() -> None:
    result = EqualWeightAllocator().allocate(("SPY", "QQQ", "IWM"))

    assert result.success
    assert result.weights == pytest.approx(
        {"SPY": 1 / 3, "QQQ": 1 / 3, "IWM": 1 / 3}
    )
    assert sum(result.weights.values()) == pytest.approx(1.0)


def test_equal_weight_respects_bounds_and_reports_infeasibility() -> None:
    allocator = EqualWeightAllocator()

    bounded = allocator.allocate(
        ("A", "B"),
        PortfolioConstraints(min_weight=0.25, max_weight=0.75),
    )
    infeasible = allocator.allocate(
        ("A", "B"),
        PortfolioConstraints(min_weight=0.6, max_weight=1.0),
    )

    assert bounded.success
    assert all(0.25 <= weight <= 0.75 for weight in bounded.weights.values())
    assert not infeasible.success
    assert not infeasible.weights


def test_symbol_duplicates_and_invalid_constraints_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        EqualWeightAllocator().allocate(("SPY", "SPY"))
    with pytest.raises(ValueError, match="min_weight"):
        PortfolioConstraints(min_weight=0.8, max_weight=0.2)


def test_covariance_requires_aligned_sufficient_returns() -> None:
    covariance = estimate_covariance(
        ("A", "B"),
        {"A": (0.01, 0.02, 0.03), "B": (0.02, 0.04, 0.06)},
    )
    assert covariance[0][1] == pytest.approx(covariance[1][0])
    assert covariance[0][0] == pytest.approx(0.0001)

    with pytest.raises(ValueError, match="aligned"):
        estimate_covariance(("A", "B"), {"A": (0.01,), "B": (0.02,)})
    with pytest.raises(ValueError, match="aligned"):
        estimate_covariance(("A", "B"), {"A": (0.01, 0.02), "B": (0.02,)})


def test_maximum_sharpe_is_long_only_within_configured_limits() -> None:
    optimizer = MaximumSharpeOptimizer(
        PortfolioConstraints(min_weight=0.1, max_weight=0.7),
        periods_per_year=1,
    )
    returns = {
        "A": (0.01, 0.02, 0.03, 0.04),
        "B": (-0.001, 0.001, -0.001, 0.001),
    }

    result = optimizer.optimize(("A", "B"), returns)

    assert result.success, result.message
    assert sum(result.weights.values()) == pytest.approx(1.0)
    assert all(0.1 - 1e-8 <= weight <= 0.7 + 1e-8 for weight in result.weights.values())
    assert result.weights["A"] == pytest.approx(0.7, abs=1e-5)
    assert result.expected_sharpe is not None
    assert result.expected_volatility is not None
    assert result.expected_volatility > 0


def test_maximum_sharpe_handles_singular_covariance_deterministically() -> None:
    optimizer = MaximumSharpeOptimizer(periods_per_year=1)
    returns = {
        "A": (0.01, 0.02, 0.03, 0.04),
        "B": (0.02, 0.04, 0.06, 0.08),
    }

    first = optimizer.optimize(("A", "B"), returns)
    second = optimizer.optimize(("A", "B"), returns)

    assert first.success, first.message
    assert first.weights == pytest.approx(second.weights)
    assert math.isfinite(first.expected_sharpe)


def test_zero_volatility_portfolio_returns_explicit_failure() -> None:
    result = MaximumSharpeOptimizer().optimize(
        ("A", "B"),
        {"A": (0.01, 0.01, 0.01), "B": (0.01, 0.01, 0.01)},
    )

    assert not result.success
    assert "failed" in result.message or "no finite Sharpe" in result.message
    assert not result.weights


def test_numerical_optimizer_failure_is_not_replaced_with_equal_weight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        optimizer_module,
        "minimize",
        lambda *args, **kwargs: SimpleNamespace(
            success=False,
            message="synthetic solver failure",
            x=(0.5, 0.5),
        ),
    )

    result = MaximumSharpeOptimizer().optimize(
        ("A", "B"),
        {"A": (0.01, 0.02, 0.03), "B": (0.02, 0.01, 0.02)},
    )

    assert not result.success
    assert "synthetic solver failure" in result.message
    assert not result.weights


def test_optimizer_rejects_insufficient_and_invalid_return_series() -> None:
    optimizer = MaximumSharpeOptimizer()

    with pytest.raises(ValueError, match="at least two"):
        optimizer.optimize(("A",), {"A": (0.01,)})
    with pytest.raises(ValueError, match="finite"):
        optimizer.optimize(("A",), {"A": (0.01, math.nan)})
