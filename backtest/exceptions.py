"""Backtest domain exceptions."""


class BacktestError(Exception):
    """Base error for backtest execution."""


class BacktestValidationError(BacktestError):
    """Raised when backtest inputs violate supported constraints."""
