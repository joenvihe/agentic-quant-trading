"""Orquestación del vertical slice de investigación cuantitativa."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import math

from config.momentum import MomentumWeights
from config.regime import RegimeThresholds
from config.settings import Settings
from data.engine import run_market_data_engine
from data.market_data import (
    MarketDataDownloadError,
    MarketDataError,
    MarketDataProvider,
    MarketDataValidationError,
    normalize_ticker,
)
from factors.momentum import MomentumRankingError, rank_momentum
from features.engine import FeatureError, FeatureSeries, calculate_features
from regime.engine import RegimeAssessment, RegimeError, detect_regime


_LOGGER = logging.getLogger(__name__)
_RETURN_FEATURES = {
    "return_1m": "momentum_1m",
    "return_3m": "momentum_3m",
    "return_6m": "momentum_6m",
    "return_12m": "momentum_12m",
}
_REPORT_FEATURES = (
    "sma_20",
    "sma_50",
    "sma_100",
    "sma_200",
    "ema_20",
    "ema_50",
    "rsi_2",
    "rsi_14",
    "atr_14",
    "realized_volatility_20",
    "bollinger_band_width_20",
    "average_volume_20",
    "relative_volume_20",
    "distance_from_52w_high",
    "rolling_drawdown_52w",
    *_RETURN_FEATURES,
)
_FEATURE_LABELS = {
    "sma_20": "SMA20",
    "sma_50": "SMA50",
    "sma_100": "SMA100",
    "sma_200": "SMA200",
    "ema_20": "EMA20",
    "ema_50": "EMA50",
    "rsi_2": "RSI2",
    "rsi_14": "RSI14",
    "atr_14": "ATR14",
    "realized_volatility_20": "realized_volatility_20",
    "bollinger_band_width_20": "bollinger_band_width_20",
    "average_volume_20": "average_volume_20",
    "relative_volume_20": "relative_volume_20",
    "distance_from_52w_high": "distance_from_52w_high",
    "rolling_drawdown_52w": "current_drawdown",
    **{key: value for key, value in _RETURN_FEATURES.items()},
}


class ResearchServiceError(Exception):
    """Error esperado al generar un informe de investigación."""


class _LoggedProvider:
    """Loguea excepciones del adaptador antes de traducirlas a error de descarga."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    def fetch(self, ticker: str) -> Iterable[Mapping[str, object]]:
        try:
            rows = list(self._provider.fetch(ticker))
        except MarketDataError:
            raise
        except Exception as exc:
            _LOGGER.error("El proveedor de mercado falló para %s: %s", ticker, exc)
            raise MarketDataDownloadError(
                f"No se pudieron descargar datos de mercado para {ticker}: {exc}"
            ) from exc
        for row_number, row in enumerate(rows, start=1):
            if not isinstance(row, Mapping):
                raise MarketDataValidationError(
                    f"Fila {row_number}: el proveedor no devolvió un objeto de "
                    "campos OHLCV."
                )
        return rows


@dataclass(frozen=True)
class ResearchReport:
    """Datos necesarios para renderizar el informe sin cálculos financieros."""

    ticker: str
    records: int
    start: datetime
    end: datetime
    data_quality_status: str
    warnings: tuple[str, ...]
    close: float
    features: Mapping[str, float | None]
    momentum_returns: Mapping[str, float | None]
    composite_momentum_score: float | None
    percentile_rank: float | None
    regime: RegimeAssessment


def _validate_feature_series(
    features: FeatureSeries,
) -> tuple[dict[str, float | None], tuple[str, ...]]:
    if not features.rows:
        raise FeatureError(f"{features.ticker}: el Feature Engine no produjo filas.")
    latest = features.rows[-1].values
    metrics: dict[str, float | None] = {}
    missing: list[str] = []
    for name in _REPORT_FEATURES:
        value = latest.get(name)
        if value is not None and not math.isfinite(value):
            raise FeatureError(f"{features.ticker}: feature {name} no es finita.")
        metrics[name] = value
        if value is None:
            missing.append(_FEATURE_LABELS[name])
    return metrics, tuple(missing)


