from datetime import datetime, timezone

import pytest

from factors.momentum import MomentumRank
from regime.engine import RegimeAssessment
from signals.types import Signal, SignalDirection
from strategies import (
    MomentumRegimeInput,
    MomentumRegimeStrategy,
    MovingAverageStrategy,
    StrategyRegistry,
    StrategyRegistryError,
    TargetPosition,
)


NOW = datetime(2025, 1, 2, tzinfo=timezone.utc)


def signal(direction: SignalDirection) -> Signal:
    return Signal(
        "SPY",
        NOW,
        direction,
        1.0 if direction is SignalDirection.LONG else 0.0,
        "test",
    )


def momentum(*, absolute: bool = True, ticker: str = "SPY") -> MomentumRank:
    return MomentumRank(
        rank=1,
        ticker=ticker,
        momentum_1m=0.01,
        momentum_3m=0.03,
        momentum_6m=0.06,
        momentum_12m=0.12 if absolute else -0.12,
        absolute_momentum=absolute,
        relative_momentum={"1m": 75.0, "3m": 75.0, "6m": 75.0, "12m": 75.0},
        percentile_rank=75.0,
        composite_score=75.0,
    )


def regime(state: str, *, ticker: str = "SPY") -> RegimeAssessment:
    return RegimeAssessment(
        ticker=ticker,
        timestamp=NOW,
        regime=state,
        metrics={},
        evidence={},
        reason_codes=(),
    )


def test_moving_average_strategy_maps_long_signal_to_long_position() -> None:
    position = MovingAverageStrategy().evaluate(signal(SignalDirection.LONG))

    assert position == TargetPosition("SPY", NOW, 1.0, "LONG: test")


def test_moving_average_strategy_maps_flat_signal_to_flat_position() -> None:
    position = MovingAverageStrategy().evaluate(signal(SignalDirection.FLAT))

    assert position == TargetPosition("SPY", NOW, 0.0, "FLAT: test")


def test_target_position_validates_weight_range_and_timestamp() -> None:
    with pytest.raises(ValueError, match="weight"):
        TargetPosition("SPY", NOW, 1.1, "invalid")
    with pytest.raises(ValueError, match="timezone-aware"):
        TargetPosition("SPY", datetime(2025, 1, 2), 0.0, "invalid")


def test_registry_registers_and_retrieves_strategies_explicitly() -> None:
    registry = StrategyRegistry()
    strategy = MovingAverageStrategy()

    registry.register(strategy)

    assert registry.get("moving_average") is strategy
    assert registry.names == ("moving_average",)


def test_registry_rejects_duplicate_strategy_names() -> None:
    registry = StrategyRegistry()
    registry.register(MovingAverageStrategy())

    with pytest.raises(StrategyRegistryError, match="already registered"):
        registry.register(MovingAverageStrategy())


def test_registry_rejects_unknown_strategy_names() -> None:
    with pytest.raises(StrategyRegistryError, match="not registered"):
        StrategyRegistry().get("unknown")


def test_registry_rejects_objects_without_strategy_contract() -> None:
    with pytest.raises(StrategyRegistryError, match="evaluate method"):
        StrategyRegistry().register(object())  # type: ignore[arg-type]


def test_momentum_regime_strategy_allows_positive_momentum_in_configured_regime() -> None:
    strategy = MomentumRegimeStrategy()
    inputs = MomentumRegimeInput(momentum(), regime("BULL_STRONG"))

    position = strategy.evaluate(inputs)

    assert position.weight == 1.0
    assert position.reason == "LONG: positive 12M momentum in BULL_STRONG"


def test_momentum_regime_strategy_allows_bull_volatile_by_default() -> None:
    position = MomentumRegimeStrategy().evaluate(
        MomentumRegimeInput(momentum(), regime("BULL_VOLATILE"))
    )

    assert position.weight == 1.0


def test_momentum_regime_strategy_blocks_unconfigured_regime() -> None:
    position = MomentumRegimeStrategy().evaluate(
        MomentumRegimeInput(momentum(), regime("RANGE"))
    )

    assert position.weight == 0.0
    assert "not allowed" in position.reason


def test_momentum_regime_strategy_blocks_non_positive_absolute_momentum() -> None:
    position = MomentumRegimeStrategy().evaluate(
        MomentumRegimeInput(momentum(absolute=False), regime("BULL_VOLATILE"))
    )

    assert position.weight == 0.0
    assert "momentum is not positive" in position.reason


def test_momentum_regime_strategy_customizes_and_validates_regime_allowlist() -> None:
    strategy = MomentumRegimeStrategy(allowed_regimes=frozenset({"RANGE"}))

    position = strategy.evaluate(
        MomentumRegimeInput(momentum(), regime("RANGE"))
    )

    assert position.weight == 1.0
    with pytest.raises(ValueError, match="Unknown regime"):
        MomentumRegimeStrategy(allowed_regimes=frozenset({"BUY"}))


def test_momentum_regime_strategy_rejects_mismatched_tickers() -> None:
    with pytest.raises(ValueError, match="tickers must match"):
        MomentumRegimeStrategy().evaluate(
            MomentumRegimeInput(momentum(ticker="QQQ"), regime("BULL_STRONG"))
        )


def test_strategy_outputs_are_deterministic() -> None:
    strategy = MomentumRegimeStrategy()
    inputs = MomentumRegimeInput(momentum(), regime("BULL_VOLATILE"))

    assert strategy.evaluate(inputs) == strategy.evaluate(inputs)
