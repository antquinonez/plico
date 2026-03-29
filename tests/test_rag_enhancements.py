# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Tests for RAG enhancements: cache, filtering, query expansion, dedup, summaries."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.RAG.FFEmbeddings import FFEmbeddings
from src.RAG.indexing.deduplication import ChunkDeduplicator
from src.RAG.search.query_expansion import QueryExpander, fuse_search_results


class TestEmbeddingCache:
    """Tests for embedding caching functionality."""

    def test_cache_enabled_by_default(self):
        """Cache should be enabled by default."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed")
            assert emb._cache_enabled is True

    def test_cache_can_be_disabled(self):
        """Cache can be disabled via constructor."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed", cache_enabled=False)
            assert emb._cache_enabled is False

    def test_cache_returns_same_embedding_for_same_text(self):
        """Repeated calls should return cached result."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed", cache_enabled=True)

            mock_response = MagicMock()
            mock_response.data = [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]

            with patch("src.RAG.FFEmbeddings.embedding", return_value=mock_response):
                result1 = emb.embed_single("test query")
                result2 = emb.embed_single("test query")

                assert result1 == result2

    def test_clear_cache_removes_entries(self):
        """clear_cache should remove all cached entries."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed", cache_enabled=True)
            emb._cache["test"] = [0.1, 0.2]

            count = emb.clear_cache()
            assert count == 1
            assert len(emb._cache) == 0

    def test_get_cache_stats(self):
        """get_cache_stats should return cache statistics."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed", cache_enabled=True, cache_size=100)
            stats = emb.get_cache_stats()

            assert stats["cache_enabled"] is True
            assert stats["max_size"] == 100
            assert stats["current_entries"] == 0


class TestQueryExpansion:
    """Tests for query expansion functionality."""

    def test_expand_without_llm_returns_original(self):
        """Without LLM function, should return original query only."""
        expander = QueryExpander(llm_generate_fn=None, n_variations=3)
        queries = expander.expand("authentication methods")

        assert len(queries) == 1
        assert queries[0] == "authentication methods"

    def test_expand_with_mock_llm(self):
        """With mock LLM, should parse response correctly."""

        def mock_llm(prompt: str) -> str:
            return "1. How to authenticate?\n2. Login methods\n3. Auth protocols"

        expander = QueryExpander(llm_generate_fn=mock_llm, n_variations=3)
        queries = expander.expand("authentication")

        assert len(queries) == 4  # original + 3 variations
        assert "authentication" in queries
        assert "How to authenticate?" in queries

    def test_expand_fallback_on_exception(self):
        """Should fallback to original query on LLM exception."""

        def failing_llm(prompt: str) -> str:
            raise RuntimeError("LLM error")

        expander = QueryExpander(llm_generate_fn=failing_llm, n_variations=3)
        queries = expander.expand("test query")

        assert len(queries) == 1
        assert queries[0] == "test query"

    def test_parse_response_handles_numbered_list(self):
        """Should correctly parse numbered list responses."""
        expander = QueryExpander()

        response = "1. First query\n2. Second query\n3. Third query"
        queries = expander._parse_response(response)

        assert len(queries) == 3
        assert queries[0] == "First query"
        assert queries[1] == "Second query"

    def test_include_original_false(self):
        """Can exclude original query from results."""

        def mock_llm(prompt: str) -> str:
            return "1. Variation one"

        expander = QueryExpander(
            llm_generate_fn=mock_llm,
            n_variations=1,
            include_original=False,
        )
        queries = expander.expand("original")

        assert len(queries) == 1
        assert queries[0] == "Variation one"


class TestFuseSearchResults:
    """Tests for search result fusion."""

    def test_fuse_empty_lists(self):
        """Empty input should return empty list."""
        result = fuse_search_results([])
        assert result == []

    def test_fuse_single_list(self):
        """Single list should be returned as-is."""
        results = [{"id": "1", "score": 0.9}]
        fused = fuse_search_results([results])

        assert len(fused) == 1
        assert fused[0]["id"] == "1"

    def test_fuse_deduplicates_by_id(self):
        """Should deduplicate results by id."""
        list1 = [{"id": "1", "score": 0.9}, {"id": "2", "score": 0.8}]
        list2 = [{"id": "1", "score": 0.7}, {"id": "3", "score": 0.6}]

        fused = fuse_search_results([list1, list2])

        assert len(fused) == 3
        ids = [r["id"] for r in fused]
        assert "1" in ids
        assert "2" in ids
        assert "3" in ids

    def test_fuse_respects_n_results_limit(self):
        """Should limit results to n_results."""
        list1 = [{"id": str(i), "score": 0.9} for i in range(10)]

        fused = fuse_search_results([list1], n_results=3)

        assert len(fused) == 3


class TestChunkDeduplication:
    """Tests for chunk deduplication."""

    def test_exact_dedup_detects_duplicates(self):
        """Exact mode should detect identical content."""
        dedup = ChunkDeduplicator(mode="exact")

        is_dup1 = dedup.is_duplicate("Hello world")
        is_dup2 = dedup.is_duplicate("Hello world")
        is_dup3 = dedup.is_duplicate("Different text")

        assert is_dup1 is False
        assert is_dup2 is True
        assert is_dup3 is False

    def test_similarity_dedup_requires_embeddings(self):
        """Similarity mode requires embeddings to detect duplicates."""
        dedup = ChunkDeduplicator(mode="similarity", similarity_threshold=0.95)

        is_dup1 = dedup.is_duplicate("Hello world", embedding=None)
        is_dup2 = dedup.is_duplicate("Hello world", embedding=[0.1, 0.2, 0.3])

        assert is_dup1 is False
        assert is_dup2 is False

    def test_filter_duplicates_removes_exact_dups(self):
        """filter_duplicates should remove exact duplicates."""
        dedup = ChunkDeduplicator(mode="exact")

        class MockChunk:
            def __init__(self, content):
                self.content = content

        chunks = [
            MockChunk("Unique content"),
            MockChunk("Duplicate"),
            MockChunk("Duplicate"),
        ]
        embeddings = [[0.1], [0.2], [0.3]]

        filtered_chunks, filtered_embeddings = dedup.filter_duplicates(chunks, embeddings)

        assert len(filtered_chunks) == 2
        assert len(filtered_embeddings) == 2

    def test_compute_hash_consistent(self):
        """Hash should be consistent for same content."""
        dedup = ChunkDeduplicator()

        hash1 = dedup.compute_hash("test content")
        hash2 = dedup.compute_hash("test content")

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_clear_resets_state(self):
        """clear should reset deduplicator state."""
        dedup = ChunkDeduplicator(mode="exact")
        dedup.is_duplicate("test")

        dedup.clear()

        assert len(dedup._seen_hashes) == 0

    def test_get_stats(self):
        """get_stats should return current state."""
        dedup = ChunkDeduplicator(mode="exact", similarity_threshold=0.9)
        dedup.is_duplicate("test")

        stats = dedup.get_stats()

        assert stats["mode"] == "exact"
        assert stats["similarity_threshold"] == 0.9
        assert stats["seen_hashes"] == 1


class TestChunkDeduplicationExtended:
    """Extended tests for chunk deduplication."""

    def test_similarity_dedup_detects_near_duplicate(self) -> None:
        """Similarity mode detects near-duplicates above threshold."""
        dedup = ChunkDeduplicator(mode="similarity", similarity_threshold=0.99)

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.5, 0.5, 0.0]
        vec3 = [1.0, 0.0, 0.0]  # identical to vec1

        assert dedup.is_duplicate("text1", embedding=vec1) is False
        assert dedup.is_duplicate("text2", embedding=vec2) is False
        assert dedup.is_duplicate("text3", embedding=vec3) is True  # near-duplicate of text1

    def test_filter_duplicates_empty_inputs(self) -> None:
        """filter_duplicates handles empty inputs."""
        dedup = ChunkDeduplicator(mode="exact")
        chunks, embeddings = dedup.filter_duplicates([], [])
        assert chunks == []
        assert embeddings == []

    def test_cosine_similarity_zero_vectors(self) -> None:
        """Cosine similarity returns 0 for zero vectors."""
        dedup = ChunkDeduplicator()
        result = dedup._cosine_similarity([0.0, 0.0], [1.0, 0.0])
        assert result == 0.0

    def test_cosine_similarity_identical(self) -> None:
        """Cosine similarity returns 1.0 for identical vectors."""
        dedup = ChunkDeduplicator()
        result = dedup._cosine_similarity([1.0, 2.0], [1.0, 2.0])
        assert abs(result - 1.0) < 0.001

    def test_similarity_mode_no_embedding(self) -> None:
        """Similarity mode without embedding returns False (not duplicate)."""
        dedup = ChunkDeduplicator(mode="similarity")
        assert dedup.is_duplicate("some text", embedding=None) is False

    def test_get_stats_includes_seen_embeddings(self) -> None:
        """get_stats includes seen_embeddings count."""
        dedup = ChunkDeduplicator(mode="similarity")
        dedup.is_duplicate("text1", embedding=[1.0, 0.0])
        dedup.is_duplicate("text2", embedding=[0.0, 1.0])

        stats = dedup.get_stats()
        assert stats["seen_embeddings"] == 2


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_identical_vectors(self):
        """Identical vectors should have similarity 1.0."""
        emb = FFEmbeddings.__new__(FFEmbeddings)
        sim = emb.cosine_similarity([1.0, 0.0], [1.0, 0.0])
        assert abs(sim - 1.0) < 0.001

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity 0.0."""
        emb = FFEmbeddings.__new__(FFEmbeddings)
        sim = emb.cosine_similarity([1.0, 0.0], [0.0, 1.0])
        assert abs(sim) < 0.001

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity -1.0."""
        emb = FFEmbeddings.__new__(FFEmbeddings)
        sim = emb.cosine_similarity([1.0, 0.0], [-1.0, 0.0])
        assert abs(sim - (-1.0)) < 0.001

    def test_zero_vector(self):
        """Zero vector should return 0.0."""
        emb = FFEmbeddings.__new__(FFEmbeddings)
        sim = emb.cosine_similarity([0.0, 0.0], [1.0, 0.0])
        assert sim == 0.0


class TestLocalEmbeddings:
    """Tests for local embeddings support."""

    def test_is_local_with_prefix(self):
        """Model starting with 'local/' should be detected as local."""
        with patch.object(FFEmbeddings, "_init_local_model"):
            emb = FFEmbeddings(model="local/all-MiniLM-L6-v2")

            assert emb.is_local is True
            assert emb.provider == "local"

    def test_is_local_false_for_api_models(self):
        """API models should not be detected as local."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed")

            assert emb.is_local is False

    def test_local_model_init_requires_sentence_transformers(self):
        """Should raise ImportError if sentence-transformers not installed."""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers"):
                FFEmbeddings(model="local/all-MiniLM-L6-v2")


