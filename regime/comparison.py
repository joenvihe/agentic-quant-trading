"""Descriptive comparison of deterministic and HMM regime assessments."""

from dataclasses import dataclass
from datetime import datetime

from regime.engine import RegimeAssessment
from regime.hmm import HMMRegimeResult


@dataclass(frozen=True)
class RegimeComparison:
    ticker: str
    timestamp: datetime
    deterministic_regime: str
    hidden_state_id: int
    statistical_label: str
    agreement: bool | None


def compare_regimes(
    deterministic: RegimeAssessment,
    hmm: HMMRegimeResult,
) -> RegimeComparison:
    if deterministic.ticker != hmm.ticker:
        raise ValueError("Regime assessments must refer to the same ticker.")
    if deterministic.timestamp != hmm.timestamp:
        raise ValueError("Regime assessments must refer to the same timestamp.")
    deterministic_direction = _deterministic_direction(deterministic.regime)
    hmm_direction = _hmm_direction(hmm.statistical_label)
    agreement = (
        deterministic_direction == hmm_direction
        if deterministic_direction is not None and hmm_direction is not None
        else None
    )
    return RegimeComparison(
        ticker=deterministic.ticker,
        timestamp=hmm.timestamp,
        deterministic_regime=deterministic.regime,
        hidden_state_id=hmm.hidden_state_id,
        statistical_label=hmm.statistical_label,
        agreement=agreement,
    )


def _deterministic_direction(regime: str) -> str | None:
    if regime in {"BULL_STRONG", "BULL_VOLATILE"}:
        return "POSITIVE_DRIFT"
    if regime == "BEAR":
        return "NEGATIVE_DRIFT"
    return None


def _hmm_direction(label: str) -> str | None:
    for direction in ("POSITIVE_DRIFT", "NEGATIVE_DRIFT", "NEUTRAL_DRIFT"):
        if label.startswith(direction):
            return direction
    return None
