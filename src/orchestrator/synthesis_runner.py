# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Synthesis runner for post-execution scoring and cross-row synthesis.

Handles score aggregation, evaluation strategy resolution, and synthesis
prompt execution. Extracted from OrchestratorBase to isolate post-execution
concerns.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..config import get_config
from .scoring import ScoreAggregator
from .synthesis import SynthesisExecutor, build_entry_results_map

logger = logging.getLogger(__name__)


def _build_synthesis_result(
    synth_prompt: dict[str, Any],
    status: str,
    evaluation_strategy: str,
    has_scoring: bool,
    response: str = "",
    resolved_prompt: str = "",
    error: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    duration_ms: float = 0.0,
) -> dict[str, Any]:
    """Build a synthesis result dictionary.

    Consolidates the duplicated result dict construction from success and
    failure paths into a single helper.

    Args:
        synth_prompt: Source synthesis prompt dictionary.
        status: "success" or "failed".
        evaluation_strategy: Active evaluation strategy name.
        has_scoring: Whether scoring is enabled.
        response: LLM response text (empty for failure).
        resolved_prompt: Full resolved prompt text (empty for failure).
        error: Error message (None for success).

    Returns:
        Result dictionary with all synthesis fields.

    """
    return {
        "sequence": synth_prompt["sequence"],
        "prompt_name": synth_prompt.get("prompt_name"),
        "prompt": synth_prompt["prompt"],
        "resolved_prompt": resolved_prompt,
        "response": response,
        "status": status,
        "attempts": 1,
        "batch_id": -1,
        "batch_name": "",
        "history": synth_prompt.get("history"),
        "condition": synth_prompt.get("condition"),
        "condition_result": None,
        "condition_error": None,
        "error": error,
        "references": None,
        "result_type": "synthesis",
        "scores": None,
        "composite_score": None,
        "scoring_status": "",
        "strategy": evaluation_strategy if has_scoring else None,
        "client": synth_prompt.get("client"),
        "agent_mode": False,
        "tool_calls": None,
        "total_rounds": None,
        "total_llm_calls": None,
        "validation_passed": None,
        "validation_attempts": None,
        "validation_critique": None,
        "semantic_query": None,
        "semantic_filter": None,
        "query_expansion": None,
        "rerank": None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "duration_ms": duration_ms,
    }


