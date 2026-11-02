"""Shared request/response helpers for quantitative application tools."""

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
import math
from pathlib import Path
import re
from typing import Any, Mapping
from uuid import uuid4


_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SERIALIZABLE_DATACLASS_MODULES = frozenset(
    {
        "application.services.research",
        "backtest.types",
        "evaluation.compare",
        "evaluation.types",
        "portfolio.types",
        "regime.engine",
        "reporting.research_report",
        "risk.types",
    }
)


@dataclass(frozen=True)
class ToolResponse:
    success: bool
    trace_id: str
    data: Mapping[str, Any]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


def resolve_trace_id(value: str | None) -> tuple[str, str | None]:
    if value is None:
        return uuid4().hex, None
    if not isinstance(value, str) or not _TRACE_ID_PATTERN.fullmatch(value):
        return uuid4().hex, "trace_id must contain 1-128 safe characters."
    return value, None


def success_response(
    trace_id: str,
    data: object,
    warnings: tuple[str, ...] = (),
) -> ToolResponse:
    serialized = to_serializable(data)
    if not isinstance(serialized, dict):
        raise TypeError("Tool response data must serialize to an object.")
    return ToolResponse(
        success=True,
        trace_id=trace_id,
        data=serialized,
        warnings=warnings,
    )


def error_response(
    trace_id: str,
    error: str,
    *,
    data: Mapping[str, Any] | None = None,
) -> ToolResponse:
    return ToolResponse(
        success=False,
        trace_id=trace_id,
        data=to_serializable(data or {}),
        errors=(error,),
    )


def to_serializable(value: object) -> Any:
    """Convert supported result values to JSON-safe primitives only."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite values cannot be serialized.")
        return value
    if isinstance(value, Enum):
        return to_serializable(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        if type(value).__module__ not in _SERIALIZABLE_DATACLASS_MODULES:
            raise TypeError(
                f"Unsupported response dataclass: {type(value).__name__}."
            )
        return {
            item.name: to_serializable(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        serialized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Serialized mapping keys must be strings.")
            serialized[key] = to_serializable(item)
        return serialized
    if isinstance(value, (tuple, list)):
        return [to_serializable(item) for item in value]
    raise TypeError(f"Unsupported response value: {type(value).__name__}.")
