# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""High-level RAG client combining embeddings, chunking, and vector storage."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ..config import get_config
from .FFEmbeddings import FFEmbeddings
from .FFVectorStore import FFVectorStore
from .indexing import BM25Index, HierarchicalIndex
from .search import HybridSearch, QueryExpander, fuse_search_results, get_reranker
from .text_splitters import (
    ChunkerBase,
    HierarchicalTextChunk,
    TextChunk,
    get_chunker,
)

logger = logging.getLogger(__name__)


class FFRAGClient:
    """High-level RAG client for document indexing and retrieval.

    Combines FFEmbeddings, FFVectorStore, and text chunking into a
    unified interface for RAG operations. Supports multiple chunking
    strategies and hybrid search.

    Args:
        collection_name: ChromaDB collection name.
        persist_dir: Directory for ChromaDB persistence.
        embedding_model: Model string or FFEmbeddings instance.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between chunks.
        n_results_default: Default number of results for search.
        chunking_strategy: Chunking strategy (character, recursive, markdown, code, hierarchical).
        search_mode: Search mode (vector, bm25, hybrid).
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
        chunking_strategy: str | None = None,
        search_mode: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        app_config = get_config()
        rag_config = getattr(app_config, "rag", None)

        self.collection_name = collection_name or (
            rag_config.collection_name if rag_config else "plico_kb"
        )
        self.persist_dir = persist_dir or (rag_config.persist_dir if rag_config else "./chroma_db")

        chunking_cfg = getattr(rag_config, "chunking", None) if rag_config else None
        search_cfg = getattr(rag_config, "search", None) if rag_config else None
        hier_cfg = getattr(rag_config, "hierarchical", None) if rag_config else None

        self.chunk_size = chunk_size or (chunking_cfg.chunk_size if chunking_cfg else 1000)
        self.chunk_overlap = chunk_overlap or (chunking_cfg.chunk_overlap if chunking_cfg else 200)
        self.n_results_default = n_results_default or (
            search_cfg.n_results_default if search_cfg else 5
        )
        self.chunking_strategy = chunking_strategy or (
            chunking_cfg.strategy if chunking_cfg else "recursive"
        )
        self.search_mode = search_mode or (search_cfg.mode if search_cfg else "vector")

        self.hierarchical_enabled = hier_cfg.enabled if hier_cfg else False
        self.parent_context = hier_cfg.parent_context if hier_cfg else True
        self.parent_chunk_size = hier_cfg.parent_chunk_size if hier_cfg else 1500

        self.hybrid_alpha = search_cfg.hybrid_alpha if search_cfg else 0.6
        self.rerank_enabled = search_cfg.rerank if search_cfg else False
        self.rerank_model = search_cfg.rerank_model if search_cfg else ""

        self.use_contextual_headers = (
            chunking_cfg.contextual_headers
            if chunking_cfg and hasattr(chunking_cfg, "contextual_headers")
            else True
        )

        self.query_expansion_enabled = (
            search_cfg.query_expansion
            if search_cfg and hasattr(search_cfg, "query_expansion")
            else False
        )
        self.query_expansion_variations = (
            search_cfg.query_expansion_variations
            if search_cfg and hasattr(search_cfg, "query_expansion_variations")
            else 3
        )

        self.generate_summaries = (
            rag_config.generate_summaries
            if rag_config and hasattr(rag_config, "generate_summaries")
            else False
        )
        self.summary_boost = (
            search_cfg.summary_boost if search_cfg and hasattr(search_cfg, "summary_boost") else 1.5
        )
        self._llm_generate_fn: Callable[[str], str] | None = None

        if config:
            self.collection_name = config.get("collection_name", self.collection_name)
            self.persist_dir = config.get("persist_dir", self.persist_dir)
            self.chunk_size = config.get("chunk_size", self.chunk_size)
            self.chunk_overlap = config.get("chunk_overlap", self.chunk_overlap)
            self.n_results_default = config.get("n_results_default", self.n_results_default)
            self.chunking_strategy = config.get("chunking_strategy", self.chunking_strategy)
            self.search_mode = config.get("search_mode", self.search_mode)

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

        self._bm25_index: BM25Index | None = None
        self._hierarchical_index: HierarchicalIndex | None = None
        self._hybrid_search: HybridSearch | None = None
        self._reranker = None

        if self.search_mode == "hybrid":
            self._init_hybrid_search()

        if self.hierarchical_enabled:
            self._hierarchical_index = HierarchicalIndex(include_parent_context=self.parent_context)

        if self.rerank_enabled:
            self._reranker = get_reranker("cross_encoder", model_name=self.rerank_model)

        self._query_expander: QueryExpander | None = None
        if self.query_expansion_enabled:
            self._query_expander = QueryExpander(
                n_variations=self.query_expansion_variations,
                include_original=True,
            )

        self._chunker = self._create_chunker()

        logger.info(
            f"FFRAGClient initialized: collection={self.collection_name}, "
            f"strategy={self.chunking_strategy}, mode={self.search_mode}, chunks={self._vector_store.count()}"
        )

    def _create_chunker(self) -> ChunkerBase:
        """Create the appropriate chunker based on strategy."""
        kwargs = {}

        if self.chunking_strategy == "markdown":
            rag_config = getattr(get_config(), "rag", None)
            if rag_config and hasattr(rag_config, "chunking"):
                md_cfg = getattr(rag_config.chunking, "markdown", None)
                if md_cfg:
                    kwargs["split_headers"] = md_cfg.split_headers
                    kwargs["preserve_structure"] = md_cfg.preserve_structure
                    kwargs["max_chunk_fallback"] = md_cfg.max_chunk_fallback
        elif self.chunking_strategy == "code":
            rag_config = getattr(get_config(), "rag", None)
            if rag_config and hasattr(rag_config, "chunking"):
                code_cfg = getattr(rag_config.chunking, "code", None)
                if code_cfg:
                    kwargs["language"] = code_cfg.language
                    kwargs["split_by"] = code_cfg.split_by
        elif self.chunking_strategy == "hierarchical":
            kwargs["parent_chunk_size"] = self.parent_chunk_size
            kwargs["max_levels"] = 2

        return get_chunker(
            strategy=self.chunking_strategy,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            **kwargs,
        )

    def _init_hybrid_search(self) -> None:
        """Initialize hybrid search with BM25 index."""
        self._bm25_index = BM25Index()

        docs = self._vector_store.get_all_documents()
        for doc in docs:
            self._bm25_index.add_document(
                doc_id=doc["id"],
                content=doc["content"],
                metadata=doc.get("metadata"),
            )

        self._hybrid_search = HybridSearch(
            vector_search_fn=self._vector_search_only,
            bm25_search_fn=self._bm25_search_only,
            alpha=self.hybrid_alpha,
        )

        logger.info(f"Hybrid search initialized with {len(docs)} documents in BM25 index")

    def _vector_search_only(self, query: str, n_results: int) -> list[dict[str, Any]]:
        """Vector-only search for hybrid."""
        return self._vector_store.search(query, n_results=n_results)

    def _bm25_search_only(self, query: str, n_results: int) -> list[dict[str, Any]]:
        """BM25-only search for hybrid."""
        if not self._bm25_index:
            return []
        return self._bm25_index.search(query, n_results=n_results)

    def add_document(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        reference_name: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        checksum: str | None = None,
        chunking_strategy: str | None = None,
    ) -> int:
        """Add a single document to the knowledge base.

        Args:
            content: Document text content.
            metadata: Optional metadata dict for all chunks.
            reference_name: Optional reference name (added to metadata).
            chunk_size: Override default chunk size.
            chunk_overlap: Override default chunk overlap.
            checksum: Document checksum for tracking (enables reindex detection).
            chunking_strategy: Chunking strategy for clean index management.

        Returns:
            Number of chunks added.

        """
        if not content or not content.strip():
            logger.warning("Attempted to add empty document")
            return 0

        meta = metadata.copy() if metadata else {}
        if reference_name:
            meta["reference_name"] = reference_name

        effective_strategy = chunking_strategy or self.chunking_strategy

        if chunk_size or chunk_overlap:
            chunker = get_chunker(
                strategy=self.chunking_strategy,
                chunk_size=chunk_size or self.chunk_size,
                chunk_overlap=chunk_overlap or self.chunk_overlap,
            )
            chunks = chunker.chunk(content, metadata=meta)
        else:
            chunks = self._chunker.chunk(content, metadata=meta)

        if (
            self.hierarchical_enabled and isinstance(chunks[0], HierarchicalTextChunk)
            if chunks
            else False
        ):
            return self._add_hierarchical_chunks(
                chunks, reference_name, checksum=checksum, chunking_strategy=effective_strategy
            )

        return self._add_regular_chunks(
            chunks, reference_name, checksum=checksum, chunking_strategy=effective_strategy
        )

    def index_document(
        self,
        content: str,
        reference_name: str,
        common_name: str,
        checksum: str,
        force: bool = False,
    ) -> int:
        """Index a document if not already indexed with current strategy/checksum.

        This is the preferred method for indexing documents from the orchestrator.
        It checks if reindexing is needed and only indexes when necessary.

        Args:
            content: Document text content.
            reference_name: Unique reference name for the document.
            common_name: Human-readable name for the document.
            checksum: Document checksum for change detection.
            force: Force reindexing even if document appears unchanged.

        Returns:
            Number of chunks indexed (0 if skipped).

        """
        strategy = self.chunking_strategy

        if not force and not self._vector_store.needs_reindex(
            reference_name=reference_name,
            checksum=checksum,
            chunking_strategy=strategy,
        ):
            logger.debug(f"Document {reference_name} already indexed, skipping")
            return 0

        logger.info(f"Indexing document {reference_name} with strategy {strategy}")

        self._vector_store.delete_by_reference_and_strategy(
            reference_name=reference_name,
            chunking_strategy=strategy,
        )

        chunks_added = self.add_document(
            content=content,
            reference_name=reference_name,
            metadata={"common_name": common_name},
            checksum=checksum,
            chunking_strategy=strategy,
        )

        if self.generate_summaries and self._llm_generate_fn and chunks_added > 0:
            self._generate_and_store_summary(content, reference_name, common_name, checksum)

        logger.info(f"Indexed {chunks_added} chunks for {reference_name}")
        return chunks_added

    SUMMARY_PROMPT = """Summarize the following document in 2-3 sentences.
