# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Scoring rubric and aggregation for structured score extraction.

Provides classes for defining evaluation criteria, extracting numerical scores
from LLM JSON responses, resolving strategy-based weight overrides, and
computing weighted composite scores across batch results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from json_repair import loads as json_repair_loads

logger = logging.getLogger(__name__)


@dataclass
class ScoringCriteria:
    """A single scoring criterion definition."""

    criteria_name: str
    description: str
    scale_min: int = 1
    scale_max: int = 10
    weight: float = 1.0
    source_prompt: str = ""


def extract_score(response: str, criteria_name: str) -> float | None:
    """Extract a numerical score from an LLM response.

    Attempts to parse the response as JSON and find the criteria_name key
    either at the top level or nested under a 'scores' key.

    Args:
        response: The LLM response text.
        criteria_name: The key to look for in the parsed JSON.

    Returns:
        The extracted score as a float, or None if not found.

    """
    if not response:
        return None
    try:
        data = json_repair_loads(response)
        if not isinstance(data, dict):
            return None

        if criteria_name in data:
            val = data[criteria_name]
            if isinstance(val, int | float):
                return float(val)

        if "scores" in data and isinstance(data["scores"], dict):
            nested = data["scores"]
            if criteria_name in nested:
                val = nested[criteria_name]
                if isinstance(val, int | float):
                    return float(val)
    except (ValueError, TypeError):
        pass
    return None


class ScoringRubric:
    """Holds scoring criteria and provides score extraction/weighting."""

    def __init__(self, criteria: list[ScoringCriteria]) -> None:
        self.criteria = criteria
        self._criteria_by_name: dict[str, ScoringCriteria] = {c.criteria_name: c for c in criteria}

    def extract_scores(
        self, results_by_name: dict[str, dict[str, Any]], batch_name: str = ""
    ) -> tuple[dict[str, float | None], list[str], list[str]]:
        """Extract scores for all criteria from batch results.

        Args:
            results_by_name: Mapping of prompt_name to result dict.
            batch_name: Name of the batch (for logging).

        Returns:
            Tuple of (extracted_scores, skipped_criteria, failed_criteria).

        """
        extracted: dict[str, float | None] = {}
        skipped: list[str] = []
        failed: list[str] = []

        for criteria in self.criteria:
            source_result = results_by_name.get(criteria.source_prompt)
            if source_result is None or source_result.get("status") == "skipped":
                skipped.append(criteria.criteria_name)
                reason = "not found" if source_result is None else "was skipped"
                logger.info(
                    f"Criteria '{criteria.criteria_name}' skipped: "
                    f"source prompt '{criteria.source_prompt}' "
                    f"{reason} for batch '{batch_name}'"
                )
                continue

            response = source_result.get("response", "")
            score = extract_score(response, criteria.criteria_name)
            if score is not None:
                extracted[criteria.criteria_name] = score
            else:
                failed.append(criteria.criteria_name)
                logger.warning(
                    f"Failed to extract score '{criteria.criteria_name}' "
                    f"from prompt '{criteria.source_prompt}' "
                    f"for batch '{batch_name}'"
                )

        return extracted, skipped, failed

    def resolve_weights(
        self, strategy_overrides: dict[str, float] | None = None
    ) -> dict[str, float]:
        """Resolve effective weights by applying strategy overrides.

        Args:
            strategy_overrides: Mapping of criteria_name to weight multiplier
                from the selected strategy. None values use base weight.

        Returns:
            Dictionary of criteria_name to effective weight.

        """
        weights: dict[str, float] = {}
        for criteria in self.criteria:
            multiplier = 1.0
            if strategy_overrides and criteria.criteria_name in strategy_overrides:
                multiplier = strategy_overrides[criteria.criteria_name]
            weights[criteria.criteria_name] = criteria.weight * multiplier
        return weights

    def compute_composite(
        self, scores: dict[str, float | None], weights: dict[str, float]
    ) -> float | None:
        """Compute weighted average of available scores.

        Args:
            scores: Dictionary of criteria_name to score value (may include None).
            weights: Dictionary of criteria_name to effective weight.

        Returns:
            Weighted composite score, or None if no scores available.

        """
        available = {k: v for k, v in scores.items() if v is not None}
        if not available:
            return None
        total_weight = sum(weights.get(k, 1.0) for k in available)
        if total_weight == 0:
            return None
        weighted_sum = sum(scores[k] * weights.get(k, 1.0) for k in available)
        return weighted_sum / total_weight


class ScoreAggregator:
    """Orchestrates score extraction and aggregation across batch results."""

    def __init__(
        self,
        rubric: ScoringRubric,
        strategy: str,
        strategy_overrides: dict[str, float] | None = None,
        failure_threshold: float = 0.5,
    ) -> None:
        self.rubric = rubric
        self.strategy = strategy
        self.strategy_overrides = strategy_overrides or {}
        self.failure_threshold = failure_threshold
        self._weights = rubric.resolve_weights(strategy_overrides)

    def aggregate_entry(
        self,
        results_by_name: dict[str, dict[str, Any]],
        batch_name: str = "",
    ) -> dict[str, Any]:
        """Aggregate scores for a single batch entry.

        Args:
            results_by_name: Mapping of prompt_name to result dict.
            batch_name: Name of the batch entry.

        Returns:
            Dictionary with keys: scores, composite_score, scoring_status, strategy.

        """
        extracted, _skipped, failed = self.rubric.extract_scores(results_by_name, batch_name)

        if not extracted and not failed:
            return {
                "scores": {},
                "composite_score": None,
                "scoring_status": "skipped",
                "strategy": self.strategy,
            }

        if not extracted:
            return {
                "scores": {},
                "composite_score": None,
                "scoring_status": "failed",
                "strategy": self.strategy,
            }

        ratio = len(failed) / len(extracted) if extracted else 0.0

        if ratio == 0:
            scoring_status = "ok"
        elif ratio > self.failure_threshold:
            logger.error(
                f"Scoring failed for batch '{batch_name}': "
                f"{len(failed)}/{len(extracted)} criteria missing"
            )
            return {
                "scores": extracted,
                "composite_score": None,
                "scoring_status": "failed",
                "strategy": self.strategy,
            }
        else:
            scoring_status = "partial"

        composite = self.rubric.compute_composite(extracted, self._weights)

        return {
            "scores": extracted,
            "composite_score": composite,
            "scoring_status": scoring_status,
            "strategy": self.strategy,
        }

    def aggregate_batch_results(
        self, batch_results: list[list[dict[str, Any]]]
    ) -> dict[int, dict[str, Any]]:
        """Aggregate scores across all batch entries.

        Args:
            batch_results: List of result lists, one per batch entry.

        Returns:
            Mapping of batch_index to scoring result dict.

        """
        scoring_results: dict[int, dict[str, Any]] = {}
        for batch_idx, results in enumerate(batch_results):
            results_by_name = {r["prompt_name"]: r for r in results}
            batch_name = results[0].get("batch_name", f"batch_{batch_idx}") if results else ""
            scoring_results[batch_idx] = self.aggregate_entry(results_by_name, batch_name)
        return scoring_results
