# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Structured return type for FFAI response generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .usage import TokenUsage


@dataclass
class ResponseResult:
    """Structured result from an FFAI response generation call.

    Replaces side-channel attributes (``last_usage``, ``last_cost_usd``,
    ``last_resolved_prompt``) with a single typed return value.

    Attributes:
        response: The cleaned AI response (str, dict, list, etc.).
        resolved_prompt: The fully interpolated prompt sent to the model.
        usage: Token usage from the API call, if available.
        cost_usd: Estimated cost in USD for this call.
        model: Model identifier used for this call.
        duration_ms: Wall-clock duration of the LLM call in milliseconds.

    """

    response: Any
    resolved_prompt: str = ""
    usage: TokenUsage | None = None
    cost_usd: float = 0.0
    model: str = ""
    duration_ms: float = 0.0
