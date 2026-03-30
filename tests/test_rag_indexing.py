# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""Tests for indexing strategies (BM25, Hierarchical, Contextual)."""

from __future__ import annotations

from src.RAG.indexing import BM25Index, ContextualEmbeddings, HierarchicalIndex


class TestBM25Index:
    """Tests for BM25 sparse index."""

    def test_add_and_search(self) -> None:
        """Basic add and search works."""
        index = BM25Index()
        index.add_document("doc1", "The quick brown fox jumps over the lazy dog")
        index.add_document("doc2", "A lazy cat sleeps all day")

        results = index.search("lazy animal", n_results=2)

        assert len(results) == 2
        assert all("id" in r and "score" in r for r in results)

    def test_search_returns_content(self) -> None:
        """Search results include content and metadata."""
        index = BM25Index()
        index.add_document("doc1", "Python programming language", metadata={"type": "doc"})
        index.add_document("doc2", "JavaScript web development", metadata={"type": "doc"})

        results = index.search("Python", n_results=1)

        assert len(results) == 1
        assert "Python" in results[0]["content"]
        assert results[0]["metadata"]["type"] == "doc"

    def test_empty_search_returns_empty(self) -> None:
        """Empty index returns empty results."""
        index = BM25Index()
        results = index.search("query", n_results=5)
        assert results == []

    def test_delete_document(self) -> None:
        """Documents can be deleted."""
        index = BM25Index()
        index.add_document("doc1", "Content to delete")
        index.add_document("doc2", "Content to keep")

        assert index.delete_document("doc1")
        assert index.count() == 1

        results = index.search("Content", n_results=5)
        assert len(results) == 1
        assert results[0]["id"] == "doc2"

    def test_delete_nonexistent(self) -> None:
        """Deleting nonexistent document returns False."""
        index = BM25Index()
        assert not index.delete_document("nonexistent")

    def test_count(self) -> None:
        """Count returns correct number of documents."""
        index = BM25Index()
        assert index.count() == 0

        index.add_document("doc1", "Content 1")
        assert index.count() == 1

        index.add_document("doc2", "Content 2")
        assert index.count() == 2

    def test_clear(self) -> None:
        """Clear removes all documents."""
        index = BM25Index()
        index.add_document("doc1", "Content 1")
        index.add_document("doc2", "Content 2")

        index.clear()
        assert index.count() == 0

    def test_get_stats(self) -> None:
        """Stats return index information."""
        index = BM25Index(k1=1.5, b=0.75)
        index.add_document("doc1", "Test content")

        stats = index.get_stats()

        assert stats["total_docs"] == 1
        assert stats["k1"] == 1.5
        assert stats["b"] == 0.75

    def test_add_documents_batch(self) -> None:
        """Multiple documents can be added at once."""
        index = BM25Index()
        docs = [
            {"id": "doc1", "content": "First document"},
            {"id": "doc2", "content": "Second document"},
            {"id": "doc3", "content": "Third document"},
        ]

        count = index.add_documents(docs)
        assert count == 3
        assert index.count() == 3


