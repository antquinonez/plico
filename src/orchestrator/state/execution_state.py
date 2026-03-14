# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Execution state management for parallel and batch execution."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .prompt_node import PromptNode

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionState:
    """Tracks state during parallel execution with thread-safe operations.

    This class manages the state of prompt execution including:
    - Which prompts are pending, in progress, or completed
    - Success/failure/skipped counts
    - Results indexed by sequence and name

    Attributes:
        completed: Set of completed sequence numbers.
        in_progress: Set of currently executing sequence numbers.
        pending: Dict of pending PromptNodes by sequence number.
        results: List of execution results.
        results_lock: Thread lock for result access.
        success_count: Number of successful executions.
        failed_count: Number of failed executions.
        skipped_count: Number of skipped executions.
        results_by_name: Results indexed by prompt name.
        current_name: Name of currently executing prompt.

    """

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

    def start_prompt(self, sequence: int) -> bool:
        """Mark a prompt as in-progress.

        Args:
            sequence: The prompt's sequence number.

        Returns:
            True if the prompt was started, False if already in progress or completed.

        """
        with self.results_lock:
            if sequence in self.in_progress or sequence in self.completed:
                logger.warning(
                    f"Attempted to start sequence {sequence} but already "
                    f"{'in progress' if sequence in self.in_progress else 'completed'}"
                )
                return False
            self.in_progress.add(sequence)
            logger.debug(f"Started prompt sequence {sequence}")
            return True

    def complete_prompt(
        self,
        sequence: int,
        result: dict[str, Any],
    ) -> None:
        """Mark a prompt as completed with its result.

        Args:
            sequence: The prompt's sequence number.
            result: The execution result dictionary.

        """
        with self.results_lock:
            self.in_progress.discard(sequence)
            self.completed.add(sequence)
            self.results.append(result)

            status = result.get("status", "unknown")
            if status == "success":
                self.success_count += 1
            elif status == "skipped":
                self.skipped_count += 1
            else:
                self.failed_count += 1

            if result.get("prompt_name"):
                self.results_by_name[result["prompt_name"]] = result

            self.current_name = result.get("prompt_name") or f"seq_{sequence}"
            logger.debug(f"Completed prompt sequence {sequence} with status: {status}")

    def fail_prompt(self, sequence: int, error: str) -> None:
        """Mark a prompt as failed without a full result.

        Args:
            sequence: The prompt's sequence number.
            error: Error message.

        """
        with self.results_lock:
            self.in_progress.discard(sequence)
            self.completed.add(sequence)
            self.failed_count += 1
            logger.debug(f"Failed prompt sequence {sequence}: {error}")

    def get_ready_nodes(self) -> list[PromptNode]:
        """Get all nodes that are ready to execute.

        Returns:
            List of PromptNodes whose dependencies are all completed.

        """
        with self.results_lock:
            return self._get_ready_nodes_unlocked()

    def _get_ready_nodes_unlocked(self) -> list[PromptNode]:
        """Get ready nodes without acquiring lock (internal use only)."""
        ready: list[PromptNode] = []
        for seq, node in self.pending.items():
            if (
                seq not in self.in_progress
                and seq not in self.completed
                and node.is_ready(self.completed)
            ):
                ready.append(node)
        return ready

    def has_deadlock(self) -> bool:
        """Check if execution is deadlocked.

        Returns:
            True if no prompts are ready and none are in progress.

        """
        with self.results_lock:
            if self.in_progress:
                return False
            ready = self._get_ready_nodes_unlocked()
            return len(ready) == 0 and len(self.pending) > len(self.completed)

    def is_complete(self) -> bool:
        """Check if all prompts are completed.

        Returns:
            True if all pending prompts are completed.

        """
        with self.results_lock:
            return len(self.completed) >= len(self.pending)

    def get_progress(self) -> dict[str, int]:
        """Get current progress statistics.

        Returns:
            Dictionary with total, completed, in_progress, success, failed, skipped counts.

        """
        with self.results_lock:
            return {
                "total": len(self.pending),
                "completed": len(self.completed),
                "in_progress": len(self.in_progress),
                "success": self.success_count,
                "failed": self.failed_count,
                "skipped": self.skipped_count,
            }

    def get_result_by_name(self, name: str) -> dict[str, Any] | None:
        """Get a result by prompt name.

        Args:
            name: The prompt name.

        Returns:
            The result dictionary or None if not found.

        """
        with self.results_lock:
            return self.results_by_name.get(name)

    def get_result_by_sequence(self, sequence: int) -> dict[str, Any] | None:
        """Get a result by sequence number.

        Args:
            sequence: The prompt's sequence number.

        Returns:
            The result dictionary or None if not found.

        """
        with self.results_lock:
            for result in self.results:
                if result.get("sequence") == sequence:
                    return result
            return None

    def get_sorted_results(self) -> list[dict[str, Any]]:
        """Get results sorted by sequence number.

        Returns:
            List of results sorted by sequence.

        """
        with self.results_lock:
            return sorted(self.results, key=lambda r: r.get("sequence", 0))
