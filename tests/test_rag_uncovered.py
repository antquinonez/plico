# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""Tests for uncovered RAG code paths.

Covers: contextual embeddings edge cases, LateChunkingEmbeddings placeholder,
query expansion parsing edge cases, BM25 search quality invariants,
HybridSearch.set_search_functions, ChunkerBase.name property, and
HierarchicalChunker.get_chunks_with_parent_context.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.RAG.indexing.contextual_embeddings import (
    ContextualEmbeddings,
    LateChunkingEmbeddings,
)
from src.RAG.indexing.deduplication import ChunkDeduplicator
from src.RAG.search import HybridSearch, reciprocal_rank_fusion
from src.RAG.search.query_expansion import QueryExpander
from src.RAG.text_splitters import (
    CharacterChunker,
    CodeChunker,
    HierarchicalChunker,
    MarkdownChunker,
    RecursiveChunker,
)


class TestContextualEmbeddingsEdgeCases:
    """Tests for ContextualEmbeddings uncovered paths."""

    def test_prepare_chunk_no_title_no_section(self) -> None:
        """When no title or section, chunk content is returned as-is."""
        ce = ContextualEmbeddings()
        result = ce.prepare_chunk_for_embedding("chunk text")
        assert result == "chunk text"

    def test_prepare_chunk_title_only(self) -> None:
        """Title adds Document prefix to output."""
        ce = ContextualEmbeddings()
        result = ce.prepare_chunk_for_embedding("chunk text", document_title="My Doc")
        assert "Document: My Doc" in result
        assert "chunk text" in result
        assert "\n\n" in result

    def test_prepare_chunk_title_and_section(self) -> None:
        """Both title and section are included in context prefix."""
        ce = ContextualEmbeddings()
        result = ce.prepare_chunk_for_embedding(
            "chunk text", document_title="My Doc", section_header="Intro"
        )
        assert "Document: My Doc" in result
        assert "Section: Intro" in result

    def test_truncate_short_text_unchanged(self) -> None:
        """Text shorter than max_length is returned unchanged."""
        ce = ContextualEmbeddings()
        assert ce._truncate("hello", 10) == "hello"

    def test_truncate_preserves_word_boundary(self) -> None:
        """Long text truncates at last space before max_length."""
        ce = ContextualEmbeddings()
        result = ce._truncate("hello world foo bar", 15)
        assert result == "hello world..."

    def test_truncate_no_space_early_hard_truncates(self) -> None:
        """When no space after midpoint, appends ellipsis without word boundary."""
        ce = ContextualEmbeddings()
        result = ce._truncate("helloworldfoobar", 10)
        assert result == "helloworld..."

    def test_truncate_empty_returns_empty(self) -> None:
        """Empty string returns empty string."""
        ce = ContextualEmbeddings()
        assert ce._truncate("", 10) == ""

    def test_prepare_chunks_batch_with_metadata_title(self) -> None:
        """Per-chunk document_title in metadata overrides batch title."""
        ce = ContextualEmbeddings()
        chunks = [
            {"content": "content", "metadata": {"document_title": "Custom Title"}},
        ]
        results = ce.prepare_chunks_batch(chunks, document_title="Batch Doc")
        assert "Custom Title" in results[0]
        assert "Batch Doc" not in results[0]

    def test_prepare_chunks_batch_with_section_header(self) -> None:
        """Section header from metadata is included in output."""
        ce = ContextualEmbeddings()
        chunks = [
            {"content": "content", "metadata": {"header": "Section 1"}},
        ]
        results = ce.prepare_chunks_batch(chunks, document_title="Doc")
        assert "Section: Section 1" in results[0]


class TestLateChunkingEmbeddings:
    """Tests for LateChunkingEmbeddings placeholder."""

    def test_returns_empty_list(self) -> None:
        """Placeholder returns empty list with no model."""
        lce = LateChunkingEmbeddings()
        result = lce.embed_document_with_tokens("doc1", "content", [(0, 7)])
        assert result == []

    def test_with_model_still_returns_empty(self) -> None:
        """Even with an embedding_model, placeholder returns empty list."""
        mock_model = MagicMock()
        lce = LateChunkingEmbeddings(embedding_model=mock_model)
        result = lce.embed_document_with_tokens("doc1", "content", [(0, 7)])
        assert result == []
        assert lce.embedding_model is mock_model


