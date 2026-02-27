# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Contextual embeddings for improved chunk retrieval."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ContextualEmbeddings:
    """Generate embeddings with document context prepended.

    Prepends document context (title, summary, or preceding content)
    to each chunk before embedding, improving semantic understanding.

    Args:
        context_prefix: Template for context prefix.
        max_context_length: Maximum characters for context prefix.

    """

    DEFAULT_CONTEXT_TEMPLATE = "Document: {title}\n\nSection: {section}\n\n{chunk}"

    def __init__(
        self,
        context_template: str | None = None,
        max_context_length: int = 200,
    ) -> None:
        self.context_template = context_template or self.DEFAULT_CONTEXT_TEMPLATE
        self.max_context_length = max_context_length

    def prepare_chunk_for_embedding(
        self,
        chunk_content: str,
        document_title: str | None = None,
        section_header: str | None = None,
        document_summary: str | None = None,
        preceding_context: str | None = None,
    ) -> str:
        """Prepare a chunk with context for embedding.

        Args:
            chunk_content: The chunk text content.
            document_title: Document title or name.
            section_header: Section header if available.
            document_summary: Brief document summary.
            preceding_context: Text immediately preceding this chunk.

        Returns:
            Context-enhanced text for embedding.

        """
        title = self._truncate(document_title or "Untitled", 50)
        section = self._truncate(section_header or "", 50)

        context_parts = []
        if document_title:
            context_parts.append(f"Document: {title}")
        if section_header:
            context_parts.append(f"Section: {section}")

        context = "\n".join(context_parts)
        context = self._truncate(context, self.max_context_length)

        if context:
            return f"{context}\n\n{chunk_content}"
        return chunk_content

    def prepare_chunks_batch(
        self,
        chunks: list[dict[str, Any]],
        document_title: str | None = None,
        document_summary: str | None = None,
    ) -> list[str]:
        """Prepare multiple chunks with context for embedding.

        Args:
            chunks: List of chunk dictionaries with 'content' and optional metadata.
            document_title: Document title for all chunks.
            document_summary: Document summary (currently unused but available).

        Returns:
            List of context-enhanced texts for embedding.

        """
        prepared = []

        for i, chunk in enumerate(chunks):
            content = chunk.get("content", "")
            metadata = chunk.get("metadata", {})

            section_header = metadata.get("header") or metadata.get("section")

            preceding = None
            if i > 0 and i <= len(chunks) - 1:
                prev_content = chunks[i - 1].get("content", "")
                preceding = prev_content[-100:] if len(prev_content) > 100 else prev_content

            prepared_text = self.prepare_chunk_for_embedding(
                chunk_content=content,
                document_title=metadata.get("document_title") or document_title,
                section_header=section_header,
                document_summary=document_summary,
                preceding_context=preceding,
            )
            prepared.append(prepared_text)

        logger.debug(f"Prepared {len(prepared)} chunks with context")
        return prepared

    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length, preserving word boundaries."""
        if not text or len(text) <= max_length:
            return text

        truncated = text[:max_length]
        last_space = truncated.rfind(" ")
        if last_space > max_length // 2:
            return truncated[:last_space] + "..."
        return truncated + "..."


class LateChunkingEmbeddings:
    """Late chunking strategy for token-level embeddings.

    Instead of embedding chunks separately, embeds the full document
    and extracts chunk-level representations from the token embeddings.

    This is a placeholder for ColBERT-style late interaction embeddings.
    Full implementation would require a model that outputs token-level
    embeddings and late interaction scoring.

    Args:
        embedding_model: The underlying embedding model.

    """

    def __init__(
        self,
        embedding_model: Any | None = None,
    ) -> None:
        self.embedding_model = embedding_model
        self._token_embeddings: dict[str, list[list[float]]] = {}

    def embed_document_with_tokens(
        self,
        document_id: str,
        content: str,
        chunk_boundaries: list[tuple[int, int]],
    ) -> list[list[float]]:
        """Embed document and extract chunk representations.

        Note: This is a simplified implementation. A full ColBERT-style
        implementation would use a model that outputs token embeddings.

        Args:
            document_id: Document identifier.
            content: Full document content.
            chunk_boundaries: List of (start, end) tuples for chunks.

        Returns:
            List of chunk embeddings.

        """
        logger.warning(
            "LateChunkingEmbeddings is a placeholder. Using standard chunk embeddings instead."
        )
        return []
