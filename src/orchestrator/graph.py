# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Dependency graph construction and condition evaluation for orchestrator.

Pure functions for building execution dependency graphs from prompt lists,
determining which prompts are ready for execution, and evaluating prompt
conditions.
"""

from __future__ import annotations

from typing import Any

from .condition_evaluator import ConditionEvaluator
from .state import ExecutionState, PromptNode


def build_execution_graph(prompts: list[dict[str, Any]]) -> dict[int, PromptNode]:
    """Build dependency graph for parallel execution.

    Args:
        prompts: List of prompt dictionaries with sequence, prompt_name,
            history, and condition fields.

    Returns:
        Dictionary mapping sequence numbers to PromptNodes.

    Raises:
        ValueError: If a dependency cycle is detected.

    """
    nodes: dict[int, PromptNode] = {}
    prompt_by_name: dict[str, int] = {}

    for prompt in prompts:
        seq = prompt["sequence"]
        nodes[seq] = PromptNode(sequence=seq, prompt=prompt)
        name = prompt.get("prompt_name")
        if name:
            prompt_by_name[name] = seq

    for prompt in prompts:
        seq = prompt["sequence"]
        history = prompt.get("history") or []
        for dep_name in history:
            if dep_name in prompt_by_name:
                nodes[seq].dependencies.add(prompt_by_name[dep_name])

        condition = prompt.get("condition") or ""
        for dep_name, _ in ConditionEvaluator.extract_referenced_names(condition):
            if dep_name in prompt_by_name:
                nodes[seq].dependencies.add(prompt_by_name[dep_name])

    level_cache: dict[int, int] = {}

    def assign_levels(seq: int, path: set[int]) -> int:
        if seq in level_cache:
            return level_cache[seq]
        if seq in path:
            cycle_seqs = sorted(path | {seq})
            raise ValueError(f"Dependency cycle detected involving sequences: {cycle_seqs}")
        path.add(seq)
        if not nodes[seq].dependencies:
            nodes[seq].level = 0
            level_cache[seq] = 0
            return 0
        max_dep_level = max(assign_levels(dep, path) for dep in nodes[seq].dependencies)
        nodes[seq].level = max_dep_level + 1
        level_cache[seq] = nodes[seq].level
        path.discard(seq)
        return nodes[seq].level

    for seq in nodes:
        assign_levels(seq, set())

    return nodes


def get_ready_prompts(state: ExecutionState, nodes: dict[int, PromptNode]) -> list[PromptNode]:
    """Get prompts ready for execution (all dependencies completed).

    Args:
        state: Current execution state.
        nodes: Execution graph nodes.

    Returns:
        List of PromptNodes ready for execution, sorted by level and sequence.

    """
    ready: list[PromptNode] = []
    for seq, node in nodes.items():
        if seq in state.completed or seq in state.in_progress:
            continue
        if node.dependencies.issubset(state.completed):
            ready.append(node)
    ready.sort(key=lambda n: (n.level, n.sequence))
    return ready


def evaluate_condition(
    prompt: dict[str, Any],
    results_by_name: dict[str, dict[str, Any]],
) -> tuple[bool, str | None, str | None]:
    """Evaluate a prompt's condition.

    Args:
        prompt: Prompt dictionary with optional condition.
        results_by_name: Results indexed by prompt_name.

    Returns:
        Tuple of (should_execute, condition_result, condition_error).

    """
    condition = prompt.get("condition")

    if not condition or not str(condition).strip():
        return True, None, None

    evaluator = ConditionEvaluator(results_by_name)
    result, error = evaluator.evaluate(str(condition))

    return result, result, error