class TestQueryExpansionParsing:
    """Tests for QueryExpander._parse_response edge cases."""

    def test_parse_empty_response(self) -> None:
        """Empty response returns empty list."""
        expander = QueryExpander()
        assert expander._parse_response("") == []

    def test_parse_short_items_filtered(self) -> None:
        """Items shorter than 4 characters are filtered out."""
        expander = QueryExpander()
        result = expander._parse_response("1. ab")
        assert result == []

    def test_parse_quoted_items_stripped(self) -> None:
        """Quoted items have their quotes stripped."""
        expander = QueryExpander()
        result = expander._parse_response('1. "hello world"\n2. test query')
        assert result == ["hello world", "test query"]

    def test_parse_parenthesis_numbered(self) -> None:
        """Parenthesis-style numbering (1)) is parsed correctly."""
        expander = QueryExpander()
        result = expander._parse_response("1) first query\n2) second query")
        assert result == ["first query", "second query"]

    def test_parse_skips_empty_lines(self) -> None:
        """Empty lines between items are skipped."""
        expander = QueryExpander()
        result = expander._parse_response("1. first\n\n3. third")
        assert result == ["first", "third"]

    def test_parse_single_quoted_items(self) -> None:
        """Single-quoted items have their quotes stripped."""
        expander = QueryExpander()
        result = expander._parse_response("1. 'hello world query'")
        assert result == ["hello world query"]

    def test_set_llm_function_updates_fn(self) -> None:
        """set_llm_function replaces the LLM generate function."""
        expander = QueryExpander()
        mock_fn = MagicMock(return_value="response")
        expander.set_llm_function(mock_fn)
        assert expander.llm_generate_fn is mock_fn

    def test_expand_deduplicates_queries(self) -> None:
        """Duplicate variations are removed while preserving order."""

        def mock_llm(prompt: str) -> str:
            return "1. authentication\n2. authentication\n3. other query"

        expander = QueryExpander(llm_generate_fn=mock_llm, n_variations=3)
        queries = expander.expand("authentication")
        assert queries.count("authentication") == 1
        assert "other query" in queries

    def test_expand_llm_returns_empty_uses_original(self) -> None:
        """When LLM returns no parseable variations, original is returned."""

        def mock_llm(prompt: str) -> str:
            return "..."

        expander = QueryExpander(llm_generate_fn=mock_llm, n_variations=3)
        queries = expander.expand("test query")
        assert queries == ["test query"]


class TestBM25SearchQualityInvariants:
    """Tests verifying BM25 search quality invariants."""

    def test_higher_tf_ranks_higher(self) -> None:
        """Document with more term occurrences ranks higher."""
        from src.RAG.indexing import BM25Index

        idx = BM25Index()
        idx.add_document("d1", "python python python")
        idx.add_document("d2", "python")
        idx.add_document("d3", "python python")

        results = idx.search("python", n_results=3)
        assert results[0]["id"] == "d1"
        assert results[1]["id"] == "d3"
        assert results[2]["id"] == "d2"

    def test_idf_penalizes_common_terms(self) -> None:
        """Terms appearing in every document score lower than rare terms."""
        from src.RAG.indexing import BM25Index

        idx = BM25Index()
        idx.add_document("d1", "python programming")
        idx.add_document("d2", "python cooking")
        idx.add_document("d3", "java programming")

        results_python = idx.search("python", n_results=3)
        results_java = idx.search("java", n_results=3)
        results_programming = idx.search("programming", n_results=3)

        python_top = results_python[0]["score"]
        java_top = results_java[0]["score"]
        programming_top = results_programming[0]["score"]

        assert java_top > python_top
        assert programming_top < java_top

    def test_scores_are_non_negative(self) -> None:
        """All BM25 scores should be non-negative."""
        from src.RAG.indexing import BM25Index

        idx = BM25Index()
        idx.add_document("d1", "test document one")
        idx.add_document("d2", "test document two")

        results = idx.search("test", n_results=5)
        for r in results:
            assert r["score"] >= 0

    def test_avg_doc_length_maintained(self) -> None:
        """Average document length is correctly computed after adds and deletes."""
        from src.RAG.indexing import BM25Index

        idx = BM25Index()
        idx.add_document("d1", "alpha beta gamma")
        idx.add_document("d2", "delta echo")
        idx.add_document("d3", "foxtrot golf")

        assert idx._avg_doc_length == 7 / 3

        idx.delete_document("d1")
        assert idx._avg_doc_length == 2.0

    def test_search_returns_at_most_n_results(self) -> None:
        """Search respects n_results parameter."""
        from src.RAG.indexing import BM25Index

        idx = BM25Index()
        for i in range(10):
            idx.add_document(f"d{i}", f"document number {i}")

        results = idx.search("document", n_results=3)
        assert len(results) == 3


