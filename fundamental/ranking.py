"""Cross-sectional ranking of available fundamental metrics."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import math

from fundamental.types import FundamentalMetrics


@dataclass(frozen=True)
class FundamentalRank:
    symbol: str
    as_of: datetime
    return_on_capital_rank: float | None
    earnings_yield_rank: float | None
    combined_rank: float | None


def rank_fundamentals(
    metrics: Sequence[FundamentalMetrics],
    as_of: datetime,
) -> tuple[FundamentalRank, ...]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware.")
    symbols = [item.symbol for item in metrics]
    if len(set(symbols)) != len(symbols):
        raise ValueError("Fundamental metric symbols must be unique.")
    if any(item.as_of > as_of for item in metrics):
        raise ValueError("Fundamental metrics include data newer than the as-of cutoff.")

    roc_ranks = _descending_ranks(
        {item.symbol: item.return_on_capital for item in metrics}
    )
    yield_ranks = _descending_ranks(
        {item.symbol: item.earnings_yield for item in metrics}
    )
    ranked = []
    for item in metrics:
        available = [
            rank
            for rank in (
                roc_ranks[item.symbol],
                yield_ranks[item.symbol],
            )
            if rank is not None
        ]
        ranked.append(
            FundamentalRank(
                symbol=item.symbol,
                as_of=as_of,
                return_on_capital_rank=roc_ranks[item.symbol],
                earnings_yield_rank=yield_ranks[item.symbol],
                combined_rank=sum(available) / len(available) if available else None,
            )
        )
    return tuple(
        sorted(
            ranked,
            key=lambda item: (
                item.combined_rank if item.combined_rank is not None else math.inf,
                item.symbol,
            ),
        )
    )


def _descending_ranks(
    values: dict[str, float | None],
) -> dict[str, float | None]:
    valid = sorted(
        ((symbol, value) for symbol, value in values.items() if value is not None),
        key=lambda item: (-item[1], item[0]),
    )
    ranks: dict[str, float | None] = {symbol: None for symbol in values}
    position = 0
    while position < len(valid):
        end = position + 1
        while end < len(valid) and valid[end][1] == valid[position][1]:
            end += 1
        average_rank = (position + 1 + end) / 2
        for symbol, _ in valid[position:end]:
            ranks[symbol] = average_rank
        position = end
    return ranks
