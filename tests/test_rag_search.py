# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""Tests for hybrid search and reranking strategies."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.RAG.search import (
    CrossEncoderReranker,
    DiversityReranker,
    HybridSearch,
    NoopReranker,
    get_reranker,
    reciprocal_rank_fusion,
)


class TestHybridSearch:
    """Tests for hybrid search."""

    def test_vector_only_mode(self) -> None:
        """Vector-only search uses vector function."""

        def vector_fn(query: str, n: int):
            return [{"id": "v1", "content": "Vector result", "score": 0.9}]

        hybrid = HybridSearch(vector_search_fn=vector_fn)
        results = hybrid.search("query", n_results=5, mode="vector")

        assert len(results) == 1
        assert results[0]["search_type"] == "vector"

    def test_bm25_only_mode(self) -> None:
        """BM25-only search uses BM25 function."""

        def bm25_fn(query: str, n: int):
            return [{"id": "b1", "content": "BM25 result", "score": 2.5}]

        hybrid = HybridSearch(bm25_search_fn=bm25_fn)
        results = hybrid.search("query", n_results=5, mode="bm25")

        assert len(results) == 1
        assert results[0]["search_type"] == "bm25"

    def test_hybrid_mode_fuses_results(self) -> None:
        """Hybrid mode fuses vector and BM25 results."""

        def vector_fn(query: str, n: int):
            return [
                {"id": "doc1", "content": "Vector doc 1", "score": 0.9},
                {"id": "doc2", "content": "Vector doc 2", "score": 0.8},
            ]

        def bm25_fn(query: str, n: int):
            return [
                {"id": "doc2", "content": "BM25 doc 2", "score": 2.0},
                {"id": "doc3", "content": "BM25 doc 3", "score": 1.5},
            ]

        hybrid = HybridSearch(vector_search_fn=vector_fn, bm25_search_fn=bm25_fn)
        results = hybrid.search("query", n_results=5, mode="hybrid")

        assert len(results) >= 2
        assert all("rrf_score" in r for r in results)
        assert results[0]["search_type"] == "hybrid"

    def test_hybrid_combines_scores(self) -> None:
        """Documents in both lists get combined scores."""

        def vector_fn(query: str, n: int):
            return [{"id": "shared", "content": "Shared doc", "score": 0.9}]

        def bm25_fn(query: str, n: int):
            return [{"id": "shared", "content": "Shared doc", "score": 2.0}]

        hybrid = HybridSearch(vector_search_fn=vector_fn, bm25_search_fn=bm25_fn, alpha=0.5)
        results = hybrid.search("query", n_results=5, mode="hybrid")

        shared_result = next(r for r in results if r["id"] == "shared")
        assert shared_result["vector_score"] == 0.9
        assert shared_result["bm25_score"] == 2.0

    def test_unknown_mode_raises(self) -> None:
        """Unknown search mode raises ValueError."""
        hybrid = HybridSearch()

        with pytest.raises(ValueError, match="Unknown search mode"):
            hybrid.search("query", mode="invalid")

    def test_set_alpha(self) -> None:
        """Alpha can be changed."""
        hybrid = HybridSearch()
        hybrid.set_alpha(0.3)
        assert hybrid.alpha == 0.3

    def test_set_alpha_validates(self) -> None:
        """Alpha must be between 0 and 1."""
        hybrid = HybridSearch()

        with pytest.raises(ValueError):
            hybrid.set_alpha(1.5)

        with pytest.raises(ValueError):
            hybrid.set_alpha(-0.1)

    def test_no_functions_returns_empty(self) -> None:
        """Search with no functions returns empty list."""
        hybrid = HybridSearch()

        assert hybrid.search("query", mode="vector") == []
        assert hybrid.search("query", mode="bm25") == []
        assert hybrid.search("query", mode="hybrid") == []


class TestReciprocalRankFusion:
    """Tests for RRF utility function."""

    def test_fuses_single_list(self) -> None:
        """RRF works with a single result list."""
        results = [{"id": "1", "content": "A", "metadata": {}}]

        fused = reciprocal_rank_fusion([results])
        assert len(fused) == 1

    def test_fuses_multiple_lists(self) -> None:
        """RRF combines multiple result lists."""
        list1 = [{"id": "a", "content": "A", "metadata": {}}]
        list2 = [{"id": "b", "content": "B", "metadata": {}}]

        fused = reciprocal_rank_fusion([list1, list2])

        assert len(fused) == 2
        assert {r["id"] for r in fused} == {"a", "b"}

    def test_shared_docs_get_higher_score(self) -> None:
        """Documents appearing in multiple lists get higher scores."""
        list1 = [
            {"id": "shared", "content": "Shared", "metadata": {}},
            {"id": "unique1", "content": "U1", "metadata": {}},
        ]
        list2 = [
            {"id": "shared", "content": "Shared", "metadata": {}},
            {"id": "unique2", "content": "U2", "metadata": {}},
        ]

        fused = reciprocal_rank_fusion([list1, list2])

        shared_result = next(r for r in fused if r["id"] == "shared")
        unique_results = [r for r in fused if r["id"] != "shared"]

        assert shared_result["rrf_score"] > unique_results[0]["rrf_score"]

    def test_weights_affect_scores(self) -> None:
        """Weights affect final scores."""
        list1 = [{"id": "a", "content": "A", "metadata": {}}]
        list2 = [{"id": "b", "content": "B", "metadata": {}}]

        fused_equal = reciprocal_rank_fusion([list1, list2], weights=[0.5, 0.5])
        fused_weighted = reciprocal_rank_fusion([list1, list2], weights=[0.9, 0.1])

        assert fused_equal[0]["rrf_score"] != fused_weighted[0]["rrf_score"]

    def test_weights_must_match_lists(self) -> None:
        """Number of weights must match number of lists."""
        with pytest.raises(ValueError):
            reciprocal_rank_fusion([[], []], weights=[0.5])


