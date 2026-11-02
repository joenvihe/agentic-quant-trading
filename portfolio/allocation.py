"""Deterministic allocation baselines."""

from portfolio.constraints import (
    PortfolioConstraints,
    constraints_are_feasible,
    validate_symbols,
)
from portfolio.types import AllocationResult


class EqualWeightAllocator:
    """Allocate equal fully invested weights without numerical dependencies."""

    def allocate(
        self,
        symbols: tuple[str, ...] | list[str],
        constraints: PortfolioConstraints | None = None,
    ) -> AllocationResult:
        assets = validate_symbols(symbols)
        limits = constraints or PortfolioConstraints()
        if not constraints_are_feasible(len(assets), limits):
            return AllocationResult(
                weights={},
                expected_return=None,
                expected_volatility=None,
                expected_sharpe=None,
                success=False,
                message="Constraints are infeasible for a fully invested portfolio.",
            )

        weight = 1.0 / len(assets)
        if not limits.min_weight <= weight <= limits.max_weight:
            return AllocationResult(
                weights={},
                expected_return=None,
                expected_volatility=None,
                expected_sharpe=None,
                success=False,
                message="Equal weights violate the configured weight bounds.",
            )
        return AllocationResult(
            weights={symbol: weight for symbol in assets},
            expected_return=None,
            expected_volatility=None,
            expected_sharpe=None,
            success=True,
            message="Equal-weight allocation completed.",
        )
