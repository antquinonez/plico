# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Prompt interpolation and JSON field extraction utilities."""

from __future__ import annotations

import json
import re
from typing import Any

INTERPOLATION_PATTERN = re.compile(r"\{\{(\w+)\.response(?:\.([\w.]+))?\}\}")


def extract_json_field(data: dict | list, path: str) -> str:
    """Extract a value from JSON using dot notation path.

    Supports:
    - Simple fields: "field_name"
    - Nested objects: "object.field"
    - Array indices: "array.0"
    - Combined: "object.array.0.field"

    Args:
        data: Parsed JSON data (dict or list)
        path: Dot-separated path to extract

    Returns:
        Extracted value as string, or empty string if not found

    """
    parts = path.split(".")
    current: Any = data

    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError):
                return ""
        else:
            return ""

        if current is None:
            return ""

    if isinstance(current, dict | list):
        return json.dumps(current)
    return str(current)


def interpolate_prompt(
    prompt: str,
    history: dict[str, str],
) -> tuple[str, set[str]]:
    """Replace {{prompt_name.response}} patterns with actual content.

    Args:
        prompt: Template containing {{}} patterns
        history: Dict mapping prompt_name to response text

    Returns:
        Tuple of (resolved_prompt, set_of_interpolated_prompt_names)

    """
    interpolated: set[str] = set()
    resolved = prompt

    for match in INTERPOLATION_PATTERN.finditer(prompt):
        full_match = match.group(0)
        prompt_name = match.group(1)
        field_path = match.group(2)

        if prompt_name not in history:
            resolved = resolved.replace(full_match, "")
            continue

        response = history[prompt_name]

        if field_path:
            try:
                data = json.loads(response)
                replacement = extract_json_field(data, field_path)
            except (json.JSONDecodeError, TypeError):
                replacement = response
        else:
            replacement = response

        resolved = resolved.replace(full_match, replacement)
        interpolated.add(prompt_name)

    return resolved, interpolated
