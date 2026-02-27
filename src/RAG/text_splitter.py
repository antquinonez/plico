# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Simple text splitting utilities for chunking documents.

DEPRECATED: This module is maintained for backward compatibility.
For new code, use the text_splitters package instead:

    from src.RAG.text_splitters import get_chunker, TextChunk
    chunker = get_chunker("recursive", chunk_size=1000, chunk_overlap=200)
    chunks = chunker.chunk(text, metadata={"source": "doc.md"})

"""

from __future__ import annotations

import logging
import warnings

from .text_splitters import TextChunk as _TextChunk
from .text_splitters import get_chunker

logger = logging.getLogger(__name__)

TextChunk = _TextChunk


def split_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    metadata: dict | None = None,
) -> list[TextChunk]:
    """Split text into overlapping chunks.

    DEPRECATED: Use get_chunker("character") instead.

    Args:
        text: The text to split.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of characters to overlap between chunks.
        metadata: Optional metadata to attach to each chunk.

    Returns:
        List of TextChunk objects.

    """
    warnings.warn(
        "split_text is deprecated. Use get_chunker('character') instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    chunker = get_chunker("character", chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.chunk(text, metadata=metadata)


def split_documents(
    documents: list[dict],
    text_key: str = "content",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[TextChunk]:
    """Split multiple documents into chunks.

    DEPRECATED: Use get_chunker("character") and iterate over documents.

    Args:
        documents: List of document dicts with text content.
        text_key: Key to access text content in each document.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of characters to overlap between chunks.

    Returns:
        List of TextChunk objects from all documents.

    """
    warnings.warn(
        "split_documents is deprecated. Use get_chunker() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    all_chunks: list[TextChunk] = []

    chunker = get_chunker("character", chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    for doc in documents:
        text = doc.get(text_key, "")
        if not text:
            continue

        metadata = {k: v for k, v in doc.items() if k != text_key}
        chunks = chunker.chunk(text, metadata=metadata)
        all_chunks.extend(chunks)

    logger.info(f"Split {len(documents)} documents into {len(all_chunks)} total chunks")
    return all_chunks
