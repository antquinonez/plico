# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""LiteLLM-backed AI client implementing FFAIClientBase contract.

This module provides FFLiteLLMClient, a client that wraps LiteLLM's completion()
function while maintaining full compatibility with FFClients' architecture including:
- FFAIClientBase contract for FFAI wrapper compatibility
- Clone pattern for thread-safe parallel execution
- Internal conversation history management
- Support for fallbacks and retries
"""

from __future__ import annotations

import copy
import logging
import os
from typing import Any

from litellm import completion

from ..FFAIClientBase import FFAIClientBase
from .model_defaults import get_model_defaults

logger = logging.getLogger(__name__)


class FFLiteLLMClient(FFAIClientBase):
    """LiteLLM-backed AI client implementing FFAIClientBase.

    This client wraps LiteLLM's completion() function while maintaining
    the FFAIClientBase contract for compatibility with FFAI wrapper.

    Key features:
    - Internal conversation history management
    - Clone pattern for parallel execution
    - Model string routing (e.g., "azure/mistral-small-2503")
    - Retry and fallback support

    Args:
        model_string: LiteLLM model identifier (e.g., "openai/gpt-4", "azure/my-deployment")
        config: Optional configuration dictionary
        api_key: API key (overrides env var)
        api_base: API base URL (overrides env var)
        system_instructions: System prompt
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens to generate
        fallbacks: List of fallback model strings
        retry_config: Retry configuration

    Example:
        >>> client = FFLiteLLMClient(model_string="azure/mistral-small-2503")
        >>> response = client.generate_response("Hello!")
        >>>
        >>> # With fallbacks
        >>> client = FFLiteLLMClient(
        ...     model_string="anthropic/claude-3-opus",
        ...     fallbacks=["openai/gpt-4", "azure/gpt-4"]
        ... )

    """

    model: str
    system_instructions: str

    def __init__(
        self,
        model_string: str,
        config: dict[str, Any] | None = None,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        api_version: str | None = None,
        system_instructions: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        fallbacks: list[str] | None = None,
        retry_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        self._model_string = model_string
        self._config = config or {}
        self._fallbacks = fallbacks or []
        self._retry_config = retry_config or {"max_retries": 3}

        self.model = model_string.split("/", 1)[-1] if "/" in model_string else model_string

        self._resolve_settings(
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
            system_instructions=system_instructions,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        self.conversation_history: list[dict[str, str]] = []
        logger.info(f"Initialized FFLiteLLMClient with model_string={model_string}")

    def _resolve_settings(
        self,
        api_key: str | None,
        api_base: str | None,
        api_version: str | None,
        system_instructions: str | None,
        temperature: float | None,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> None:
        """Resolve all settings with priority chain."""
        defaults = get_model_defaults(self._model_string)

        self.api_key = api_key or self._config.get("api_key") or self._get_env("API_KEY")
        self.api_base = api_base or self._config.get("api_base") or self._get_env("API_BASE")
        self.api_version = (
            api_version or self._config.get("api_version") or self._get_env("API_VERSION")
        )
        self.system_instructions = (
            system_instructions
            or self._config.get("system_instructions")
            or defaults.get("system_instructions", "You are a helpful assistant.")
        )
        self.temperature = (
            temperature
            if temperature is not None
            else self._config.get("temperature", defaults.get("temperature", 0.7))
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else self._config.get("max_tokens", defaults.get("max_tokens", 4096))
        )

        self._extra_kwargs = kwargs

    def _get_env(self, suffix: str) -> str | None:
        """Get environment variable with provider-specific prefix."""
        provider = self._model_string.split("/")[0] if "/" in self._model_string else "openai"

        prefixes = {
            "azure": f"AZURE_{self.model.upper().replace('-', '_')}",
            "anthropic": "ANTHROPIC",
            "mistral": "MISTRAL",
            "openai": "OPENAI",
            "gemini": "GEMINI",
            "perplexity": "PERPLEXITY",
            "nvidia_nim": "NVIDIA",
        }

        prefix = prefixes.get(provider, provider.upper())

        patterns = [
            f"{prefix}_{suffix}",
            f"{prefix}_API_KEY" if suffix == "API_KEY" else None,
            f"LITELLM_{suffix}",
        ]

        for pattern in patterns:
            if pattern and (value := os.getenv(pattern)):
                return value

        return None

    def generate_response(
        self,
        prompt: str,
        model: str | None = None,
        system_instructions: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate a response from the AI model.

        Args:
            prompt: The user prompt
            model: Override model (appends to provider prefix)
            system_instructions: Override system instructions
            temperature: Override temperature
            max_tokens: Override max tokens
            **kwargs: Additional LiteLLM parameters

        Returns:
            The generated response text

        Raises:
            ValueError: If prompt is empty
            RuntimeError: If all models (including fallbacks) fail

        """
        if not prompt.strip():
            raise ValueError("Empty prompt provided")

        self.conversation_history.append({"role": "user", "content": prompt})

        messages = self._build_messages(system_instructions)

        model_string = self._model_string
        if model:
            if "/" not in model and "/" in self._model_string:
                provider = self._model_string.split("/")[0]
                model_string = f"{provider}/{model}"
            else:
                model_string = model

        api_params: dict[str, Any] = {
            "model": model_string,
            "messages": messages,
            "temperature": (temperature if temperature is not None else self.temperature),
            "max_tokens": max_tokens or self.max_tokens,
        }

        if self.api_key:
            api_params["api_key"] = self.api_key
        if self.api_base:
            api_params["api_base"] = self.api_base
        if self.api_version:
            api_params["api_version"] = self.api_version

        api_params.update(self._extra_kwargs)
        api_params.update(kwargs)

        logger.debug(
            f"Calling LiteLLM with model={model_string}, temperature={api_params.get('temperature')}"
        )

        try:
            response = completion(**api_params)
            assistant_response = response.choices[0].message.content

            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            logger.debug(f"Response received: {assistant_response[:100]}...")
            return assistant_response

        except Exception as e:
            logger.warning(f"Primary model {model_string} failed: {e}")
            return self._try_fallbacks(messages, api_params, str(e))

    def _build_messages(self, system_instructions: str | None = None) -> list[dict[str, str]]:
        """Build messages list for LiteLLM API call."""
        messages: list[dict[str, str]] = []

        system = system_instructions or self.system_instructions
        if system:
            messages.append({"role": "system", "content": system})

        messages.extend(self.conversation_history)

        return messages

    def _try_fallbacks(
        self,
        messages: list[dict[str, str]],
        original_params: dict[str, Any],
        original_error: str,
    ) -> str:
        """Try fallback models if primary fails."""
        for fallback_model in self._fallbacks:
            try:
                logger.info(f"Trying fallback model: {fallback_model}")
                params = original_params.copy()
                params["model"] = fallback_model
                response = completion(**params)
                assistant_response = response.choices[0].message.content
                self.conversation_history.append(
                    {"role": "assistant", "content": assistant_response}
                )
                logger.info(f"Fallback model {fallback_model} succeeded")
                return assistant_response
            except Exception as e:
                logger.warning(f"Fallback model {fallback_model} failed: {e}")
                continue

        raise RuntimeError(f"All models failed. Primary error: {original_error}")

    def clear_conversation(self) -> None:
        """Clear the conversation history."""
        logger.debug("Clearing conversation history")
        self.conversation_history = []

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get the conversation history."""
        return self.conversation_history.copy()

    def set_conversation_history(self, history: list[dict[str, str]]) -> None:
        """Set the conversation history."""
        self.conversation_history = list(history)
        logger.debug(f"Set conversation history with {len(history)} messages")

    def clone(self) -> FFLiteLLMClient:
        """Create a fresh clone of this client with empty history.

        Used for thread-safe parallel execution where each thread
        needs an isolated client instance with the same configuration.

        Returns:
            New FFLiteLLMClient with same config, empty history.

        """
        logger.debug(f"Cloning client with model_string={self._model_string}")
        return FFLiteLLMClient(
            model_string=self._model_string,
            config=copy.deepcopy(self._config),
            api_key=self.api_key,
            api_base=self.api_base,
            api_version=self.api_version,
            system_instructions=self.system_instructions,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            fallbacks=copy.copy(self._fallbacks) if self._fallbacks else None,
            retry_config=copy.copy(self._retry_config),
            **copy.deepcopy(self._extra_kwargs),
        )

    def __repr__(self) -> str:
        return f"FFLiteLLMClient(model_string={self._model_string!r}, model={self.model!r})"
