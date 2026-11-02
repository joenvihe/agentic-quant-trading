"""Seeded Gaussian HMM regime analysis over normalized OHLCV bars."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import math
from numbers import Integral
from statistics import median, pstdev

from hmmlearn.hmm import GaussianHMM as _GaussianHMM
from numpy.linalg import LinAlgError

from data.market_data import MarketData


class HMMRegimeError(ValueError):
    """Raised when HMM regime inputs or model configuration are invalid."""


@dataclass(frozen=True)
class HMMStateStatistics:
    hidden_state_id: int
    mean_log_return: float | None
    mean_normalized_range: float | None
    volatility: float | None
    observations: int


@dataclass(frozen=True)
class HMMRegimeResult:
    ticker: str
    timestamp: datetime
    state_statistics: Mapping[int, HMMStateStatistics]
    state_labels: Mapping[int, str]
    hidden_state_id: int
    statistical_label: str
    statistics: HMMStateStatistics
    warnings: tuple[str, ...]


class GaussianHMMRegime:
    """Fit a reproducible Gaussian HMM using log returns and normalized range."""

    def __init__(
        self,
        *,
        random_state: int,
        n_components: int = 2,
        min_observations_per_state: int = 2,
    ) -> None:
        if isinstance(random_state, bool) or not isinstance(random_state, Integral):
            raise HMMRegimeError("random_state must be an integer.")
        if random_state < 0:
            raise HMMRegimeError("random_state must be non-negative.")
        if isinstance(n_components, bool) or not isinstance(n_components, int):
            raise HMMRegimeError("n_components must be a positive integer.")
        if n_components < 1:
            raise HMMRegimeError("n_components must be positive.")
        if (
            isinstance(min_observations_per_state, bool)
            or not isinstance(min_observations_per_state, int)
            or min_observations_per_state < 1
        ):
            raise HMMRegimeError("min_observations_per_state must be positive.")
        self.random_state = int(random_state)
        self.n_components = n_components
        self.min_observations_per_state = min_observations_per_state

    def fit_predict(self, market_data: MarketData) -> HMMRegimeResult:
        if not market_data.bars:
            raise HMMRegimeError("Insufficient history: market data is empty.")
        if len(market_data.bars) < max(11, self.n_components * 5 + 1):
            raise HMMRegimeError(
                f"Insufficient history: need at least "
                f"{max(11, self.n_components * 5 + 1)} bars."
            )

        observations: list[tuple[float, float]] = []
        timestamps: list[datetime] = []
        previous_close: float | None = None
        previous_timestamp: datetime | None = None
        for bar in market_data.bars:
            if bar.timestamp.tzinfo is None or bar.timestamp.utcoffset() is None:
                raise HMMRegimeError("Market timestamps must be timezone-aware.")
            if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
                raise HMMRegimeError(
                    "Market timestamps must be unique and chronologically ordered."
                )
            if not all(
                math.isfinite(value)
                for value in (bar.open, bar.high, bar.low, bar.close)
            ):
                raise HMMRegimeError("OHLC values must be finite.")
            if (
                min(bar.open, bar.high, bar.low, bar.close) <= 0
                or bar.high < max(bar.open, bar.close)
                or bar.low > min(bar.open, bar.close)
            ):
                raise HMMRegimeError("OHLC values must be positive and consistent.")
            if previous_close is not None:
                log_return = math.log(bar.close / previous_close)
                normalized_range = (bar.high - bar.low) / bar.close
                if not math.isfinite(log_return) or not math.isfinite(normalized_range):
                    raise HMMRegimeError("HMM observations must be finite.")
                observations.append((log_return, normalized_range))
                timestamps.append(bar.timestamp)
            previous_close = bar.close
            previous_timestamp = bar.timestamp

        model = _GaussianHMM(
            n_components=self.n_components,
            covariance_type="diag",
            n_iter=200,
            random_state=self.random_state,
        )
        try:
            model.fit(observations)
            predicted_states = model.predict(observations)
        except (ValueError, ArithmeticError, LinAlgError) as exc:
            raise HMMRegimeError(f"Gaussian HMM fitting failed: {exc}") from exc

        hidden_states = tuple(int(state) for state in predicted_states)
        grouped_observations = {
            state_id: [
                observations[index]
                for index, observed_state in enumerate(hidden_states)
                if observed_state == state_id
            ]
            for state_id in range(self.n_components)
        }
        state_statistics = {
            state_id: HMMStateStatistics(
                hidden_state_id=state_id,
                mean_log_return=(
                    sum(item[0] for item in values) / len(values)
                    if values
                    else None
                ),
                mean_normalized_range=(
                    sum(item[1] for item in values) / len(values)
                    if values
                    else None
                ),
                volatility=(
                    pstdev(item[0] for item in values)
                    if len(values) > 1
                    else None
                ),
                observations=len(values),
            )
            for state_id, values in grouped_observations.items()
        }
        labels = self._label_states(state_statistics)
        latest_state = hidden_states[-1]
        warnings = (
            ("Gaussian HMM did not converge.",)
            if not model.monitor_.converged
            else ()
        )
        return HMMRegimeResult(
            ticker=market_data.ticker,
            timestamp=timestamps[-1],
            state_statistics=state_statistics,
            state_labels=labels,
            hidden_state_id=latest_state,
            statistical_label=labels[latest_state],
            statistics=state_statistics[latest_state],
            warnings=warnings,
        )

    def _label_states(
        self,
        statistics: Mapping[int, HMMStateStatistics],
    ) -> dict[int, str]:
        supported_volatilities = [
            item.volatility
            for item in statistics.values()
            if item.observations >= self.min_observations_per_state
            and item.volatility is not None
        ]
        volatility_cutoff = (
            median(supported_volatilities) if supported_volatilities else None
        )
        labels: dict[int, str] = {}
        for state_id, item in statistics.items():
            if (
                item.observations < self.min_observations_per_state
                or item.mean_log_return is None
            ):
                labels[state_id] = "INSUFFICIENT_OBSERVATIONS"
                continue
            if item.mean_log_return > 0:
                drift = "POSITIVE_DRIFT"
            elif item.mean_log_return < 0:
                drift = "NEGATIVE_DRIFT"
            else:
                drift = "NEUTRAL_DRIFT"
            volatility_label = (
                "HIGH_VOLATILITY"
                if item.volatility is not None
                and volatility_cutoff is not None
                and item.volatility > volatility_cutoff
                else "LOW_VOLATILITY"
            )
            labels[state_id] = f"{drift}_{volatility_label}"
        return labels
