# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Abstract base class for AI client implementations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from .usage import TokenUsage

logger = logging.getLogger(__name__)


class FFAIClientBase(ABC):
    """Abstract base class defining the contract for AI client implementations.

    All AI provider clients (Mistral, Anthropic, OpenAI, etc.) must inherit
    from this class and implement its abstract methods.

    Attributes:
        model: The model identifier string.
        system_instructions: System prompt/instructions for the AI.

    """

    model: str
    system_instructions: str
    retry_config: dict[str, Any] | None = None

    _last_usage: TokenUsage | None = None
    _last_cost_usd: float = 0.0

    @staticmethod
    def get_default_retry_config() -> dict[str, Any]:
        """Get default retry configuration from global config.

        Returns:
            Dictionary with retry configuration parameters.

        """
        try:
            from ..config import get_config

            app_config = get_config()
            retry_settings = getattr(app_config, "retry", None)

            if retry_settings:
                return {
                    "max_attempts": getattr(retry_settings, "max_attempts", 3),
                    "min_wait_seconds": getattr(retry_settings, "min_wait_seconds", 1),
                    "max_wait_seconds": getattr(retry_settings, "max_wait_seconds", 60),
                    "exponential_base": getattr(retry_settings, "exponential_base", 2),
                    "exponential_jitter": getattr(retry_settings, "exponential_jitter", True),
                    "log_level": getattr(retry_settings, "log_level", "INFO"),
                }
        except Exception as e:
            logger.debug(f"Could not load retry config: {e}")

        return {
            "max_attempts": 3,
            "min_wait_seconds": 1,
            "max_wait_seconds": 60,
            "exponential_base": 2,
            "exponential_jitter": True,
            "log_level": "INFO",
        }

    def configure_retry(self, retry_config: dict[str, Any] | None = None) -> None:
        """Configure retry behavior for this client.

        Args:
            retry_config: Optional retry configuration. If None, uses global config.

        """
        self.retry_config = retry_config or self.get_default_retry_config()
        logger.debug(f"Configured retry: {self.retry_config}")

    def _reset_usage(self) -> None:
        """Reset per-call usage metadata. Called at the start of generate_response()."""
        self._last_usage = None
        self._last_cost_usd = 0.0

    def _extract_token_usage(self, response: Any, model: str) -> None:
        """Extract token usage from an API response object.

        Works for Mistral SDK, OpenAI-compatible (FFPerplexity, FFGemini),
        and any response with a usage attribute containing prompt/completion
        token counts.

        Args:
            response: The API response object.
            model: The model identifier for cost lookup.

        """
        from .pricing import estimate_cost

        usage = getattr(response, "usage", None)
        if usage is not None and hasattr(usage, "prompt_tokens"):
            self._last_usage = TokenUsage(
                input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
            )
            self._last_cost_usd = float(
                estimate_cost(
                    model,
                    self._last_usage.input_tokens,
                    self._last_usage.output_tokens,
                )
            )
            logger.debug(
                f"Usage for {model}: "
                f"in={self._last_usage.input_tokens}, "
                f"out={self._last_usage.output_tokens}, "
                f"cost=${self._last_cost_usd:.6f}"
            )

    @contextmanager
    def _trace_llm_call(
        self, model: str, prompt_name: str | None = None
    ) -> Generator[None, None, None]:
        """Context manager that wraps an LLM call with an OTel span.

        Emits a child span with model, usage, and cost attributes.
        No-op when observability is disabled.

        Args:
            model: The model identifier.
            prompt_name: Optional prompt name for the span.

        Yields:
            Nothing; the body of the with-block is the LLM call.

        """
        from ..observability.telemetry import get_telemetry_manager

        mgr = get_telemetry_manager()
        span_name = f"llm.{self.__class__.__name__}"
        if prompt_name:
            span_name = f"llm.{prompt_name}"

        with mgr.span(span_name) as span:
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.client_type", self.__class__.__name__)
            if prompt_name:
                span.set_attribute("llm.prompt_name", prompt_name)
            try:
                yield
            finally:
                if self._last_usage:
                    span.set_attribute("llm.input_tokens", self._last_usage.input_tokens)
                    span.set_attribute("llm.output_tokens", self._last_usage.output_tokens)
                    span.set_attribute("llm.total_tokens", self._last_usage.total_tokens)
                span.set_attribute("llm.cost_usd", self._last_cost_usd)

    @property
    def last_usage(self) -> TokenUsage | None:
        """Token usage from the most recent generate_response() call."""
        return self._last_usage

    @property
    def last_cost_usd(self) -> float:
        """Estimated cost in USD from the most recent generate_response() call."""
        return self._last_cost_usd

    @abstractmethod
    def generate_response(self, prompt: str, **kwargs: Any) -> str:
        """Generate a response from the AI model.

        Args:
            prompt: The user prompt to send to the model.
            **kwargs: Additional model-specific parameters (temperature, max_tokens, etc.)

        Returns:
            The generated response string.

        """
        pass

    @abstractmethod
    def clear_conversation(self) -> None:
        """Clear the conversation history."""
        pass

    @abstractmethod
    def get_conversation_history(self) -> list[dict[str, Any]]:
        """Get the conversation history.

        Returns:
            List of message dictionaries with role and content keys.

        """
        pass

    @abstractmethod
    def set_conversation_history(self, history: list[dict[str, Any]]) -> None:
        """Set the conversation history.

        Args:
            history: List of message dictionaries with role and content keys.

        """
        pass

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """Add a tool result to the conversation history.

        Default implementation appends a tool-role message. Subclasses
        that manage conversation history differently (e.g. via an external
        API) should override this method.

        Args:
            tool_call_id: The ID of the tool call this result responds to.
            content: The tool execution result string.

        """
        history = self.get_conversation_history()
        history.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})
        self.set_conversation_history(history)

    @abstractmethod
    def clone(self) -> FFAIClientBase:
        """Create a fresh clone of this client with empty history.

        Used for thread-safe parallel execution where each thread needs an
        isolated client instance with the same configuration.

        Returns:
            New client instance with same config, empty history.

        """
        pass
