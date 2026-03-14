# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Batch sequential execution strategy."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .base import ExecutionStrategy

if TYPE_CHECKING:
    from ..excel_orchestrator import ExcelOrchestrator

logger = logging.getLogger(__name__)


class BatchSequentialStrategy(ExecutionStrategy):
    """Execute all prompts for each batch row sequentially."""

    @property
    def name(self) -> str:
        return "batch_sequential"

    def execute(self, orchestrator: ExcelOrchestrator) -> list[dict[str, Any]]:
        """Execute all prompts for each batch row sequentially."""
        results: list[dict[str, Any]] = []
        total_batches = len(orchestrator.batch_data)
        total_prompts = len(orchestrator.prompts)
        total = total_batches * total_prompts

        for batch_idx, data_row in enumerate(orchestrator.batch_data, start=1):
            batch_name = orchestrator._resolve_batch_name(data_row, batch_idx)
            logger.info(f"Starting batch {batch_idx}/{total_batches}: {batch_name}")

            batch_results = orchestrator._execute_single_batch(batch_idx, data_row, batch_name)
            results.extend(batch_results)

            batch_failed = sum(1 for r in batch_results if r["status"] == "failed")
            if batch_failed > 0:
                on_error = orchestrator.config.get("on_batch_error", "continue")
                if on_error == "stop":
                    logger.error(f"Stopping at batch {batch_idx} due to {batch_failed} failures")
                    break

            if orchestrator.progress_callback:
                completed = len(results)
                success = sum(1 for r in results if r["status"] == "success")
                failed = sum(1 for r in results if r["status"] == "failed")
                orchestrator.progress_callback(
                    completed,
                    total,
                    success,
                    failed,
                    current_name=f"batch_{batch_idx}",
                    running=1,
                )

        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        logger.info(
            f"Batch execution complete: {successful} succeeded, {failed} failed, {skipped} skipped"
        )
        return results