class TestFFEmbeddingsExtended:
    """Extended tests for FFEmbeddings."""

    def test_embed_empty_list(self) -> None:
        """embed returns empty list for empty input."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed")
            result = emb.embed([])
            assert result == []

    def test_embed_single_string(self) -> None:
        """embed converts single string to list."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed")
            mock_response = MagicMock()
            mock_response.data = [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]
            with patch("src.RAG.FFEmbeddings.embedding", return_value=mock_response):
                result = emb.embed("hello")
                assert len(result) == 1
                assert result[0] == [0.1, 0.2, 0.3]

    def test_embed_single_method(self) -> None:
        """embed_single returns single vector."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed")
            mock_response = MagicMock()
            mock_response.data = [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]
            with patch("src.RAG.FFEmbeddings.embedding", return_value=mock_response):
                result = emb.embed_single("test")
                assert result == [0.1, 0.2, 0.3]

    def test_get_dimension(self) -> None:
        """get_dimension returns embedding dimension."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed")
            mock_response = MagicMock()
            mock_response.data = [{"index": 0, "embedding": [0.1] * 768}]
            with patch("src.RAG.FFEmbeddings.embedding", return_value=mock_response):
                dim = emb.get_dimension()
                assert dim == 768

    def test_embed_api_no_api_key_raises(self) -> None:
        """embed_api raises ValueError when no API key."""
        emb = FFEmbeddings(model="mistral/mistral-embed", api_key=None)
        emb._is_local = False
        emb.api_key = None
        with pytest.raises(ValueError, match="No API key"):
            emb._embed_api(["test"])

    def test_embed_api_error_raises_runtime(self) -> None:
        """embed_api raises RuntimeError on API failure."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed")
            with patch("src.RAG.FFEmbeddings.embedding", side_effect=Exception("API error")):
                with pytest.raises(RuntimeError, match="Embedding generation failed"):
                    emb._embed_api(["test"])

    def test_embed_api_with_base_url(self) -> None:
        """embed_api passes api_base when configured."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed", api_base="https://custom.api/v1")
            mock_response = MagicMock()
            mock_response.data = [{"index": 0, "embedding": [0.1]}]
            with patch("src.RAG.FFEmbeddings.embedding", return_value=mock_response) as mock_emb:
                emb._embed_api(["test"])
                call_kwargs = mock_emb.call_args[1]
                assert call_kwargs["api_base"] == "https://custom.api/v1"

    def test_embed_api_caches_results(self) -> None:
        """API embeddings are cached."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed", cache_enabled=True, cache_size=10)
            mock_response = MagicMock()
            mock_response.data = [{"index": 0, "embedding": [0.1]}]
            with patch("src.RAG.FFEmbeddings.embedding", return_value=mock_response) as mock_emb:
                emb._embed_api(["test"])
                emb._embed_api(["test"])
                assert mock_emb.call_count == 1

    def test_embed_api_cache_eviction(self) -> None:
        """Cache evicts oldest entries when full."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="mistral/mistral-embed", cache_enabled=True, cache_size=2)
            mock_response = MagicMock()
            mock_response.data = [{"index": 0, "embedding": [0.1]}]
            with patch("src.RAG.FFEmbeddings.embedding", return_value=mock_response):
                emb._embed_api(["text1"])
                emb._embed_api(["text2"])
                emb._embed_api(["text3"])
                assert len(emb._cache) == 2
                assert "text1" not in emb._cache

    def test_provider_unknown_model(self) -> None:
        """Provider returns 'unknown' for model without slash."""
        with patch.object(FFEmbeddings, "_get_default_api_key", return_value="test-key"):
            emb = FFEmbeddings(model="unknownmodel")
            assert emb.provider == "unknown"

    def test_get_default_api_key_unknown_provider(self) -> None:
        """_get_default_api_key constructs env var for unknown provider."""
        emb = FFEmbeddings.__new__(FFEmbeddings)
        emb.model = "custom/model"
        with patch.dict("os.environ", {}, clear=True):
            key = emb._get_default_api_key()
            assert key is None
