# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Model pricing registry for cost estimation.

Provides approximate per-1K-token pricing for common models. Used by
native clients (FFMistral, FFGemini, FFPerplexity) that cannot use
litellm.completion_cost(). Pricing is updated manually and may lag
behind provider changes.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

PRICING_TABLE: dict[str, tuple[float, float]] = {
    "mistral-large-latest": (0.002, 0.006),
    "mistral-small-latest": (0.0001, 0.0003),
    "mistral-small-2503": (0.0001, 0.0003),
    "mistral-medium-latest": (0.002, 0.006),
    "mistral-tiny": (0.0001, 0.0003),
    "open-mistral-nemo": (0.0001, 0.0003),
    "sonar": (0.001, 0.001),
    "sonar-pro": (0.003, 0.015),
    "sonar-reasoning": (0.001, 0.005),
    "gemini-1.5-pro-002": (0.00125, 0.005),
    "google/gemini-1.5-pro-002": (0.00125, 0.005),
    "gemini-1.5-flash-002": (0.000075, 0.0003),
    "gemini-2.0-flash": (0.0001, 0.0004),
    "gemini-2.5-flash": (0.00015, 0.0006),
    "gemini-2.5-flash-lite": (0.000075, 0.0003),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a completion.

    Args:
        model: Model identifier (e.g. "mistral-small-2503").
        input_tokens: Number of prompt tokens.
        output_tokens: Number of completion tokens.

    Returns:
        Estimated cost in USD, or 0.0 if model is not in the pricing table.

    """
    model_lower = model.lower().strip()

    pricing = PRICING_TABLE.get(model_lower)
    if pricing is None:
        for key, val in PRICING_TABLE.items():
            if key in model_lower or model_lower in key:
                pricing = val
                break

    if pricing is None:
        logger.debug(f"No pricing data for model '{model}', cost estimate is $0.00")
        return 0.0

    input_price, output_price = pricing
    cost = (input_tokens / 1000.0) * input_price + (output_tokens / 1000.0) * output_price
    return cost
