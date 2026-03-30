# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""ResultBuilder for constructing PromptResult objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .result import PromptResult

if TYPE_CHECKING:
    from ...agent.agent_result import AgentResult


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

    def increment_attempts(self) -> ResultBuilder:
        """Increment the number of execution attempts.

        Returns:
            Self for chaining.

        """
        self._result.attempts += 1
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

    def with_agent_result(self, agent_result: AgentResult) -> ResultBuilder:
        """Set result from agentic execution.

        Populates tool call records, round counts, and the final response
        from an AgentLoop execution.

        Args:
            agent_result: The result from an AgentLoop.execute() call.

        Returns:
            Self for chaining.

        """
        self._result.agent_mode = True
        self._result.tool_calls = [tc.to_dict() for tc in agent_result.tool_calls]
        self._result.total_rounds = agent_result.total_rounds
        self._result.total_llm_calls = agent_result.total_llm_calls
        self._result.response = agent_result.response
        if agent_result.status == "max_rounds_exceeded":
            self._result.status = "max_rounds_exceeded"
            self._result.error = f"Agent loop exceeded max rounds ({agent_result.total_rounds})"
        elif agent_result.status == "failed":
            self._result.status = "failed"
        else:
            self._result.status = "success"
        return self

    def with_validation_result(
        self,
        passed: bool | None,
        attempts: int,
        critique: str | None = None,
    ) -> ResultBuilder:
        """Set result from response validation.

        Args:
            passed: Whether the response passed validation.
            attempts: Number of validation attempts made.
            critique: Last critique if validation failed.

        Returns:
            Self for chaining.

        """
        self._result.validation_passed = passed
        self._result.validation_attempts = attempts
        self._result.validation_critique = critique
        return self

    def with_scoring(
        self,
        scores: dict[str, Any],
        composite_score: float,
        scoring_status: str,
        strategy: str,
    ) -> ResultBuilder:
        """Set scoring results.

        Args:
            scores: Dictionary of criteria_name to score values.
            composite_score: Weighted composite score.
            scoring_status: Aggregation status (ok, partial, failed, skipped).
            strategy: Evaluation strategy used.

        Returns:
            Self for chaining.

        """
        self._result.scores = scores
        self._result.composite_score = composite_score
        self._result.scoring_status = scoring_status
        self._result.strategy = strategy
        return self

    def as_synthesis(self) -> ResultBuilder:
        """Mark this result as a synthesis result.

        Returns:
            Self for chaining.

        """
        self._result.result_type = "synthesis"
        self._result.batch_id = -1
        self._result.batch_name = ""
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
