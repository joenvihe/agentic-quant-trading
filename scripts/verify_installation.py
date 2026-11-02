"""Safe local readiness checks; does not download market data."""

import importlib
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import sys
import tempfile

from config.settings import Settings


REQUIRED_DISTRIBUTIONS = (
    "hmmlearn",
    "scipy",
    "vaderSentiment",
    "xgboost",
    "yfinance",
)
REQUIRED_IMPORTS = (
    "application.services.strategy_research",
    "backtest.engine",
    "data.engine",
    "evaluation.metrics",
    "experiments.registry",
    "features.engine",
    "reporting.html_report",
    "strategies.registry",
)


def main() -> int:
    ready = True
    python_ok = sys.version_info >= (3, 11)
    print(
        f"Python: {sys.version.split()[0]} "
        f"({'OK' if python_ok else 'requires Python 3.11+'})"
    )
    ready = ready and python_ok

    for distribution in REQUIRED_DISTRIBUTIONS:
        try:
            installed_version = version(distribution)
        except PackageNotFoundError:
            print(f"Dependency: {distribution} NOT INSTALLED")
            ready = False
        else:
            print(f"Dependency: {distribution} {installed_version}")

    for module_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            print(f"Import: {module_name} FAILED ({type(exc).__name__}: {exc})")
            ready = False
        else:
            print(f"Import: {module_name} OK")

    workspace = Settings.from_env().research_workspace
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        for name in ("reports", "experiments", "data"):
            (workspace / name).mkdir(parents=True, exist_ok=True)
        descriptor, probe_name = tempfile.mkstemp(
            prefix=".aqt-write-check-", dir=workspace
        )
        os.close(descriptor)
        Path(probe_name).unlink()
    except OSError as exc:
        print(f"Workspace: {workspace} NOT ACCESSIBLE ({type(exc).__name__}: {exc})")
        ready = False
    else:
        print(f"Workspace: {workspace.resolve()} OK")

    print("READY" if ready else "NOT READY")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
