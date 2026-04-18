# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Execution plan preview for orchestrator workflows.

Builds and formats an explain plan that shows the execution DAG, dependency
edge sources (history vs. condition), and prompt metadata — all without
making any API calls.

Usage::

    from src.orchestrator.explain import build_explain_plan, format_explain

    plan = build_explain_plan(prompts)
    print(format_explain(plan))
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .graph import ExecutionGraph, build_execution_graph_with_edges


@dataclass
class LevelGroup:
    """Prompts grouped by execution level."""

    level: int
    prompts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExplainPlan:
    """Complete execution plan for display.

    Attributes:
        graph: The execution graph with edge metadata.
        levels: Prompts grouped by execution level.
        total_prompts: Total number of prompts.
        total_levels: Number of execution levels.
        has_batch: Whether batch data rows exist.
        batch_count: Number of batch rows (0 if no batch).

    """

    graph: ExecutionGraph
    levels: list[LevelGroup] = field(default_factory=list)
    total_prompts: int = 0
    total_levels: int = 0
    has_batch: bool = False
    batch_count: int = 0


def build_explain_plan(
    prompts: list[dict[str, Any]],
    *,
    batch_data: list[dict[str, Any]] | None = None,
) -> ExplainPlan:
    """Build an explain plan from prompt declarations.

    Args:
        prompts: List of prompt dictionaries.
        batch_data: Optional batch data rows.

    Returns:
        ExplainPlan with DAG, edges, and grouped levels.

    """
    graph = build_execution_graph_with_edges(prompts)

    levels_map: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for _seq, node in sorted(graph.nodes.items()):
        levels_map[node.level].append(node.prompt)

    levels = [LevelGroup(level=lvl, prompts=levels_map[lvl]) for lvl in sorted(levels_map)]

    batch_count = len(batch_data) if batch_data else 0

    return ExplainPlan(
        graph=graph,
        levels=levels,
        total_prompts=len(prompts),
        total_levels=len(levels),
        has_batch=batch_count > 0,
        batch_count=batch_count,
    )


def _seq_to_name(nodes: dict[int, Any], seq: int) -> str:
    """Look up a prompt name by sequence number."""
    node = nodes.get(seq)
    if node is None:
        return f"seq_{seq}"
    return node.prompt.get("prompt_name") or f"seq_{seq}"


def format_explain(
    plan: ExplainPlan,
    *,
    title: str = "",
    concurrency: int = 1,
) -> str:
    """Format an explain plan as a human-readable string.

    Args:
        plan: The explain plan to format.
        title: Optional title (e.g., workbook filename).
        concurrency: Concurrency setting for the run.

    Returns:
        Formatted string suitable for terminal output.

    """
    lines: list[str] = []

    header = title or "Execution Plan"
    lines.append(f"\n{'═' * 60}")
    lines.append(f"  {header}")
    lines.append(f"{'═' * 60}")

    parts = [f"Prompts: {plan.total_prompts}"]
    parts.append(f"Levels: {plan.total_levels}")
    if plan.has_batch:
        parts.append(f"Batch rows: {plan.batch_count}")
    parts.append(f"Concurrency: {concurrency}")
    lines.append("  " + "  |  ".join(parts))
    lines.append("")

    lines.append(_format_dag(plan))
    lines.append("")
    lines.append(_format_edges(plan))

    cost_lines = _format_cost_estimate(plan)
    if cost_lines:
        lines.append("")
        lines.append(cost_lines)

    return "\n".join(lines)


def _format_dag(plan: ExplainPlan) -> str:
    """Format the execution DAG grouped by levels."""
    lines: list[str] = []
    lines.append("─── Execution DAG ───")
    lines.append("")

    for level_group in plan.levels:
        lvl = level_group.level
        if lvl == 0:
            label = "Level 0 (independent, runs first)"
        else:
            label = f"Level {lvl} (depends on Level {lvl - 1}+)"

        lines.append(f"  {label}")
        lines.append(f"  {'─' * 50}")

        for p in level_group.prompts:
            seq = p.get("sequence", "?")
            name = p.get("prompt_name") or "(unnamed)"

            annotations: list[str] = []

            hist = p.get("history") or []
            if hist:
                annotations.append(f"hist: {', '.join(hist)}")

            refs = p.get("references") or []
            if refs:
                ref_names = [r if isinstance(r, str) else str(r) for r in refs]
                annotations.append(f"refs: {', '.join(ref_names)}")

            client = p.get("client")
            if client:
                annotations.append(f"client: {client}")

            condition = p.get("condition")
            if condition:
                cond_str = str(condition)
                if len(cond_str) > 50:
                    cond_str = cond_str[:47] + "..."
                annotations.append(f"cond: {cond_str}")

            agent = p.get("agent_mode")
            if agent:
                tools = p.get("tools") or []
                annotations.append(f"agent [{', '.join(tools) if tools else 'no tools'}]")

            phase = p.get("phase")
            if phase:
                annotations.append(f"phase: {phase}")

            ann_str = f"  →  {'  |  '.join(annotations)}" if annotations else ""
            lines.append(f"    Seq {seq:>3}  {name}{ann_str}")

        lines.append("")

    return "\n".join(lines)