class TestHybridSearchExtended:
    """Extended tests for HybridSearch uncovered paths."""

    def test_set_search_functions_both(self) -> None:
        """set_search_functions updates both functions."""
        hs = HybridSearch()

        def vf(q, n):
            return []

        def bf(q, n):
            return []

        hs.set_search_functions(vector_search_fn=vf, bm25_search_fn=bf)
        assert hs.vector_search_fn is vf
        assert hs.bm25_search_fn is bf

    def test_set_search_functions_vector_only(self) -> None:
        """set_search_functions only updates provided functions."""
        hs = HybridSearch()

        def vf(q, n):
            return [{"id": "1", "content": "V", "score": 0.9}]

        hs.set_search_functions(vector_search_fn=vf)
        assert hs.vector_search_fn is vf
        assert hs.bm25_search_fn is None

    def test_hybrid_with_missing_id_in_results(self) -> None:
        """Results missing 'id' field are excluded from fusion."""

        def missing_id_fn(q, n):
            return [{"content": "no id", "score": 0.9}]

        hs = HybridSearch(vector_search_fn=missing_id_fn, bm25_search_fn=missing_id_fn)
        results = hs.search("test", mode="hybrid")
        assert results == []

    def test_hybrid_fusion_ordering(self) -> None:
        """Doc appearing in both lists ranks above docs in only one list."""

        def vf(q, n):
            return [{"id": "shared", "content": "S", "score": 0.9}]

        def bf(q, n):
            return [{"id": "shared", "content": "S", "score": 2.0}]

        hs = HybridSearch(vector_search_fn=vf, bm25_search_fn=bf)
        results = hs.search("test", mode="hybrid")
        assert len(results) == 1
        assert results[0]["id"] == "shared"
        assert results[0]["vector_score"] == 0.9
        assert results[0]["bm25_score"] == 2.0

    def test_reciprocal_rank_fusion_empty_list_in_lists(self) -> None:
        """RRF handles empty sub-lists gracefully."""
        fused = reciprocal_rank_fusion([[{"id": "a", "content": "A", "metadata": {}}], []])
        assert len(fused) == 1
        assert fused[0]["id"] == "a"


class TestChunkerBaseName:
    """Tests for ChunkerBase.name property."""

    def test_character_chunker_name(self) -> None:
        assert CharacterChunker().name == "character"

    def test_recursive_chunker_name(self) -> None:
        assert RecursiveChunker().name == "recursive"

    def test_markdown_chunker_name(self) -> None:
        assert MarkdownChunker().name == "markdown"

    def test_code_chunker_name(self) -> None:
        assert CodeChunker().name == "code"

    def test_hierarchical_chunker_name(self) -> None:
        assert HierarchicalChunker().name == "hierarchical"


class TestHierarchicalChunkerParentContext:
    """Tests for HierarchicalChunker.get_chunks_with_parent_context."""

    def test_child_gets_parent_content(self) -> None:
        """Child chunks receive their parent's content."""
        chunker = HierarchicalChunker(chunk_size=50, chunk_overlap=10, parent_chunk_size=150)
        text = "A" * 20 + " " + "B" * 20 + " " + "C" * 20 + " " + "D" * 20 + " " + "E" * 20
        all_chunks = chunker.chunk(text)

        parents = [c for c in all_chunks if c.hierarchy_level == 0]
        children = [c for c in all_chunks if c.hierarchy_level > 0]

        if children and parents:
            results = chunker.get_chunks_with_parent_context(children, all_chunks)
            for r in results:
                assert r["child"] in children
                if r["parent"] is not None:
                    assert r["parent"].hierarchy_level == 0
                    assert r["parent_content"] is not None


class TestDeduplicationInvariants:
    """Property-based tests for chunk deduplication invariants."""

    def test_exact_dedup_idempotent(self) -> None:
        """Calling is_duplicate twice with same text: first False, second True."""
        dedup = ChunkDeduplicator(mode="exact")
        assert dedup.is_duplicate("hello") is False
        assert dedup.is_duplicate("hello") is True

    def test_similarity_dedup_identical_vectors(self) -> None:
        """Identical vectors are detected as duplicates above threshold."""
        dedup = ChunkDeduplicator(mode="similarity", similarity_threshold=0.99)
        vec = [1.0, 0.0, 0.0]
        assert dedup.is_duplicate("text1", embedding=vec) is False
        assert dedup.is_duplicate("text2", embedding=vec) is True

    def test_hash_deterministic(self) -> None:
        """Same content always produces same hash."""
        dedup = ChunkDeduplicator()
        h1 = dedup.compute_hash("test content")
        h2 = dedup.compute_hash("test content")
        assert h1 == h2

    def test_hash_different_content(self) -> None:
        """Different content produces different hashes."""
        dedup = ChunkDeduplicator()
        h1 = dedup.compute_hash("content A")
        h2 = dedup.compute_hash("content B")
        assert h1 != h2

    def test_cosine_similarity_bounds(self) -> None:
        """Cosine similarity is always in [-1, 1]."""
        dedup = ChunkDeduplicator()
        pairs = [
            ([1, 0], [0, 1]),
            ([1, 0], [1, 0]),
            ([1, 0], [-1, 0]),
            ([0, 0], [1, 0]),
            ([1, 1], [2, 2]),
        ]
        for v1, v2 in pairs:
            sim = dedup._cosine_similarity(v1, v2)
            assert -1.0 <= sim <= 1.0, f"sim={sim} for {v1}, {v2}"