def generate_research_report(
    ticker: str,
    provider: MarketDataProvider,
    settings: Settings | None = None,
    momentum_weights: MomentumWeights | None = None,
    regime_thresholds: RegimeThresholds | None = None,
) -> ResearchReport:
    """Ejecuta Data -> Features -> Momentum -> Regime y arma el informe."""
    normalized_ticker = normalize_ticker(ticker)
    configuration = settings or Settings.from_env()

    try:
        market_data = run_market_data_engine(
            normalized_ticker,
            _LoggedProvider(provider),
            configuration.data_dir,
        ).market_data
        features = calculate_features(market_data)
        feature_metrics, missing_metrics = _validate_feature_series(features)

        momentum_returns: dict[str, float | None] = {
            horizon: None for horizon in ("1m", "3m", "6m", "12m")
        }
        momentum_inputs = {name: feature_metrics[name] for name in _RETURN_FEATURES}
        if all(value is not None for value in momentum_inputs.values()):
            ranking = rank_momentum(
                {normalized_ticker: features},
                (
                    momentum_weights
                    if momentum_weights is not None
                    else MomentumWeights.from_env()
                ),
            )
            latest_momentum = ranking[0]
            momentum_returns = {
                "1m": latest_momentum.momentum_1m,
                "3m": latest_momentum.momentum_3m,
                "6m": latest_momentum.momentum_6m,
                "12m": latest_momentum.momentum_12m,
            }

        regime = detect_regime(
            features,
            (
                regime_thresholds
                if regime_thresholds is not None
                else RegimeThresholds.from_env()
            ),
        )
    except (MarketDataError, FeatureError, MomentumRankingError, RegimeError):
        raise
    except OSError as exc:
        _LOGGER.error(
            "No se pudieron leer o guardar datos para %s: %s",
            normalized_ticker,
            exc,
        )
        raise ResearchServiceError(
            f"No se pudo acceder al almacenamiento de datos para "
            f"{normalized_ticker}: {exc}"
        ) from exc

    warnings = (
        (f"Historial insuficiente para {', '.join(missing_metrics)}.",)
        if missing_metrics
        else ()
    )

    return ResearchReport(
        ticker=market_data.ticker,
        records=len(market_data.bars),
        start=market_data.bars[0].timestamp,
        end=market_data.bars[-1].timestamp,
        data_quality_status="WARNING" if warnings else "PASS",
        warnings=warnings,
        close=market_data.bars[-1].close,
        features=feature_metrics,
        momentum_returns=momentum_returns,
        composite_momentum_score=None,
        percentile_rank=None,
        regime=regime,
    )


def _format_value(
    value: float | None,
    *,
    percentage: bool = False,
    decimals: int = 4,
) -> str:
    if value is None:
        return "N/A"
    if percentage:
        return f"{value:.2%}"
    return f"{value:,.{decimals}f}"


def _feature_value(report: ResearchReport, name: str) -> float | None:
    return report.features.get(name)


def render_research_report(report: ResearchReport) -> str:
    """Formatea el resultado; no calcula features, factores ni regímenes."""
    warnings = "\n".join(f"- {warning}" for warning in report.warnings) or "None"
    returns = {
        "1M": report.momentum_returns["1m"],
        "3M": report.momentum_returns["3m"],
        "6M": report.momentum_returns["6m"],
        "12M": report.momentum_returns["12m"],
    }
    regime_evidence = report.regime.evidence
    evidence_json = json.dumps(regime_evidence, indent=2, allow_nan=False)
    lines = [
        "=" * 50,
        "QUANT RESEARCH REPORT",
        "=" * 50,
        "",
        "ASSET",
        f"Ticker: {report.ticker}",
        "",
        "DATA QUALITY",
        f"Status: {report.data_quality_status}",
        f"Records: {report.records}",
        f"Start: {report.start.isoformat()}",
        f"End: {report.end.isoformat()}",
        f"Warnings:\n{warnings}",
        "",
        "TREND",
        f"Close: {_format_value(report.close)}",
        f"SMA20: {_format_value(_feature_value(report, 'sma_20'))}",
        f"SMA50: {_format_value(_feature_value(report, 'sma_50'))}",
        f"SMA100: {_format_value(_feature_value(report, 'sma_100'))}",
        f"SMA200: {_format_value(_feature_value(report, 'sma_200'))}",
        f"EMA20: {_format_value(_feature_value(report, 'ema_20'))}",
        f"EMA50: {_format_value(_feature_value(report, 'ema_50'))}",
        "",
        "MOMENTUM",
        *(
            f"{horizon}: {_format_value(value, percentage=True)}"
            for horizon, value in returns.items()
        ),
        f"RSI2: {_format_value(_feature_value(report, 'rsi_2'))}",
        f"RSI14: {_format_value(_feature_value(report, 'rsi_14'))}",
        "Composite Momentum Score: "
        + (
            "N/A (requiere universo comparativo)"
            if report.composite_momentum_score is None
            else _format_value(report.composite_momentum_score, decimals=2)
        ),
        "Percentile Rank: "
        + (
            "N/A (requiere universo comparativo)"
            if report.percentile_rank is None
            else _format_value(report.percentile_rank, decimals=2)
        ),
        "",
        "VOLATILITY",
        f"ATR14: {_format_value(_feature_value(report, 'atr_14'))}",
        "Realized Volatility: "
        + _format_value(
            _feature_value(report, "realized_volatility_20"), percentage=True
        ),
        "Bollinger Band Width: "
        + _format_value(
            _feature_value(report, "bollinger_band_width_20"), percentage=True
        ),
        "",
        "VOLUME",
        "Average Volume: "
        + _format_value(_feature_value(report, "average_volume_20"), decimals=2),
        "Relative Volume: "
        + _format_value(_feature_value(report, "relative_volume_20"), decimals=2),
        "",
        "MARKET STRUCTURE",
        "Distance from 52W High: "
        + _format_value(
            _feature_value(report, "distance_from_52w_high"), percentage=True
        ),
        "Current Drawdown: "
        + _format_value(
            _feature_value(report, "rolling_drawdown_52w"), percentage=True
        ),
        "",
        "MARKET REGIME",
        f"Regime: {report.regime.regime}",
        f"Direction: {regime_evidence['direction']['state']}",
        f"Strength: {regime_evidence['strength']['state']}",
        f"Volatility State: {regime_evidence['volatility']['state']}",
        "Evidence:",
        evidence_json,
        "Reason Codes: " + ", ".join(report.regime.reason_codes),
        "",
        "=" * 50,
    ]
    return "\n".join(lines)