class SynthesisRunner:
    """Handles post-execution scoring aggregation and synthesis prompt execution.

    Usage:
        runner = SynthesisRunner()
        runner.aggregate_scores(orchestrator)
        runner.execute_synthesis(orchestrator)
    """

    def resolve_evaluation_strategy(self, orchestrator: Any) -> str:
        """Resolve the effective evaluation strategy.

        Resolution order:
        1. Workbook config sheet evaluation_strategy (if present and valid)
        2. config/main.yaml evaluation.default_strategy
        3. Hardcoded fallback: 'balanced'

        Args:
            orchestrator: Orchestrator instance to read config from.

        Returns:
            Strategy name string.

        """
        config_strategy = orchestrator.config.get("evaluation_strategy", "").strip()
        try:
            eval_config = get_config().evaluation
            available = eval_config.strategies if eval_config else {}
            if config_strategy and config_strategy in available:
                return config_strategy
            if eval_config and eval_config.default_strategy:
                return eval_config.default_strategy
        except Exception:
            logger.debug("Could not load evaluation config", exc_info=True)
        return "balanced"

    def aggregate_scores(self, orchestrator: Any) -> None:
        """Extract scores from batch results and compute composites.

        Mutates orchestrator.results in-place, adding scores, composite_score,
        scoring_status, strategy, and result_type fields to each batch result.

        Args:
            orchestrator: Orchestrator instance with results to score.

        """
        if not orchestrator.scoring_rubric or not orchestrator.is_batch_mode:
            return

        try:
            eval_config = get_config().evaluation
            failure_threshold = eval_config.scoring_failure_threshold if eval_config else 0.5
            strategy_overrides = {}
            if eval_config and orchestrator.evaluation_strategy in eval_config.strategies:
                strategy_overrides = eval_config.strategies[
                    orchestrator.evaluation_strategy
                ].criteria_overrides
        except Exception:
            failure_threshold = 0.5
            strategy_overrides = {}
            logger.debug("Could not load evaluation config for scoring", exc_info=True)

        aggregator = ScoreAggregator(
            rubric=orchestrator.scoring_rubric,
            strategy=orchestrator.evaluation_strategy,
            strategy_overrides=strategy_overrides,
            failure_threshold=failure_threshold,
        )

        grouped: dict[int, list[dict[str, Any]]] = {}
        for r in orchestrator.results:
            batch_id = r.get("batch_id")
            if batch_id is None:
                continue
            if batch_id not in grouped:
                grouped[batch_id] = []
            grouped[batch_id].append(r)

        for batch_id, batch_results in grouped.items():
            results_by_name = {r["prompt_name"]: r for r in batch_results}
            batch_name = (
                batch_results[0].get("batch_name", f"batch_{batch_id}") if batch_results else ""
            )
            scoring_result = aggregator.aggregate_entry(results_by_name, batch_name)

            for r in batch_results:
                r["scores"] = scoring_result["scores"]
                r["composite_score"] = scoring_result["composite_score"]
                r["scoring_status"] = scoring_result["scoring_status"]
                r["strategy"] = scoring_result["strategy"]
                r["result_type"] = "batch"

    def execute_synthesis(self, orchestrator: Any) -> None:
        """Execute synthesis prompts with cross-row batch context.

        Iterates synthesis prompts, builds context from batch results,
        resolves history dependencies, calls LLM, and appends synthesis
        results to orchestrator.results.

        Args:
            orchestrator: Orchestrator instance with results and synthesis prompts.

        """
        if not orchestrator.synthesis_prompts or not orchestrator.is_batch_mode:
            return

        try:
            eval_config = get_config().evaluation
            max_context = eval_config.max_synthesis_context_chars if eval_config else 30000
        except Exception:
            max_context = 30000
            logger.debug("Could not load evaluation config for synthesis", exc_info=True)

        executor = SynthesisExecutor(max_context_chars=max_context)

        grouped: dict[int, list[dict[str, Any]]] = {}
        for r in orchestrator.results:
            batch_id = r.get("batch_id", 0)
            if batch_id not in grouped:
                grouped[batch_id] = []
            grouped[batch_id].append(r)

        sorted_batch_ids = sorted(grouped.keys())
        batch_results_list = [grouped[bid] for bid in sorted_batch_ids]

        entry_results_map = build_entry_results_map(batch_results_list)

        criteria_list: list[dict[str, Any]] = []
        if orchestrator.scoring_rubric:
            criteria_list = [
                {"criteria_name": c.criteria_name} for c in orchestrator.scoring_rubric.criteria
            ]

        sorted_entries = executor.sort_entries(
            batch_results_list,
            scoring_criteria=criteria_list,
            has_scoring=orchestrator.has_scoring,
        )

        for entry in sorted_entries:
            bid = entry.get("batch_id", 0)
            entry["_all_results"] = entry_results_map.get(bid, {})

        orchestrator._response_context.clear()
        synthesis_results: list[dict[str, Any]] = []
        results_by_name: dict[str, dict[str, Any]] = {}

        for synth_prompt in orchestrator.synthesis_prompts:
            try:
                source_scope = synth_prompt.get("source_scope", "all")
                source_prompts = synth_prompt.get("source_prompts", [])
                include_scores = synth_prompt.get("include_scores", True)

                entries = executor.resolve_source_scope(source_scope, sorted_entries)

                scale_max = 10
                if orchestrator.scoring_rubric and orchestrator.scoring_rubric.criteria:
                    scale_max = orchestrator.scoring_rubric.criteria[0].scale_max

                context = executor.format_entry_context(
                    entries,
                    source_prompts,
                    include_scores,
                    strategy=orchestrator.evaluation_strategy if orchestrator.has_scoring else "",
                    scale_max=scale_max,
                )

                resolved_history = ""
                history_deps = synth_prompt.get("history") or []
                for dep_name in history_deps:
                    dep_result = results_by_name.get(dep_name)
                    if dep_result and dep_result.get("status") == "failed":
                        logger.warning(
                            f"Synthesis prompt '{synth_prompt.get('prompt_name')}' "
                            f"references failed prompt '{dep_name}', "
                            f"which returned empty response"
                        )
                    dep_response = dep_result.get("response", "") if dep_result else ""
                    resolved_history += f"--- {dep_name} ---\n{dep_response}\n\n"
                    if dep_result:
                        orchestrator._response_context.record_raw(dep_result)

                prompt_parts = [context]
                if resolved_history.strip():
                    prompt_parts.append(resolved_history.strip())
                prompt_parts.append(synth_prompt["prompt"])
                full_prompt = "\n\n===\n\n".join(prompt_parts)

                ffai = orchestrator._get_isolated_ffai(synth_prompt.get("client"))
                call_start = time.monotonic()
                synth_result = ffai.generate_response(
                    prompt=full_prompt,
                    prompt_name=synth_prompt.get("prompt_name"),
                )
                call_duration_ms = (time.monotonic() - call_start) * 1000

                input_tokens = synth_result.usage.input_tokens if synth_result.usage else 0
                output_tokens = synth_result.usage.output_tokens if synth_result.usage else 0
                total_tokens = synth_result.usage.total_tokens if synth_result.usage else 0
                cost_usd = synth_result.cost_usd

                result = _build_synthesis_result(
                    synth_prompt,
                    status="success",
                    evaluation_strategy=orchestrator.evaluation_strategy,
                    has_scoring=orchestrator.has_scoring,
                    response=synth_result.response,
                    resolved_prompt=full_prompt,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost_usd=cost_usd,
                    duration_ms=call_duration_ms,
                )

            except Exception as e:
                logger.error(
                    f"Synthesis prompt '{synth_prompt.get('prompt_name')}' failed: {e}",
                    exc_info=True,
                )
                result = _build_synthesis_result(
                    synth_prompt,
                    status="failed",
                    evaluation_strategy=orchestrator.evaluation_strategy,
                    has_scoring=orchestrator.has_scoring,
                    error=str(e),
                )

            synthesis_results.append(result)
            if result.get("prompt_name"):
                results_by_name[result["prompt_name"]] = result

        orchestrator.results.extend(synthesis_results)
        logger.info(f"Synthesis complete: {len(synthesis_results)} prompts executed")
