# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Recursive character-based text chunking with hierarchical splitting."""

from __future__ import annotations

import logging
import re
from typing import Any

from .base import ChunkerBase, TextChunk

logger = logging.getLogger(__name__)


class RecursiveChunker(ChunkerBase):
    """Recursive chunking that splits hierarchically by separators.

    Attempts to split text by larger structural boundaries first
    (paragraphs, sentences), then falls back to smaller boundaries
    (words, characters) as needed.

    Args:
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.
        metadata: Default metadata for all chunks.
        separators: List of separators in order of preference.
        keep_separator: Whether to keep the separator with chunks.

    """

    DEFAULT_SEPARATORS = [
        "\n\n\n",
        "\n\n",
        "\n",
        ". ",
        "! ",
        "? ",
        "; ",
        ", ",
        " ",
        "",
    ]

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        metadata: dict[str, Any] | None = None,
        separators: list[str] | None = None,
        keep_separator: bool = True,
    ) -> None:
        super().__init__(chunk_size, chunk_overlap, metadata)
        self.separators = separators or self.DEFAULT_SEPARATORS
        self.keep_separator = keep_separator
        self._validate_params()

    def chunk(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[TextChunk]:
        """Split text recursively using hierarchical separators.

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

        split_texts = self._split_text_recursive(text, self.separators)

        current_chunks: list[tuple[str, int, int]] = []
        current_pos = 0

        for split_text in split_texts:
            split_len = len(split_text)
            split_start = text.find(split_text, current_pos)
            if split_start == -1:
                split_start = current_pos

            if self._get_current_length(current_chunks) + split_len <= self.chunk_size:
                current_chunks.append((split_text, split_start, split_start + split_len))
            else:
                if current_chunks:
                    self._finalize_chunks(current_chunks, chunks, merged_metadata)
                    overlap_text = self._get_overlap_text(current_chunks)
                    current_chunks = []

                    if overlap_text:
                        overlap_start = text.find(overlap_text, split_start - len(overlap_text))
                        if overlap_start != -1:
                            current_chunks.append(
                                (overlap_text, overlap_start, overlap_start + len(overlap_text))
                            )

                if split_len <= self.chunk_size:
                    current_chunks.append((split_text, split_start, split_start + split_len))
                else:
                    sub_chunks = self._split_large_text(split_text, split_start)
                    for sub_text, sub_start, sub_end in sub_chunks:
                        if (
                            self._get_current_length(current_chunks) + len(sub_text)
                            <= self.chunk_size
                        ):
                            current_chunks.append((sub_text, sub_start, sub_end))
                        else:
                            if current_chunks:
                                self._finalize_chunks(current_chunks, chunks, merged_metadata)
                            current_chunks = [(sub_text, sub_start, sub_end)]

            current_pos = split_start + split_len

        if current_chunks:
            self._finalize_chunks(current_chunks, chunks, merged_metadata)

        logger.debug(
            f"RecursiveChunker: {len(chunks)} chunks (size={self.chunk_size}, overlap={self.chunk_overlap})"
        )
        return chunks

    def _split_text_recursive(self, text: str, separators: list[str]) -> list[str]:
        """Split text recursively using separators."""
        if not separators:
            return [text] if text else []

        separator = separators[0]
        remaining_separators = separators[1:]

        if separator == "":
            return list(text)

        if self.keep_separator:
            splits = re.split(f"({re.escape(separator)})", text)
            splits = [s for s in splits if s]
        else:
            splits = text.split(separator)
            splits = [s for s in splits if s]

        if not splits:
            return [text] if text else []

        result: list[str] = []
        for split in splits:
            if len(split) <= self.chunk_size:
                result.append(split)
            else:
                sub_splits = self._split_text_recursive(split, remaining_separators)
                result.extend(sub_splits)

        return result

    def _split_large_text(self, text: str, start_offset: int) -> list[tuple[str, int, int]]:
        """Split text that exceeds chunk_size by characters."""
        result: list[tuple[str, int, int]] = []
        pos = 0

        while pos < len(text):
            end = min(pos + self.chunk_size, len(text))

            if end < len(text):
                last_space = text.rfind(" ", pos, end)
                if last_space > pos:
                    end = last_space

            chunk_text = text[pos:end].strip()
            if chunk_text:
                result.append((chunk_text, start_offset + pos, start_offset + end))

            pos = end

        return result

    def _get_current_length(self, chunks: list[tuple[str, int, int]]) -> int:
        """Get total length of current chunks."""
        return sum(len(c[0]) for c in chunks)

    def _get_overlap_text(self, chunks: list[tuple[str, int, int]]) -> str:
        """Get text from the end of current chunks for overlap."""
        if not chunks:
            return ""

        combined = "".join(c[0] for c in chunks)
        if len(combined) <= self.chunk_overlap:
            return combined

        overlap_start = len(combined) - self.chunk_overlap
        overlap_text = combined[overlap_start:]

        space_idx = overlap_text.find(" ")
        if space_idx > 0:
            return overlap_text[space_idx + 1 :]

        return overlap_text

    def _finalize_chunks(
        self,
        current_chunks: list[tuple[str, int, int]],
        chunks: list[TextChunk],
        metadata: dict[str, Any],
    ) -> None:
        """Convert current chunks to TextChunk objects."""
        if not current_chunks:
            return

        combined_text = "".join(c[0] for c in current_chunks).strip()
        if not combined_text:
            return

        start_char = current_chunks[0][1]
        end_char = current_chunks[-1][2]

        chunks.append(
            TextChunk(
                content=combined_text,
                chunk_index=len(chunks),
                start_char=start_char,
                end_char=end_char,
                metadata=metadata.copy(),
            )
        )