Focus on the main topic, key concepts, and purpose.

Document:
{content}

Summary:"""

    def set_llm_generate_fn(self, fn: Callable[[str], str]) -> None:
        """Set the LLM generate function for query expansion and summaries.

        Args:
            fn: Function that takes a prompt and returns LLM response.

        """
        self._llm_generate_fn = fn
        if self._query_expander:
            self._query_expander.set_llm_function(fn)
        logger.info("LLM generate function configured for RAG client")

    def _generate_and_store_summary(
        self,
        content: str,
        reference_name: str,
        common_name: str | None = None,
        checksum: str | None = None,
    ) -> bool:
        """Generate and store a document summary as a special chunk.

        Args:
            content: Full document content.
            reference_name: Document reference name.
            common_name: Human-readable name.
            checksum: Document checksum.

        Returns:
            True if summary was generated and stored.

        """
        if not self._llm_generate_fn:
            return False

        try:
            content_for_summary = content[:3000] if len(content) > 3000 else content
            prompt = self.SUMMARY_PROMPT.format(content=content_for_summary)
            summary = self._llm_generate_fn(prompt)

            if not summary or not summary.strip():
                logger.warning(f"Empty summary generated for {reference_name}")
                return False

            from .text_splitter import TextChunk

            summary_chunk = TextChunk(
                content=f"[DOCUMENT SUMMARY]\n{summary.strip()}",
                chunk_index=-1,
                start_char=0,
                end_char=len(content),
                metadata={
                    "reference_name": reference_name,
                    "common_name": common_name or reference_name,
                    "chunk_type": "summary",
                },
            )

            self._vector_store.add_chunks(
                [summary_chunk],
                chunking_strategy=f"{self.chunking_strategy}_summary",
                document_checksum=checksum or "",
            )

            logger.info(f"Generated summary for {reference_name}")
            return True

        except Exception as e:
            logger.warning(f"Failed to generate summary for {reference_name}: {e}")
            return False

    def _add_regular_chunks(
        self,
        chunks: list[TextChunk],
        reference_name: str | None = None,
        checksum: str | None = None,
        chunking_strategy: str | None = None,
    ) -> int:
        """Add regular (non-hierarchical) chunks."""
        texts_for_embedding = None

        if self.use_contextual_headers:
            from .indexing.contextual_embeddings import ContextualEmbeddings

            contextual = ContextualEmbeddings()
            chunks_for_context = [{"content": c.content, "metadata": c.metadata} for c in chunks]
            texts_for_embedding = contextual.prepare_chunks_batch(
                chunks_for_context,
                document_title=reference_name,
            )

        count = self._vector_store.add_chunks(
            chunks,
            chunking_strategy=chunking_strategy or self.chunking_strategy,
            document_checksum=checksum or "",
            texts_for_embedding=texts_for_embedding,
        )

        if self._bm25_index:
            for chunk in chunks:
                chunk_id = (
                    f"{(chunk.metadata or {}).get('reference_name', 'doc')}_{chunk.chunk_index}"
                )
                self._bm25_index.add_document(
                    doc_id=chunk_id,
                    content=chunk.content,
                    metadata=chunk.metadata,
                )

        return count

    def _add_hierarchical_chunks(
        self,
        chunks: list[HierarchicalTextChunk],
        reference_name: str | None = None,
        checksum: str | None = None,
        chunking_strategy: str | None = None,
    ) -> int:
        """Add hierarchical chunks with parent-child relationships."""
        if not self._hierarchical_index:
            self._hierarchical_index = HierarchicalIndex(include_parent_context=self.parent_context)

        child_chunks = [c for c in chunks if c.hierarchy_level > 0]

        texts = [c.content for c in child_chunks]
        embeddings = self._embeddings.embed(texts)

        ids = []
        for i, chunk in enumerate(child_chunks):
            chunk_id = (
                f"{(chunk.metadata or {}).get('reference_name', 'doc')}_{chunk.chunk_index}_{i}"
            )
            ids.append(chunk_id)

            self._hierarchical_index.add_chunk(
                chunk_id=chunk_id,
                content=chunk.content,
                embedding=embeddings[i] if i < len(embeddings) else None,
                parent_id=chunk.parent_id,
                hierarchy_level=chunk.hierarchy_level,
                metadata=chunk.metadata,
            )

        count = self._vector_store.add_chunks(
            child_chunks,
            ids=ids,
            chunking_strategy=chunking_strategy or self.chunking_strategy,
            document_checksum=checksum or "",
        )

        if self._bm25_index:
            for chunk_id, chunk in zip(ids, child_chunks):
                self._bm25_index.add_document(
                    doc_id=chunk_id,
                    content=chunk.content,
                    metadata=chunk.metadata,
                )

        return count

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
        total = 0
        for doc in documents:
            content = doc.get(text_key, "")
            metadata = {k: v for k, v in doc.items() if k != text_key}
            reference_name = metadata.get("reference_name")
            total += self.add_document(content, metadata=metadata, reference_name=reference_name)
        return total

    def search(
        self,
        query: str,
        n_results: int | None = None,
        where: dict | None = None,
        query_expansion: bool | None = None,
        rerank: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Search for relevant documents.

        Args:
            query: Query text.
            n_results: Number of results (defaults to n_results_default).
            where: Optional metadata filter.
            query_expansion: Override instance query_expansion setting.
            rerank: Override instance rerank_enabled setting.

        Returns:
            List of results with content, metadata, and score.

        """
        n = n_results or self.n_results_default

        use_expansion = (
            query_expansion if query_expansion is not None else self.query_expansion_enabled
        )
        use_rerank = rerank if rerank is not None else self.rerank_enabled

        if use_expansion:
            self._ensure_query_expander()
            if self._query_expander and self._query_expander.llm_generate_fn:
                return self._search_with_expansion(query, n, where, use_rerank)

        return self._search_single(query, n, where, use_rerank)

    def _ensure_query_expander(self) -> None:
        """Lazily initialize query expander if needed."""
        if self._query_expander is None:
            self._query_expander = QueryExpander(
                n_variations=self.query_expansion_variations,
                include_original=True,
            )
            if self._llm_generate_fn:
                self._query_expander.set_llm_function(self._llm_generate_fn)
            logger.info("Query expander lazily initialized for per-prompt override")

    def _ensure_reranker(self) -> None:
        """Lazily initialize reranker if needed."""
        if self._reranker is None:
            self._reranker = get_reranker("cross_encoder", model_name=self.rerank_model)
            logger.info("Reranker lazily initialized for per-prompt override")

    def _search_single(
        self,
        query: str,
        n_results: int,
        where: dict | None = None,
        rerank: bool = True,
    ) -> list[dict[str, Any]]:
        """Perform a single search without query expansion."""
        fetch_count = n_results * 2 if self.generate_summaries else n_results

        if self._hybrid_search and self.search_mode == "hybrid":
            results = self._hybrid_search.search(query, n_results=fetch_count, mode="hybrid")
        else:
            results = self._vector_store.search(query, n_results=fetch_count, where=where)

        for result in results:
            if result.get("distance") is not None:
                result["score"] = 1.0 - result["distance"]
            elif result.get("rrf_score") is not None:
                result["score"] = result["rrf_score"]
            elif result.get("score") is None:
                result["score"] = 0.0

        if self.generate_summaries:
            for result in results:
                if result.get("metadata", {}).get("chunk_type") == "summary":
                    result["score"] = result.get("score", 1.0) * self.summary_boost
                    result["is_summary"] = True
            results.sort(key=lambda x: x.get("score", 0.0), reverse=True)

        if self._hierarchical_index and self.parent_context:
            results = self._hierarchical_index.enhance_results_with_context(results)

        if rerank:
            self._ensure_reranker()
            if self._reranker and results:
                results = self._reranker.rerank(query, results, n_results=n_results)
                logger.info("Search results reranked")
                return results

        return results[:n_results]

    def _search_with_expansion(
        self,
        query: str,
        n_results: int,
        where: dict | None = None,
        rerank: bool = True,
    ) -> list[dict[str, Any]]:
        """Perform multi-query search with expansion."""
        queries = self._query_expander.expand(query)
        logger.info(f"Query expansion: {len(queries)} variations generated")

        all_result_lists = []
        for q in queries:
            results = self._vector_store.search(q, n_results=n_results * 2, where=where)
            all_result_lists.append(results)

        fused = fuse_search_results(all_result_lists, n_results=n_results * 2)

        for result in fused:
            if result.get("distance") is not None:
                result["score"] = 1.0 - result["distance"]
            elif result.get("score") is None:
                result["score"] = 0.0

        if self._hierarchical_index and self.parent_context:
            fused = self._hierarchical_index.enhance_results_with_context(fused)

        if rerank:
            self._ensure_reranker()
            if self._reranker and fused:
                fused = self._reranker.rerank(query, fused, n_results=n_results)
                logger.info("Query expansion search results reranked")
                return fused[:n_results]

        return fused[:n_results]

    def set_query_expansion_llm(self, llm_generate_fn: Callable[[str], str]) -> None:
        """Set the LLM function for query expansion.

        Args:
            llm_generate_fn: Function that takes a prompt and returns LLM response.

        """
        if self._query_expander:
            self._query_expander.set_llm_function(llm_generate_fn)
            logger.info("Query expansion LLM function configured")
        else:
            logger.warning("Query expansion is not enabled")

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
            score = result.get("score", 0.0)

            parent_content = result.get("parent_content")
            if parent_content and self.parent_context:
                context_note = (
                    f"\n[Parent context: {parent_content[:200]}...]"
                    if len(parent_content) > 200
                    else f"\n[Parent context: {parent_content}]"
                )
            else:
                context_note = ""

            chunk_text = (
                f"[{i}] (source: {source}, relevance: {score:.2f})\n{content}{context_note}\n"
            )

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

        if self._bm25_index:
            all_docs = self._bm25_index.search(reference_name, n_results=1000)
            for doc in all_docs:
                meta = doc.get("metadata", {})
                if meta.get("reference_name") == reference_name:
                    self._bm25_index.delete_document(doc["id"])

        if self._hierarchical_index:
            self._hierarchical_index.delete_by_reference(reference_name)

    def clear_chunking_strategy(self, chunking_strategy: str) -> int:
        """Clear all chunks for a specific chunking strategy.

        Args:
            chunking_strategy: The chunking strategy to clear (e.g., "recursive", "markdown").

        Returns:
            Approximate number of chunks cleared.

        """
        logger.info(f"Clearing all chunks with chunking_strategy={chunking_strategy}")

        indexed_docs = self._vector_store.get_indexed_documents(chunking_strategy=chunking_strategy)
        count = 0
        for doc in indexed_docs:
            ref_name = doc.get("reference_name")
            if ref_name:
                self._vector_store.delete_by_reference_and_strategy(ref_name, chunking_strategy)
                count += 1

        if self._bm25_index:
            self._bm25_index.clear()

        if self._hierarchical_index:
            self._hierarchical_index.clear()

        logger.info(f"Cleared chunking_strategy={chunking_strategy} for {count} documents")
        return count

    def get_indexed_documents(self, chunking_strategy: str | None = None) -> list[dict[str, Any]]:
        """Get list of indexed documents.

        Args:
            chunking_strategy: Optional filter by chunking strategy.

        Returns:
            List of dicts with reference_name, chunking_strategy, document_checksum, indexed_at.

        """
        return self._vector_store.get_indexed_documents(chunking_strategy=chunking_strategy)

    def needs_reindex(
        self, reference_name: str, checksum: str, chunking_strategy: str | None = None
    ) -> bool:
        """Check if a document needs re-indexing.

        Args:
            reference_name: Document reference name.
            checksum: Current document checksum.
            chunking_strategy: Chunking strategy to check (defaults to current strategy).

        Returns:
            True if document needs re-indexing.

        """
        effective_strategy = chunking_strategy or self.chunking_strategy
        return self._vector_store.needs_reindex(reference_name, checksum, effective_strategy)

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
        stats["chunking_strategy"] = self.chunking_strategy
        stats["search_mode"] = self.search_mode
        stats["hierarchical_enabled"] = self.hierarchical_enabled

        if self._bm25_index:
            stats["bm25_docs"] = self._bm25_index.count()
        if self._hierarchical_index:
            stats["hierarchical"] = self._hierarchical_index.get_stats()

        return stats

    def clear(self) -> None:
        """Clear all documents from the knowledge base."""
        self._vector_store.clear()

        if self._bm25_index:
            self._bm25_index.clear()

        if self._hierarchical_index:
            self._hierarchical_index.clear()

    @property
    def vector_store(self) -> FFVectorStore:
        """Access the underlying FFVectorStore for advanced operations."""
        return self._vector_store

    @property
    def embeddings(self) -> FFEmbeddings:
        """Access the underlying FFEmbeddings instance."""
        return self._embeddings

    @property
    def chunker(self) -> ChunkerBase:
        """Access the chunker instance."""
        return self._chunker
