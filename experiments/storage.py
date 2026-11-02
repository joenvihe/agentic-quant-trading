"""Atomic, exclusive JSON storage for experiment metadata."""

from dataclasses import asdict
from datetime import date, datetime
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from experiments.hashing import sanitize_metadata
from experiments.types import ExperimentRecord


class ExperimentStorageError(Exception):
    """Raised when an experiment cannot be safely persisted or loaded."""


def save_experiment(
    record: ExperimentRecord,
    output_directory: str | Path,
) -> Path:
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{_validate_id(record.experiment_id)}.json"
    payload = sanitize_metadata(asdict(record))
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    ) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=directory,
            prefix=".experiment-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.link(temporary_path, destination)
    except FileExistsError as exc:
        raise ExperimentStorageError(
            f"Experiment already exists: {record.experiment_id}"
        ) from exc
    except OSError as exc:
        raise ExperimentStorageError(f"Could not atomically save experiment: {exc}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return destination


def load_experiment(
    experiment_id: str,
    directory: str | Path,
) -> dict[str, Any]:
    path = Path(directory) / f"{_validate_id(experiment_id)}.json"
    try:
        with path.open(encoding="utf-8") as file:
            value = json.load(file)
    except FileNotFoundError as exc:
        raise ExperimentStorageError(f"Experiment not found: {experiment_id}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentStorageError(f"Could not load experiment: {exc}") from exc
    if not isinstance(value, dict):
        raise ExperimentStorageError("Experiment metadata must be a JSON object.")
    return value


def _validate_id(experiment_id: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    if (
        not experiment_id
        or len(experiment_id) > 128
        or any(character not in allowed for character in experiment_id)
    ):
        raise ValueError("experiment_id contains invalid filename characters.")
    return experiment_id


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable.")