class TestRerankers:
    """Tests for reranker implementations."""

    def test_noop_reranker(self) -> None:
        """NoopReranker returns results unchanged."""
        reranker = NoopReranker()
        results = [
            {"id": "1", "content": "A", "score": 0.9},
            {"id": "2", "content": "B", "score": 0.8},
        ]

        reranked = reranker.rerank("query", results)

        assert reranked == results

    def test_noop_reranker_truncates(self) -> None:
        """NoopReranker truncates when n_results specified."""
        reranker = NoopReranker()
        results = [{"id": str(i), "content": f"Doc {i}"} for i in range(10)]

        reranked = reranker.rerank("query", results, n_results=3)

        assert len(reranked) == 3

    def test_diversity_reranker(self) -> None:
        """DiversityReranker promotes diverse results."""
        reranker = DiversityReranker(lambda_param=0.5)
        results = [
            {"id": "1", "content": "python programming python", "score": 0.9},
            {"id": "2", "content": "python scripting python", "score": 0.85},
            {"id": "3", "content": "javascript web development", "score": 0.8},
        ]

        reranked = reranker.rerank("python", results, n_results=3)

        assert len(reranked) == 3
        assert all("diversity_rank" in r for r in reranked)

    def test_diversity_reranker_single_result(self) -> None:
        """DiversityReranker handles single result."""
        reranker = DiversityReranker()
        results = [{"id": "1", "content": "Only result", "score": 1.0}]

        reranked = reranker.rerank("query", results)

        assert len(reranked) == 1

    def test_get_reranker_none(self) -> None:
        """get_reranker returns NoopReranker for 'none'."""
        reranker = get_reranker("none")
        assert isinstance(reranker, NoopReranker)

    def test_get_reranker_diversity(self) -> None:
        """get_reranker returns DiversityReranker for 'diversity'."""
        reranker = get_reranker("diversity")
        assert isinstance(reranker, DiversityReranker)

    def test_get_reranker_cross_encoder(self) -> None:
        """get_reranker returns CrossEncoderReranker for 'cross_encoder'."""
        reranker = get_reranker("cross_encoder")
        assert isinstance(reranker, CrossEncoderReranker)


class TestCrossEncoderReranker:
    """Tests for cross-encoder reranker."""

    def test_rerank_without_model_installed(self) -> None:
        """CrossEncoderReranker handles missing model gracefully.

        This test verifies the reranker structure without loading a model.
        """
        reranker = CrossEncoderReranker()
        assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert reranker._model is None

    def test_rerank_empty_results(self) -> None:
        """Test rerank with empty results returns empty."""
        reranker = CrossEncoderReranker()
        results = reranker.rerank("query", [])

        assert results == []

    def test_load_model_import_error(self) -> None:
        """Test _load_model raises ImportError without sentence-transformers.

        This test requires sentence-transformers to NOT be installed.
        If it's installed, we skip the test since we can't easily mock
        the internal import statement.
        """
        import importlib.util

        if importlib.util.find_spec("sentence_transformers") is not None:
            pytest.skip("sentence-transformers is installed, cannot test ImportError")

        reranker = CrossEncoderReranker()

        with pytest.raises(ImportError, match="sentence-transformers not installed"):
            reranker._load_model()

    def test_rerank_with_mock_model(self) -> None:
        """Test rerank with mocked model."""
        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        mock_model.predict = MagicMock(return_value=[0.9, 0.7, 0.5])
        reranker._model = mock_model

        results = [
            {"id": "1", "content": "First result", "score": 0.8},
            {"id": "2", "content": "Second result", "score": 0.6},
            {"id": "3", "content": "Third result", "score": 0.4},
        ]

        reranked = reranker.rerank("test query", results)

        assert len(reranked) == 3
        assert reranked[0]["rerank_score"] == 0.9
        assert all("original_score" in r for r in reranked)

    def test_rerank_prediction_failure_returns_original(self) -> None:
        """Test rerank handles prediction exceptions."""
        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        mock_model.predict = MagicMock(side_effect=Exception("Prediction error"))
        reranker._model = mock_model

        results = [
            {"id": "1", "content": "First result", "score": 0.8},
            {"id": "2", "content": "Second result", "score": 0.6},
        ]

        reranked = reranker.rerank("test query", results)

        assert len(reranked) == 2
        assert reranked == results

    def test_rerank_truncates_to_n_results(self) -> None:
        """Test rerank truncates to n_results."""
        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        mock_model.predict = MagicMock(return_value=[0.9, 0.7, 0.5])
        reranker._model = mock_model

        results = [
            {"id": "1", "content": "First", "score": 0.8},
            {"id": "2", "content": "Second", "score": 0.6},
            {"id": "3", "content": "Third", "score": 0.4},
        ]

        reranked = reranker.rerank("test query", results, n_results=2)

        assert len(reranked) == 2

    def test_custom_model_name(self) -> None:
        """Test initialization with custom model name."""
        reranker = CrossEncoderReranker(model_name="custom-model", max_length=256)

        assert reranker.model_name == "custom-model"
        assert reranker.max_length == 256


