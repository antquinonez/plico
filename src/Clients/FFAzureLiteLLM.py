# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Azure AI client factory for LiteLLM-based clients.

Provides a factory function for creating Azure AI clients with
environment-based configuration, maintaining backward compatibility
with existing FFAzure* client patterns.
"""

import logging
import os
from typing import Any

from .FFLiteLLMClient import FFLiteLLMClient
from .model_defaults import get_model_defaults

logger = logging.getLogger(__name__)


def create_azure_client(
    deployment_name: str,
    env_prefix: str,
    *,
    model_defaults: dict[str, Any] | None = None,
    system_instructions: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs: Any,
) -> FFLiteLLMClient:
    """Factory for Azure AI clients with environment-based configuration.

    This provides backward compatibility with existing Azure client patterns
    while using LiteLLM under the hood.

    Args:
        deployment_name: Azure deployment name (e.g., "mistral-small-2503")
        env_prefix: Environment variable prefix (e.g., "AZURE_MISTRALSMALL")
        model_defaults: Optional model-specific defaults
        system_instructions: System prompt override
        temperature: Temperature override
        max_tokens: Max tokens override
        **kwargs: Additional FFLiteLLMClient parameters

    Returns:
        Configured FFLiteLLMClient for Azure model

    Example:
        >>> client = create_azure_client(
        ...     deployment_name="mistral-small-2503",
        ...     env_prefix="AZURE_MISTRALSMALL"
        ... )

    """
    model_string = f"azure/{deployment_name}"

    defaults = get_model_defaults(model_string)
    if model_defaults:
        defaults = {**defaults, **model_defaults}

    api_key = os.getenv(f"{env_prefix}_KEY")
    api_base = os.getenv(f"{env_prefix}_ENDPOINT")
    api_version = os.getenv(f"{env_prefix}_API_VERSION", "2024-02-01")

    env_temperature = os.getenv(f"{env_prefix}_TEMPERATURE")
    env_max_tokens = os.getenv(f"{env_prefix}_MAX_TOKENS")
    env_instructions = os.getenv(f"{env_prefix}_ASSISTANT_INSTRUCTIONS")

    resolved_temperature = temperature
    if resolved_temperature is None:
        if env_temperature:
            try:
                resolved_temperature = float(env_temperature)
            except ValueError:
                resolved_temperature = defaults.get("temperature")
        else:
            resolved_temperature = defaults.get("temperature")

    resolved_max_tokens = max_tokens
    if resolved_max_tokens is None:
        if env_max_tokens:
            try:
                resolved_max_tokens = int(env_max_tokens)
            except ValueError:
                resolved_max_tokens = defaults.get("max_tokens")
        else:
            resolved_max_tokens = defaults.get("max_tokens")

    resolved_instructions = (
        system_instructions or env_instructions or defaults.get("system_instructions")
    )

    logger.info(
        f"Creating Azure client: deployment={deployment_name}, "
        f"endpoint={api_base[:30] + '...' if api_base else 'not set'}"
    )

    return FFLiteLLMClient(
        model_string=model_string,
        api_key=api_key,
        api_base=api_base,
        api_version=api_version,
        system_instructions=resolved_instructions,
        temperature=resolved_temperature,
        max_tokens=resolved_max_tokens,
        **kwargs,
    )
