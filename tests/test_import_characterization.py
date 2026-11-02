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
