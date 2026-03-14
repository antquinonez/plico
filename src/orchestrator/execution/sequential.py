# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Sequential execution strategy."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .base import ExecutionStrategy

if TYPE_CHECKING:
    from ..excel_orchestrator import ExcelOrchestrator

logger = logging.getLogger(__name__)


class SequentialStrategy(ExecutionStrategy):
    """Execute prompts sequentially with dependency-aware ordering."""

    @property
    def name(self) -> str:
        return "sequential"

    def execute(self, orchestrator: ExcelOrchestrator) -> list[dict[str, Any]]:
        """Execute all prompts in sequence with dependency-aware ordering."""
        results: list[dict[str, Any]] = []
        results_by_name: dict[str, dict[str, Any]] = {}
        total = len(orchestrator.prompts)

        nodes = orchestrator._build_execution_graph()
        sorted_prompts = sorted(
            orchestrator.prompts, key=lambda p: (nodes[p["sequence"]].level, p["sequence"])
        )

        for prompt in sorted_prompts:
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

            if result.get("prompt_name"):
                results_by_name[result["prompt_name"]] = result

        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        skipped = sum(1 for r in results if r["status"] == "skipped")

        if orchestrator.progress_callback:
            orchestrator.progress_callback(
                total,
                total,
                successful,
                failed,
                current_name=None,
                running=0,
            )

        logger.info(
            f"Execution complete: {successful} succeeded, {failed} failed, {skipped} skipped"
        )
        return results
