# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Cross-row synthesis for comparing and ranking batch entries.

Provides context formatting, source scope resolution, and entry sorting
for synthesis prompts that operate across batch results after scoring.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SynthesisPrompt:
    """A synthesis prompt definition."""

    sequence: int
    prompt_name: str | None
    prompt: str
    source_scope: str = "all"
    source_prompts: list[str] = field(default_factory=list)
    include_scores: bool = True
    history: list[str] | None = None
    condition: str | None = None
    client: str | None = None


class SynthesisExecutor:
    """Formats and manages synthesis context for cross-row prompts."""

    def __init__(
        self,
        max_context_chars: int = 30000,
    ) -> None:
        self.max_context_chars = max_context_chars

    def resolve_source_scope(
        self,
        scope: str,
        sorted_entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter entries based on source_scope.

        Args:
            scope: Either 'all' or 'top:N' where N is a positive integer.
            sorted_entries: Entries pre-sorted by composite_score descending.

        Returns:
            Filtered list of entries.

        Raises:
            ValueError: If scope syntax is invalid.

        """
        if scope == "all":
            return list(sorted_entries)

        match = re.match(r"^top:(\d+)$", scope.strip())
        if not match:
            raise ValueError(f"Invalid source_scope '{scope}'. Must be 'all' or 'top:N'.")

        n = int(match.group(1))
        if n <= 0:
            raise ValueError(f"top:N requires N > 0, got N={n}.")

        return sorted_entries[:n]

    def get_entry_name(self, entry: dict[str, Any]) -> str:
        """Extract display name from a batch entry result.

        Uses the first data-row column that is not a system column.
        Falls back to batch_name.

        Args:
            entry: A batch result dict.

        Returns:
            Display name string.

        """
        system_keys = {
            "id",
            "batch_name",
            "_documents",
            "_row_idx",
            "sequence",
            "prompt_name",
            "prompt",
            "resolved_prompt",
            "history",
            "client",
            "condition",
            "condition_result",
            "condition_error",
            "response",
            "status",
            "attempts",
            "error",
            "references",
            "semantic_query",
            "semantic_filter",
            "query_expansion",
            "rerank",
            "agent_mode",
            "tool_calls",
            "total_rounds",
            "total_llm_calls",
            "validation_passed",
            "validation_attempts",
            "validation_critique",
            "scores",
            "composite_score",
            "scoring_status",
            "strategy",
            "result_type",
            "batch_id",
            "_all_results",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cost_usd",
            "duration_ms",
            "condition_trace",
            "extraction_trace",
        }

        for key, value in entry.items():
            if key not in system_keys and value is not None and str(value).strip():
                return str(value).strip()

        return entry.get("batch_name", "unknown")

    def sort_entries(
        self,
        entries: list[list[dict[str, Any]]],
        scoring_criteria: list[dict[str, Any]] | None = None,
        has_scoring: bool = False,
    ) -> list[dict[str, Any]]:
        """Sort batch entries by composite_score with tiebreaking.

        Tiebreaking order (final_plan §4.9):
        1. Composite score (descending)
        2. First criteria score in scoring sheet order (descending)
        3. Second criteria, etc.
        4. batch_id (ascending)
        5. Same rank

        Args:
            entries: List of result lists, one per batch entry.
            scoring_criteria: List of scoring criteria dicts with criteria_name.
            has_scoring: Whether scoring is active.

        Returns:
            List of representative entries (first result of each batch),
            sorted by composite score.

        """
        if not entries:
            return []

        representative: list[dict[str, Any]] = []
        for batch_results in entries:
            if batch_results:
                representative.append(batch_results[0])

        if not has_scoring:
            representative.sort(key=lambda e: e.get("batch_name", ""))
            logger.warning(
                "Synthesis requested but no scoring sheet. "
                "Entries sorted alphabetically by batch_name."
            )
            return representative

        criteria_names: list[str] = []
        if scoring_criteria:
            criteria_names = [c["criteria_name"] for c in scoring_criteria]

        def sort_key(entry: dict[str, Any]) -> tuple:
            composite = entry.get("composite_score")
            primary = float(composite) if composite is not None else float("-inf")

            criteria_scores: list[float] = []
            scores_dict = entry.get("scores", {})
            if isinstance(scores_dict, dict):
                for name in criteria_names:
                    val = scores_dict.get(name)
                    criteria_scores.append(float(val) if val is not None else float("-inf"))

            batch_id = entry.get("batch_id", 0)

            return tuple([-primary] + [-s for s in criteria_scores] + [batch_id])

        representative.sort(key=sort_key)
        return representative

    def format_entry_context(
        self,
        entries: list[dict[str, Any]],
        source_prompts: list[str],
        include_scores: bool,
        strategy: str = "",
        scale_max: int = 10,
    ) -> str:
        """Format batch entries as XML context for synthesis prompts.

        Args:
            entries: Sorted, filtered batch entries.
            source_prompts: Prompt names whose responses to include.
            include_scores: Whether to include scoring breakdown.
            strategy: Evaluation strategy name for header.

        Returns:
            XML-formatted context string.

        Raises:
            ValueError: If no single entry can fit within budget.

        """
        if not entries:
            return ""

        total_count = len(entries)
        included_count = len(entries)

        per_entry_budget = self.max_context_chars // included_count

        for _ in range(included_count, 0, -1):
            per_entry_budget = self.max_context_chars // included_count
            min_content = self._min_entry_content(include_scores)
            if min_content <= per_entry_budget:
                break
            included_count -= 1
        else:
            raise ValueError(
                f"Cannot fit any entries within max_context_chars={self.max_context_chars}. "
                f"Minimum content per entry is ~{min_content} chars. "
                f"Increase max_synthesis_context_chars or reduce source_prompts."
            )

        if included_count < total_count:
            logger.warning(
                f"Reduced source_scope entries from {total_count} to "
                f"{included_count} due to context limits"
            )
            entries = entries[:included_count]

        parts: list[str] = []
        header_attrs = f' strategy="{strategy}"' if strategy else ""
        parts.append(
            f'<ENTRIES{header_attrs} total_count="{total_count}" included_count="{included_count}">'
        )

        for rank, entry in enumerate(entries, start=1):
            entry_block = self._format_single_entry(
                entry, rank, source_prompts, include_scores, per_entry_budget, scale_max
            )
            parts.append(entry_block)

        parts.append("</ENTRIES>")
        return "\n".join(parts)

    def _min_entry_content(self, include_scores: bool) -> int:
        estimate = 200
        if include_scores:
            estimate += 150
        return estimate

    def _format_single_entry(
        self,
        entry: dict[str, Any],
        rank: int,
        source_prompts: list[str],
        include_scores: bool,
        budget: int,
        scale_max: int = 10,
    ) -> str:
        name = self.get_entry_name(entry)
        composite = entry.get("composite_score")
        batch_id = entry.get("batch_id", 0)
        composite_str = f"{composite:.1f}" if composite is not None else "N/A"

        parts: list[str] = []
        parts.append(
            f'<ENTRY rank="{rank}" name="{name}" '
            f'composite_score="{composite_str}" batch_id="{batch_id}">'
        )

        used = 0

        if include_scores:
            scores_block = self._format_scores_block(entry, scale_max=scale_max)
            parts.append(scores_block)
            used += len(scores_block)

        remaining = budget - used - 50

        if remaining > 0:
            response_blocks = self._format_response_blocks(entry, source_prompts, remaining)
            for block in response_blocks:
                parts.append(block)

        parts.append("</ENTRY>")
        return "\n".join(parts)

    def _format_scores_block(self, entry: dict[str, Any], scale_max: int = 10) -> str:
        scores = entry.get("scores", {})
        if not scores or not isinstance(scores, dict):
            return "<SCORES>\nNo scores available\n</SCORES>"

        lines = ["<SCORES>"]
        for key, value in scores.items():
            if isinstance(value, int | float):
                lines.append(f"{key}: {value}/{scale_max}")
            else:
                lines.append(f"{key}: {value}")
        lines.append("</SCORES>")
        return "\n".join(lines)

    def _format_response_blocks(
        self,
        entry: dict[str, Any],
        source_prompts: list[str],
        budget: int,
    ) -> list[str]:
        blocks: list[str] = []
        used = 0
        prompt_name_tag_re = re.compile(r"[^a-zA-Z0-9_]")

        all_results = entry.get("_all_results", {})
        if not all_results:
            all_results = {}

        for prompt_name in source_prompts:
            result = all_results.get(prompt_name)
            if result is None:
                response_text = ""
            elif isinstance(result, dict):
                response_text = result.get("response", "")
            else:
                response_text = str(result)

            tag = prompt_name_tag_re.sub("_", prompt_name).upper()
            tag = re.sub(r"_+", "_", tag).strip("_")

            if not tag:
                tag = "RESPONSE"

            available = budget - used
            if available <= 20:
                break

            if not response_text:
                blocks.append(f"<{tag}>\n[no response]\n</{tag}>")
                used += len(tag) + 30
            elif len(response_text) > available:
                truncated_text = response_text[: available - 30]
                blocks.append(
                    f"<{tag}>\n{truncated_text}\n[...truncated at {available} chars...]\n</{tag}>"
                )
                used = budget
            else:
                blocks.append(f"<{tag}>\n{response_text}\n</{tag}>")
                used += len(response_text) + len(tag) + 20

        return blocks


def build_entry_results_map(
    batch_results: list[list[dict[str, Any]]],
) -> dict[int, dict[str, dict[str, Any]]]:
    """Build a mapping of batch_id to (prompt_name -> result).

    Args:
        batch_results: List of result lists, one per batch entry.

    Returns:
        Mapping of batch_id to {prompt_name: result_dict}.

    """
    entry_map: dict[int, dict[str, dict[str, Any]]] = {}
    for results in batch_results:
        if not results:
            continue
        batch_id = results[0].get("batch_id", 0)
        by_name: dict[str, dict[str, Any]] = {}
        for r in results:
            name = r.get("prompt_name")
            if name:
                by_name[name] = r
        entry_map[batch_id] = by_name
    return entry_map
