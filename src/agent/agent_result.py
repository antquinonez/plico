# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Data structures for agentic execution results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRecord:
    """Record of a single tool call within an agentic loop.

    Attributes:
        round: The round number (1-indexed) when this call was made.
        tool_name: Name of the tool that was called.
        tool_call_id: Provider-specific ID for the tool call.
        arguments: Arguments passed to the tool.
        result: The tool's return value as a string.
        duration_ms: Wall-clock duration of tool execution in milliseconds.
        error: Error message if the tool execution failed, None otherwise.

    """

    round: int
    tool_name: str
    tool_call_id: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    duration_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "round": self.round,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "arguments": self.arguments,
            "result": self.result,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCallRecord:
        """Create from dictionary."""
        return cls(
            round=data.get("round", 0),
            tool_name=data.get("tool_name", ""),
            tool_call_id=data.get("tool_call_id", ""),
            arguments=data.get("arguments", {}),
            result=data.get("result", ""),
            duration_ms=data.get("duration_ms", 0.0),
            error=data.get("error"),
        )


@dataclass
class AgentResult:
    """Result of an agentic execution loop.

    Attributes:
        response: The final response text from the LLM.
        tool_calls: List of tool call records from all rounds.
        total_rounds: Number of rounds executed.
        total_llm_calls: Total number of LLM API calls made.
        status: Execution status - "success", "failed", or "max_rounds_exceeded".

    """

    response: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    total_rounds: int = 0
    total_llm_calls: int = 0
    status: str = "success"

    VALID_STATUSES = ("success", "failed", "max_rounds_exceeded")

    @property
    def tool_calls_count(self) -> int:
        """Total number of tool calls made."""
        return len(self.tool_calls)

    @property
    def last_tool_name(self) -> str:
        """Name of the last tool called, or empty string if no tools used."""
        if self.tool_calls:
            return self.tool_calls[-1].tool_name
        return ""

    @property
    def failed_tool_calls(self) -> list[ToolCallRecord]:
        """List of tool calls that resulted in errors."""
        return [tc for tc in self.tool_calls if tc.error is not None]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "response": self.response,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "total_rounds": self.total_rounds,
            "total_llm_calls": self.total_llm_calls,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentResult:
        """Create from dictionary."""
        tool_calls = [ToolCallRecord.from_dict(tc) for tc in data.get("tool_calls", [])]
        return cls(
            response=data.get("response", ""),
            tool_calls=tool_calls,
            total_rounds=data.get("total_rounds", 0),
            total_llm_calls=data.get("total_llm_calls", 0),
            status=data.get("status", "success"),
        )
