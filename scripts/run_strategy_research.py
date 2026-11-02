"""CLI for the deterministic, multi-asset strategy research pipeline."""

import argparse
from collections.abc import Sequence
from datetime import date
import math
import sys
import traceback
from typing import Any

from application.services.strategy_research import (
    StrategyResearchError,
    run_strategy_research,
)
from data.market_data import MarketDataError, MarketDataProvider


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Fecha inválida {value!r}; usa el formato YYYY-MM-DD."
        ) from exc


def _parameter_value(value: str) -> Any:
    normalized = value.strip()
    if normalized.casefold() in {"true", "false"}:
        return normalized.casefold() == "true"
    try:
        if "." not in normalized and "e" not in normalized.casefold():
            return int(normalized)
        return float(normalized)
    except ValueError:
        return normalized


def _strategy_parameters(
    values: Sequence[str], parser: argparse.ArgumentParser
) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            parser.error(f"Parámetro de estrategia inválido: {item!r}; usa clave=valor.")
        name, raw_value = item.split("=", 1)
        name = name.strip()
        if not name:
            parser.error(f"Parámetro de estrategia inválido: {item!r}.")
        if name in parameters:
            parser.error(f"Parámetro de estrategia duplicado: {name}.")
        parameters[name] = _parameter_value(raw_value)
    return parameters


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Ejecuta investigación cuantitativa multi-activo sin LLM "
            "ni operaciones reales."
        )
    )
    parser.add_argument(
        "symbols",
        nargs="+",
        help="Uno o más símbolos, por ejemplo SPY QQQ.",
    )
    parser.add_argument("--start-date", type=_iso_date, help="Fecha inicial YYYY-MM-DD.")
    parser.add_argument("--end-date", type=_iso_date, help="Fecha final YYYY-MM-DD.")
    parser.add_argument(
        "--strategy",
        choices=("moving_average", "momentum_regime"),
        default="moving_average",
    )
    parser.add_argument(
        "--strategy-param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Parámetro de estrategia; puede repetirse.",
    )
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--commission-bps", type=float, default=0.0)
    parser.add_argument("--slippage-bps", type=float, default=0.0)
    parser.add_argument(
        "--output-dir",
        default="reports/generated",
        help="Directorio de reportes y experimentos.",
    )
    parser.add_argument("--debug", action="store_true", help="Muestra traceback.")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    provider: MarketDataProvider | None = None,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if (
        args.start_date is not None
        and args.end_date is not None
        and args.start_date > args.end_date
    ):
        parser.error("--start-date no puede ser posterior a --end-date.")
    if any(
        not math.isfinite(value)
        for value in (args.initial_cash, args.commission_bps, args.slippage_bps)
    ):
        parser.error("Capital, comisión y slippage deben ser valores finitos.")
    if args.initial_cash <= 0:
        parser.error("--initial-cash debe ser positivo.")
    if args.commission_bps < 0:
        parser.error("--commission-bps no puede ser negativo.")
    if not 0 <= args.slippage_bps < 10_000:
        parser.error("--slippage-bps debe estar en el intervalo [0, 10000).")

    parameters = _strategy_parameters(args.strategy_param, parser)
    try:
        if provider is None:
            from config.settings import Settings
            from data.providers.yahoo_finance import YahooFinanceProvider

            settings = Settings.from_env()
            market_data_provider: MarketDataProvider = YahooFinanceProvider()
            data_directory = settings.data_dir
        else:
            from config.settings import Settings

            settings = Settings.from_env()
            market_data_provider = provider
            data_directory = settings.data_dir

        result = run_strategy_research(
            args.symbols,
            market_data_provider,
            data_directory=data_directory,
            output_directory=args.output_dir,
            strategy_name=args.strategy,
            strategy_parameters=parameters,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_cash=args.initial_cash,
            commission_bps=args.commission_bps,
            slippage_bps=args.slippage_bps,
        )
    except (
        MarketDataError,
        StrategyResearchError,
        OSError,
        ValueError,
    ) as exc:
        return _report_error(str(exc), args.debug)
    except Exception as exc:
        return _report_error(
            f"Error inesperado ({type(exc).__name__}): {exc}",
            args.debug,
        )

    print(f"Strategy: {result.report.strategy_name}")
    print(f"Symbols: {', '.join(result.report.symbols)}")
    print(f"Total return: {result.metrics.total_return}")
    print(f"Sharpe: {result.metrics.sharpe}")
    print(f"Benchmark return difference: {result.comparison.total_return_difference}")
    print(f"Experiment: {result.experiment['experiment_id']}")
    print("Reports:")
    for path in result.output_files:
        print(f"  {path}")
    return 0


def _report_error(message: str, debug: bool) -> int:
    print(f"Error: {message}", file=sys.stderr)
    if debug:
        traceback.print_exc()
    else:
        print("Usa --debug para ver el diagnóstico completo.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
