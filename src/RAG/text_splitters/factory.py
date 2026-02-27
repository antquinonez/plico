# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Factory for creating text chunkers based on strategy."""

from __future__ import annotations

import logging
from typing import Any

from .base import ChunkerBase, TextChunk
from .character import CharacterChunker
from .code import CodeChunker
from .hierarchical import HierarchicalChunker
from .markdown import MarkdownChunker
from .recursive import RecursiveChunker

logger = logging.getLogger(__name__)


CHUNKER_REGISTRY: dict[str, type[ChunkerBase]] = {
    "character": CharacterChunker,
    "recursive": RecursiveChunker,
    "markdown": MarkdownChunker,
    "code": CodeChunker,
    "hierarchical": HierarchicalChunker,
}


def get_chunker(
    strategy: str = "recursive",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> ChunkerBase:
    """Get a chunker instance based on strategy name.

    Args:
        strategy: Chunking strategy name (character, recursive, markdown, code, hierarchical).
        chunk_size: Maximum chunk size.
        chunk_overlap: Overlap between chunks.
        metadata: Default metadata for chunks.
        **kwargs: Additional strategy-specific parameters.

    Returns:
        Configured chunker instance.

    Raises:
        ValueError: If strategy name is not recognized.

    Example:
        >>> chunker = get_chunker("markdown", chunk_size=500)
        >>> chunks = chunker.chunk("# Header\\n\\nContent...")

    """
    strategy_lower = strategy.lower()

    if strategy_lower not in CHUNKER_REGISTRY:
        available = ", ".join(CHUNKER_REGISTRY.keys())
        raise ValueError(f"Unknown chunking strategy: '{strategy}'. Available: {available}")

    chunker_class = CHUNKER_REGISTRY[strategy_lower]

    common_kwargs = {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "metadata": metadata,
    }

    if strategy_lower == "markdown":
        common_kwargs["split_headers"] = kwargs.get("split_headers", ["h1", "h2", "h3"])
        common_kwargs["preserve_structure"] = kwargs.get("preserve_structure", True)
        common_kwargs["max_chunk_fallback"] = kwargs.get("max_chunk_fallback", True)
    elif strategy_lower == "code":
        common_kwargs["language"] = kwargs.get("language", "python")
        common_kwargs["split_by"] = kwargs.get("split_by", "function")
    elif strategy_lower == "hierarchical":
        common_kwargs["parent_chunk_size"] = kwargs.get("parent_chunk_size", chunk_size * 3)
        common_kwargs["max_levels"] = kwargs.get("max_levels", 2)
    elif strategy_lower == "recursive":
        common_kwargs["separators"] = kwargs.get("separators")
        common_kwargs["keep_separator"] = kwargs.get("keep_separator", True)
    elif strategy_lower == "character":
        common_kwargs["respect_word_boundaries"] = kwargs.get("respect_word_boundaries", True)

    common_kwargs = {k: v for k, v in common_kwargs.items() if v is not None}

    chunker = chunker_class(**common_kwargs)

    logger.debug(
        f"Created {chunker_class.__name__} with chunk_size={chunk_size}, overlap={chunk_overlap}"
    )
    return chunker


def list_chunkers() -> list[str]:
    """List available chunking strategies.

    Returns:
        List of strategy names.

    """
    return list(CHUNKER_REGISTRY.keys())


def chunk_text(
    text: str,
    strategy: str = "recursive",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> list[TextChunk]:
    """Convenience function to chunk text with a single call.

    Args:
        text: Text to chunk.
        strategy: Chunking strategy name.
        chunk_size: Maximum chunk size.
        chunk_overlap: Overlap between chunks.
        metadata: Metadata to attach to chunks.
        **kwargs: Additional strategy-specific parameters.

    Returns:
        List of TextChunk objects.

    Example:
        >>> chunks = chunk_text("# Header\\n\\nContent", strategy="markdown")

    """
    chunker = get_chunker(
        strategy=strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        metadata=metadata,
        **kwargs,
    )
    return chunker.chunk(text, metadata=metadata)
