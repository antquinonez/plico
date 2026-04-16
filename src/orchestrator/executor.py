# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Executor for orchestrator execution modes.

This module provides a single Executor class that handles all four execution
modes (sequential, parallel, batch, batch_parallel) for both ExcelOrchestrator
and ManifestOrchestrator, eliminating duplicate code.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .results import ResultBuilder
from .state import ExecutionState, PromptNode

logger = logging.getLogger(__name__)


class Executor:
    """Handles all execution modes for orchestrators.

    This class provides four execution methods that can be called by
    either ExcelOrchestrator or ManifestOrchestrator, eliminating
    duplicate execution logic.

    Usage:
        executor = Executor()

        # Sequential execution
        results = executor.execute_sequential(orchestrator)

        # Parallel execution with dependencies
        results = executor.execute_parallel(orchestrator)

        # Batch execution (sequential batches)
        results = executor.execute_batch(orchestrator)

        # Parallel batch execution
        results = executor.execute_batch_parallel(orchestrator)
    """

    def execute_sequential(self, orchestrator: Any) -> list[dict[str, Any]]:
        """Execute all prompts in sequence with dependency-aware ordering.

        Args:
            orchestrator: Orchestrator instance with prompts, config, etc.

        Returns:
            List of result dictionaries.

        """
        results: list[dict[str, Any]] = []
        results_by_name: dict[str, dict[str, Any]] = {}
        total = len(orchestrator.prompts)

        nodes = orchestrator._build_execution_graph()
        ready = [node for node in nodes.values() if not node.dependencies]
        ready.sort(key=lambda n: (n.level, n.sequence))
        executed: set[int] = set()

        while ready:
            node = ready.pop(0)
            if node.sequence in executed:
                continue
            prompt = node.prompt
            if orchestrator.progress_callback:
                orchestrator.progress_callback(
                    len(results),
                    total,
                    sum(1 for r in results if r["status"] == "success"),
                    sum(1 for r in results if r["status"] == "failed"),
                    current_name=prompt.get("prompt_name"),
                    running=1,
                )

            result = orchestrator._execute_prompt(prompt, results_by_name)
            results.append(result)
            executed.add(node.sequence)

            if result.get("prompt_name"):
                results_by_name[result["prompt_name"]] = result

            for candidate in nodes.values():
                if candidate.sequence in executed:
                    continue
                if candidate.sequence in {n.sequence for n in ready}:
                    continue
                if candidate.dependencies.issubset(executed):
                    ready.append(candidate)

            ready.sort(key=lambda n: (n.level, n.sequence))

        self._log_completion(results, "Execution")

        if orchestrator.progress_callback:
            orchestrator.progress_callback(
                total,
                total,
                sum(1 for r in results if r["status"] == "success"),
                sum(1 for r in results if r["status"] == "failed"),
                current_name=None,
                running=0,
            )

        return results

    def execute_parallel(self, orchestrator: Any) -> list[dict[str, Any]]:
        """Execute prompts in parallel with dependency-aware scheduling.

        Args:
            orchestrator: Orchestrator instance with prompts, config, etc.

        Returns:
            List of result dictionaries sorted by sequence.

        """
        nodes = orchestrator._build_execution_graph()
        state = ExecutionState(pending=dict(nodes))
        total = len(nodes)

        def update_progress() -> None:
            if orchestrator.progress_callback:
                orchestrator.progress_callback(
                    len(state.completed),
                    total,
                    state.success_count,
                    state.failed_count,
                    current_name=state.current_name,
                    running=len(state.in_progress),
                )

        logger.info(f"Starting parallel execution with concurrency={orchestrator.concurrency}")

        with ThreadPoolExecutor(max_workers=orchestrator.concurrency) as executor:
            while len(state.completed) < total:
                ready = orchestrator._get_ready_prompts(state, nodes)

                if not ready and not state.in_progress:
                    logger.error("Deadlock detected: no ready prompts and none in progress")
                    break

                futures = {}
                for node in ready:
                    if len(state.in_progress) >= orchestrator.concurrency:
                        break
                    state.in_progress.add(node.sequence)
                    future = executor.submit(
                        orchestrator._execute_prompt_isolated, node.prompt, state
                    )
                    futures[future] = node.sequence

                for future in as_completed(futures):
                    seq = futures[future]
                    try:
                        result = future.result()
                        with state.results_lock:
                            state.results.append(result)
                            state.completed.add(seq)
                            state.current_name = result.get("prompt_name") or f"seq_{seq}"
                            self._update_state_counts(state, result)
                            if result.get("prompt_name"):
                                state.results_by_name[result["prompt_name"]] = result
                    except Exception as e:
                        logger.error(f"Unexpected error for sequence {seq}: {e}")
                        self._handle_execution_error(state, nodes[seq], str(e))
                    finally:
                        state.in_progress.discard(seq)
                        update_progress()

        state.results.sort(key=lambda r: r["sequence"])

        logger.info(
            f"Parallel execution complete: {state.success_count} succeeded, "
            f"{state.failed_count} failed, {state.skipped_count} skipped"
        )

        return state.results

    def execute_batch(self, orchestrator: Any) -> list[dict[str, Any]]:
        """Execute all prompts for each batch row sequentially.

        Args:
            orchestrator: Orchestrator instance with prompts, batch_data, etc.

        Returns:
            List of result dictionaries for all batches.

        """
        results: list[dict[str, Any]] = []
        total_batches = len(orchestrator.batch_data)
        total_prompts = len(orchestrator.prompts)
        total = total_batches * total_prompts

        for batch_idx, data_row in enumerate(orchestrator.batch_data, start=1):
            batch_name = orchestrator._resolve_batch_name(data_row, batch_idx)
            batch_history: list[dict[str, Any]] = list(orchestrator.shared_prompt_attr_history)
            batch_history_lock = threading.Lock()
            logger.info(f"Starting batch {batch_idx}/{total_batches}: {batch_name}")

            batch_results = orchestrator._execute_single_batch(
                batch_idx,
                data_row,
                batch_name,
                batch_history=batch_history,
                batch_history_lock=batch_history_lock,
            )
            results.extend(batch_results)

            batch_failed = sum(1 for r in batch_results if r["status"] == "failed")
            if batch_failed > 0:
                on_error = orchestrator.config.get("on_batch_error", "continue")
                if on_error == "stop":
                    logger.error(f"Stopping at batch {batch_idx} due to {batch_failed} failures")
                    break

            if orchestrator.progress_callback:
                orchestrator.progress_callback(
                    len(results),
                    total,
                    sum(1 for r in results if r["status"] == "success"),
                    sum(1 for r in results if r["status"] == "failed"),
                    current_name=f"batch_{batch_idx}",
                    running=1,
                )

        self._log_completion(results, "Batch execution")

        return results

    def execute_batch_parallel(self, orchestrator: Any) -> list[dict[str, Any]]:
        """Execute batches in parallel with sequential prompts within each batch.

        Args:
            orchestrator: Orchestrator instance with prompts, batch_data, etc.

        Returns:
            List of result dictionaries sorted by (batch_id, sequence).

        """
        total_batches = len(orchestrator.batch_data)
        total_prompts = len(orchestrator.prompts)
        total = total_batches * total_prompts

        state = ExecutionState()
        results_lock = threading.Lock()
        all_results: list[dict[str, Any]] = []
        failed_batches: list[int] = []
        base_history_snapshot: list[dict[str, Any]] = list(orchestrator.shared_prompt_attr_history)

        def execute_single_batch(batch_idx: int, data_row: dict[str, Any]) -> list[dict[str, Any]]:
            """Execute all prompts for a single batch (runs in thread)."""
            batch_name = orchestrator._resolve_batch_name(data_row, batch_idx)
            batch_results: list[dict[str, Any]] = []
            batch_results_by_name: dict[str, dict[str, Any]] = {}
            batch_history: list[dict[str, Any]] = list(base_history_snapshot)
            batch_history_lock = threading.Lock()

            for prompt in orchestrator.prompts:
                resolved_prompt = orchestrator._resolve_prompt_variables(prompt, data_row)

                result = orchestrator._execute_prompt_with_batch(
                    resolved_prompt,
                    batch_idx,
                    batch_name,
                    batch_results_by_name,
                    batch_history=batch_history,
                    batch_history_lock=batch_history_lock,
                )
                batch_results.append(result)

                if result.get("prompt_name"):
                    batch_results_by_name[result["prompt_name"]] = result

                if result["status"] == "failed":
                    on_error = orchestrator.config.get("on_batch_error", "continue")
                    if on_error == "stop":
                        break

            return batch_results

        logger.info(
            f"Starting parallel batch execution with concurrency={orchestrator.concurrency}"
        )

        with ThreadPoolExecutor(max_workers=orchestrator.concurrency) as executor:
            futures = {}
            for batch_idx, data_row in enumerate(orchestrator.batch_data, start=1):
                future = executor.submit(execute_single_batch, batch_idx, data_row)
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
                        orchestrator.progress_callback(
                            len(all_results),
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

    def _update_state_counts(self, state: ExecutionState, result: dict[str, Any]) -> None:
        """Update state counters based on result status."""
        if result["status"] == "success":
            state.success_count += 1
        elif result["status"] == "skipped":
            state.skipped_count += 1
        else:
            state.failed_count += 1

    def _handle_execution_error(self, state: ExecutionState, node: PromptNode, error: str) -> None:
        """Handle an exception during parallel execution."""
        with state.results_lock:
            state.completed.add(node.sequence)
            state.failed_count += 1
            state.current_name = node.prompt.get("prompt_name") or f"seq_{node.sequence}"
            result = ResultBuilder(node.prompt).as_failed_exception(error).build_dict()
            state.results.append(result)

    def _log_completion(self, results: list[dict[str, Any]], prefix: str) -> None:
        """Log execution completion summary."""
        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        logger.info(
            f"{prefix} complete: {successful} succeeded, {failed} failed, {skipped} skipped"
        )
