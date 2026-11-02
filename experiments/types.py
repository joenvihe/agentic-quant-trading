"""Experiment metadata contract."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    timestamp: datetime
    strategy_name: str
    strategy_parameters: Mapping[str, Any]
    data_fingerprint: str
    symbols: tuple[str, ...]
    start_date: datetime | None
    end_date: datetime | None
    code_version: str | None
    metrics: Mapping[str, Any]
    output_files: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            self.timestamp.tzinfo is None
            or self.timestamp.utcoffset() != timezone.utc.utcoffset(self.timestamp)
        ):
            raise ValueError("timestamp must be UTC-aware.")
        for name, value in (
            ("start_date", self.start_date),
            ("end_date", self.end_date),
        ):
            if value is not None and (
                value.tzinfo is None
                or value.utcoffset() != timezone.utc.utcoffset(value)
            ):
                raise ValueError(f"{name} must be UTC-aware.")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date cannot be after end_date.")