class TestHierarchicalIndex:
    """Tests for hierarchical index."""

    def test_add_parent_chunk(self) -> None:
        """Parent chunks can be added."""
        index = HierarchicalIndex()
        index.add_chunk(
            chunk_id="parent1",
            content="Parent content",
            hierarchy_level=0,
            metadata={"type": "parent"},
        )

        chunk = index.get_chunk("parent1")
        assert chunk is not None
        assert chunk["hierarchy_level"] == 0

    def test_add_child_with_parent(self) -> None:
        """Child chunks reference their parent."""
        index = HierarchicalIndex()
        index.add_chunk(
            chunk_id="parent1",
            content="Parent content",
            hierarchy_level=0,
        )
        index.add_chunk(
            chunk_id="child1",
            content="Child content",
            parent_id="parent1",
            hierarchy_level=1,
        )

        parent = index.get_parent("child1")
        assert parent is not None
        assert parent["id"] == "parent1"

        children = index.get_children("parent1")
        assert len(children) == 1
        assert children[0]["id"] == "child1"

    def test_get_parent_chunks(self) -> None:
        """Can filter to get only parent chunks."""
        index = HierarchicalIndex()
        index.add_chunk("parent1", "P1", hierarchy_level=0)
        index.add_chunk("child1", "C1", parent_id="parent1", hierarchy_level=1)

        parents = index.get_parent_chunks()
        assert len(parents) == 1
        assert parents[0]["id"] == "parent1"

    def test_get_child_chunks(self) -> None:
        """Can filter to get only child chunks."""
        index = HierarchicalIndex()
        index.add_chunk("parent1", "P1", hierarchy_level=0)
        index.add_chunk("child1", "C1", parent_id="parent1", hierarchy_level=1)
        index.add_chunk("child2", "C2", parent_id="parent1", hierarchy_level=1)

        children = index.get_child_chunks()
        assert len(children) == 2

    def test_enhance_results_with_context(self) -> None:
        """Results can be enhanced with parent context."""
        index = HierarchicalIndex(include_parent_context=True)
        index.add_chunk("parent1", "Full parent content here", hierarchy_level=0)
        index.add_chunk(
            "child1",
            "Child excerpt",
            parent_id="parent1",
            hierarchy_level=1,
        )

        results = [{"id": "child1", "content": "Child excerpt", "score": 0.9}]
        enhanced = index.enhance_results_with_context(results)

        assert len(enhanced) == 1
        assert enhanced[0]["parent_content"] == "Full parent content here"
        assert enhanced[0]["parent_id"] == "parent1"

    def test_delete_chunk(self) -> None:
        """Chunks can be deleted."""
        index = HierarchicalIndex()
        index.add_chunk("chunk1", "Content", hierarchy_level=0)

        assert index.delete_chunk("chunk1")
        assert index.get_chunk("chunk1") is None

    def test_delete_parent_removes_children(self) -> None:
        """Deleting parent removes children."""
        index = HierarchicalIndex()
        index.add_chunk("parent1", "P1", hierarchy_level=0)
        index.add_chunk("child1", "C1", parent_id="parent1", hierarchy_level=1)

        index.delete_chunk("parent1")

        assert index.get_chunk("parent1") is None
        assert index.get_chunk("child1") is None

    def test_count_stats(self) -> None:
        """Count methods return correct values."""
        index = HierarchicalIndex()
        index.add_chunk("parent1", "P1", hierarchy_level=0)
        index.add_chunk("child1", "C1", parent_id="parent1", hierarchy_level=1)
        index.add_chunk("child2", "C2", parent_id="parent1", hierarchy_level=1)

        assert index.count() == 3
        assert index.count_parents() == 1
        assert index.count_children() == 2


