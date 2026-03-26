# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""ResultBuilder for constructing PromptResult objects."""

from __future__ import annotations

from typing import Any

from .result import PromptResult


class ResultBuilder:
    """Builder for constructing PromptResult objects.

    Provides a fluent interface for building results with consistent structure.

    Usage:
        result = (
            ResultBuilder(prompt)
            .with_batch(batch_id=1, batch_name="test")
            .with_response("AI response")
            .build()
        )
    """

    def __init__(self, prompt: dict[str, Any]) -> None:
        """Initialize builder from prompt dictionary.

        Args:
            prompt: Prompt dictionary with sequence, prompt_name, prompt, etc.

        """
        self._result = PromptResult(
            sequence=prompt["sequence"],
            prompt_name=prompt.get("prompt_name"),
            prompt=prompt["prompt"],
            history=prompt.get("history"),
            client=prompt.get("client"),
            condition=prompt.get("condition"),
            references=prompt.get("references"),
            semantic_query=prompt.get("semantic_query"),
            semantic_filter=prompt.get("semantic_filter"),
            query_expansion=prompt.get("query_expansion"),
            rerank=prompt.get("rerank"),
        )

    def with_batch(self, batch_id: int, batch_name: str) -> ResultBuilder:
        """Add batch information.

        Args:
            batch_id: Batch identifier.
            batch_name: Batch name.

        Returns:
            Self for chaining.

        """
        self._result.batch_id = batch_id
        self._result.batch_name = batch_name
        return self

    def with_response(self, response: str) -> ResultBuilder:
        """Set successful response.

        Args:
            response: The AI-generated response.

        Returns:
            Self for chaining.

        """
        self._result.response = response
        self._result.status = "success"
        return self

    def with_error(self, error: str, attempts: int) -> ResultBuilder:
        """Set failed execution.

        Args:
            error: Error message.
            attempts: Number of attempts made.

        Returns:
            Self for chaining.

        """
        self._result.error = error
        self._result.attempts = attempts
        self._result.status = "failed"
        return self

    def with_attempts(self, attempts: int) -> ResultBuilder:
        """Set number of attempts.

        Args:
            attempts: Number of attempts made.

        Returns:
            Self for chaining.

        """
        self._result.attempts = attempts
        return self

    def as_skipped(
        self, condition_result: Any = None, condition_error: str | None = None
    ) -> ResultBuilder:
        """Mark as skipped due to condition.

        Args:
            condition_result: Result of condition evaluation.
            condition_error: Error from condition evaluation.

        Returns:
            Self for chaining.

        """
        self._result.status = "skipped"
        self._result.condition_result = condition_result
        self._result.condition_error = condition_error
        return self

    def with_condition_result(
        self, condition_result: Any, condition_error: str | None = None
    ) -> ResultBuilder:
        """Set condition evaluation result.

        Args:
            condition_result: Result of condition evaluation.
            condition_error: Error from condition evaluation if any.

        Returns:
            Self for chaining.

        """
        self._result.condition_result = condition_result
        self._result.condition_error = condition_error
        return self

    def with_resolved_prompt(self, resolved_prompt: str) -> ResultBuilder:
        """Set the fully resolved prompt text.

        The resolved prompt contains the prompt text after document reference
        injection and {{variable}} interpolation have been applied.

        Args:
            resolved_prompt: The prompt text after variable and reference resolution.

        Returns:
            Self for chaining.

        """
        self._result.resolved_prompt = resolved_prompt
        return self

    def as_failed_exception(self, error: str) -> ResultBuilder:
        """Mark as failed due to unexpected exception.

        Args:
            error: Exception message.

        Returns:
            Self for chaining.

        """
        self._result.status = "failed"
        self._result.error = error
        self._result.attempts = 1
        return self

    def build(self) -> PromptResult:
        """Build and return the PromptResult.

        Returns:
            The constructed PromptResult object.

        """
        return self._result

    def build_dict(self) -> dict[str, Any]:
        """Build and return as dictionary.

        Returns:
            The constructed result as a dictionary.

        """
        return self._result.to_dict()
