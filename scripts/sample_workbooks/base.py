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
    client: str | None = None
    condition: str | None = None
    references: str | None = None
    semantic_query: str | None = None
    semantic_filter: str | None = None
    query_expansion: str | None = None
    rerank: str | None = None

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
            "client": self.client or "",
            "condition": self.condition or "",
            "references": self.references or "",
            "semantic_query": self.semantic_query or "",
            "semantic_filter": self.semantic_filter or "",
            "query_expansion": self.query_expansion or "",
            "rerank": self.rerank or "",
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


DEFAULT_CONFIG_FIELDS = [
    ("client_type", "default_client_type"),
    ("model", "default_model"),
    ("max_retries", "default_retries"),
    ("temperature", "default_temperature"),
    ("max_tokens", "default_max_tokens"),
    ("system_instructions", "default_system_instructions"),
    ("created_at", None),
]

DEFAULT_PROMPT_HEADERS = [
    "sequence",
    "prompt_name",
    "prompt",
    "history",
    "client",
    "condition",
    "references",
    "semantic_query",
    "semantic_filter",
    "query_expansion",
    "rerank",
]

DEFAULT_PROMPT_COLUMN_WIDTHS = {
    "A": 10,
    "B": 20,
    "C": 60,
    "D": 30,
    "E": 10,
    "F": 60,
    "G": 35,
    "H": 30,
    "I": 40,
    "J": 15,
    "K": 10,
}

DEFAULT_CONFIG_COLUMN_WIDTHS = {
    "A": 20,
    "B": 70,
}

DEFAULT_CLIENTS_HEADERS = [
    "name",
    "client_type",
    "api_key_env",
    "model",
    "temperature",
    "max_tokens",
]

DEFAULT_CLIENTS_COLUMN_WIDTHS = {
    "A": 12,
    "B": 15,
    "C": 18,
    "D": 20,
    "E": 12,
    "F": 12,
}

DEFAULT_DOCUMENTS_HEADERS = [
    "reference_name",
    "common_name",
    "file_path",
    "notes",
]

DEFAULT_DOCUMENTS_COLUMN_WIDTHS = {
    "A": 18,
    "B": 25,
    "C": 50,
    "D": 30,
}

STATUS_COLUMN = 12
SEQUENCE_COLUMN = 3
PROMPT_NAME_COLUMN = 4
CONDITION_RESULT_COLUMN = 9
CONDITION_ERROR_COLUMN = 10
BATCH_INDEX_COLUMN = 2
