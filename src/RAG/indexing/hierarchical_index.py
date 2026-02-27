# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Hierarchical index for parent-child chunk retrieval."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class HierarchicalIndex:
    """Index for hierarchical chunk storage and retrieval.

    Stores both parent and child chunks, enabling:
    - Fine-grained search on child chunks
    - Parent context retrieval for matched children

    Args:
        include_parent_context: Whether to include parent content in results.

    """

    def __init__(
        self,
        include_parent_context: bool = True,
    ) -> None:
        self.include_parent_context = include_parent_context

        self._chunks: dict[str, dict[str, Any]] = {}
        self._parent_to_children: dict[str, list[str]] = {}
        self._child_to_parent: dict[str, str] = {}

    def add_chunk(
        self,
        chunk_id: str,
        content: str,
        embedding: list[float] | None = None,
        parent_id: str | None = None,
        hierarchy_level: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a chunk to the hierarchical index.

        Args:
            chunk_id: Unique chunk identifier.
            content: Chunk text content.
            embedding: Chunk embedding vector (optional).
            parent_id: Parent chunk ID (None for root/parent chunks).
            hierarchy_level: Level in hierarchy (0=parent, 1+=children).
            metadata: Optional metadata dictionary.

        """
        self._chunks[chunk_id] = {
            "id": chunk_id,
            "content": content,
            "embedding": embedding,
            "parent_id": parent_id,
            "hierarchy_level": hierarchy_level,
            "metadata": metadata or {},
        }

        if parent_id:
            self._child_to_parent[chunk_id] = parent_id
            if parent_id not in self._parent_to_children:
                self._parent_to_children[parent_id] = []
            self._parent_to_children[parent_id].append(chunk_id)
        else:
            if chunk_id not in self._parent_to_children:
                self._parent_to_children[chunk_id] = []

        logger.debug(f"Added chunk {chunk_id} to hierarchical index (level={hierarchy_level})")

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        """Get a chunk by ID.

        Args:
            chunk_id: Chunk identifier.

        Returns:
            Chunk data dictionary or None if not found.

        """
        return self._chunks.get(chunk_id)

    def get_parent(self, chunk_id: str) -> dict[str, Any] | None:
        """Get the parent of a chunk.

        Args:
            chunk_id: Child chunk identifier.

        Returns:
            Parent chunk data or None if not found or no parent.

        """
        parent_id = self._child_to_parent.get(chunk_id)
        if parent_id:
            return self._chunks.get(parent_id)
        return None

    def get_children(self, parent_id: str) -> list[dict[str, Any]]:
        """Get all children of a parent chunk.

        Args:
            parent_id: Parent chunk identifier.

        Returns:
            List of child chunk data dictionaries.

        """
        child_ids = self._parent_to_children.get(parent_id, [])
        return [self._chunks[cid] for cid in child_ids if cid in self._chunks]

    def get_parent_chunks(self) -> list[dict[str, Any]]:
        """Get all parent chunks (level 0).

        Returns:
            List of parent chunk data dictionaries.

        """
        return [chunk for chunk in self._chunks.values() if chunk["hierarchy_level"] == 0]

    def get_child_chunks(self) -> list[dict[str, Any]]:
        """Get all child chunks (level > 0).

        Returns:
            List of child chunk data dictionaries.

        """
        return [chunk for chunk in self._chunks.values() if chunk["hierarchy_level"] > 0]

    def get_child_embeddings(self) -> tuple[list[str], list[list[float]]]:
        """Get IDs and embeddings for all child chunks.

        Returns:
            Tuple of (chunk_ids, embeddings).

        """
        child_chunks = self.get_child_chunks()
        ids = []
        embeddings = []

        for chunk in child_chunks:
            if chunk.get("embedding"):
                ids.append(chunk["id"])
                embeddings.append(chunk["embedding"])

        return ids, embeddings

    def enhance_results_with_context(
        self,
        results: list[dict[str, Any]],
        include_parent: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Enhance search results with parent context.

        Args:
            results: Search results with chunk IDs.
            include_parent: Override default include_parent_context.

        Returns:
            Enhanced results with parent content added.

        """
        if include_parent is None:
            include_parent = self.include_parent_context

        if not include_parent:
            return results

        enhanced = []
        for result in results:
            chunk_id = result.get("id")
            enhanced_result = result.copy()

            parent = self.get_parent(chunk_id) if chunk_id else None
            if parent:
                enhanced_result["parent_content"] = parent.get("content")
                enhanced_result["parent_id"] = parent.get("id")
                enhanced_result["parent_metadata"] = parent.get("metadata")

            enhanced.append(enhanced_result)

        return enhanced

    def delete_chunk(self, chunk_id: str) -> bool:
        """Delete a chunk and update relationships.

        Args:
            chunk_id: Chunk identifier to delete.

        Returns:
            True if deleted, False if not found.

        """
        if chunk_id not in self._chunks:
            return False

        chunk = self._chunks[chunk_id]
        parent_id = chunk.get("parent_id")

        if parent_id and parent_id in self._parent_to_children:
            self._parent_to_children[parent_id] = [
                cid for cid in self._parent_to_children[parent_id] if cid != chunk_id
            ]

        if chunk_id in self._child_to_parent:
            del self._child_to_parent[chunk_id]

        if chunk_id in self._parent_to_children:
            for child_id in self._parent_to_children[chunk_id]:
                if child_id in self._chunks:
                    del self._chunks[child_id]
                if child_id in self._child_to_parent:
                    del self._child_to_parent[child_id]
            del self._parent_to_children[chunk_id]

        del self._chunks[chunk_id]

        logger.debug(f"Deleted chunk {chunk_id} from hierarchical index")
        return True

    def delete_by_reference(self, reference_name: str) -> int:
        """Delete all chunks for a document reference.

        Args:
            reference_name: Document reference name in metadata.

        Returns:
            Number of chunks deleted.

        """
        to_delete = [
            chunk_id
            for chunk_id, chunk in self._chunks.items()
            if chunk.get("metadata", {}).get("reference_name") == reference_name
        ]

        count = 0
        for chunk_id in to_delete:
            if self.delete_chunk(chunk_id):
                count += 1

        logger.info(f"Deleted {count} chunks for reference: {reference_name}")
        return count

    def clear(self) -> None:
        """Clear all chunks from the index."""
        self._chunks.clear()
        self._parent_to_children.clear()
        self._child_to_parent.clear()
        logger.info("Hierarchical index cleared")

    def count(self) -> int:
        """Get total number of chunks."""
        return len(self._chunks)

    def count_parents(self) -> int:
        """Get number of parent chunks."""
        return len(self.get_parent_chunks())

    def count_children(self) -> int:
        """Get number of child chunks."""
        return len(self.get_child_chunks())

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        return {
            "total_chunks": self.count(),
            "parent_chunks": self.count_parents(),
            "child_chunks": self.count_children(),
            "include_parent_context": self.include_parent_context,
        }
