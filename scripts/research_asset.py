"""CLI para generar un informe cuantitativo de un activo."""

import argparse
from collections.abc import Sequence
import sys

from application.services.research import (
    ResearchServiceError,
    generate_research_report,
    render_research_report,
)
from config.logging_config import configure_logging
from config.settings import Settings
from data.market_data import (
    MarketDataDownloadError,
    MarketDataError,
    MarketDataValidationError,
)
from data.providers.yahoo_finance import YahooFinanceProvider
from factors.momentum import MomentumRankingError
from features.engine import FeatureError
from regime.engine import RegimeError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera un informe cuantitativo de investigación para un activo."
    )
    parser.add_argument("ticker", help="Símbolo del activo, por ejemplo SPY.")
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
        configure_logging(settings)
        report = generate_research_report(
            args.ticker,
            YahooFinanceProvider(),
            settings=settings,
        )
    except MarketDataValidationError as exc:
        print(
            f"QUANT RESEARCH REPORT\nTicker: {args.ticker}\n"
            f"DATA QUALITY\nStatus: FAIL\nWarnings: {exc}",
            file=sys.stderr,
        )
        return 1
    except (
        MarketDataDownloadError,
        MarketDataError,
        FeatureError,
        MomentumRankingError,
        RegimeError,
        ResearchServiceError,
        OSError,
        ValueError,
    ) as exc:
        print(
            f"QUANT RESEARCH REPORT\nTicker: {args.ticker}\n"
            f"DATA QUALITY\nStatus: FAIL\nWarnings: {exc}",
            file=sys.stderr,
        )
        return 1

    print(render_research_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
