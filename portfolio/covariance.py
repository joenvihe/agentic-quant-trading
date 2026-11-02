"""Sample covariance estimation for normalized return series."""

from collections.abc import Mapping, Sequence
import math
from statistics import fmean

from portfolio.constraints import validate_symbols


def estimate_covariance(
    symbols: Sequence[str],
    returns_by_symbol: Mapping[str, Sequence[float]],
) -> tuple[tuple[float, ...], ...]:
    """Return annualization-neutral sample covariance in the given symbol order."""
    assets = validate_symbols(symbols)
    if set(returns_by_symbol) != set(assets):
        raise ValueError("Return series must be provided for exactly the requested symbols.")

    series = tuple(tuple(returns_by_symbol[symbol]) for symbol in assets)
    lengths = {len(values) for values in series}
    if len(lengths) != 1 or next(iter(lengths), 0) < 2:
        raise ValueError("At least two aligned return observations are required.")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for values in series
        for value in values
    ):
        raise ValueError("Returns must be finite real numbers.")

    means = tuple(fmean(values) for values in series)
    observations = len(series[0])
    return tuple(
        tuple(
            sum(
                (left[index] - means[row]) * (right[index] - means[column])
                for index in range(observations)
            )
            / (observations - 1)
            for column, right in enumerate(series)
        )
        for row, left in enumerate(series)
    )
