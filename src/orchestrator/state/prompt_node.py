# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""PromptNode for execution dependency graph."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import PromptSpec


@dataclass
class PromptNode:
    """Represents a prompt in the execution dependency graph.

    Attributes:
        sequence: The prompt's sequence number.
        prompt: The prompt dictionary.
        dependencies: Set of sequence numbers this prompt depends on.
        level: The execution level (0 = no dependencies).

    """

    sequence: int
    prompt: PromptSpec
    dependencies: set[int] = field(default_factory=set)
    level: int = 0

    def __hash__(self) -> int:
        """Make PromptNode hashable by sequence."""
        return hash(self.sequence)

    def __eq__(self, other: object) -> bool:
        """Compare by sequence number."""
        if not isinstance(other, PromptNode):
            return NotImplemented
        return self.sequence == other.sequence

    def is_ready(self, completed: set[int]) -> bool:
        """Check if this node is ready to execute.

        Args:
            completed: Set of completed sequence numbers.

        Returns:
            True if all dependencies are completed.

        """
        return self.dependencies.issubset(completed)

    def add_dependency(self, sequence: int) -> None:
        """Add a dependency to this node.

        Args:
            sequence: Sequence number of the dependency.

        """
        self.dependencies.add(sequence)

    def get_prompt_name(self) -> str | None:
        """Get the prompt name if available.

        Returns:
            The prompt name or None.

        """
        return self.prompt.get("prompt_name")
