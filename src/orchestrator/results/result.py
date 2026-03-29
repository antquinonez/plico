# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""PromptResult dataclass for orchestrator execution results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PromptResult:
    """Result of a prompt execution.

    Attributes:
        sequence: The prompt's sequence number.
        prompt_name: Optional name of the prompt.
        prompt: The prompt text.
        history: List of prompt names this prompt depends on.
        client: Optional client name for multi-client execution.
        condition: Optional condition expression.
        condition_result: Result of condition evaluation.
        condition_error: Error from condition evaluation.
        response: The AI-generated response.
        status: Execution status (pending, success, failed, skipped).
        attempts: Number of execution attempts.
        error: Error message if failed.
        references: Document references.
        semantic_query: Semantic search query.
        semantic_filter: Filter for semantic search.
        query_expansion: Whether to use query expansion.
        rerank: Whether to rerank results.
        batch_id: Batch identifier for batch mode.
        batch_name: Batch name for batch mode.
        agent_mode: Whether this prompt used agentic tool-call loop.
        tool_calls: List of tool call records from agentic execution.
        total_rounds: Number of rounds in the agentic loop.
        total_llm_calls: Total LLM API calls within the agentic loop.
        validation_passed: Whether the response passed validation (None if no validation).
        validation_attempts: Number of validation attempts.
        validation_critique: Last validation critique if validation failed.

    """

    sequence: int
    prompt_name: str | None = None
    prompt: str = ""
    resolved_prompt: str | None = None
    history: list[str] | None = None
    client: str | None = None
    condition: str | None = None
    condition_result: Any = None
    condition_error: str | None = None
    response: str | None = None
    status: str = "pending"
    attempts: int = 0
    error: str | None = None
    references: list[str] | None = None
    semantic_query: str | None = None
    semantic_filter: str | None = None
    query_expansion: str | None = None
    rerank: str | None = None
    batch_id: int | None = None
    batch_name: str | None = None
    agent_mode: bool = False
    tool_calls: list[dict[str, Any]] | None = None
    total_rounds: int | None = None
    total_llm_calls: int | None = None
    validation_passed: bool | None = None
    validation_attempts: int | None = None
    validation_critique: str | None = None

    VALID_STATUSES = ("pending", "success", "failed", "skipped", "max_rounds_exceeded")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        result = {
            "sequence": self.sequence,
            "prompt_name": self.prompt_name,
            "prompt": self.prompt,
            "resolved_prompt": self.resolved_prompt,
            "history": self.history,
            "client": self.client,
            "condition": self.condition,
            "condition_result": self.condition_result,
            "condition_error": self.condition_error,
            "response": self.response,
            "status": self.status,
            "attempts": self.attempts,
            "error": self.error,
            "references": self.references,
            "semantic_query": self.semantic_query,
            "semantic_filter": self.semantic_filter,
            "query_expansion": self.query_expansion,
            "rerank": self.rerank,
        }
        if self.batch_id is not None:
            result["batch_id"] = self.batch_id
        if self.batch_name is not None:
            result["batch_name"] = self.batch_name
        if self.agent_mode:
            result["agent_mode"] = self.agent_mode
            result["tool_calls"] = self.tool_calls
            result["total_rounds"] = self.total_rounds
            result["total_llm_calls"] = self.total_llm_calls
        if self.validation_passed is not None:
            result["validation_passed"] = self.validation_passed
            result["validation_attempts"] = self.validation_attempts
            result["validation_critique"] = self.validation_critique
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptResult:
        """Create from dictionary."""
        return cls(
            sequence=data.get("sequence", 0),
            prompt_name=data.get("prompt_name"),
            prompt=data.get("prompt", ""),
            resolved_prompt=data.get("resolved_prompt"),
            history=data.get("history"),
            client=data.get("client"),
            condition=data.get("condition"),
            condition_result=data.get("condition_result"),
            condition_error=data.get("condition_error"),
            response=data.get("response"),
            status=data.get("status", "pending"),
            attempts=data.get("attempts", 0),
            error=data.get("error"),
            references=data.get("references"),
            semantic_query=data.get("semantic_query"),
            semantic_filter=data.get("semantic_filter"),
            query_expansion=data.get("query_expansion"),
            rerank=data.get("rerank"),
            batch_id=data.get("batch_id"),
            batch_name=data.get("batch_name"),
            agent_mode=data.get("agent_mode", False),
            tool_calls=data.get("tool_calls"),
            total_rounds=data.get("total_rounds"),
            total_llm_calls=data.get("total_llm_calls"),
            validation_passed=data.get("validation_passed"),
            validation_attempts=data.get("validation_attempts"),
            validation_critique=data.get("validation_critique"),
        )
