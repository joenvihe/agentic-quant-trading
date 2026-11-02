from pathlib import Path
import subprocess
import sys


def test_project_imports_do_not_download_or_configure_logging() -> None:
    import_script = """
import importlib
import logging
import socket
import yfinance

def forbidden(*args, **kwargs):
    raise AssertionError("Unexpected import-time side effect")

logging.basicConfig = forbidden
yfinance.Ticker = forbidden
yfinance.download = forbidden
socket.socket.connect = forbidden

modules = (
    "config.logging_config",
    "config.momentum",
    "config.regime",
    "config.settings",
    "data.engine",
    "data.market_data",
    "data.providers.yahoo_finance",
    "data.storage",
    "features.engine",
    "factors.momentum",
    "regime.engine",
    "regime.comparison",
    "regime.hmm",
    "backtest",
    "backtest.costs",
    "backtest.engine",
    "backtest.exceptions",
    "backtest.types",
    "evaluation",
    "evaluation.benchmark",
    "evaluation.compare",
    "evaluation.metrics",
    "evaluation.robustness",
    "evaluation.splits",
    "evaluation.types",
    "evaluation.walk_forward",
    "signals",
    "signals.base",
    "signals.trend",
    "signals.types",
    "strategies",
    "strategies.base",
    "strategies.momentum_regime",
    "strategies.moving_average",
    "strategies.registry",
    "strategies.types",
    "risk",
    "risk.drawdown",
    "risk.engine",
    "risk.limits",
    "risk.sizing",
    "risk.types",
    "risk.volatility",
    "portfolio",
    "portfolio.allocation",
    "portfolio.constraints",
    "portfolio.covariance",
    "portfolio.optimizer",
    "portfolio.types",
    "fundamental",
    "fundamental.metrics",
    "fundamental.magic_formula",
    "fundamental.provider",
    "fundamental.ranking",
    "fundamental.types",
    "universe",
    "universe.filters",
    "universe.provider",
    "universe.service",
    "universe.static",
    "universe.types",
    "reporting",
    "reporting.charts",
    "reporting.csv_report",
    "reporting.html_report",
    "reporting.json_report",
    "reporting.research_report",
    "reporting.tables",
    "experiments",
    "experiments.hashing",
    "experiments.registry",
    "experiments.storage",
    "experiments.types",
    "sentiment",
    "sentiment.aggregate",
    "sentiment.alignment",
    "sentiment.provider",
    "sentiment.types",
    "sentiment.vader",
    "models",
    "models.baseline",
    "models.datasets",
    "models.evaluation",
    "models.preprocessing",
    "models.targets",
    "models.types",
    "models.xgboost_model",
    "application.services.research",
    "scripts.analyze_features",
    "scripts.detect_regime",
    "scripts.download_market_data",
    "scripts.rank_momentum",
    "scripts.research_asset",
)
for module in modules:
    importlib.import_module(module)
"""
    project_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "-c", import_script],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