def _format_edges(plan: ExplainPlan) -> str:
    """Format dependency edges with source annotations."""
    import re

    lines: list[str] = []
    lines.append("─── Dependency Edges ───")

    edges = plan.graph.edges
    nodes = plan.graph.nodes
    if not edges:
        lines.append("  (no dependencies)")
        return "\n".join(lines)

    history_edges = [e for e in edges if e.source == "history"]
    condition_edges = [e for e in edges if e.source == "condition"]

    if history_edges:
        lines.append("")
        for edge in history_edges:
            from_name = _seq_to_name(nodes, edge.from_seq)
            to_name = _seq_to_name(nodes, edge.to_seq)
            lines.append(f"  {from_name} → {to_name}  [history]")

    if condition_edges:
        lines.append("")
        var_pattern = re.compile(r"\{\{(\w+\.\w+)\}\}")
        for edge in condition_edges:
            from_name = _seq_to_name(nodes, edge.from_seq)
            to_name = _seq_to_name(nodes, edge.to_seq)
            cond = edge.condition_text or ""
            if len(cond) > 60:
                cond = cond[:57] + "..."
            lines.append(f"  {from_name} → {to_name}  [condition] ⚠")
            lines.append(f"    condition: {cond}")
            refs = var_pattern.findall(cond)
            if refs:
                ref_str = ", ".join(f"{{{{{r}}}}}" for r in refs)
                lines.append(f'    references: {ref_str} → prompt "{from_name}"')
            else:
                lines.append(f'    references prompt "{from_name}" via condition')

    return "\n".join(lines)


def format_prompt_preview(
    prompt: dict[str, Any],
    *,
    batch_row: dict[str, Any] | None = None,
    upstream_results: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Format a resolved prompt preview for a single prompt.

    Simulates variable substitution and shows the prompt as the LLM would
    receive it — including batch variable resolution, upstream response
    references, and history context structure. No API calls are made.

    Args:
        prompt: The prompt dictionary.
        batch_row: Optional batch data row for variable substitution.
        upstream_results: Optional mapping of prompt_name to result dicts
            for resolving {{name.property}} references.

    Returns:
        Formatted string showing the resolved prompt.

    """
    import re

    lines: list[str] = []
    name = prompt.get("prompt_name") or "(unnamed)"
    seq = prompt.get("sequence", "?")
    lines.append(f"\n{'═' * 60}")
    lines.append(f"  Resolved Prompt: {name} (seq {seq})")
    lines.append(f"{'═' * 60}")

    raw_prompt = str(prompt.get("prompt", ""))

    resolved = raw_prompt

    if batch_row:
        for key, value in batch_row.items():
            if key in ("id", "batch_name", "_documents"):
                continue
            resolved = resolved.replace(f"{{{{{key}}}}}", str(value))

        lines.append("")
        lines.append("── Template Variables ──")
        for key, value in batch_row.items():
            if key in ("id", "batch_name", "_documents"):
                continue
            lines.append(f"  {{{{{key}}}}}  →  {value}")
        unresolved = re.findall(r"\{\{(\w+)\}\}", resolved)
        if unresolved:
            lines.append(f"  ⚠ Unresolved: {', '.join(set(unresolved))}")

    name_prop_pattern = re.compile(r"\{\{(\w+)\.(\w+)\}\}")
    name_refs = name_prop_pattern.findall(resolved)
    if name_refs and upstream_results:
        lines.append("")
        lines.append("── Upstream References ──")
        for ref_name, prop in name_refs:
            result = upstream_results.get(ref_name, {})
            value = result.get(prop, "<not yet executed>")
            display = str(value)
            if len(display) > 80:
                display = display[:77] + "..."
            lines.append(f"  {{{{{ref_name}.{prop}}}}}  →  {display}")

    history = prompt.get("history") or []
    if history:
        lines.append("")
        lines.append("── History Context ──")
        for hist_name in history:
            if upstream_results and hist_name in upstream_results:
                resp = upstream_results[hist_name].get("response", "")
                preview = resp[:100] + "..." if len(resp) > 100 else resp
                lines.append(f"  <interaction prompt_name='{hist_name}'>")
                lines.append(f"    SYSTEM: {preview}")
                lines.append("  </interaction>")
            else:
                lines.append(
                    f"  <interaction prompt_name='{hist_name}'>"
                    f"  (result not yet available)"
                    f"  </interaction>"
                )

    refs = prompt.get("references") or []
    if refs:
        lines.append("")
        lines.append("── Injected Document References ──")
        for ref in refs:
            ref_name = ref if isinstance(ref, str) else str(ref)
            lines.append(f"  [{ref_name}] (content injected at runtime)")

    lines.append("")
    lines.append("── Final Prompt ──")
    lines.append("")
    final = resolved
    if len(final) > 500:
        lines.append(final[:500])
        lines.append(f"... ({len(final) - 500} more characters)")
    else:
        lines.append(final)

    lines.append("")
    lines.append("  No API call made. This is a preview only.")

    return "\n".join(lines)


def _format_cost_estimate(plan: ExplainPlan) -> str:
    """Format a static cost estimate."""
    total_calls = plan.total_prompts
    if plan.has_batch:
        total_calls = plan.total_prompts * plan.batch_count

    lines: list[str] = []
    lines.append("─── Cost Estimate ───")
    lines.append("")

    if plan.has_batch:
        lines.append(
            f"  {plan.total_prompts} prompts × {plan.batch_count} batch rows "
            f"= {total_calls} LLM calls"
        )
    else:
        lines.append(f"  {plan.total_prompts} prompts = {total_calls} LLM calls")

    prompt_chars = sum(
        len(str(p.get("prompt", ""))) for p in [n.prompt for n in plan.graph.nodes.values()]
    )
    avg_chars = prompt_chars // max(plan.total_prompts, 1)
    est_tokens = (avg_chars // 4) * total_calls

    lines.append(f"  Estimated input tokens: ~{est_tokens:,}")
    lines.append(f"  (based on avg {avg_chars} chars/prompt)")
    lines.append("")
    lines.append("  No API calls made. Run with full execution for actual costs.")

    return "\n".join(lines)
