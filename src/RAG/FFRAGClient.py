# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""High-level RAG client combining embeddings, chunking, and vector storage."""

from __future__ import annotations

import logging
from typing import Any

from ..config import get_config
from .FFEmbeddings import FFEmbeddings
from .FFVectorStore import FFVectorStore
from .text_splitter import split_text

logger = logging.getLogger(__name__)


class FFRAGClient:
    """High-level RAG client for document indexing and retrieval.

    Combines FFEmbeddings, FFVectorStore, and text chunking into a
    unified interface for RAG operations.

    Args:
        collection_name: ChromaDB collection name.
        persist_dir: Directory for ChromaDB persistence.
        embedding_model: Model string or FFEmbeddings instance.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between chunks.
        n_results_default: Default number of results for search.
        config: Optional config dict (overrides defaults from YAML).

    Example:
        >>> rag = FFRAGClient()
        >>> rag.add_document("Long document content...", metadata={"source": "file.md"})
        >>> results = rag.search("What is the document about?")
        >>> for r in results:
        ...     print(f"Score: {r['score']:.2f} - {r['content'][:50]}")

    """

    def __init__(
        self,
        collection_name: str | None = None,
        persist_dir: str | None = None,
        embedding_model: str | FFEmbeddings | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        n_results_default: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        app_config = get_config()
        rag_config = getattr(app_config, "rag", None)

        self.collection_name = collection_name or (
            rag_config.collection_name if rag_config else "ffclients_kb"
        )
        self.persist_dir = persist_dir or (rag_config.persist_dir if rag_config else "./chroma_db")
        self.chunk_size = chunk_size or (rag_config.chunk_size if rag_config else 1000)
        self.chunk_overlap = chunk_overlap or (rag_config.chunk_overlap if rag_config else 200)
        self.n_results_default = n_results_default or (
            rag_config.n_results_default if rag_config else 5
        )

        if config:
            self.collection_name = config.get("collection_name", self.collection_name)
            self.persist_dir = config.get("persist_dir", self.persist_dir)
            self.chunk_size = config.get("chunk_size", self.chunk_size)
            self.chunk_overlap = config.get("chunk_overlap", self.chunk_overlap)
            self.n_results_default = config.get("n_results_default", self.n_results_default)

        if embedding_model is None:
            model_str = rag_config.embedding_model if rag_config else "mistral/mistral-embed"
            self._embeddings = FFEmbeddings(model=model_str)
        elif isinstance(embedding_model, str):
            self._embeddings = FFEmbeddings(model=embedding_model)
        else:
            self._embeddings = embedding_model

        self._vector_store = FFVectorStore(
            collection_name=self.collection_name,
            persist_dir=self.persist_dir,
            embedding_model=self._embeddings,
        )

        logger.info(
            f"FFRAGClient initialized: collection={self.collection_name}, "
            f"persist_dir={self.persist_dir}, chunks={self._vector_store.count()}"
        )

    def add_document(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        reference_name: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> int:
        """Add a single document to the knowledge base.

        Args:
            content: Document text content.
            metadata: Optional metadata dict for all chunks.
            reference_name: Optional reference name (added to metadata).
            chunk_size: Override default chunk size.
            chunk_overlap: Override default chunk overlap.

        Returns:
            Number of chunks added.

        """
        if not content or not content.strip():
            logger.warning("Attempted to add empty document")
            return 0

        meta = metadata.copy() if metadata else {}
        if reference_name:
            meta["reference_name"] = reference_name

        chunks = split_text(
            content,
            chunk_size=chunk_size or self.chunk_size,
            chunk_overlap=chunk_overlap or self.chunk_overlap,
            metadata=meta,
        )

        return self._vector_store.add_chunks(chunks)

    def add_documents(
        self,
        documents: list[dict],
        text_key: str = "content",
    ) -> int:
        """Add multiple documents to the knowledge base.

        Args:
            documents: List of document dicts with text and metadata.
            text_key: Key to access text content in each document.

        Returns:
            Total number of chunks added.

        """
        return self._vector_store.add_documents(
            documents,
            text_key=text_key,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    def search(
        self,
        query: str,
        n_results: int | None = None,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Search for relevant documents.

        Args:
            query: Query text.
            n_results: Number of results (defaults to n_results_default).
            where: Optional metadata filter.

        Returns:
            List of results with content, metadata, and score.

        """
        n = n_results or self.n_results_default
        results = self._vector_store.search(query, n_results=n, where=where)

        for result in results:
            if result["distance"] is not None:
                result["score"] = 1.0 - result["distance"]
            else:
                result["score"] = 0.0

        return results

    def format_results_for_prompt(
        self,
        results: list[dict[str, Any]],
        max_chars: int | None = None,
    ) -> str:
        """Format search results for injection into a prompt.

        Args:
            results: Search results from search().
            max_chars: Maximum total characters (None = no limit).

        Returns:
            Formatted string for prompt injection.

        """
        if not results:
            return ""

        formatted_chunks = []
        total_chars = 0

        for i, result in enumerate(results, start=1):
            content = result.get("content", "")
            source = result.get("metadata", {}).get("reference_name", "unknown")

            chunk_text = f"[{i}] (source: {source})\n{content}\n"

            if max_chars and total_chars + len(chunk_text) > max_chars:
                break

            formatted_chunks.append(chunk_text)
            total_chars += len(chunk_text)

        return "".join(formatted_chunks)

    def search_and_format(
        self,
        query: str,
        n_results: int | None = None,
        max_chars: int | None = None,
        where: dict | None = None,
    ) -> str:
        """Search and return formatted results for prompt injection.

        Convenience method combining search() and format_results_for_prompt().

        Args:
            query: Query text.
            n_results: Number of results.
            max_chars: Maximum characters in output.
            where: Optional metadata filter.

        Returns:
            Formatted string of relevant chunks.

        """
        results = self.search(query, n_results=n_results, where=where)
        return self.format_results_for_prompt(results, max_chars=max_chars)

    def delete_by_reference(self, reference_name: str) -> None:
        """Delete all chunks from a specific document.

        Args:
            reference_name: Document reference name to delete.

        """
        self._vector_store.delete_by_reference(reference_name)

    def count(self) -> int:
        """Get total number of chunks in the knowledge base."""
        return self._vector_store.count()

    def list_documents(self) -> list[str]:
        """List all document reference names in the knowledge base."""
        return self._vector_store.list_documents()

    def get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics."""
        stats = self._vector_store.get_stats()
        stats["chunk_size"] = self.chunk_size
        stats["chunk_overlap"] = self.chunk_overlap
        return stats

    def clear(self) -> None:
        """Clear all documents from the knowledge base."""
        self._vector_store.clear()

    @property
    def vector_store(self) -> FFVectorStore:
        """Access the underlying FFVectorStore for advanced operations."""
        return self._vector_store

    @property
    def embeddings(self) -> FFEmbeddings:
        """Access the underlying FFEmbeddings instance."""
        return self._embeddings
