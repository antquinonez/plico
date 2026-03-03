# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Abstract base class for AI client implementations."""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class FFAIClientBase(ABC):
    """Abstract base class defining the contract for AI client implementations.

    from __future__ import annotations
        All AI provider clients (Mistral, Anthropic, OpenAI, etc.) must inherit
        from this class and implement its abstract methods.

        Attributes:
            model: The model identifier string.
            system_instructions: System prompt/instructions for the AI.

    """

    model: str
    system_instructions: str

    @abstractmethod
    def generate_response(self, prompt: str, **kwargs: Any) -> str:  # noqa: ANN401
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

    @abstractmethod
    def clone(self) -> "FFAIClientBase":
        """Create a fresh clone of this client with empty history.

        Used for thread-safe parallel execution where each thread needs an
        isolated client instance with the same configuration.

        Returns:
            New client instance with same config, empty history.

        """
        pass
