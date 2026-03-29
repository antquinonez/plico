#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Shared base types and utilities for sample workbook creation and validation.

This module provides:
    - PromptSpec: Dataclass for prompt specifications
    - SectionDefinition: Dataclass for validation section definitions
    - Default constants for headers, columns, and widths
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PromptSpec:
    """Specification for a single prompt in a workbook.

    Attributes:
        sequence: Execution order (1-indexed)
        name: Unique prompt identifier
        prompt: The prompt text
        history: JSON list of dependency names (e.g., '["prompt_1", "prompt_2"]')
        client: Named client to use (optional)
        condition: Conditional expression (optional)
        references: JSON list of document references (optional)
        semantic_query: RAG search query string (optional)
        semantic_filter: JSON metadata filter for RAG (optional)
        query_expansion: Enable query expansion (optional)
        rerank: Enable result reranking (optional)

    """

    sequence: int
    name: str
    prompt: str
    history: str | None = None
    notes: str | None = None
    client: str | None = None
    condition: str | None = None
    references: str | None = None
    semantic_query: str | None = None
    semantic_filter: str | None = None
    query_expansion: str | None = None
    rerank: str | None = None
    agent_mode: str | None = None
    tools: str | None = None
    max_tool_rounds: int | None = None
    validation_prompt: str | None = None
    max_validation_retries: int | None = None

    def to_row(
        self,
        extra_columns: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convert to a row dictionary for workbook writing."""
        row = {
            "sequence": self.sequence,
            "prompt_name": self.name,
            "prompt": self.prompt,
            "history": self.history or "",
            "notes": self.notes or "",
            "client": self.client or "",
            "condition": self.condition or "",
            "references": self.references or "",
            "semantic_query": self.semantic_query or "",
            "semantic_filter": self.semantic_filter or "",
            "query_expansion": self.query_expansion or "",
            "rerank": self.rerank or "",
            "agent_mode": self.agent_mode or "",
            "tools": self.tools or "",
            "max_tool_rounds": self.max_tool_rounds or "",
            "validation_prompt": self.validation_prompt or "",
            "max_validation_retries": self.max_validation_retries or "",
        }
        if extra_columns:
            row.update(extra_columns)
        return row


@dataclass
class SectionDefinition:
    """Definition of a validation section.

    Attributes:
        range: Tuple of (start, end) sequence numbers
        description: Human-readable description
        features: List of features tested in this section (optional)
        extra_fields: Additional fields to track per prompt (optional)

    """

    range: tuple[int, int]
    description: str
    features: list[str] | None = None
    extra_fields: list[str] = field(default_factory=list)


DEFAULT_CONFIG_FIELDS: list[tuple[str, str | None, str]] = [
    ("name", None, "Human-readable name for this process/workbook"),
    ("description", None, "Brief description of what this process does"),
    ("client_type", "default_client_type", "AI client type from config/clients.yaml client_types"),
    ("model", "default_model", "Model identifier (e.g., mistral-small-latest, claude-3-5-sonnet)"),
    ("api_key_env", None, "Environment variable name containing the API key"),
    ("max_retries", "default_retries", "Maximum retry attempts on transient failures (1-10)"),
    (
        "temperature",
        "default_temperature",
        "Sampling temperature for response randomness (0.0-2.0)",
    ),
    ("max_tokens", "default_max_tokens", "Maximum tokens in the response"),
    ("system_instructions", "default_system_instructions", "System prompt/instructions for the AI"),
    ("created_at", None, "ISO timestamp when workbook was created (auto-generated)"),
]

DEFAULT_BATCH_CONFIG_FIELDS: list[tuple[str, str, str]] = [
    ("batch_mode", "mode", "Batch execution mode: 'per_row' (execute for each data row)"),
    ("batch_output", "output", "Output format: 'combined' (single sheet) or 'separate_sheets'"),
    (
        "on_batch_error",
        "on_error",
        "Error handling: 'continue' (skip failed) or 'stop' (halt on error)",
    ),
]

DEFAULT_PROMPT_HEADERS = [
    "sequence",
    "prompt_name",
    "prompt",
    "history",
    "notes",
    "client",
    "condition",
    "references",
    "semantic_query",
    "semantic_filter",
    "query_expansion",
    "rerank",
    "agent_mode",
    "tools",
    "max_tool_rounds",
    "validation_prompt",
    "max_validation_retries",
]

DEFAULT_PROMPT_COLUMN_WIDTHS = {
    "A": 10,
    "B": 24,
    "C": 80,
    "D": 40,
    "E": 36,
    "F": 12,
    "G": 80,
    "H": 40,
    "I": 30,
    "J": 45,
    "K": 15,
    "L": 10,
    "M": 18,
    "N": 18,
    "O": 18,
    "P": 18,
    "Q": 20,
}

DEFAULT_CONFIG_COLUMN_WIDTHS = {
    "A": 22,
    "B": 60,
    "C": 60,
}

DEFAULT_CLIENTS_COLUMN_WIDTHS = {
    "A": 14,
    "B": 22,
    "C": 18,
    "D": 28,
    "E": 14,
    "F": 14,
}

DEFAULT_DOCUMENTS_COLUMN_WIDTHS = {
    "A": 22,
    "B": 30,
    "C": 55,
    "D": 45,
    "E": 50,
}

DEFAULT_CLIENTS_HEADERS = [
    "name",
    "client_type",
    "api_key_env",
    "model",
    "temperature",
    "max_tokens",
]

DEFAULT_DOCUMENTS_HEADERS = [
    "reference_name",
    "common_name",
    "file_path",
    "tags",
    "notes",
]

DEFAULT_TOOLS_HEADERS = [
    "name",
    "description",
    "parameters",
    "implementation",
    "enabled",
]

DEFAULT_TOOLS_COLUMN_WIDTHS = {
    "A": 22,
    "B": 60,
    "C": 80,
    "D": 30,
    "E": 10,
}

DEFAULT_DOCUMENTS_COLUMN_WIDTHS = {
    "A": 18,
    "B": 25,
    "C": 50,
    "D": 30,
    "E": 30,
}

STATUS_COLUMN = 12
SEQUENCE_COLUMN = 3
PROMPT_NAME_COLUMN = 4
CONDITION_RESULT_COLUMN = 9
CONDITION_ERROR_COLUMN = 10
BATCH_INDEX_COLUMN = 2