class TestHierarchicalIndexExtended:
    """Extended tests for hierarchical index edge cases."""

    def test_get_parent_returns_none_for_root(self) -> None:
        """get_parent returns None for chunks without parents."""
        index = HierarchicalIndex()
        index.add_chunk("root", "Root content", hierarchy_level=0)
        assert index.get_parent("root") is None

    def test_get_parent_returns_none_for_unknown(self) -> None:
        """get_parent returns None for unknown chunk IDs."""
        index = HierarchicalIndex()
        assert index.get_parent("nonexistent") is None

    def test_get_child_embeddings(self) -> None:
        """get_child_embeddings returns IDs and embeddings for child chunks."""
        index = HierarchicalIndex()
        index.add_chunk("parent1", "P1", hierarchy_level=0)
        index.add_chunk(
            "child1",
            "C1",
            parent_id="parent1",
            hierarchy_level=1,
            embedding=[0.1, 0.2],
        )
        index.add_chunk(
            "child2",
            "C2",
            parent_id="parent1",
            hierarchy_level=1,
            embedding=[0.3, 0.4],
        )

        ids, embeddings = index.get_child_embeddings()
        assert len(ids) == 2
        assert len(embeddings) == 2
        assert "child1" in ids
        assert "child2" in ids

    def test_get_child_embeddings_skips_none_embedding(self) -> None:
        """get_child_embeddings skips children without embeddings."""
        index = HierarchicalIndex()
        index.add_chunk("parent1", "P1", hierarchy_level=0)
        index.add_chunk("child1", "C1", parent_id="parent1", hierarchy_level=1, embedding=None)
        index.add_chunk("child2", "C2", parent_id="parent1", hierarchy_level=1, embedding=[0.1])

        ids, embeddings = index.get_child_embeddings()
        assert len(ids) == 1
        assert ids[0] == "child2"

    def test_enhance_results_with_context_disabled(self) -> None:
        """enhance_results_with_context skips parent when disabled."""
        index = HierarchicalIndex(include_parent_context=False)
        index.add_chunk("parent1", "Parent", hierarchy_level=0)
        index.add_chunk("child1", "Child", parent_id="parent1", hierarchy_level=1)

        results = [{"id": "child1", "content": "Child"}]
        enhanced = index.enhance_results_with_context(results)
        assert "parent_content" not in enhanced[0]

    def test_enhance_results_override_include_parent(self) -> None:
        """include_parent parameter overrides default."""
        index = HierarchicalIndex(include_parent_context=False)
        index.add_chunk("parent1", "Parent", hierarchy_level=0)
        index.add_chunk("child1", "Child", parent_id="parent1", hierarchy_level=1)

        results = [{"id": "child1", "content": "Child"}]
        enhanced = index.enhance_results_with_context(results, include_parent=True)
        assert enhanced[0]["parent_content"] == "Parent"

    def test_enhance_results_no_chunk_id(self) -> None:
        """enhance_results handles results without id field."""
        index = HierarchicalIndex(include_parent_context=True)
        index.add_chunk("parent1", "Parent", hierarchy_level=0)

        results = [{"content": "no id"}]
        enhanced = index.enhance_results_with_context(results)
        assert "parent_content" not in enhanced[0]

    def test_delete_nonexistent_chunk(self) -> None:
        """delete_chunk returns False for nonexistent chunk."""
        index = HierarchicalIndex()
        assert index.delete_chunk("nonexistent") is False

    def test_delete_child_updates_parent(self) -> None:
        """Deleting child updates parent's children list."""
        index = HierarchicalIndex()
        index.add_chunk("parent1", "P1", hierarchy_level=0)
        index.add_chunk("child1", "C1", parent_id="parent1", hierarchy_level=1)
        index.add_chunk("child2", "C2", parent_id="parent1", hierarchy_level=1)

        assert index.delete_chunk("child1")
        children = index.get_children("parent1")
        assert len(children) == 1
        assert children[0]["id"] == "child2"

    def test_delete_child_removes_mapping(self) -> None:
        """Deleting child removes child_to_parent mapping."""
        index = HierarchicalIndex()
        index.add_chunk("parent1", "P1", hierarchy_level=0)
        index.add_chunk("child1", "C1", parent_id="parent1", hierarchy_level=1)

        index.delete_chunk("child1")
        assert index.get_parent("child1") is None

    def test_delete_by_reference(self) -> None:
        """delete_by_reference removes all chunks for a reference."""
        index = HierarchicalIndex()
        index.add_chunk("c1", "Content1", hierarchy_level=0, metadata={"reference_name": "doc1"})
        index.add_chunk("c2", "Content2", hierarchy_level=0, metadata={"reference_name": "doc1"})
        index.add_chunk("c3", "Content3", hierarchy_level=0, metadata={"reference_name": "doc2"})

        count = index.delete_by_reference("doc1")
        assert count == 2
        assert index.count() == 1
        assert index.get_chunk("c3") is not None

    def test_delete_by_reference_no_matches(self) -> None:
        """delete_by_reference returns 0 for unknown reference."""
        index = HierarchicalIndex()
        index.add_chunk("c1", "Content", hierarchy_level=0)

        count = index.delete_by_reference("nonexistent")
        assert count == 0

    def test_clear(self) -> None:
        """clear removes all chunks."""
        index = HierarchicalIndex()
        index.add_chunk("p1", "Parent", hierarchy_level=0)
        index.add_chunk("c1", "Child", parent_id="p1", hierarchy_level=1)

        index.clear()
        assert index.count() == 0
        assert index.count_parents() == 0
        assert index.count_children() == 0

    def test_get_stats(self) -> None:
        """get_stats returns index statistics."""
        index = HierarchicalIndex(include_parent_context=False)
        index.add_chunk("p1", "P", hierarchy_level=0)
        index.add_chunk("c1", "C", parent_id="p1", hierarchy_level=1)

        stats = index.get_stats()
        assert stats["total_chunks"] == 2
        assert stats["parent_chunks"] == 1
        assert stats["child_chunks"] == 1
        assert stats["include_parent_context"] is False

    def test_add_child_to_existing_parent(self) -> None:
        """Adding child to parent that already exists initializes children list."""
        index = HierarchicalIndex()
        index.add_chunk("p1", "P", hierarchy_level=0)
        index.add_chunk("c1", "C1", parent_id="p1", hierarchy_level=1)
        index.add_chunk("c2", "C2", parent_id="p1", hierarchy_level=1)

        children = index.get_children("p1")
        assert len(children) == 2


