# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Variable resolution and batch templating for orchestrator prompts.

Pure functions for replacing {{variable}} placeholders in prompt text,
resolving variables across prompt dictionaries, and generating batch names.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .models import PromptSpec
from .workbook_parser import parse_history_string

logger = logging.getLogger(__name__)


def resolve_variables(text: str | None, data_row: dict[str, Any]) -> str | None:
    """Replace {{variable}} placeholders with values from data row.

    Args:
        text: Text with {{variable}} placeholders, or None.
        data_row: Dictionary of variable values.

    Returns:
        Text with placeholders replaced, or None if text was None.

    """
    if not text:
        return text

    pattern = r"\{\{(\w+)\}\}"

    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        if var_name in data_row and data_row[var_name] is not None:
            return str(data_row[var_name])
        logger.warning(f"Variable '{var_name}' not found in data row")
        return match.group(0)

    return re.sub(pattern, replacer, text)


def resolve_prompt_variables(prompt: PromptSpec, data_row: dict[str, Any]) -> PromptSpec:
    """Resolve all {{variable}} placeholders in a prompt.

    Also merges per-row ``_documents`` from the data row into the prompt's
    ``references`` list (additive merge).

    Args:
        prompt: Prompt dictionary.
        data_row: Dictionary of variable values.

    Returns:
        New prompt dictionary with resolved placeholders.

    """
    resolved = dict(prompt)
    resolved["prompt"] = resolve_variables(prompt.get("prompt", ""), data_row)
    if prompt.get("prompt_name"):
        resolved["prompt_name"] = resolve_variables(prompt["prompt_name"], data_row)

    row_docs = data_row.get("_documents")
    if row_docs:
        doc_refs = parse_history_string(row_docs)
        if doc_refs:
            existing_refs = resolved.get("references") or []
            resolved["references"] = list(existing_refs) + doc_refs

    return resolved


def resolve_batch_name(data_row: dict[str, Any], batch_id: int) -> str:
    """Generate batch name from data row or default.

    Args:
        data_row: Dictionary with optional batch_name field.
        batch_id: Default batch ID number.

    Returns:
        Batch name string.

    """
    if data_row.get("batch_name"):
        name = resolve_variables(str(data_row["batch_name"]), data_row)
        return re.sub(r"[^\w\-]", "_", name)[:50]
    return f"batch_{batch_id}"
