# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Simple text splitting utilities for chunking documents."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""

    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict | None = None


def split_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    metadata: dict | None = None,
) -> list[TextChunk]:
    """Split text into overlapping chunks.

    Args:
        text: The text to split.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of characters to overlap between chunks.
        metadata: Optional metadata to attach to each chunk.

    Returns:
        List of TextChunk objects.

    """
    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be less than chunk_size")

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
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
                    metadata=metadata.copy() if metadata else None,
                )
            )
            chunk_index += 1

        # Calculate next start position, ensuring forward progress
        if end < len(text):
            overlap_start = max(0, end - chunk_overlap)
            # If overlap would prevent forward progress, continue from end instead
            start = end if overlap_start <= start else overlap_start
        else:
            start = end
            overlap_start = end  # For consistency in walkback logic below

        # Walk back to word boundary, but never before overlap_start
        # This handles very long words by accepting mid-word splits when necessary
        max_walkback = chunk_overlap * 2
        walkback_distance = 0
        while (
            start > overlap_start
            and start < len(text)
            and text[start] not in (" ", "\n")
            and walkback_distance < max_walkback
        ):
            start -= 1
            walkback_distance += 1

    logger.debug(
        f"Split text into {len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})"
    )
    return chunks


def split_documents(
    documents: list[dict],
    text_key: str = "content",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[TextChunk]:
    """Split multiple documents into chunks.

    Args:
        documents: List of document dicts with text content.
        text_key: Key to access text content in each document.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of characters to overlap between chunks.

    Returns:
        List of TextChunk objects from all documents.

    """
    all_chunks = []

    for doc in documents:
        text = doc.get(text_key, "")
        if not text:
            continue

        metadata = {k: v for k, v in doc.items() if k != text_key}
        chunks = split_text(text, chunk_size, chunk_overlap, metadata)
        all_chunks.extend(chunks)

    logger.info(f"Split {len(documents)} documents into {len(all_chunks)} total chunks")
    return all_chunks
