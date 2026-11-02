"""Serializable state and tool-call records for research-agent runs."""

from dataclasses import dataclass, field
from typing import Any, Mapping

from application.tools.types import to_serializable


@dataclass(frozen=True)
class AgentToolCall:
    name: str
    arguments: Mapping[str, str]


@dataclass
class ResearchAgentState:
    request: str
    symbols: list[str]
    selected_strategy: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    final_report: str | None = None
    trace_id: str | None = None
    success: bool = False
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(
            {
                "request": self.request,
                "symbols": self.symbols,
                "selected_strategy": self.selected_strategy,
                "tool_calls": self.tool_calls,
                "evidence": self.evidence,
                "warnings": self.warnings,
                "final_report": self.final_report,
                "trace_id": self.trace_id,
                "success": self.success,
                "errors": self.errors,
                "dry_run": self.dry_run,
            }
        )
