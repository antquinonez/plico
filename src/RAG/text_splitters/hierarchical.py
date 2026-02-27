# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Hierarchical text chunking with parent-child relationships."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from .base import ChunkerBase, HierarchicalTextChunk

logger = logging.getLogger(__name__)


class HierarchicalChunker(ChunkerBase):
    """Hierarchical chunking with parent-child relationships.

    Creates small chunks for fine-grained retrieval while maintaining
    links to larger parent chunks for context injection.

    Args:
        chunk_size: Maximum characters per leaf chunk.
        chunk_overlap: Overlap between leaf chunks.
        metadata: Default metadata for all chunks.
        parent_chunk_size: Size of parent chunks (larger).
        max_levels: Maximum hierarchy depth.

    """

    def __init__(
        self,
        chunk_size: int = 400,
        chunk_overlap: int = 100,
        metadata: dict[str, Any] | None = None,
        parent_chunk_size: int = 1500,
        max_levels: int = 2,
    ) -> None:
        super().__init__(chunk_size, chunk_overlap, metadata)
        self.parent_chunk_size = parent_chunk_size
        self.max_levels = max_levels
        self._validate_params()

    def chunk(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[HierarchicalTextChunk]:
        """Split text into hierarchical chunks with parent-child relationships.

        Args:
            text: The text to split.
            metadata: Optional metadata to attach to each chunk.

        Returns:
            List of HierarchicalTextChunk objects with parent-child links.

        """
        if not text or not text.strip():
            return []

        merged_metadata = self._merge_metadata(metadata)
        all_chunks: list[HierarchicalTextChunk] = []

        parent_chunks = self._create_parent_chunks(text, merged_metadata)

        for parent in parent_chunks:
            parent.children = []
            child_chunks = self._create_child_chunks(
                parent.content,
                parent.start_char,
                merged_metadata,
                parent.id,
            )

            for child in child_chunks:
                child.parent_id = parent.id
                child.hierarchy_level = 1
                parent.child_ids.append(child.id)

            all_chunks.append(parent)
            all_chunks.extend(child_chunks)

        logger.debug(
            f"HierarchicalChunker: {len(all_chunks)} total chunks "
            f"({len(parent_chunks)} parents, {len(all_chunks) - len(parent_chunks)} children)"
        )
        return all_chunks

    def _create_parent_chunks(
        self,
        text: str,
        metadata: dict[str, Any],
    ) -> list[HierarchicalTextChunk]:
        """Create parent-level chunks."""
        chunks: list[HierarchicalTextChunk] = []
        start = 0

        while start < len(text):
            end = min(start + self.parent_chunk_size, len(text))

            if end < len(text):
                last_para = text.rfind("\n\n", start, end)
                last_newline = text.rfind("\n", start, end)
                last_space = text.rfind(" ", start, end)

                break_point = max(last_para, last_newline, last_space)
                if break_point > start + self.parent_chunk_size // 2:
                    end = break_point

            chunk_content = text[start:end].strip()

            if chunk_content:
                chunk_id = str(uuid.uuid4())
                chunks.append(
                    HierarchicalTextChunk(
                        content=chunk_content,
                        chunk_index=len(chunks),
                        start_char=start,
                        end_char=end,
                        metadata=metadata.copy(),
                        id=chunk_id,
                        parent_id=None,
                        child_ids=[],
                        hierarchy_level=0,
                    )
                )

            start = end
            while start < len(text) and text[start] in " \n":
                start += 1

        return chunks

    def _create_child_chunks(
        self,
        parent_text: str,
        parent_start: int,
        metadata: dict[str, Any],
        parent_id: str,
    ) -> list[HierarchicalTextChunk]:
        """Create child-level chunks within a parent."""
        chunks: list[HierarchicalTextChunk] = []
        start = 0

        while start < len(parent_text):
            end = min(start + self.chunk_size, len(parent_text))

            if end < len(parent_text):
                last_newline = parent_text.rfind("\n", start, end)
                last_space = parent_text.rfind(" ", start, end)

                break_point = max(last_newline, last_space)
                if break_point > start:
                    end = break_point

            chunk_content = parent_text[start:end].strip()

            if chunk_content:
                chunk_id = str(uuid.uuid4())
                chunks.append(
                    HierarchicalTextChunk(
                        content=chunk_content,
                        chunk_index=len(chunks),
                        start_char=parent_start + start,
                        end_char=parent_start + end,
                        metadata={
                            **metadata,
                            "parent_chunk_size": len(parent_text),
                        },
                        id=chunk_id,
                        parent_id=parent_id,
                        child_ids=[],
                        hierarchy_level=1,
                    )
                )

            if end < len(parent_text):
                overlap_start = max(0, end - self.chunk_overlap)
                start = end if overlap_start <= start else overlap_start
            else:
                start = end

        return chunks

    def get_parent_chunks(self, chunks: list[HierarchicalTextChunk]) -> list[HierarchicalTextChunk]:
        """Filter to return only parent chunks."""
        return [c for c in chunks if c.hierarchy_level == 0]

    def get_child_chunks(self, chunks: list[HierarchicalTextChunk]) -> list[HierarchicalTextChunk]:
        """Filter to return only child chunks."""
        return [c for c in chunks if c.hierarchy_level > 0]

    def get_chunks_with_parent_context(
        self,
        child_chunks: list[HierarchicalTextChunk],
        all_chunks: list[HierarchicalTextChunk],
    ) -> list[dict[str, Any]]:
        """Get child chunks with their parent context for retrieval.

        Args:
            child_chunks: Child chunks retrieved from search.
            all_chunks: All chunks (to look up parents).

        Returns:
            List of dicts with child content and parent context.

        """
        chunk_by_id = {c.id: c for c in all_chunks if hasattr(c, "id")}
        results: list[dict[str, Any]] = []

        for child in child_chunks:
            parent = None
            if child.parent_id and child.parent_id in chunk_by_id:
                parent = chunk_by_id[child.parent_id]

            results.append(
                {
                    "child": child,
                    "parent": parent,
                    "combined_content": child.content,
                    "parent_content": parent.content if parent else None,
                }
            )

        return results
