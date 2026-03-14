# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Factory for execution strategies."""

from .base import ExecutionStrategy
from .batch_parallel import BatchParallelStrategy
from .batch_sequential import BatchSequentialStrategy
from .parallel import ParallelStrategy
from .sequential import SequentialStrategy


def get_execution_strategy(is_batch_mode: bool, concurrency: int) -> ExecutionStrategy:
    """Select the appropriate execution strategy.

    Args:
        is_batch_mode: Whether batch mode is enabled.
        concurrency: Maximum concurrent executions.

    Returns:
        The appropriate ExecutionStrategy instance.

    """
    if is_batch_mode:
        if concurrency > 1:
            return BatchParallelStrategy()
        return BatchSequentialStrategy()
    else:
        if concurrency > 1:
            return ParallelStrategy()
        return SequentialStrategy()


__all__ = [
    "ExecutionStrategy",
    "SequentialStrategy",
    "ParallelStrategy",
    "BatchSequentialStrategy",
    "BatchParallelStrategy",
    "get_execution_strategy",
]
