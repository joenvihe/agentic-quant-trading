"""Application tool for point-in-time single-symbol research."""

from dataclasses import dataclass

from application.services.research import (
    ResearchServiceError,
    generate_research_report,
)
from config.settings import Settings
from data.market_data import MarketDataError, MarketDataProvider
from factors.momentum import MomentumRankingError
from features.engine import FeatureError
from regime.engine import RegimeError
from application.tools.types import (
    ToolResponse,
    error_response,
    resolve_trace_id,
    success_response,
)


@dataclass(frozen=True)
class ResearchRequest:
    symbol: str
    trace_id: str | None = None


def research_symbol(
    request: ResearchRequest,
    provider: MarketDataProvider,
    settings: Settings,
) -> ToolResponse:
    trace_id, trace_error = resolve_trace_id(request.trace_id)
    if trace_error:
        return error_response(trace_id, trace_error)
    if not isinstance(request.symbol, str) or not request.symbol.strip():
        return error_response(trace_id, "symbol must be a non-empty string.")
    if not isinstance(settings, Settings):
        return error_response(trace_id, "settings must be a Settings value.")
    if not callable(getattr(provider, "fetch", None)):
        return error_response(trace_id, "provider must implement fetch(ticker).")
    try:
        report = generate_research_report(request.symbol, provider, settings)
    except (
        MarketDataError,
        FeatureError,
        MomentumRankingError,
        RegimeError,
        ResearchServiceError,
        OSError,
        ValueError,
    ) as exc:
        return error_response(trace_id, str(exc))
    return success_response(
        trace_id,
        report,
        warnings=report.warnings,
    )
