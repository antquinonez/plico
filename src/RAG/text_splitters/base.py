# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Base classes for text chunking strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""

    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict[str, Any] | None = None


@dataclass
class HierarchicalTextChunk(TextChunk):
    """Text chunk with hierarchical parent-child relationships."""

    id: str = ""
    parent_id: str | None = None
    child_ids: list[str] | None = None
    hierarchy_level: int = 0

    def __post_init__(self) -> None:
        if self.child_ids is None:
            self.child_ids = []
        if self.metadata is None:
            self.metadata = {}


class ChunkerBase(ABC):
    """Abstract base class for text chunking strategies.

    All chunkers must implement the chunk() method that splits text
    into TextChunk objects.

    Args:
        chunk_size: Maximum size of each chunk (interpretation varies by strategy).
        chunk_overlap: Overlap between consecutive chunks.
        metadata: Default metadata to attach to all chunks.

    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.default_metadata = metadata or {}

    @abstractmethod
    def chunk(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Split text into chunks.

        Args:
            text: The text to split.
            metadata: Optional metadata to attach to each chunk (merged with default).

        Returns:
            List of TextChunk objects.

        """
        pass

    def _merge_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        """Merge provided metadata with default metadata."""
        merged = self.default_metadata.copy()
        if metadata:
            merged.update(metadata)
        return merged

    def _validate_params(self) -> None:
        """Validate chunker parameters."""
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

    @property
    def name(self) -> str:
        """Return the chunker strategy name."""
        return self.__class__.__name__.replace("Chunker", "").lower()
