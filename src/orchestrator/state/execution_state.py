# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Execution state management for parallel and batch execution."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from .prompt_node import PromptNode


@dataclass
class ExecutionState:
    """Tracks state during parallel execution with thread-safe operations.

    Attributes:
        completed: Set of completed sequence numbers.
        in_progress: Set of currently executing sequence numbers.
        pending: Dict of pending PromptNodes by sequence number.
        results: List of execution results.
        results_lock: Thread lock for result access.
        success_count: Number of successful executions.
        failed_count: Number of failed executions.
        skipped_count: Number of skipped executions.
        aborted_count: Number of aborted executions.
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
    aborted_count: int = 0
    results_by_name: dict[str, dict[str, Any]] = field(default_factory=dict)
    current_name: str = ""
    aborted: bool = False
