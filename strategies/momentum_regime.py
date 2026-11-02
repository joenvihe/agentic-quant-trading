"""Long-only strategy gated by the existing momentum factor and regime."""

from dataclasses import dataclass, field

from factors.momentum import MomentumRank
from regime.engine import RegimeAssessment
from strategies.types import TargetPosition


REGIME_STATES = frozenset(
    {
        "BULL_STRONG",
        "BULL_VOLATILE",
        "RANGE",
        "TRANSITION",
        "BEAR",
        "CHAOTIC",
    }
)
DEFAULT_ALLOWED_REGIMES = frozenset({"BULL_STRONG", "BULL_VOLATILE"})


@dataclass(frozen=True)
class MomentumRegimeInput:
    momentum: MomentumRank
    regime: RegimeAssessment


@dataclass(frozen=True)
class MomentumRegimeStrategy:
    allowed_regimes: frozenset[str] = field(
        default_factory=lambda: DEFAULT_ALLOWED_REGIMES
    )
    name: str = "momentum_regime"

    def __post_init__(self) -> None:
        allowed = frozenset(self.allowed_regimes)
        unknown = allowed - REGIME_STATES
        if unknown:
            raise ValueError(
                f"Unknown regime state(s): {', '.join(sorted(unknown))}."
            )
        object.__setattr__(self, "allowed_regimes", allowed)

    def evaluate(self, inputs: MomentumRegimeInput) -> TargetPosition:
        if not isinstance(inputs, MomentumRegimeInput):
            raise TypeError("MomentumRegimeStrategy requires MomentumRegimeInput.")

        momentum = inputs.momentum
        regime = inputs.regime
        if momentum.ticker != regime.ticker:
            raise ValueError("Momentum and regime tickers must match.")
        if regime.regime not in REGIME_STATES:
            raise ValueError(f"Unknown regime state: {regime.regime}.")

        eligible_regime = regime.regime in self.allowed_regimes
        is_long = momentum.absolute_momentum and eligible_regime
        if not momentum.absolute_momentum:
            reason = "FLAT: absolute momentum is not positive"
        elif not eligible_regime:
            reason = f"FLAT: regime {regime.regime} is not allowed"
        else:
            reason = f"LONG: positive 12M momentum in {regime.regime}"

        return TargetPosition(
            symbol=momentum.ticker,
            timestamp=regime.timestamp,
            weight=1.0 if is_long else 0.0,
            reason=reason,
        )
