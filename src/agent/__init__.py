# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Agentic execution module for Plico orchestrator.

Provides tool-call loop execution, tool registry, built-in tools,
and MCP server for opt-in agentic capabilities within the
deterministic DAG orchestrator.
"""

from __future__ import annotations

from .agent_result import AgentResult, ToolCallRecord

__all__ = [
    "AgentResult",
    "ToolCallRecord",
]
