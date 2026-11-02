"""Maximum-Sharpe long-only portfolio optimization."""

from collections.abc import Mapping, Sequence
import math
from numbers import Real
from statistics import fmean

from scipy.optimize import minimize

from portfolio.constraints import (
    PortfolioConstraints,
    constraints_are_feasible,
    validate_symbols,
)
from portfolio.covariance import estimate_covariance
from portfolio.types import AllocationResult


class MaximumSharpeOptimizer:
    """Optimize long-only fully invested weights using deterministic SLSQP."""

    def __init__(
        self,
        constraints: PortfolioConstraints | None = None,
        periods_per_year: int = 252,
    ) -> None:
        if (
            isinstance(periods_per_year, bool)
            or not isinstance(periods_per_year, int)
            or periods_per_year <= 0
        ):
            raise ValueError("periods_per_year must be a positive integer.")
        self.constraints = constraints or PortfolioConstraints()
        self.periods_per_year = periods_per_year

    def optimize(
        self,
        symbols: Sequence[str],
        returns_by_symbol: Mapping[str, Sequence[float]],
        risk_free_rate: float = 0.0,
    ) -> AllocationResult:
        assets = validate_symbols(symbols)
        if (
            isinstance(risk_free_rate, bool)
            or not isinstance(risk_free_rate, Real)
            or not math.isfinite(risk_free_rate)
        ):
            raise ValueError("risk_free_rate must be finite.")
        covariance = estimate_covariance(assets, returns_by_symbol)
        if not constraints_are_feasible(len(assets), self.constraints):
            return _failed("Constraints cannot produce a fully invested portfolio.")

        means = tuple(
            fmean(returns_by_symbol[symbol]) * self.periods_per_year
            for symbol in assets
        )
        annual_covariance = tuple(
            tuple(value * self.periods_per_year for value in row)
            for row in covariance
        )
        lower = self.constraints.min_weight
        upper = self.constraints.max_weight

        def portfolio_statistics(
            weights: Sequence[float],
        ) -> tuple[float, float, float | None]:
            expected_return = sum(weight * mean for weight, mean in zip(weights, means))
            variance = sum(
                weights[row] * annual_covariance[row][column] * weights[column]
                for row in range(len(assets))
                for column in range(len(assets))
            )
            if variance < -1e-12:
                return expected_return, math.nan, None
            volatility = math.sqrt(max(0.0, variance))
            if volatility == 0:
                return expected_return, volatility, None
            sharpe = (expected_return - risk_free_rate) / volatility
            return expected_return, volatility, (
                sharpe if math.isfinite(sharpe) else None
            )

        def objective(weights: Sequence[float]) -> float:
            _, volatility, sharpe = portfolio_statistics(weights)
            if sharpe is None or volatility <= 1e-12:
                return 1e100
            return -sharpe

        initial = [1.0 / len(assets)] * len(assets)
        result = minimize(
            objective,
            initial,
            method="SLSQP",
            bounds=[(lower, upper)] * len(assets),
            constraints=({"type": "eq", "fun": lambda weights: sum(weights) - 1.0},),
            options={"maxiter": 1000, "ftol": 1e-12},
        )
        if not result.success:
            return _failed(f"Maximum-Sharpe optimization failed: {result.message}")

        weights = tuple(float(weight) for weight in result.x)
        if (
            len(weights) != len(assets)
            or any(
                not math.isfinite(weight)
                or weight < lower - 1e-8
                or weight > upper + 1e-8
                for weight in weights
            )
            or not math.isclose(sum(weights), 1.0, abs_tol=1e-7)
        ):
            return _failed("Maximum-Sharpe optimizer returned infeasible weights.")
        expected_return, volatility, sharpe = portfolio_statistics(weights)
        if sharpe is None:
            return _failed(
                "Maximum-Sharpe optimization has no finite Sharpe ratio "
                "(portfolio volatility is zero or invalid)."
            )
        return AllocationResult(
            weights=dict(zip(assets, weights)),
            expected_return=expected_return,
            expected_volatility=volatility,
            expected_sharpe=sharpe,
            success=True,
            message="Maximum-Sharpe optimization completed.",
        )


def _failed(message: str) -> AllocationResult:
    return AllocationResult(
        weights={},
        expected_return=None,
        expected_volatility=None,
        expected_sharpe=None,
        success=False,
        message=message,
    )