class TestContextualEmbeddings:
    """Tests for contextual embeddings preparation."""

    def test_prepare_chunk_basic(self) -> None:
        """Basic chunk preparation adds context."""
        preparer = ContextualEmbeddings()
        result = preparer.prepare_chunk_for_embedding(
            chunk_content="This is the chunk content.",
            document_title="Test Document",
        )

        assert "Test Document" in result
        assert "This is the chunk content." in result

    def test_prepare_with_section(self) -> None:
        """Section header is included."""
        preparer = ContextualEmbeddings()
        result = preparer.prepare_chunk_for_embedding(
            chunk_content="Content here.",
            document_title="Doc",
            section_header="Introduction",
        )

        assert "Introduction" in result

    def test_prepare_chunks_batch(self) -> None:
        """Batch preparation works for multiple chunks."""
        preparer = ContextualEmbeddings()
        chunks = [
            {"content": "First chunk.", "metadata": {}},
            {"content": "Second chunk.", "metadata": {"header": "Section 1"}},
        ]

        results = preparer.prepare_chunks_batch(
            chunks,
            document_title="Test Doc",
        )

        assert len(results) == 2
        assert all("Test Doc" in r for r in results)

    def test_truncates_long_context(self) -> None:
        """Long context is truncated."""
        preparer = ContextualEmbeddings(max_context_length=50)
        result = preparer.prepare_chunk_for_embedding(
            chunk_content="Chunk content.",
            document_title="A" * 100,
        )

        assert len(result) < 200


class TestBM25SearchQuality:
    """Tests for BM25 search quality."""

    def test_exact_match_ranks_higher(self) -> None:
        """Exact matches should rank higher."""
        index = BM25Index()
        index.add_document("doc1", "python programming tutorial")
        index.add_document("doc2", "cooking recipes for dinner")

        results = index.search("python programming", n_results=2)

        assert results[0]["id"] == "doc1"

    def test_partial_match_returns_results(self) -> None:
        """Partial matches return relevant results."""
        index = BM25Index()
        index.add_document("doc1", "machine learning algorithms")
        index.add_document("doc2", "deep learning neural networks")

        results = index.search("learning", n_results=2)

        assert len(results) == 2
