# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Parallel execution strategy."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..results import ResultBuilder
from .base import ExecutionStrategy

if TYPE_CHECKING:
    from ..excel_orchestrator import ExcelOrchestrator, PromptNode

logger = logging.getLogger(__name__)


@dataclass
class ParallelExecutionState:
    """Tracks state during parallel execution."""

    completed: set[int] = field(default_factory=set)
    in_progress: set[int] = field(default_factory=set)
    pending: dict[int, PromptNode] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)
    results_lock: threading.Lock = field(default_factory=threading.Lock)
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    results_by_name: dict[str, dict[str, Any]] = field(default_factory=dict)
    current_name: str = ""


class ParallelStrategy(ExecutionStrategy):
    """Execute prompts in parallel with dependency-aware scheduling."""

    @property
    def name(self) -> str:
        return "parallel"

    def execute(self, orchestrator: ExcelOrchestrator) -> list[dict[str, Any]]:
        """Execute prompts in parallel with dependency-aware scheduling."""
        nodes = orchestrator._build_execution_graph()
        state = ParallelExecutionState(pending=dict(nodes))

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
                            if result["status"] == "success":
                                state.success_count += 1
                            elif result["status"] == "skipped":
                                state.skipped_count += 1
                            else:
                                state.failed_count += 1
                            if result.get("prompt_name"):
                                state.results_by_name[result["prompt_name"]] = result
                    except Exception as e:
                        logger.error(f"Unexpected error for sequence {seq}: {e}")
                        with state.results_lock:
                            state.completed.add(seq)
                            state.failed_count += 1
                            state.current_name = (
                                nodes[seq].prompt.get("prompt_name") or f"seq_{seq}"
                            )
                            result = (
                                ResultBuilder(nodes[seq].prompt)
                                .as_failed_exception(str(e))
                                .build_dict()
                            )
                            state.results.append(result)
                    finally:
                        state.in_progress.discard(seq)
                        update_progress()

        state.results.sort(key=lambda r: r["sequence"])

        logger.info(
            f"Parallel execution complete: {state.success_count} succeeded, "
            f"{state.failed_count} failed, {state.skipped_count} skipped"
        )
        return state.results
