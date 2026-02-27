# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Character-based text chunking with word-boundary awareness."""

from __future__ import annotations

import logging
from typing import Any

from .base import ChunkerBase, TextChunk

logger = logging.getLogger(__name__)


class CharacterChunker(ChunkerBase):
    """Character-based chunking with word-boundary awareness.

    Splits text by character count, attempting to break at word
    boundaries (spaces or newlines) when possible.

    Args:
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.
        metadata: Default metadata for all chunks.
        respect_word_boundaries: Whether to prefer word boundaries for splits.

    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        metadata: dict[str, Any] | None = None,
        respect_word_boundaries: bool = True,
    ) -> None:
        super().__init__(chunk_size, chunk_overlap, metadata)
        self.respect_word_boundaries = respect_word_boundaries
        self._validate_params()

    def chunk(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Split text into overlapping chunks.

        Args:
            text: The text to split.
            metadata: Optional metadata to attach to each chunk.

        Returns:
            List of TextChunk objects.

        """
        if not text or not text.strip():
            return []

        merged_metadata = self._merge_metadata(metadata)
        chunks: list[TextChunk] = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            if self.respect_word_boundaries and end < len(text):
                last_newline = text.rfind("\n", start, end)
                last_space = text.rfind(" ", start, end)
                break_point = max(last_newline, last_space)
                if break_point > start:
                    end = break_point

            chunk_content = text[start:end].strip()

            if chunk_content:
                chunks.append(
                    TextChunk(
                        content=chunk_content,
                        chunk_index=chunk_index,
                        start_char=start,
                        end_char=end,
                        metadata=merged_metadata.copy(),
                    )
                )
                chunk_index += 1

            if end < len(text):
                overlap_start = max(0, end - self.chunk_overlap)
                start = end if overlap_start <= start else overlap_start
            else:
                start = end

            if self.respect_word_boundaries and start < len(text):
                max_walkback = self.chunk_overlap * 2
                walkback_distance = 0
                while (
                    start > end - self.chunk_overlap
                    and start < len(text)
                    and text[start] not in (" ", "\n")
                    and walkback_distance < max_walkback
                ):
                    start -= 1
                    walkback_distance += 1

        logger.debug(
            f"CharacterChunker: {len(chunks)} chunks (size={self.chunk_size}, overlap={self.chunk_overlap})"
        )
        return chunks
