# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Document registry for managing document definitions and content retrieval.

Validates document references and provides content injection for prompts
referencing external documents via the 'documents' workbook sheet.
Supports semantic search via RAG for semantic_query prompts.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .document_processor import DocumentProcessor

if TYPE_CHECKING:
    from ..RAG import FFRAGClient

logger = logging.getLogger(__name__)


class DocumentRegistry:
    """Manages document definitions and content retrieval for prompt references.

    Documents are defined in the workbook's 'documents' sheet and processed
    through the DocumentProcessor. This registry validates all references
    and provides content for prompt injection.

    Supports semantic search via RAG for semantic_query functionality.

    Attributes:
        documents: Dictionary mapping reference_name to document config
        processor: DocumentProcessor instance for parsing/caching
        workbook_dir: Directory containing the workbook (for relative paths)
        rag_client: Optional FFRAGClient for semantic search

    """

    def __init__(
        self,
        documents: list[dict[str, Any]],
        processor: DocumentProcessor,
        workbook_dir: str,
        rag_client: FFRAGClient | None = None,
    ) -> None:
        """Initialize the document registry.

        Args:
            documents: List of document configs from workbook sheet.
            processor: DocumentProcessor for parsing documents.
            workbook_dir: Directory containing the workbook.
            rag_client: Optional FFRAGClient for semantic search.

        """
        self.processor = processor
        self.workbook_dir = Path(workbook_dir).resolve()
        self.rag_client = rag_client
        self.documents: dict[str, dict[str, Any]] = {}
        self._content_cache: dict[str, str] = {}

        for doc in documents:
            ref_name = doc.get("reference_name")
            if ref_name:
                self.documents[ref_name] = doc

        logger.info(f"DocumentRegistry initialized with {len(self.documents)} documents")

    def resolve_path(self, file_path: str) -> str:
        """Resolve a file path relative to the workbook directory.

        Args:
            file_path: Path from the documents sheet (may be relative)

        Returns:
            Absolute path to the document

        """
        path = Path(file_path)

        if path.is_absolute():
            return str(path)

        resolved = (self.workbook_dir / path).resolve()
        return str(resolved)

    def validate_documents(self) -> list[str]:
        """Validate that all registered documents exist on disk.

        Returns:
            List of reference names that are valid

        Raises:
            FileNotFoundError: If any document file doesn't exist

        """
        missing = []
        valid = []

        for ref_name, doc in self.documents.items():
            file_path = self.resolve_path(doc.get("file_path", ""))
            if not os.path.exists(file_path):
                missing.append(f"{ref_name}: {file_path}")
            else:
                valid.append(ref_name)

        if missing:
            raise FileNotFoundError("Document(s) not found:\n" + "\n".join(missing))

        logger.info(f"All {len(valid)} documents validated")
        return valid

    def get_reference_names(self) -> set[str]:
        """Get all registered reference names."""
        return set(self.documents.keys())

    def get_document_config(self, reference_name: str) -> dict[str, Any] | None:
        """Get the configuration for a document by reference name."""
        return self.documents.get(reference_name)

    def get_content(self, reference_name: str) -> str:
        """Get the content of a document by reference name.

        Uses the DocumentProcessor for parsing/caching. Results are
        cached in memory for the session.

        Args:
            reference_name: The reference name from the documents sheet

        Returns:
            Document content as markdown string

        Raises:
            KeyError: If reference_name not found
            FileNotFoundError: If document file doesn't exist

        """
        if reference_name in self._content_cache:
            return self._content_cache[reference_name]

        if reference_name not in self.documents:
            raise KeyError(f"Document reference not found: {reference_name}")

        doc = self.documents[reference_name]
        file_path = self.resolve_path(doc.get("file_path", ""))
        common_name = doc.get("common_name", reference_name)

        content = self.processor.get_document_content(
            file_path=file_path, reference_name=reference_name, common_name=common_name
        )

        self._content_cache[reference_name] = content
        return content

    def get_all_content(self, reference_names: list[str]) -> dict[str, str]:
        """Get content for multiple documents.

        Args:
            reference_names: List of reference names

        Returns:
            Dictionary mapping reference names to content

        """
        result = {}
        for ref_name in reference_names:
            try:
                result[ref_name] = self.get_content(ref_name)
            except (KeyError, FileNotFoundError) as e:
                logger.error(f"Failed to get content for {ref_name}: {e}")
                raise
        return result

    def format_references_block(self, reference_names: list[str]) -> str:
        """Format document content as an XML references block.

        Output format:
        <REFERENCES>
        <DOC name='ref1'>
        content...
        </DOC>

        <DOC name='ref2'>
        content...
        </DOC>
        </REFERENCES>

        Args:
            reference_names: List of reference names to include

        Returns:
            Formatted XML string

        """
        if not reference_names:
            return ""

        docs_content = self.get_all_content(reference_names)

        doc_blocks = []
        for ref_name in reference_names:
            if ref_name in docs_content:
                content = docs_content[ref_name]
                doc_blocks.append(f"<DOC name='{ref_name}'>\n{content}\n</DOC>")

        if not doc_blocks:
            return ""

        return "<REFERENCES>\n" + "\n\n".join(doc_blocks) + "\n</REFERENCES>"

    def inject_references_into_prompt(self, prompt: str, reference_names: list[str] | None) -> str:
        """Inject document references into a prompt.

        Format:
        <REFERENCES>
        <DOC name='...'>content</DOC>
        </REFERENCES>

        ===
        Based on the documents above, please answer: [original prompt]

        Args:
            prompt: Original prompt text
            reference_names: List of document reference names

        Returns:
            Prompt with injected document references

        """
        if not reference_names:
            return prompt

        refs_block = self.format_references_block(reference_names)

        if not refs_block:
            return prompt

        return f"{refs_block}\n\n===\nBased on the documents above, please answer: {prompt}"

    def clear_cache(self) -> None:
        """Clear the in-memory content cache."""
        self._content_cache.clear()
        logger.info("Document content cache cleared")

    def semantic_search(
        self,
        query: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
        query_expansion: bool | None = None,
        rerank: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Perform semantic search across indexed documents.

        Args:
            query: Search query text.
            n_results: Maximum number of results to return.
            where: Optional metadata filter (e.g., {"reference_name": "doc1"}).
            query_expansion: Override global query expansion setting.
            rerank: Override global rerank setting.

        Returns:
            List of search results with content, metadata, and score.

        Raises:
            RuntimeError: If RAG client is not configured.

        """
        if not self.rag_client:
            raise RuntimeError("RAG client not configured for semantic search")

        logger.debug(f"Semantic search: {query[:50]}...")
        return self.rag_client.search(
            query,
            n_results=n_results,
            where=where,
            query_expansion=query_expansion,
            rerank=rerank,
        )

    def format_semantic_results(
        self,
        results: list[dict[str, Any]],
        max_chars: int | None = None,
    ) -> str:
        """Format semantic search results for prompt injection.

        Args:
            results: Search results from semantic_search().
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
            score = result.get("score", 0.0)

            chunk_text = f"[{i}] (source: {source}, relevance: {score:.2f})\n{content}\n"

            if max_chars and total_chars + len(chunk_text) > max_chars:
                break

            formatted_chunks.append(chunk_text)
            total_chars += len(chunk_text)

        return "".join(formatted_chunks)

    def inject_semantic_query(
        self,
        prompt: str,
        semantic_query: str,
        semantic_filter: dict[str, Any] | None = None,
        n_results: int = 5,
        max_chars: int | None = None,
        query_expansion: bool | None = None,
        rerank: bool | None = None,
    ) -> str:
        """Inject semantic search results into a prompt.

        Performs semantic search and formats results for RAG-style prompt.

        Args:
            prompt: Original prompt text.
            semantic_query: Query for semantic search.
            semantic_filter: Optional metadata filter for search.
            n_results: Number of results to retrieve.
            max_chars: Maximum characters in injected content.
            query_expansion: Override global query expansion setting.
            rerank: Override global rerank setting.

        Returns:
            Prompt with injected semantic search results.

        Raises:
            RuntimeError: If RAG client is not configured.

        """
        if not semantic_query:
            return prompt

        filter_str = f" with filter: {semantic_filter}" if semantic_filter else ""
        expansion_str = f" (expansion={query_expansion})" if query_expansion else ""
        rerank_str = f" (rerank={rerank})" if rerank else ""
        logger.info(
            f"Performing semantic search for query: {semantic_query}{filter_str}{expansion_str}{rerank_str}"
        )
        results = self.semantic_search(
            semantic_query,
            n_results=n_results,
            where=semantic_filter,
            query_expansion=query_expansion,
            rerank=rerank,
        )

        if not results:
            logger.warning(f"No semantic results for query: {semantic_query}")
            return prompt

        logger.info(f"Found {len(results)} semantic results, injecting into prompt")
        context = self.format_semantic_results(results, max_chars=max_chars)

        return f"<RELEVANT_CONTEXT>\n{context}</RELEVANT_CONTEXT>\n\n===\nBased on the context above, please answer: {prompt}"

    def index_all_documents(self, force: bool = False) -> dict[str, int]:
        """Index all registered documents for RAG search.

        This method should be called at orchestrator startup to ensure
        all documents in the 'documents' sheet are indexed and searchable.

        Args:
            force: Force reindexing of all documents, even if unchanged.

        Returns:
            Dictionary mapping reference_name to number of chunks indexed.

        """
        if not self.rag_client:
            logger.info("RAG client not configured, skipping document indexing")
            return {}

        results: dict[str, int] = {}

        for ref_name, doc in self.documents.items():
            file_path = self.resolve_path(doc.get("file_path", ""))
            common_name = doc.get("common_name", ref_name)

            if not os.path.exists(file_path):
                logger.warning(f"Document file not found, skipping: {file_path}")
                continue

            try:
                checksum = self.processor.get_document_checksum(file_path)

                content = self.get_content(ref_name)

                chunks_indexed = self.processor.index_to_rag(
                    reference_name=ref_name,
                    common_name=common_name,
                    content=content,
                    checksum=checksum,
                    force=force,
                )
                results[ref_name] = chunks_indexed

            except Exception as e:
                logger.error(f"Failed to index document {ref_name}: {e}")
                results[ref_name] = 0

        total_chunks = sum(results.values())
        indexed_count = sum(1 for v in results.values() if v > 0)
        logger.info(
            f"Document indexing complete: {indexed_count}/{len(self.documents)} documents, "
            f"{total_chunks} total chunks"
        )

        return results
