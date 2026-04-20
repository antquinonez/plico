# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Typed domain models for orchestrator pipeline data shapes.

These TypedDict definitions document the dict shapes that flow through the
orchestrator pipeline. They are runtime-transparent (no behavioral change)
and serve static analysis, IDE autocomplete, and developer documentation.
"""

from __future__ import annotations

from typing import TypedDict


class PromptSpec(TypedDict, total=False):
    sequence: int
    prompt_name: str
    prompt: str
    history: list[str] | None
    notes: str | None
    client: str | None
    condition: str | None
    references: list[str] | None
    semantic_query: str | None
    semantic_filter: str | None
    query_expansion: str | None
    rerank: str | None
    agent_mode: bool
    tools: list[str] | None
    max_tool_rounds: int | None
    validation_prompt: str | None
    max_validation_retries: int | None
    abort_condition: str | None
    phase: str
    generator: bool
    _generated: bool
    _generated_by: str


class Interaction(TypedDict, total=False):
    prompt: str
    response: str
    prompt_name: str | None
    timestamp: float
    model: str | None
    history: list[str] | None


class ConfigSpec(TypedDict, total=False):
    name: str
    description: str
    client_type: str
    model: str
    api_key_env: str
    max_retries: int
    temperature: float
    max_tokens: int
    system_instructions: str
    created_at: str
    evaluation_strategy: str
    batch_mode: str
    batch_output: str
    on_batch_error: str


class DocumentSpec(TypedDict, total=False):
    reference_name: str
    common_name: str
    file_path: str
    tags: str
    chunking_strategy: str
    notes: str


class Message(TypedDict, total=False):
    role: str
    content: str
    tool_call_id: str
