# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Chunk deduplication for cleaner vector indices."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ChunkDeduplicator:
    """Detect and filter duplicate/near-duplicate chunks.

    Supports multiple deduplication modes:
    - exact: Hash-based exact content matching
    - similarity: Embedding cosine similarity threshold

    Args:
        mode: Deduplication mode ("exact" or "similarity").
        similarity_threshold: Threshold for similarity-based dedup (0.0-1.0).

    Example:
        >>> dedup = ChunkDeduplicator(mode="exact")
        >>> chunks, embeddings = dedup.filter_duplicates(chunks, embeddings)

    """

    def __init__(
        self,
        mode: str = "exact",
        similarity_threshold: float = 0.95,
    ) -> None:
        self.mode = mode
        self.similarity_threshold = similarity_threshold
        self._seen_hashes: set[str] = set()
        self._seen_embeddings: list[tuple[str, list[float]]] = []

    def compute_hash(self, content: str) -> str:
        """Compute content hash for exact deduplication.

        Args:
            content: Chunk text content.

        Returns:
            SHA256 hash (first 16 chars).

        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def is_duplicate(
        self,
        content: str,
        embedding: list[float] | None = None,
    ) -> bool:
        """Check if chunk is a duplicate of previously seen content.

        Args:
            content: Chunk text content.
            embedding: Optional embedding vector for similarity-based dedup.

        Returns:
            True if chunk is a duplicate.

        """
        if self.mode == "exact":
            content_hash = self.compute_hash(content)
            if content_hash in self._seen_hashes:
                return True
            self._seen_hashes.add(content_hash)
            return False

        elif self.mode == "similarity" and embedding:
            for _, seen_emb in self._seen_embeddings:
                sim = self._cosine_similarity(embedding, seen_emb)
                if sim >= self.similarity_threshold:
                    return True
            self._seen_embeddings.append((self.compute_hash(content), embedding))
            return False

        return False

    def filter_duplicates(
        self,
        chunks: list[Any],
        embeddings: list[list[float]],
    ) -> tuple[list[Any], list[list[float]]]:
        """Filter duplicate chunks from a batch.

        Args:
            chunks: List of chunk objects (must have .content attribute or be string).
            embeddings: List of embedding vectors.

        Returns:
            Tuple of (filtered_chunks, filtered_embeddings).

        """
        if not chunks or not embeddings:
            return chunks, embeddings

        filtered_chunks = []
        filtered_embeddings = []
        dup_count = 0

        for chunk, emb in zip(chunks, embeddings):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            if not self.is_duplicate(content, emb if self.mode == "similarity" else None):
                filtered_chunks.append(chunk)
                filtered_embeddings.append(emb)
            else:
                dup_count += 1

        if dup_count > 0:
            logger.info(f"Filtered {dup_count} duplicate chunks ({self.mode} mode)")

        return filtered_chunks, filtered_embeddings

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First vector.
            b: Second vector.

        Returns:
            Cosine similarity score (0.0 to 1.0).

        """
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def clear(self) -> None:
        """Clear seen hashes and embeddings."""
        self._seen_hashes.clear()
        self._seen_embeddings.clear()
        logger.debug("Deduplicator state cleared")

    def get_stats(self) -> dict[str, Any]:
        """Get deduplicator statistics.

        Returns:
            Dict with mode, threshold, and counts.

        """
        return {
            "mode": self.mode,
            "similarity_threshold": self.similarity_threshold,
            "seen_hashes": len(self._seen_hashes),
            "seen_embeddings": len(self._seen_embeddings),
        }
