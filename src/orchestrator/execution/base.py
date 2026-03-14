# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Execution strategies for orchestrator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..excel_orchestrator import ExcelOrchestrator


class ExecutionStrategy(ABC):
    """Abstract base class for execution strategies.

    Defines the interface for different prompt execution modes.
    """

    @abstractmethod
    def execute(self, orchestrator: ExcelOrchestrator) -> list[dict[str, Any]]:
        """Execute prompts according to this strategy.

        Args:
            orchestrator: The orchestrator instance to execute with.

        Returns:
            List of result dictionaries.

        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name for logging."""
        ...
