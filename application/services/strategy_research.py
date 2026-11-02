"""Orchestration for multi-asset strategy research using existing engines."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
import csv
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any
from uuid import uuid4

from backtest.engine import run_backtest
from backtest.types import BacktestConfig, BacktestResult, EquityPoint, Trade
from config.momentum import MomentumWeights
from config.regime import RegimeThresholds
from data.engine import run_market_data_engine
from data.market_data import (
    MarketData,
    MarketDataDownloadError,
    MarketDataProvider,
    MarketDataValidationError,
    normalize_ticker,
)
from evaluation.benchmark import buy_and_hold_benchmark
from evaluation.compare import PerformanceComparison, compare_performance
from evaluation.types import PerformanceMetrics
from experiments.registry import ExperimentRegistry
from experiments.storage import _stage_experiment
from factors.momentum import MomentumRank, rank_momentum
from features.engine import FeatureSeries, calculate_features
from portfolio.allocation import EqualWeightAllocator
from portfolio.constraints import PortfolioConstraints
from reporting.csv_report import write_csv_report
from reporting.html_report import write_html_report
from reporting.json_report import write_json_report
from reporting.research_report import ResearchReport, build_research_report
from risk.engine import evaluate_risk
from risk.types import RiskLimits
from regime.engine import RegimeAssessment, detect_regime
from signals.trend import MovingAverageCrossSignal
from strategies.momentum_regime import (
    MomentumRegimeInput,
    MomentumRegimeStrategy,
)
from strategies.moving_average import MovingAverageStrategy
from strategies.registry import StrategyRegistry, StrategyRegistryError
from strategies.types import TargetPosition
from universe.filters import UniverseFilters
from universe.service import select_universe
from universe.static import StaticUniverseProvider
from universe.types import UniverseAssetData


class StrategyResearchError(Exception):
    """Expected failure while running the strategy-research pipeline."""


@dataclass(frozen=True)
class StrategyResearchResult:
    report: ResearchReport
    benchmark: BacktestResult
    comparison: PerformanceComparison
    metrics: PerformanceMetrics
    experiment: Mapping[str, Any]
    output_files: tuple[Path, ...]


class _FetchedUniverseDataProvider:
    def __init__(self, data: Mapping[str, MarketData]) -> None:
        self._data = data

    def fetch(self, symbol: str, as_of: datetime) -> UniverseAssetData | None:
        market_data = self._data.get(symbol)
        if market_data is None:
            return None
        eligible = tuple(bar for bar in market_data.bars if bar.timestamp <= as_of)
        if not eligible:
            return None
        return UniverseAssetData(
            as_of=as_of,
            current_price=eligible[-1].close,
            history_count=len(eligible),
        )


def run_strategy_research(
    symbols: Sequence[str],
    provider: MarketDataProvider,
    *,
    data_directory: str | Path,
    output_directory: str | Path,
    strategy_name: str = "moving_average",
    strategy_parameters: Mapping[str, Any] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    initial_cash: float = 100_000.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> StrategyResearchResult:
    """Run the deterministic research pipeline and persist reports/tracking."""
    if start_date is not None and end_date is not None and start_date > end_date:
        raise StrategyResearchError("start_date cannot be after end_date.")
    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        raise StrategyResearchError("At least one symbol is required.")

    parameters = dict(strategy_parameters or {})
    strategy, signal_generator, parameters = _build_strategy(
        strategy_name, parameters
    )
    settings = BacktestConfig(
        initial_cash=initial_cash,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    universe = StaticUniverseProvider(normalized_symbols)
    fetched: dict[str, MarketData] = {}
    feature_history: dict[str, MarketData] = {}
    for symbol in universe.get_symbols():
        try:
            loaded = run_market_data_engine(symbol, provider, Path(data_directory))
        except MarketDataDownloadError as exc:
            raise MarketDataDownloadError(
                f"Unable to load validated market data for {symbol}: {exc}"
            ) from exc
        except MarketDataValidationError:
            raise
        except OSError as exc:
            raise StrategyResearchError(
                f"Unable to access market-data storage for {symbol}: {exc}"
            ) from exc
        feature_history[symbol] = loaded.market_data
        filtered = _filter_dates(loaded.market_data, start_date, end_date)
        if not filtered.bars:
            raise StrategyResearchError(
                f"{symbol}: no market data in the requested date range."
            )
        fetched[symbol] = filtered

    as_of = min(data.bars[-1].timestamp for data in fetched.values())
    selection = select_universe(
        universe,
        _FetchedUniverseDataProvider(fetched),
        as_of,
        UniverseFilters(minimum_history=1),
    )
    if selection.rejected_symbols:
        reasons = ", ".join(
            f"{item.symbol}: {item.reason}" for item in selection.rejected_symbols
        )
        raise StrategyResearchError(f"Universe selection rejected assets: {reasons}.")
    selected_symbols = selection.accepted_symbols
    common_timestamps = set(bar.timestamp for bar in fetched[selected_symbols[0]].bars)
    for symbol in selected_symbols[1:]:
        common_timestamps.intersection_update(
            bar.timestamp for bar in fetched[symbol].bars
        )
    timestamps = tuple(sorted(common_timestamps))
    if not timestamps:
        raise StrategyResearchError("Selected assets have no common market timestamps.")

    aligned_data = {
        symbol: MarketData(
            ticker=symbol,
            bars=tuple(
                bar for bar in fetched[symbol].bars if bar.timestamp in common_timestamps
            ),
        )
        for symbol in selected_symbols
    }
    feature_series = {
        symbol: calculate_features(feature_history[symbol])
        for symbol in selected_symbols
    }
    target_positions = _generate_positions(
        selected_symbols,
        feature_series,
        timestamps,
        strategy_name,
        strategy,
        signal_generator,
    )

    sleeve_cash = settings.initial_cash / len(selected_symbols)
    sleeve_config = BacktestConfig(
        initial_cash=sleeve_cash,
        commission_bps=settings.commission_bps,
        slippage_bps=settings.slippage_bps,
    )
    strategy_results: list[BacktestResult] = []
    benchmark_results: list[BacktestResult] = []
    for symbol in selected_symbols:
        sleeve_positions = tuple(
            TargetPosition(
                symbol=position.symbol,
                timestamp=position.timestamp,
                weight=position.weight * len(selected_symbols),
                reason=position.reason,
            )
            for position in target_positions[symbol]
        )
        strategy_results.append(
            run_backtest(
                aligned_data[symbol],
                sleeve_positions,
                strategy_name,
                sleeve_config,
            )
        )
        benchmark_results.append(
            buy_and_hold_benchmark(aligned_data[symbol], sleeve_config)
        )

    combined_result = _combine_results(strategy_name, strategy_results)
    combined_benchmark = _combine_results("equal_weight_buy_and_hold", benchmark_results)
    comparison = compare_performance(combined_result, combined_benchmark)
    metrics = comparison.strategy

    run_token = uuid4().hex
    output_root = Path(output_directory)
    base = output_root / f"{strategy_name}-{run_token}"
    output_files = (
        base.with_suffix(".json"),
        base.with_suffix(".csv"),
        base.with_suffix(".html"),
    )
    warnings = (
        "Multi-asset results aggregate equal-capital single-asset backtests "
        "on common timestamps.",
        "Risk drawdown checks use each asset's rolling 52-week close drawdown, "
        "not a portfolio-level circuit breaker.",
    )
    report = build_research_report(
        combined_result,
        metrics,
        comparison,
        configuration={
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "initial_cash": settings.initial_cash,
            "commission_bps": settings.commission_bps,
            "slippage_bps": settings.slippage_bps,
            "portfolio_allocator": "equal_weight",
            "risk_limits": asdict(RiskLimits()),
        },
        strategy_parameters=parameters,
        symbols=selected_symbols,
        warnings=warnings,
        output_files=tuple(str(path) for path in output_files),
    )
    registry = ExperimentRegistry(
        output_root / "experiments",
        repository_root=Path(__file__).resolve().parents[2],
    )
    experiment_record = registry.prepare(
        strategy_name=strategy_name,
        strategy_parameters=parameters,
        data=aligned_data,
        symbols=selected_symbols,
        start_date=combined_result.equity_curve[0].timestamp,
        end_date=combined_result.equity_curve[-1].timestamp,
        metrics=asdict(metrics),
        output_files=tuple(str(path) for path in output_files),
        warnings=warnings,
    )
    staged_files: list[tuple[Path, Path]] = []
    try:
        writers = (
            (write_json_report, output_files[0]),
            (write_csv_report, output_files[1]),
            (write_html_report, output_files[2]),
        )
        for writer, destination in writers:
            staged_files.append(_stage_report(report, destination, writer))
        staged_files.append(_stage_experiment(experiment_record, registry.storage_directory))
        _publish_staged_files(staged_files)
    except Exception as exc:
        for cleanup_error in _cleanup_staged_files(staged_files):
            exc.add_note(f"Staged artifact cleanup failed: {cleanup_error}")
        raise

    return StrategyResearchResult(
        report=report,
        benchmark=combined_benchmark,
        comparison=comparison,
        metrics=metrics,
        experiment=asdict(experiment_record),
        output_files=output_files,
    )


def _stage_report(
    report: ResearchReport,
    destination: Path,
    writer: Callable[[ResearchReport, str | Path], Path],
) -> tuple[Path, Path]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-",
        suffix=f".tmp{destination.suffix}",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        writer(report, temporary_path)
        _validate_staged_report(temporary_path, destination.suffix)
    except Exception as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError as cleanup_error:
            exc.add_note(f"Staged report cleanup failed: {cleanup_error}")
        raise
    return temporary_path, destination


def _validate_staged_report(path: Path, suffix: str) -> None:
    if suffix == ".json":
        with path.open(encoding="utf-8") as file:
            if not isinstance(json.load(file), dict):
                raise ValueError("Staged JSON report must contain an object.")
    elif suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as file:
            rows = csv.reader(file)
            header = next(rows, None)
            if header != [
                "section",
                "timestamp",
                "symbol",
                "field",
                "value",
                "details",
            ]:
                raise ValueError("Staged CSV report has an invalid header.")
            if next(rows, None) is None:
                raise ValueError("Staged CSV report must contain a summary row.")
    elif suffix == ".html":
        content = path.read_text(encoding="utf-8")
        if (
            not content.lstrip().lower().startswith("<!doctype html>")
            or not content.rstrip().lower().endswith("</html>")
        ):
            raise ValueError("Staged HTML report is incomplete.")
    else:
        raise ValueError(f"Unsupported staged report format: {suffix}.")


def _publish_staged_files(staged_files: Sequence[tuple[Path, Path]]) -> None:
    published: list[Path] = []
    try:
        for temporary_path, destination in staged_files:
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(f"Refusing to overwrite {destination}.")
            os.link(temporary_path, destination)
            published.append(destination)
            temporary_path.unlink()
    except Exception as exc:
        cleanup_errors = _cleanup_staged_files(staged_files, published)
        for cleanup_error in cleanup_errors:
            exc.add_note(f"Staged artifact cleanup failed: {cleanup_error}")
        raise


def _cleanup_staged_files(
    staged_files: Sequence[tuple[Path, Path]],
    published: Sequence[Path] = (),
) -> tuple[OSError, ...]:
    errors: list[OSError] = []
    published_set = set(published)
    for temporary_path, destination in reversed(staged_files):
        if destination in published_set:
            try:
                destination.unlink(missing_ok=True)
            except OSError as exc:
                errors.append(exc)
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(exc)
    return tuple(errors)


def _normalize_symbols(symbols: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized_symbol = normalize_ticker(symbol)
        if normalized_symbol in seen:
            raise StrategyResearchError(f"Duplicate symbol: {normalized_symbol}.")
        seen.add(normalized_symbol)
        normalized.append(normalized_symbol)
    return tuple(normalized)


def _build_strategy(
    strategy_name: str, parameters: Mapping[str, Any]
) -> tuple[
    MovingAverageStrategy | MomentumRegimeStrategy,
    MovingAverageCrossSignal | None,
    dict[str, Any],
]:
    registry = StrategyRegistry()
    try:
        if strategy_name == "moving_average":
            allowed = {"fast_window", "slow_window"}
            unknown = set(parameters) - allowed
            if unknown:
                raise StrategyResearchError(
                    f"Unknown moving_average parameter(s): {', '.join(sorted(unknown))}."
                )
            generator = MovingAverageCrossSignal(
                fast_window=parameters.get("fast_window", 20),
                slow_window=parameters.get("slow_window", 50),
            )
            strategy = MovingAverageStrategy()
            registry.register(strategy)
            effective_parameters = {
                "fast_window": generator.fast_window,
                "slow_window": generator.slow_window,
            }
            return strategy, generator, effective_parameters
        if strategy_name == "momentum_regime":
            allowed = {"allowed_regimes"}
            unknown = set(parameters) - allowed
            if unknown:
                raise StrategyResearchError(
                    "Unknown momentum_regime parameter(s): "
                    f"{', '.join(sorted(unknown))}."
                )
            regimes = parameters.get(
                "allowed_regimes", ("BULL_STRONG", "BULL_VOLATILE")
            )
            if isinstance(regimes, str):
                regimes = tuple(item.strip() for item in regimes.split(",") if item.strip())
            strategy = MomentumRegimeStrategy(allowed_regimes=frozenset(regimes))
            registry.register(strategy)
            return (
                strategy,
                None,
                {"allowed_regimes": tuple(sorted(strategy.allowed_regimes))},
            )
    except StrategyRegistryError as exc:
        raise StrategyResearchError(str(exc)) from exc
    except (TypeError, ValueError) as exc:
        if isinstance(exc, StrategyResearchError):
            raise
        raise StrategyResearchError(f"Invalid parameters for {strategy_name}: {exc}") from exc
    raise StrategyResearchError(
        f"Unknown strategy {strategy_name!r}; choose moving_average or momentum_regime."
    )


def _filter_dates(
    market_data: MarketData,
    start_date: date | None,
    end_date: date | None,
) -> MarketData:
    start = (
        datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        if start_date is not None
        else None
    )
    end_exclusive = (
        datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        if end_date is not None
        else None
    )
    bars = tuple(
        bar
        for bar in market_data.bars
        if (start is None or bar.timestamp >= start)
        and (end_exclusive is None or bar.timestamp < end_exclusive)
    )
    return MarketData(ticker=market_data.ticker, bars=bars)


def _generate_positions(
    symbols: tuple[str, ...],
    feature_series: Mapping[str, FeatureSeries],
    timestamps: tuple[datetime, ...],
    strategy_name: str,
    strategy: MovingAverageStrategy | MomentumRegimeStrategy,
    signal_generator: MovingAverageCrossSignal | None,
) -> dict[str, tuple[TargetPosition, ...]]:
    thresholds = RegimeThresholds.from_env()
    momentum_weights = MomentumWeights.from_env()
    allocator = EqualWeightAllocator()
    portfolio = allocator.allocate(
        symbols,
        PortfolioConstraints(max_weight=1.0 / len(symbols)),
    )
    if not portfolio.success:
        raise StrategyResearchError(portfolio.message)

    risk_limits = RiskLimits()
    generated: dict[str, list[TargetPosition]] = {symbol: [] for symbol in symbols}
    for timestamp in timestamps:
        prefixes = {
            symbol: FeatureSeries(
                ticker=symbol,
                rows=tuple(
                    row for row in series.rows if row.timestamp <= timestamp
                ),
            )
            for symbol, series in feature_series.items()
        }
        ranks: dict[str, MomentumRank] = {}
        if all(
            all(
                prefixes[symbol].rows[-1].values.get(name) is not None
                for name in (
                    "return_1m",
                    "return_3m",
                    "return_6m",
                    "return_12m",
                )
            )
            for symbol in symbols
        ):
            ranks = {
                item.ticker: item
                for item in rank_momentum(prefixes, momentum_weights)
            }
        regimes: dict[str, RegimeAssessment] = {
            symbol: detect_regime(prefixes[symbol], thresholds)
            for symbol in symbols
        }
        current_exposure = 0.0
        for symbol in symbols:
            if strategy_name == "moving_average":
                if signal_generator is None:
                    raise StrategyResearchError("Moving-average signal is not configured.")
                signal = signal_generator.generate(prefixes[symbol])
                proposed = strategy.evaluate(signal)
            else:
                rank = ranks.get(symbol)
                if rank is None:
                    proposed = TargetPosition(
                        symbol=symbol,
                        timestamp=timestamp,
                        weight=0.0,
                        reason="FLAT: insufficient momentum history",
                    )
                else:
                    proposed = strategy.evaluate(
                        MomentumRegimeInput(momentum=rank, regime=regimes[symbol])
                    )

            latest = prefixes[symbol].rows[-1].values
            volatility = latest.get("realized_volatility_20")
            drawdown_value = latest.get("rolling_drawdown_52w")
            drawdown = (
                max(0.0, -drawdown_value)
                if drawdown_value is not None
                else None
            )
            allocation_weight = portfolio.weights[symbol] if proposed.weight > 0 else 0.0
            decision = evaluate_risk(
                allocation_weight,
                current_exposure,
                risk_limits,
                realized_volatility=volatility,
                current_drawdown=drawdown,
            )
            current_exposure += decision.approved_weight
            reason = proposed.reason
            if decision.reasons != ("APPROVED_WITHIN_LIMITS",):
                reason = f"{reason}; risk: {', '.join(decision.reasons)}"
            generated[symbol].append(
                TargetPosition(
                    symbol=symbol,
                    timestamp=timestamp,
                    weight=decision.approved_weight
                    * len(symbols),
                    reason=reason,
                )
            )
    return {symbol: tuple(items) for symbol, items in generated.items()}


def _combine_results(
    strategy_name: str, results: Sequence[BacktestResult]
) -> BacktestResult:
    if not results:
        raise StrategyResearchError("Cannot combine an empty set of backtests.")
    timestamps = tuple(point.timestamp for point in results[0].equity_curve)
    if any(
        tuple(point.timestamp for point in result.equity_curve) != timestamps
        for result in results[1:]
    ):
        raise StrategyResearchError("Backtest results do not share timestamps.")
    curve = tuple(
        EquityPoint(
            timestamp=timestamp,
            equity=math.fsum(result.equity_curve[index].equity for result in results),
            cash=math.fsum(result.equity_curve[index].cash for result in results),
            market_value=math.fsum(
                result.equity_curve[index].market_value for result in results
            ),
        )
        for index, timestamp in enumerate(timestamps)
    )
    trades = tuple(
        sorted(
            (trade for result in results for trade in result.trades),
            key=lambda trade: (trade.timestamp, trade.symbol, trade.side),
        )
    )
    return BacktestResult(
        strategy_name=strategy_name,
        equity_curve=curve,
        trades=trades,
        initial_cash=math.fsum(result.initial_cash for result in results),
        final_equity=math.fsum(result.final_equity for result in results),
    )
