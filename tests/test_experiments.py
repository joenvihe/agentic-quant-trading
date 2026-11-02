from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from backtest.types import BacktestResult, EquityPoint
from experiments import (
    ExperimentRegistry,
    data_fingerprint,
    load_experiment,
    save_experiment,
)
from experiments.storage import ExperimentStorageError
from experiments.types import ExperimentRecord


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def sample_record(experiment_id: str = "run-001") -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        timestamp=START,
        strategy_name="trend",
        strategy_parameters={"fast": 20, "api_token": "do-not-persist"},
        data_fingerprint="abc123",
        symbols=("SPY",),
        start_date=START,
        end_date=START + timedelta(days=3),
        code_version="deadbeef",
        metrics={"sharpe": 1.2, "password": "also-secret"},
        output_files=("reports/generated/run.json",),
        warnings=("synthetic warning",),
    )


def test_data_fingerprint_is_stable_for_equivalent_inputs() -> None:
    first = {"bars": [{"close": 10.0, "timestamp": START}], "ticker": "SPY"}
    second = {"ticker": "SPY", "bars": [{"timestamp": START, "close": 10.0}]}

    assert data_fingerprint(first) == data_fingerprint(second)
    assert data_fingerprint(first) != data_fingerprint({"ticker": "SPY", "bars": []})


def test_experiment_storage_loads_json_and_redacts_secret_fields(tmp_path) -> None:
    path = save_experiment(sample_record(), tmp_path)
    loaded = load_experiment("run-001", tmp_path)

    assert path.exists()
    assert loaded["timestamp"] == START.isoformat()
    assert loaded["strategy_parameters"]["api_token"] == "[REDACTED]"
    assert loaded["metrics"]["password"] == "[REDACTED]"
    assert "do-not-persist" not in path.read_text(encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == loaded
    assert not list(tmp_path.glob("*.tmp"))


def test_experiment_storage_never_overwrites_existing_run(tmp_path) -> None:
    record = sample_record()
    path = save_experiment(record, tmp_path)
    before = path.read_bytes()

    with pytest.raises(ExperimentStorageError, match="already exists"):
        save_experiment(record, tmp_path)

    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_experiment_storage_failure_does_not_publish_partial_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import experiments.storage as storage_module

    def fail_link(source, destination):
        assert Path(source).read_text(encoding="utf-8").endswith("\n")
        raise OSError("synthetic atomic publish failure")

    monkeypatch.setattr(storage_module.os, "link", fail_link)
    with pytest.raises(ExperimentStorageError, match="atomically save"):
        save_experiment(sample_record(), tmp_path)

    assert not (tmp_path / "run-001.json").exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_experiment_registry_records_metadata_and_loads_it(tmp_path) -> None:
    registry = ExperimentRegistry(tmp_path, repository_root=tmp_path)
    result = BacktestResult(
        strategy_name="momentum",
        equity_curve=(EquityPoint(START, 1000, 1000, 0),),
        trades=(),
        initial_cash=1000,
        final_equity=1000,
    )

    record = registry.register(
        strategy_name="momentum",
        strategy_parameters={"lookback": 20},
        data=result,
        symbols=("spy", "qqq"),
        start_date=START,
        end_date=START,
        metrics={"total_return": 0.0},
        output_files=("report.html",),
        warnings=("no trades",),
        timestamp=START,
    )
    loaded = registry.load(record.experiment_id)

    assert record.timestamp.tzinfo == timezone.utc
    assert record.symbols == ("SPY", "QQQ")
    assert record.data_fingerprint == data_fingerprint(result)
    assert loaded["strategy_name"] == "momentum"
    assert loaded["code_version"] is None
    assert registry.list() == (loaded,)


def test_registry_rejects_invalid_date_ranges_and_duplicate_symbols(tmp_path) -> None:
    registry = ExperimentRegistry(tmp_path)
    common = {
        "strategy_name": "test",
        "strategy_parameters": {},
        "data": {"bars": []},
        "start_date": START,
        "end_date": START - timedelta(days=1),
        "metrics": {},
    }

    with pytest.raises(ValueError, match="after"):
        registry.register(symbols=("SPY",), **common)
    with pytest.raises(ValueError, match="unique"):
        registry.register(
            **{**common, "end_date": START},
            symbols=("SPY", "SPY"),
        )


def test_storage_rejects_path_traversal_ids(tmp_path) -> None:
    with pytest.raises(ValueError, match="invalid filename"):
        save_experiment(sample_record("../escape"), tmp_path)
