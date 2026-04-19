# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Shared prompt attribute history with thread-safe recording."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class ResponseContext:
    """Manages the shared ``prompt_attr_history`` list with thread-safe recording.

    This class centralises all mutation of the shared prompt-attribute history
    that ``PromptBuilder`` reads from for ``{{name.response}}`` interpolation.
    It replaces the inline history recording previously scattered through
    ``FFAI.generate_response()`` and direct list appends in
    ``PlanningRunner`` / ``SynthesisRunner``.

    Args:
        shared_prompt_attr_history: Optional pre-existing list to share.
            When ``None`` a new empty list is created.
        history_lock: Optional lock for thread-safe access.

    """

    def __init__(
        self,
        shared_prompt_attr_history: list[dict[str, Any]] | None = None,
        history_lock: threading.Lock | None = None,
    ) -> None:
        self.prompt_attr_history: list[dict[str, Any]] = (
            shared_prompt_attr_history if shared_prompt_attr_history is not None else []
        )
        self._history_lock = history_lock

    def record(
        self,
        prompt: str,
        response: Any,
        model: str,
        prompt_name: str | None = None,
        history: list[str] | None = None,
    ) -> None:
        """Record an interaction to ``prompt_attr_history``.

        If *response* is a ``dict`` (JSON response from the LLM), each
        top-level key-value pair is recorded as a separate entry so that
        ``{{key_name.response}}`` interpolation works.

        Args:
            prompt: The original prompt text (or JSON key name).
            response: The cleaned response (str, dict, etc.).
            model: Model identifier used for this call.
            prompt_name: Optional logical name for the prompt.
            history: Optional list of history dependency names.

        """
        interaction = {
            "prompt": prompt,
            "response": response,
            "prompt_name": prompt_name,
            "timestamp": time.time(),
            "model": model,
            "history": history,
        }

        if isinstance(response, dict):
            for attr, value in response.items():
                attr_interaction = {
                    "prompt": attr,
                    "response": value,
                    "prompt_name": attr,
                    "timestamp": time.time(),
                    "model": model,
                    "history": history,
                }
                self._append(attr_interaction)
                logger.debug(f"Added attr interaction to prompt_attr_history: {attr_interaction}")
        else:
            self._append(interaction)
            logger.debug(f"Added interaction to prompt_attr_history: {interaction}")

    def record_raw(
        self,
        interaction: dict[str, Any],
    ) -> None:
        """Append a pre-built interaction dict.

        Used by ``PlanningRunner`` and ``SynthesisRunner`` to inject results
        that were not produced by ``FFAI.generate_response()``.

        Args:
            interaction: A dict with at least ``prompt``, ``response``,
                ``prompt_name`` keys.

        """
        self._append(interaction)

    def clear(self) -> None:
        """Clear the shared history list (used by synthesis phase reset)."""
        if self._history_lock:
            with self._history_lock:
                self.prompt_attr_history.clear()
        else:
            self.prompt_attr_history.clear()

    @property
    def history_lock(self) -> threading.Lock | None:
        """The lock used for thread-safe history access."""
        return self._history_lock

    def _append(self, interaction: dict[str, Any]) -> None:
        if self._history_lock:
            with self._history_lock:
                self.prompt_attr_history.append(interaction)
        else:
            self.prompt_attr_history.append(interaction)
