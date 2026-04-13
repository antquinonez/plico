# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Response cleaning and JSON extraction utilities."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_MARKDOWN_PATTERN = re.compile(r"```(?:json)?\s*(?P<content>[\s\S]*?)\s*```")
_THINK_TAG_PATTERN = re.compile(r"<think[\s\S]*?</think\s*>")


def _clean_text(text: str) -> str:
    return text.strip().replace("\ufeff", "")


def _extract_from_markdown(text: str) -> str | None:
    if match := _MARKDOWN_PATTERN.search(text):
        return _clean_text(match.group("content"))
    return None


def extract_json(text: str) -> Any | None:
    """Extract JSON from text, handling markdown code blocks.

    Checks if JSON appears within the first 20 characters. If found,
    tries markdown extraction first, then falls back to full text parse.

    Args:
        text: Response text that may contain JSON.

    Returns:
        Parsed JSON object or None if no valid JSON found.

    """
    first_20_chars = text[:20]
    try:
        if json.loads(first_20_chars):
            markdown_content = _extract_from_markdown(text)
            if markdown_content:
                try:
                    return json.loads(markdown_content)
                except json.JSONDecodeError:
                    pass

            return json.loads(_clean_text(text))
    except json.JSONDecodeError:
        pass

    return None


def clean_response(response: Any) -> Any:
    """Process and validate a response, removing think tags and extracting JSON.

    Args:
        response: The raw response from the AI client.

    Returns:
        Cleaned response. If JSON is detected, returns the parsed object.
        Otherwise returns the cleaned string with think tags removed.

    """
    if not isinstance(response, str):
        return response

    response = _THINK_TAG_PATTERN.sub("", response)

    cleaned_json = extract_json(response)

    if cleaned_json is not None:
        if isinstance(cleaned_json, dict):
            for key, value in cleaned_json.items():
                if isinstance(value, str):
                    cleaned_json[key] = _THINK_TAG_PATTERN.sub("", value)
        return cleaned_json
    return response
