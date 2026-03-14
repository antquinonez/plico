# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Batch parallel execution strategy."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..condition_evaluator import ConditionEvaluator
from ..results import ResultBuilder
from .base import ExecutionStrategy

if TYPE_CHECKING:
    from ..excel_orchestrator import ExcelOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class BatchExecutionState:
    """Tracks state during batch parallel execution."""

    success_count: int = 0
    failed_count: int = 0


class BatchParallelStrategy(ExecutionStrategy):
    """Execute batches in parallel with dependency-aware prompt execution within each batch."""

    @property
    def name(self) -> str:
        return "batch_parallel"

    def execute(self, orchestrator: ExcelOrchestrator) -> list[dict[str, Any]]:
        """Execute batches in parallel with dependency-aware prompt execution within each batch."""
        total_batches = len(orchestrator.batch_data)
        total_prompts = len(orchestrator.prompts)
        total = total_batches * total_prompts

        state = BatchExecutionState()
        results_lock = threading.Lock()

        all_results: list[dict[str, Any]] = []
        failed_batches: list[int] = []

        logger.info(
            f"Starting parallel batch execution with concurrency={orchestrator.concurrency}"
        )

        with ThreadPoolExecutor(max_workers=orchestrator.concurrency) as executor:
            futures = {}
            for batch_idx, data_row in enumerate(orchestrator.batch_data, start=1):
                future = executor.submit(
                    self._execute_batch_isolated,
                    orchestrator,
                    batch_idx,
                    data_row,
                )
                futures[future] = batch_idx

            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    batch_results = future.result()
                    with results_lock:
                        all_results.extend(batch_results)
                        state.success_count += sum(
                            1 for r in batch_results if r["status"] == "success"
                        )
                        state.failed_count += sum(
                            1 for r in batch_results if r["status"] == "failed"
                        )

                    if orchestrator.progress_callback:
                        completed = len(all_results)
                        orchestrator.progress_callback(
                            completed,
                            total,
                            state.success_count,
                            state.failed_count,
                            current_name=f"batch_{batch_idx}",
                            running=len([f for f in futures if not f.done()]),
                        )

                    batch_failed = sum(1 for r in batch_results if r["status"] == "failed")
                    if batch_failed > 0:
                        failed_batches.append(batch_idx)

                except Exception as e:
                    logger.error(f"Batch {batch_idx} failed with exception: {e}")
                    failed_batches.append(batch_idx)

        all_results.sort(key=lambda r: (r["batch_id"], r["sequence"]))

        logger.info(
            f"Parallel batch execution complete: {state.success_count} succeeded, "
            f"{state.failed_count} failed across {total_batches} batches"
        )
        if failed_batches:
            logger.warning(f"Failed batches: {failed_batches}")

        return all_results

    def _execute_batch_isolated(
        self,
        orchestrator: ExcelOrchestrator,
        batch_idx: int,
        data_row: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Execute a single batch in isolation for parallel execution."""
        batch_name = orchestrator._resolve_batch_name(data_row, batch_idx)
        batch_results: list[dict[str, Any]] = []
        batch_results_by_name: dict[str, dict[str, Any]] = {}

        for prompt in orchestrator.prompts:
            resolved_prompt = orchestrator._resolve_prompt_variables(prompt, data_row)

            max_retries = orchestrator.config.get("max_retries", 3)
            builder = ResultBuilder(resolved_prompt).with_batch(batch_idx, batch_name)

            evaluator = ConditionEvaluator(batch_results_by_name)
            should_execute, cond_error = evaluator.evaluate(resolved_prompt.get("condition") or "")
            builder.with_condition_result(should_execute, cond_error)

            if not should_execute:
                builder.as_skipped(should_execute, cond_error)
                result = builder.build_dict()
                batch_results.append(result)
                if result.get("prompt_name"):
                    batch_results_by_name[result["prompt_name"]] = result
                continue

            client_name = resolved_prompt.get("client")

            for attempt in range(1, max_retries + 1):
                builder.with_attempts(attempt)
                try:
                    ffai = orchestrator._get_isolated_ffai(client_name)

                    injected_prompt = orchestrator._inject_references(resolved_prompt)

                    response = ffai.generate_response(
                        prompt=injected_prompt,
                        prompt_name=resolved_prompt.get("prompt_name"),
                        history=resolved_prompt.get("history"),
                        model=orchestrator.config.get("model"),
                        temperature=orchestrator.config.get("temperature"),
                        max_tokens=orchestrator.config.get("max_tokens"),
                    )

                    builder.with_response(response)
                    break

                except Exception as e:
                    builder.with_error(str(e), attempt)

            result = builder.build_dict()
            batch_results.append(result)
            if result["status"] == "success" and result.get("prompt_name"):
                batch_results_by_name[result["prompt_name"]] = result

            if result["status"] == "failed":
                on_error = orchestrator.config.get("on_batch_error", "continue")
                if on_error == "stop":
                    break

        return batch_results