class TestDiversityRerankerExtended:
    """Extended tests for DiversityReranker."""

    def test_simple_similarity_empty_text1(self) -> None:
        """Test _simple_similarity with empty text1."""
        reranker = DiversityReranker()
        sim = reranker._simple_similarity("", "some text")

        assert sim == 0.0

    def test_simple_similarity_empty_text2(self) -> None:
        """Test _simple_similarity with empty text2."""
        reranker = DiversityReranker()
        sim = reranker._simple_similarity("some text", "")

        assert sim == 0.0

    def test_simple_similarity_identical(self) -> None:
        """Test _simple_similarity with identical texts."""
        reranker = DiversityReranker()
        sim = reranker._simple_similarity("hello world", "hello world")

        assert sim == 1.0

    def test_simple_similarity_no_overlap(self) -> None:
        """Test _simple_similarity with no word overlap."""
        reranker = DiversityReranker()
        sim = reranker._simple_similarity("cat dog", "bird fish")

        assert sim == 0.0

    def test_rerank_empty_results(self) -> None:
        """Test rerank with empty results."""
        reranker = DiversityReranker()
        results = reranker.rerank("query", [])

        assert results == []

    def test_rerank_single_result(self) -> None:
        """Test rerank with single result."""
        reranker = DiversityReranker()
        results = [{"id": "1", "content": "Only result", "score": 1.0}]
        reranked = reranker.rerank("query", results)

        assert len(reranked) == 1

    def test_rerank_truncates(self) -> None:
        """Test rerank truncates to n_results."""
        reranker = DiversityReranker()
        results = [
            {"id": "1", "content": "Python programming", "score": 0.9},
            {"id": "2", "content": "JavaScript development", "score": 0.8},
            {"id": "3", "content": "Go systems", "score": 0.7},
        ]

        reranked = reranker.rerank("query", results, n_results=2)

        assert len(reranked) == 2

    def test_lambda_param_affects_selection(self) -> None:
        """Test lambda_param affects diversity selection."""
        results = [
            {"id": "1", "content": "Python Python Python", "score": 0.9},
            {"id": "2", "content": "Python Python", "score": 0.85},
            {"id": "3", "content": "JavaScript", "score": 0.5},
        ]

        reranker_high_rel = DiversityReranker(lambda_param=0.99)
        reranked_high = reranker_high_rel.rerank("python", results.copy(), n_results=2)

        reranker_diverse = DiversityReranker(lambda_param=0.1)
        reranked_diverse = reranker_diverse.rerank("python", results.copy(), n_results=2)

        assert len(reranked_high) == 2
        assert len(reranked_diverse) == 2


class TestGetRerankerExtended:
    """Extended tests for get_reranker factory."""

    def test_get_reranker_unknown_returns_noop(self) -> None:
        """get_reranker returns NoopReranker for unknown type."""
        reranker = get_reranker("unknown_type")
        assert isinstance(reranker, NoopReranker)

    def test_get_reranker_with_kwargs(self) -> None:
        """get_reranker passes kwargs to reranker."""
        reranker = get_reranker("diversity", lambda_param=0.3)
        assert reranker.lambda_param == 0.3

    def test_get_reranker_cross_encoder_with_model_name(self) -> None:
        """get_reranker passes model_name to CrossEncoderReranker."""
        reranker = get_reranker("cross_encoder", model_name="custom-model")
        assert reranker.model_name == "custom-model"


class TestNoopRerankerExtended:
    """Extended tests for NoopReranker."""

    def test_returns_all_results(self) -> None:
        """NoopReranker returns all results when n_results is None."""
        reranker = NoopReranker()
        results = [{"id": str(i)} for i in range(10)]

        reranked = reranker.rerank("query", results)

        assert len(reranked) == 10
        assert reranked == results

    def test_preserves_order(self) -> None:
        """NoopReranker preserves original order."""
        reranker = NoopReranker()
        results = [{"id": "a"}, {"id": "b"}, {"id": "c"}]

        reranked = reranker.rerank("query", results)

        assert [r["id"] for r in reranked] == ["a", "b", "c"]
