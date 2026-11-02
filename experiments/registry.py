"""Explicit local experiment registry."""

from dataclasses import asdict
from datetime import datetime, timezone
import subprocess
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from experiments.hashing import data_fingerprint, sanitize_metadata
from experiments.storage import load_experiment, save_experiment
from experiments.types import ExperimentRecord


class ExperimentRegistry:
    def __init__(
        self,
        storage_directory: str | Path,
        *,
        repository_root: str | Path | None = None,
    ) -> None:
        self.storage_directory = Path(storage_directory)
        self.repository_root = Path(repository_root) if repository_root else Path.cwd()

    def register(
        self,
        *,
        strategy_name: str,
        strategy_parameters: Mapping[str, Any],
        data: Any,
        symbols: tuple[str, ...] | list[str],
        start_date: datetime | None,
        end_date: datetime | None,
        metrics: Mapping[str, Any],
        output_files: tuple[str, ...] | list[str] = (),
        warnings: tuple[str, ...] | list[str] = (),
        timestamp: datetime | None = None,
    ) -> ExperimentRecord:
        record = self.prepare(
            strategy_name=strategy_name,
            strategy_parameters=strategy_parameters,
            data=data,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            output_files=output_files,
            warnings=warnings,
            timestamp=timestamp,
        )
        save_experiment(record, self.storage_directory)
        return record

    def prepare(
        self,
        *,
        strategy_name: str,
        strategy_parameters: Mapping[str, Any],
        data: Any,
        symbols: tuple[str, ...] | list[str],
        start_date: datetime | None,
        end_date: datetime | None,
        metrics: Mapping[str, Any],
        output_files: tuple[str, ...] | list[str] = (),
        warnings: tuple[str, ...] | list[str] = (),
        timestamp: datetime | None = None,
    ) -> ExperimentRecord:
        """Validate and construct metadata without publishing it."""
        if not strategy_name.strip():
            raise ValueError("strategy_name cannot be empty.")
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware.")
        timestamp = timestamp.astimezone(timezone.utc)
        for name, value in (("start_date", start_date), ("end_date", end_date)):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} must be timezone-aware.")
        if start_date is not None:
            start_date = start_date.astimezone(timezone.utc)
        if end_date is not None:
            end_date = end_date.astimezone(timezone.utc)
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date cannot be after end_date.")
        normalized_symbols = tuple(symbol.strip().upper() for symbol in symbols)
        if any(not symbol for symbol in normalized_symbols):
            raise ValueError("symbols must be non-empty.")
        if len(set(normalized_symbols)) != len(normalized_symbols):
            raise ValueError("symbols must be unique.")

        return ExperimentRecord(
            experiment_id=uuid4().hex,
            timestamp=timestamp,
            strategy_name=strategy_name,
            strategy_parameters=sanitize_metadata(dict(strategy_parameters)),
            data_fingerprint=data_fingerprint(data),
            symbols=normalized_symbols,
            start_date=start_date,
            end_date=end_date,
            code_version=self._git_version(),
            metrics=sanitize_metadata(dict(metrics)),
            output_files=tuple(str(item) for item in output_files),
            warnings=tuple(str(item) for item in warnings),
        )

    def load(self, experiment_id: str) -> dict[str, Any]:
        return load_experiment(experiment_id, self.storage_directory)

    def list(self) -> tuple[dict[str, Any], ...]:
        if not self.storage_directory.exists():
            return ()
        return tuple(
            self.load(path.stem)
            for path in sorted(self.storage_directory.glob("*.json"))
        )

    def _git_version(self) -> str | None:
        if self.repository_root is None:
            return None
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repository_root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        version = result.stdout.strip()
        return version or None
