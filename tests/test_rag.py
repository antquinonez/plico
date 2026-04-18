# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Tests for RAG module functionality."""

from __future__ import annotations

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.RAG import CHROMADB_AVAILABLE, FFEmbeddings, RAGMCPTools
from src.RAG.text_splitters import TextChunk, get_chunker

if CHROMADB_AVAILABLE:
    from src.RAG import FFRAGClient, FFVectorStore

requires_chromadb = pytest.mark.skipif(
    not CHROMADB_AVAILABLE,
    reason="chromadb not installed or not compatible with this Python version",
)


class TestTextSplitter:
    """Tests for text splitting functionality."""

    def test_split_text_basic(self):
        """Test basic text splitting."""
        text = "This is a test. " * 100
        chunker = get_chunker("character", chunk_size=50, chunk_overlap=10)
        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        assert all(isinstance(c, TextChunk) for c in chunks)
        assert all(len(c.content) <= 60 for c in chunks)  # Allow some overflow for word boundaries

    def test_split_text_empty(self):
        """Test splitting empty text."""
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk("")
        assert chunks == []

    def test_split_text_single_chunk(self):
        """Test text shorter than chunk size."""
        text = "Short text"
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].content == text

    def test_split_text_invalid_params(self):
        """Test invalid parameters raise errors."""
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            get_chunker("character", chunk_size=0)

        with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
            get_chunker("character", chunk_size=100, chunk_overlap=-1)

        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            get_chunker("character", chunk_size=50, chunk_overlap=50)

    def test_split_text_metadata(self):
        """Test metadata is attached to chunks."""
        text = "Test content"
        metadata = {"source": "test.txt", "author": "test"}
        chunker = get_chunker("character", chunk_size=100, chunk_overlap=20)
        chunks = chunker.chunk(text, metadata=metadata)

        assert len(chunks) == 1
        assert chunks[0].metadata == metadata

    def test_split_text_overlap(self):
        """Test that overlap works correctly."""
        text = "A" * 50 + "B" * 50 + "C" * 50
        chunker = get_chunker("character", chunk_size=60, chunk_overlap=20)
        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        # Check that consecutive chunks have overlapping content
        if len(chunks) > 1:
            # There should be some overlap between chunks
            assert any(
                chunks[i].end_char > chunks[i + 1].start_char for i in range(len(chunks) - 1)
            )

    def test_split_documents(self):
        """Test splitting multiple documents."""
        documents = [
            {"content": "Doc 1 content", "source": "doc1.txt"},
            {"content": "Doc 2 content", "source": "doc2.txt"},
        ]
        chunker = get_chunker("character", chunk_size=50, chunk_overlap=10)
        chunks = []
        for doc in documents:
            metadata = {k: v for k, v in doc.items() if k != "content"}
            chunks.extend(chunker.chunk(doc["content"], metadata=metadata))

        assert len(chunks) == 2
        assert chunks[0].metadata == {"source": "doc1.txt"}
        assert chunks[1].metadata == {"source": "doc2.txt"}


class TestFFEmbeddings:
    """Tests for embedding generation."""

    def test_init_default_model(self):
        """Test initialization with default model."""
        embeddings = FFEmbeddings()

        assert embeddings.model == "mistral/mistral-embed"
        assert embeddings.provider == "mistral"

    def test_init_custom_model(self):
        """Test initialization with custom model."""
        embeddings = FFEmbeddings(model="openai/text-embedding-3-small")

        assert embeddings.model == "openai/text-embedding-3-small"
        assert embeddings.provider == "openai"

    def test_embed_single(self):
        """Test embedding a single text."""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3], "index": 0}]

        with patch("src.RAG.FFEmbeddings.embedding", return_value=mock_response):
            embeddings = FFEmbeddings(api_key="test-key")
            result = embeddings.embed_single("test text")

            assert result == [0.1, 0.2, 0.3]

    def test_embed_multiple(self):
        """Test embedding multiple texts."""
        mock_response = MagicMock()
        mock_response.data = [
            {"embedding": [0.1, 0.2, 0.3], "index": 0},
            {"embedding": [0.4, 0.5, 0.6], "index": 1},
        ]

        with patch("src.RAG.FFEmbeddings.embedding", return_value=mock_response):
            embeddings = FFEmbeddings(api_key="test-key")
            results = embeddings.embed(["text 1", "text 2"])

            assert len(results) == 2
            assert results[0] == [0.1, 0.2, 0.3]
            assert results[1] == [0.4, 0.5, 0.6]

    def test_embed_empty_list(self):
        """Test embedding empty list."""
        embeddings = FFEmbeddings(api_key="test-key")
        result = embeddings.embed([])

        assert result == []

    def test_embed_no_api_key_raises(self):
        """Test that embedding without API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            embeddings = FFEmbeddings(api_key=None)
            assert embeddings.api_key is None
            with pytest.raises(ValueError, match="No API key configured"):
                embeddings.embed("test")


@requires_chromadb
class TestFFVectorStore:
    """Tests for ChromaDB vector store."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings that return fixed vectors."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock = MagicMock(spec=FFEmbeddings)
        mock.embed = MagicMock(side_effect=make_embed_mock)
        mock.embed_single = MagicMock(return_value=[0.1] * 384)
        mock.model = "test-model"
        return mock

    def test_init_creates_collection(self, temp_persist_dir, mock_embeddings):
        """Test that initialization creates a collection."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        assert store.collection_name == "test_collection"
        assert store.count() == 0

    def test_init_with_custom_client(self, temp_persist_dir, mock_embeddings):
        """Test initialization with pre-configured client."""
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=temp_persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        store = FFVectorStore(
            collection_name="custom_client_collection",
            embedding_model=mock_embeddings,
            client=client,
        )

        assert store._client is client

    def test_init_with_string_embedding_model(self, temp_persist_dir):
        """Test initialization with string embedding model."""
        mock_embeddings = MagicMock(spec=FFEmbeddings)
        mock_embeddings.model = "custom-model"

        with patch("src.RAG.FFVectorStore.FFEmbeddings", return_value=mock_embeddings):
            store = FFVectorStore(
                collection_name="string_model_collection",
                persist_dir=temp_persist_dir,
                embedding_model="openai/text-embedding-3-small",
            )

        assert store._embeddings == mock_embeddings

    def test_init_with_none_embedding_model(self, temp_persist_dir):
        """Test initialization with None embedding model creates default."""
        mock_embeddings = MagicMock(spec=FFEmbeddings)
        mock_embeddings.model = "mistral/mistral-embed"

        with patch("src.RAG.FFVectorStore.FFEmbeddings", return_value=mock_embeddings):
            store = FFVectorStore(
                collection_name="none_model_collection",
                persist_dir=temp_persist_dir,
                embedding_model=None,
            )

        assert store._embeddings == mock_embeddings

    def test_add_chunks(self, temp_persist_dir, mock_embeddings):
        """Test adding text chunks."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(content="Chunk 1", chunk_index=0, start_char=0, end_char=7),
            TextChunk(content="Chunk 2", chunk_index=1, start_char=7, end_char=14),
        ]

        count = store.add_chunks(chunks)

        assert count == 2
        assert store.count() == 2

    def test_add_chunks_empty(self, temp_persist_dir, mock_embeddings):
        """Test add_chunks with empty list returns 0."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        count = store.add_chunks([])

        assert count == 0

    def test_add_chunks_with_dedup(self, temp_persist_dir, mock_embeddings):
        """Test add_chunks with deduplication enabled."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(content="Unique chunk", chunk_index=0, start_char=0, end_char=12),
        ]

        count = store.add_chunks(chunks, dedup=True, dedup_mode="exact")

        assert count >= 1

    def test_add_chunks_with_texts_for_embedding(self, temp_persist_dir, mock_embeddings):
        """Test add_chunks with custom texts for embedding."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(content="Content", chunk_index=0, start_char=0, end_char=7),
        ]

        count = store.add_chunks(
            chunks,
            texts_for_embedding=["Contextual header: Content"],
        )

        assert count == 1

    def test_add_documents(self, temp_persist_dir, mock_embeddings):
        """Test adding documents with automatic chunking."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        documents = [
            {"content": "Document 1 content", "source": "doc1.txt"},
            {"content": "Document 2 content", "source": "doc2.txt"},
        ]

        count = store.add_documents(documents, chunk_size=100, chunk_overlap=20)

        assert count >= 2
        assert store.count() >= 2

    def test_search(self, temp_persist_dir, mock_embeddings):
        """Test semantic search."""
        mock_embeddings.embed_single = MagicMock(return_value=[0.1] * 384)
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(
                content="Authentication requires API keys",
                chunk_index=0,
                start_char=0,
                end_char=30,
                metadata={"reference_name": "auth_doc"},
            ),
        ]
        store.add_chunks(chunks)

        results = store.search("how to authenticate", n_results=5)

        assert len(results) == 1
        assert "Authentication" in results[0]["content"]
        assert results[0]["metadata"]["reference_name"] == "auth_doc"

    def test_delete_by_reference(self, temp_persist_dir, mock_embeddings):
        """Test deleting documents by reference name."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(
                content="Content 1",
                chunk_index=0,
                start_char=0,
                end_char=9,
                metadata={"reference_name": "doc1"},
            ),
            TextChunk(
                content="Content 2",
                chunk_index=0,
                start_char=0,
                end_char=9,
                metadata={"reference_name": "doc2"},
            ),
        ]
        store.add_chunks(chunks)

        assert store.count() == 2

        store.delete_by_reference("doc1")

        assert store.count() == 1

    def test_delete_requires_ids_or_where(self, temp_persist_dir, mock_embeddings):
        """Test delete raises ValueError without ids or where."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        with pytest.raises(ValueError, match="Must provide either ids or where filter"):
            store.delete()

    def test_delete_by_reference_and_strategy(self, temp_persist_dir, mock_embeddings):
        """Test delete_by_reference_and_strategy method."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(
                content="Content",
                chunk_index=0,
                start_char=0,
                end_char=7,
                metadata={"reference_name": "doc1"},
            ),
        ]
        store.add_chunks(chunks, chunking_strategy="recursive")

        result = store.delete_by_reference_and_strategy("doc1", "recursive")

        assert result == 0

    def test_list_documents(self, temp_persist_dir, mock_embeddings):
        """Test listing document references."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(
                content="Content",
                chunk_index=0,
                start_char=0,
                end_char=7,
                metadata={"reference_name": "doc1"},
            ),
            TextChunk(
                content="Content",
                chunk_index=1,
                start_char=0,
                end_char=7,
                metadata={"reference_name": "doc2"},
            ),
        ]
        store.add_chunks(chunks)

        docs = store.list_documents()

        assert "doc1" in docs
        assert "doc2" in docs

    def test_get_stats(self, temp_persist_dir, mock_embeddings):
        """Test getting collection statistics."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        stats = store.get_stats()

        assert stats["collection_name"] == "test_collection"
        assert "count" in stats
        assert "persist_dir" in stats

    def test_clear(self, temp_persist_dir, mock_embeddings):
        """Test clearing the collection."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(content="Content", chunk_index=0, start_char=0, end_char=7),
        ]
        store.add_chunks(chunks)

        assert store.count() == 1

        store.clear()

        assert store.count() == 0

    def test_get_indexed_documents(self, temp_persist_dir, mock_embeddings):
        """Test get_indexed_documents method."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(
                content="Content",
                chunk_index=0,
                start_char=0,
                end_char=7,
                metadata={"reference_name": "indexed_doc"},
            ),
        ]
        store.add_chunks(chunks, chunking_strategy="recursive", document_checksum="abc123")

        indexed = store.get_indexed_documents()

        assert len(indexed) >= 1
        assert any(d["reference_name"] == "indexed_doc" for d in indexed)

    def test_get_indexed_documents_with_strategy_filter(self, temp_persist_dir, mock_embeddings):
        """Test get_indexed_documents with chunking_strategy filter."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(
                content="Content",
                chunk_index=0,
                start_char=0,
                end_char=7,
                metadata={"reference_name": "filtered_doc"},
            ),
        ]
        store.add_chunks(chunks, chunking_strategy="character")

        indexed = store.get_indexed_documents(chunking_strategy="character")

        assert all(d["chunking_strategy"] == "character" for d in indexed)

    def test_needs_reindex_new_document(self, temp_persist_dir, mock_embeddings):
        """Test needs_reindex for new document returns True."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        needs = store.needs_reindex("new_doc", "checksum123", "recursive")

        assert needs is True

    def test_needs_reindex_same_checksum(self, temp_persist_dir, mock_embeddings):
        """Test needs_reindex with same checksum returns False."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(
                content="Content",
                chunk_index=0,
                start_char=0,
                end_char=7,
                metadata={"reference_name": "same_checksum_doc"},
            ),
        ]
        store.add_chunks(chunks, chunking_strategy="recursive", document_checksum="checksum123")

        needs = store.needs_reindex("same_checksum_doc", "checksum123", "recursive")

        assert needs is False

    def test_needs_reindex_changed_checksum(self, temp_persist_dir, mock_embeddings):
        """Test needs_reindex with changed checksum returns True."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(
                content="Content",
                chunk_index=0,
                start_char=0,
                end_char=7,
                metadata={"reference_name": "changed_checksum_doc"},
            ),
        ]
        store.add_chunks(chunks, chunking_strategy="recursive", document_checksum="old_checksum")

        needs = store.needs_reindex("changed_checksum_doc", "new_checksum", "recursive")

        assert needs is True

    def test_get_all_documents(self, temp_persist_dir, mock_embeddings):
        """Test get_all_documents method."""
        store = FFVectorStore(
            collection_name="test_collection",
            persist_dir=temp_persist_dir,
            embedding_model=mock_embeddings,
        )

        chunks = [
            TextChunk(
                content="Document content",
                chunk_index=0,
                start_char=0,
                end_char=16,
                metadata={"reference_name": "all_doc"},
            ),
        ]
        store.add_chunks(chunks)

        docs = store.get_all_documents()

        assert len(docs) >= 1
        assert all("id" in d and "content" in d and "metadata" in d for d in docs)


@requires_chromadb
class TestFFRAGClientInit:
    """Tests for FFRAGClient initialization options."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock = MagicMock(spec=FFEmbeddings)
        mock.embed = MagicMock(side_effect=make_embed_mock)
        mock.embed_single = MagicMock(return_value=[0.1] * 384)
        mock.model = "test-model"
        return mock

    def test_init_with_config_override(self, temp_persist_dir, mock_embeddings):
        """Test config parameter overrides defaults."""
        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                config={
                    "collection_name": "custom_collection",
                    "chunk_size": 500,
                    "chunk_overlap": 100,
                    "n_results_default": 10,
                    "chunking_strategy": "character",
                    "search_mode": "bm25",
                },
            )
            client._embeddings = mock_embeddings

        assert client.collection_name == "custom_collection"
        assert client.chunk_size == 500
        assert client.chunk_overlap == 100
        assert client.n_results_default == 10
        assert client.chunking_strategy == "character"
        assert client.search_mode == "bm25"

    def test_init_with_string_embedding_model(self, temp_persist_dir):
        """Test initialization with string embedding model."""
        mock_embeddings = MagicMock(spec=FFEmbeddings)
        mock_embeddings.model = "custom-model"

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model="openai/text-embedding-3-small",
            )

        assert client._embeddings == mock_embeddings

    def test_init_with_none_embedding_model(self, temp_persist_dir):
        """Test initialization with None embedding model creates default."""
        mock_embeddings = MagicMock(spec=FFEmbeddings)
        mock_embeddings.model = "mistral/mistral-embed"

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=None,
            )

        assert client._embeddings == mock_embeddings


@requires_chromadb
class TestFFRAGClientHybridSearch:
    """Tests for FFRAGClient hybrid search functionality."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock = MagicMock(spec=FFEmbeddings)
        mock.embed = MagicMock(side_effect=make_embed_mock)
        mock.embed_single = MagicMock(return_value=[0.1] * 384)
        mock.model = "test-model"
        return mock

    def test_init_hybrid_search_mode(self, temp_persist_dir, mock_embeddings):
        """Test initialization with search_mode='hybrid'."""
        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                search_mode="hybrid",
            )
            client._embeddings = mock_embeddings

        assert client._bm25_index is not None
        assert client._hybrid_search is not None

    def test_init_hybrid_search_loads_existing_docs(self, temp_persist_dir, mock_embeddings):
        """Test that hybrid search loads existing documents into BM25."""
        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client1 = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                collection_name="test_hybrid",
            )
            client1._embeddings = mock_embeddings

        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])
        client1.add_document(content="Test document for hybrid", reference_name="hybrid_doc")

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client2 = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                collection_name="test_hybrid",
                search_mode="hybrid",
            )
            client2._embeddings = mock_embeddings

        assert client2._bm25_index is not None

    def test_vector_search_only(self, temp_persist_dir, mock_embeddings):
        """Test _vector_search_only helper."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])
        mock_embeddings.embed_single = MagicMock(return_value=[0.1] * 384)

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings

        client.add_document(content="Test content", reference_name="test_doc")
        results = client._vector_search_only("test query", n_results=5)

        assert isinstance(results, list)

    def test_bm25_search_only(self, temp_persist_dir, mock_embeddings):
        """Test _bm25_search_only helper."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                search_mode="hybrid",
            )
            client._embeddings = mock_embeddings

        client.add_document(content="Test content", reference_name="test_doc")
        results = client._bm25_search_only("test", n_results=5)

        assert isinstance(results, list)


@requires_chromadb
class TestFFRAGClientIndexDocument:
    """Tests for FFRAGClient.index_document method."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock = MagicMock(spec=FFEmbeddings)
        mock.embed = MagicMock(side_effect=make_embed_mock)
        mock.embed_single = MagicMock(return_value=[0.1] * 384)
        mock.model = "test-model"
        return mock

    @pytest.fixture
    def rag_client(self, temp_persist_dir, mock_embeddings):
        """Create a RAG client with mocked embeddings."""
        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            return client

    def test_index_document_new(self, rag_client, mock_embeddings):
        """Test index_document for new document."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        chunks = rag_client.index_document(
            content="This is new content to index.",
            reference_name="new_doc",
            common_name="New Document",
            checksum="abc123",
        )

        assert chunks >= 1

    def test_index_document_already_indexed(self, rag_client, mock_embeddings):
        """Test index_document skips if already indexed with same checksum."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        rag_client.index_document(
            content="Content to index.",
            reference_name="cached_doc",
            common_name="Cached Doc",
            checksum="checksum1",
        )
        count_after_first = rag_client.count()

        chunks = rag_client.index_document(
            content="Content to index.",
            reference_name="cached_doc",
            common_name="Cached Doc",
            checksum="checksum1",
        )

        assert chunks == 0
        assert rag_client.count() == count_after_first

    def test_index_document_force_reindex(self, rag_client, mock_embeddings):
        """Test index_document with force=True."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        rag_client.index_document(
            content="Original content.",
            reference_name="force_doc",
            common_name="Force Doc",
            checksum="checksum1",
        )

        chunks = rag_client.index_document(
            content="Original content.",
            reference_name="force_doc",
            common_name="Force Doc",
            checksum="checksum1",
            force=True,
        )

        assert chunks >= 1

    def test_index_document_checksum_changed(self, rag_client, mock_embeddings):
        """Test index_document when checksum changes."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        rag_client.index_document(
            content="Modified content.",
            reference_name="changed_doc",
            common_name="Changed Doc",
            checksum="checksum1",
        )

        chunks = rag_client.index_document(
            content="Modified content.",
            reference_name="changed_doc",
            common_name="Changed Doc",
            checksum="checksum2",
        )

        assert chunks >= 1

    def test_index_document_with_summaries(self, temp_persist_dir, mock_embeddings):
        """Test index_document with summary generation."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        mock_llm = MagicMock(return_value="This is a summary of the document.")

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            client.generate_summaries = True
            client._llm_generate_fn = mock_llm

        chunks = client.index_document(
            content="Document content for summary.",
            reference_name="summary_doc",
            common_name="Summary Doc",
            checksum="sum123",
        )

        assert chunks >= 1


@requires_chromadb
class TestFFRAGClientLLMIntegration:
    """Tests for FFRAGClient LLM integration methods."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock = MagicMock(spec=FFEmbeddings)
        mock.embed = MagicMock(side_effect=make_embed_mock)
        mock.embed_single = MagicMock(return_value=[0.1] * 384)
        mock.model = "test-model"
        return mock

    @pytest.fixture
    def rag_client(self, temp_persist_dir, mock_embeddings):
        """Create a RAG client with mocked embeddings."""
        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            return client

    def test_set_llm_generate_fn(self, rag_client):
        """Test setting LLM generate function."""
        mock_fn = MagicMock(return_value="LLM response")

        rag_client.set_llm_generate_fn(mock_fn)

        assert rag_client._llm_generate_fn == mock_fn

    def test_set_llm_generate_fn_with_query_expander(self, rag_client):
        """Test setting LLM function propagates to query expander."""
        mock_fn = MagicMock(return_value="LLM response")
        rag_client._query_expander = MagicMock()
        rag_client._query_expander.set_llm_function = MagicMock()

        rag_client.set_llm_generate_fn(mock_fn)

        rag_client._query_expander.set_llm_function.assert_called_once_with(mock_fn)

    def test_generate_and_store_summary(self, rag_client, mock_embeddings):
        """Test summary generation and storage."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])
        mock_llm = MagicMock(return_value="This is a generated summary.")

        rag_client._llm_generate_fn = mock_llm

        result = rag_client._generate_and_store_summary(
            content="Long document content for summarization.",
            reference_name="test_doc",
            common_name="Test Document",
            checksum="checksum123",
        )

        assert result is True
        mock_llm.assert_called_once()

    def test_generate_summary_empty_response(self, rag_client):
        """Test summary generation with empty LLM response."""
        mock_llm = MagicMock(return_value="   ")

        rag_client._llm_generate_fn = mock_llm

        result = rag_client._generate_and_store_summary(
            content="Document content.",
            reference_name="empty_summary_doc",
            common_name="Empty Summary Doc",
        )

        assert result is False

    def test_generate_summary_exception(self, rag_client):
        """Test summary generation exception handling."""
        mock_llm = MagicMock(side_effect=Exception("LLM error"))

        rag_client._llm_generate_fn = mock_llm

        result = rag_client._generate_and_store_summary(
            content="Document content.",
            reference_name="error_doc",
            common_name="Error Doc",
        )

        assert result is False

    def test_generate_summary_no_llm_fn(self, rag_client):
        """Test summary generation when no LLM function is set."""
        rag_client._llm_generate_fn = None

        result = rag_client._generate_and_store_summary(
            content="Document content.",
            reference_name="no_llm_doc",
        )

        assert result is False

    def test_set_query_expansion_llm(self, rag_client):
        """Test setting query expansion LLM function."""
        mock_fn = MagicMock(return_value="Expanded query")
        rag_client._query_expander = MagicMock()
        rag_client._query_expander.set_llm_function = MagicMock()

        rag_client.set_query_expansion_llm(mock_fn)

        rag_client._query_expander.set_llm_function.assert_called_once_with(mock_fn)

    def test_set_query_expansion_llm_not_enabled(self, rag_client):
        """Test setting query expansion LLM when not enabled."""
        mock_fn = MagicMock(return_value="Expanded query")
        rag_client._query_expander = None

        rag_client.set_query_expansion_llm(mock_fn)


@requires_chromadb
class TestFFRAGClientChunkAddition:
    """Tests for FFRAGClient chunk addition methods."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock = MagicMock(spec=FFEmbeddings)
        mock.embed = MagicMock(side_effect=make_embed_mock)
        mock.embed_single = MagicMock(return_value=[0.1] * 384)
        mock.model = "test-model"
        return mock

    @pytest.fixture
    def rag_client(self, temp_persist_dir, mock_embeddings):
        """Create a RAG client with mocked embeddings."""
        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            return client

    def test_add_document_with_custom_chunk_size(self, rag_client, mock_embeddings):
        """Test add_document with custom chunk_size/overlap."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock_embeddings.embed = MagicMock(side_effect=make_embed_mock)

        content = "A" * 500
        chunks = rag_client.add_document(
            content=content,
            reference_name="custom_chunk_doc",
            chunk_size=100,
            chunk_overlap=20,
        )

        assert chunks >= 1

    def test_add_regular_chunks_with_contextual_headers(self, temp_persist_dir, mock_embeddings):
        """Test _add_regular_chunks with contextual headers enabled."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock_embeddings.embed = MagicMock(side_effect=make_embed_mock)

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            client.use_contextual_headers = False

        from src.RAG.text_splitter import TextChunk

        chunks = [TextChunk(content="Test chunk", chunk_index=0, start_char=0, end_char=10)]

        count = client._add_regular_chunks(chunks, reference_name="ctx_doc")

        assert count >= 1

    def test_add_regular_chunks_syncs_bm25(self, temp_persist_dir, mock_embeddings):
        """Test BM25 index sync in _add_regular_chunks."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                search_mode="hybrid",
            )
            client._embeddings = mock_embeddings

        from src.RAG.text_splitter import TextChunk

        chunks = [
            TextChunk(
                content="Test chunk",
                chunk_index=0,
                start_char=0,
                end_char=10,
                metadata={"reference_name": "bm25_doc"},
            )
        ]

        count = client._add_regular_chunks(chunks, reference_name="bm25_doc")

        assert count >= 1
        assert client._bm25_index is not None


@requires_chromadb
class TestFFRAGClientSearch:
    """Tests for FFRAGClient search functionality."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock = MagicMock(spec=FFEmbeddings)
        mock.embed = MagicMock(side_effect=make_embed_mock)
        mock.embed_single = MagicMock(return_value=[0.1] * 384)
        mock.model = "test-model"
        return mock

    @pytest.fixture
    def rag_client(self, temp_persist_dir, mock_embeddings):
        """Create a RAG client with mocked embeddings."""
        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            return client

    def test_search_with_query_expansion_override(self, rag_client, mock_embeddings):
        """Test search with query_expansion=True override."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])
        mock_embeddings.embed_single = MagicMock(return_value=[0.1] * 384)

        rag_client.add_document(content="Test document content", reference_name="expand_doc")

        rag_client._query_expander = MagicMock()
        rag_client._query_expander.llm_generate_fn = MagicMock(return_value="expanded")
        rag_client._query_expander.expand = MagicMock(return_value=["query", "expanded query"])

        results = rag_client.search("query", query_expansion=True)

        assert isinstance(results, list)

    def test_search_with_rerank_override(self, rag_client, mock_embeddings):
        """Test search with rerank parameter override."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])
        mock_embeddings.embed_single = MagicMock(return_value=[0.1] * 384)

        rag_client.add_document(content="Test document", reference_name="rerank_doc")

        results = rag_client.search("test", rerank=False)

        assert isinstance(results, list)

    def test_ensure_query_expander_lazy_init(self, rag_client):
        """Test lazy initialization of query expander."""
        rag_client._query_expander = None

        rag_client._ensure_query_expander()

        assert rag_client._query_expander is not None

    def test_ensure_query_expander_with_llm_fn(self, rag_client):
        """Test lazy init of query expander with LLM function."""
        rag_client._query_expander = None
        rag_client._llm_generate_fn = MagicMock(return_value="response")

        rag_client._ensure_query_expander()

        assert rag_client._query_expander is not None
        assert rag_client._query_expander.llm_generate_fn is not None

    def test_ensure_reranker_lazy_init(self, rag_client):
        """Test lazy initialization of reranker."""
        rag_client._reranker = None

        rag_client._ensure_reranker()

        assert rag_client._reranker is not None

    def test_search_single_hybrid_mode(self, temp_persist_dir, mock_embeddings):
        """Test _search_single with hybrid search mode."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])
        mock_embeddings.embed_single = MagicMock(return_value=[0.1] * 384)

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                search_mode="hybrid",
            )
            client._embeddings = mock_embeddings

        client.add_document(content="Hybrid test document", reference_name="hybrid_doc")

        results = client._search_single("test", n_results=5, rerank=False)

        assert isinstance(results, list)

    def test_search_single_with_summaries(self, temp_persist_dir, mock_embeddings):
        """Test _search_single with summary boosting."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])
        mock_embeddings.embed_single = MagicMock(return_value=[0.1] * 384)

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            client.generate_summaries = True

        client.add_document(content="Document with summary", reference_name="sum_doc")

        from src.RAG.text_splitter import TextChunk

        summary_chunk = TextChunk(
            content="[DOCUMENT SUMMARY]\nThis is a summary.",
            chunk_index=-1,
            start_char=0,
            end_char=20,
            metadata={"reference_name": "sum_doc", "chunk_type": "summary"},
        )
        client._vector_store.add_chunks([summary_chunk])

        results = client._search_single("summary", n_results=5, rerank=False)

        assert isinstance(results, list)


@requires_chromadb
class TestFFRAGClientUtilities:
    """Tests for FFRAGClient utility methods."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock = MagicMock(spec=FFEmbeddings)
        mock.embed = MagicMock(side_effect=make_embed_mock)
        mock.embed_single = MagicMock(return_value=[0.1] * 384)
        mock.model = "test-model"
        return mock

    @pytest.fixture
    def rag_client(self, temp_persist_dir, mock_embeddings):
        """Create a RAG client with mocked embeddings."""
        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            return client

    def test_format_results_with_parent_context(self, rag_client):
        """Test format_results_for_prompt with parent_content."""
        results = [
            {
                "content": "Child chunk content",
                "metadata": {"reference_name": "doc1"},
                "score": 0.9,
                "parent_content": "This is the parent chunk content that provides context.",
            }
        ]

        rag_client.parent_context = True
        formatted = rag_client.format_results_for_prompt(results)

        assert "[Parent context:" in formatted

    def test_format_results_with_short_parent_context(self, rag_client):
        """Test format_results_for_prompt with short parent_content."""
        results = [
            {
                "content": "Child chunk",
                "metadata": {"reference_name": "doc1"},
                "score": 0.9,
                "parent_content": "Short parent",
            }
        ]

        rag_client.parent_context = True
        formatted = rag_client.format_results_for_prompt(results)

        assert "[Parent context: Short parent]" in formatted

    def test_add_documents_batch(self, rag_client, mock_embeddings):
        """Test adding multiple documents at once."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        documents = [
            {"content": "Document 1", "reference_name": "batch1"},
            {"content": "Document 2", "reference_name": "batch2"},
        ]

        total = rag_client.add_documents(documents)

        assert total >= 2

    def test_delete_by_reference_with_bm25(self, temp_persist_dir, mock_embeddings):
        """Test delete_by_reference syncs BM25 index."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                search_mode="hybrid",
            )
            client._embeddings = mock_embeddings

        client.add_document(
            content="Test document to delete",
            reference_name="delete_bm25_doc",
            metadata={"reference_name": "delete_bm25_doc"},
        )

        client.delete_by_reference("delete_bm25_doc")

        docs = client.list_documents()
        assert "delete_bm25_doc" not in docs

    def test_delete_by_reference_with_hierarchical(self, temp_persist_dir, mock_embeddings):
        """Test delete_by_reference syncs hierarchical index."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            client.hierarchical_enabled = True
            client._hierarchical_index = MagicMock()

        client.add_document(content="Hierarchical doc", reference_name="hier_del_doc")
        client.delete_by_reference("hier_del_doc")

        docs = client.list_documents()
        assert "hier_del_doc" not in docs

    def test_clear_chunking_strategy(self, rag_client, mock_embeddings):
        """Test clearing all chunks for a chunking strategy."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        rag_client.add_document(content="Strategy doc", reference_name="strat_doc")

        count = rag_client.clear_chunking_strategy("recursive")

        assert count >= 0

    def test_clear_chunking_strategy_with_bm25(self, temp_persist_dir, mock_embeddings):
        """Test clear_chunking_strategy clears BM25."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                search_mode="hybrid",
            )
            client._embeddings = mock_embeddings

        client.add_document(content="Doc to clear", reference_name="clear_doc")

        client.clear_chunking_strategy("recursive")

        assert client._bm25_index is not None

    def test_get_indexed_documents(self, rag_client, mock_embeddings):
        """Test get_indexed_documents method."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        rag_client.add_document(content="Indexed doc", reference_name="indexed_doc")

        indexed = rag_client.get_indexed_documents()

        assert isinstance(indexed, list)

    def test_get_indexed_documents_with_filter(self, rag_client, mock_embeddings):
        """Test get_indexed_documents with chunking_strategy filter."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        rag_client.add_document(content="Filtered doc", reference_name="filtered_doc")

        indexed = rag_client.get_indexed_documents(chunking_strategy="recursive")

        assert isinstance(indexed, list)

    def test_needs_reindex(self, rag_client, mock_embeddings):
        """Test needs_reindex method."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        rag_client.add_document(content="Reindex doc", reference_name="reindex_doc")

        needs = rag_client.needs_reindex("reindex_doc", "different_checksum")

        assert needs is True

    def test_needs_reindex_same_checksum(self, rag_client, mock_embeddings):
        """Test needs_reindex with same checksum returns False."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        rag_client.add_document(
            content="Same checksum doc",
            reference_name="same_checksum_doc",
            checksum="checksum123",
        )

        needs = rag_client.needs_reindex("same_checksum_doc", "checksum123")

        assert needs is False

    def test_get_stats_with_bm25(self, temp_persist_dir, mock_embeddings):
        """Test get_stats includes BM25 stats."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                search_mode="hybrid",
            )
            client._embeddings = mock_embeddings

        stats = client.get_stats()

        assert "bm25_docs" in stats

    def test_get_stats_with_hierarchical(self, temp_persist_dir, mock_embeddings):
        """Test get_stats includes hierarchical stats."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            client._hierarchical_index = MagicMock()
            client._hierarchical_index.get_stats = MagicMock(return_value={"total": 0})

        stats = client.get_stats()

        assert "hierarchical" in stats

    def test_clear_with_bm25_and_hierarchical(self, temp_persist_dir, mock_embeddings):
        """Test clear clears all indexes."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
                search_mode="hybrid",
            )
            client._embeddings = mock_embeddings
            client._hierarchical_index = MagicMock()

        client.add_document(content="Doc to clear", reference_name="clear_all_doc")
        client.clear()

        assert client.count() == 0

    def test_vector_store_property(self, rag_client):
        """Test vector_store property accessor."""
        vs = rag_client.vector_store

        assert vs is rag_client._vector_store

    def test_embeddings_property(self, rag_client):
        """Test embeddings property accessor."""
        emb = rag_client.embeddings

        assert emb is rag_client._embeddings

    def test_chunker_property(self, rag_client):
        """Test chunker property accessor."""
        chunker = rag_client.chunker

        assert chunker is rag_client._chunker


@requires_chromadb
class TestFFRAGClient:
    """Tests for high-level RAG client."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_embeddings(self):
        """Create mock embeddings."""

        def make_embed_mock(texts):
            n = len(texts) if isinstance(texts, list) else 1
            return [[0.1] * 384 for _ in range(n)]

        mock = MagicMock(spec=FFEmbeddings)
        mock.embed = MagicMock(side_effect=make_embed_mock)
        mock.embed_single = MagicMock(return_value=[0.1] * 384)
        mock.model = "test-model"
        return mock

    @pytest.fixture
    def rag_client(self, temp_persist_dir, mock_embeddings):
        """Create a RAG client with mocked embeddings."""
        with patch("src.RAG.FFRAGClient.FFEmbeddings", return_value=mock_embeddings):
            client = FFRAGClient(
                persist_dir=temp_persist_dir,
                embedding_model=mock_embeddings,
            )
            client._embeddings = mock_embeddings
            return client

    def test_add_document(self, rag_client, mock_embeddings):
        """Test adding a document."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        chunks = rag_client.add_document(
            content="This is a test document content.",
            reference_name="test_doc",
            metadata={"source": "test"},
        )

        assert chunks >= 1
        assert rag_client.count() >= 1

    def test_add_document_empty(self, rag_client):
        """Test adding empty document."""
        chunks = rag_client.add_document(content="", reference_name="empty_doc")

        assert chunks == 0

    def test_search(self, rag_client, mock_embeddings):
        """Test searching documents."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])
        mock_embeddings.embed_single = MagicMock(return_value=[0.1] * 384)

        rag_client.add_document(
            content="Authentication requires API keys set in environment variables.",
            reference_name="auth_doc",
        )

        results = rag_client.search("how to authenticate")

        assert len(results) >= 1
        assert "score" in results[0]
        assert "content" in results[0]
        assert "metadata" in results[0]

    def test_format_results_for_prompt(self, rag_client):
        """Test formatting results for prompt injection."""
        results = [
            {
                "content": "Content 1",
                "metadata": {"reference_name": "doc1"},
                "score": 0.9,
            },
            {
                "content": "Content 2",
                "metadata": {"reference_name": "doc2"},
                "score": 0.8,
            },
        ]

        formatted = rag_client.format_results_for_prompt(results)

        assert "[1]" in formatted
        assert "[2]" in formatted
        assert "doc1" in formatted
        assert "doc2" in formatted

    def test_format_results_empty(self, rag_client):
        """Test formatting empty results."""
        formatted = rag_client.format_results_for_prompt([])

        assert formatted == ""

    def test_format_results_max_chars(self, rag_client):
        """Test formatting with character limit."""
        results = [
            {
                "content": "Short",
                "metadata": {"reference_name": "doc1"},
                "score": 0.9,
            },
            {
                "content": "B" * 100,
                "metadata": {"reference_name": "doc2"},
                "score": 0.8,
            },
        ]

        formatted = rag_client.format_results_for_prompt(results, max_chars=50)

        assert "Short" in formatted
        assert "doc1" in formatted
        assert "doc2" not in formatted

    def test_delete_by_reference(self, rag_client, mock_embeddings):
        """Test deleting by reference name."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])

        rag_client.add_document(content="Test content", reference_name="delete_me")
        assert rag_client.count() >= 1

        rag_client.delete_by_reference("delete_me")

        docs = rag_client.list_documents()
        assert "delete_me" not in docs

    def test_get_stats(self, rag_client):
        """Test getting client statistics."""
        stats = rag_client.get_stats()

        assert "collection_name" in stats
        assert "count" in stats
        assert "chunk_size" in stats
        assert "chunk_overlap" in stats

    def test_search_and_format(self, rag_client, mock_embeddings):
        """Test combined search and format."""
        mock_embeddings.embed = MagicMock(return_value=[[0.1] * 384])
        mock_embeddings.embed_single = MagicMock(return_value=[0.1] * 384)

        rag_client.add_document(
            content="Python is a programming language.",
            reference_name="python_doc",
        )

        formatted = rag_client.search_and_format("programming", n_results=1)

        assert "Python" in formatted
        assert "python_doc" in formatted


@requires_chromadb
class TestRAGMCPTools:
    """Tests for MCP tools."""

    @pytest.fixture
    def mock_rag_client(self):
        """Create a mock RAG client."""
        mock = MagicMock(spec=FFRAGClient)
        mock.search.return_value = [
            {"content": "Result 1", "score": 0.9, "metadata": {"reference_name": "doc1"}},
        ]
        mock.add_document.return_value = 3
        mock.list_documents.return_value = ["doc1", "doc2"]
        mock.get_stats.return_value = {"count": 5, "collection_name": "test"}
        return mock

    @pytest.fixture
    def mcp_tools(self, mock_rag_client):
        """Create MCP tools with mock client."""
        return RAGMCPTools(rag_client=mock_rag_client)

    def test_rag_search(self, mcp_tools, mock_rag_client):
        """Test rag_search tool."""
        results = mcp_tools.rag_search("test query", n_results=5)

        mock_rag_client.search.assert_called_once_with("test query", n_results=5)
        assert len(results) == 1

    def test_rag_add_document(self, mcp_tools, mock_rag_client):
        """Test rag_add_document tool."""
        result = mcp_tools.rag_add_document(
            content="Test content",
            reference_name="test_doc",
        )

        mock_rag_client.add_document.assert_called_once()
        assert result["status"] == "success"
        assert result["chunks_added"] == 3

    def test_rag_list_documents(self, mcp_tools, mock_rag_client):
        """Test rag_list_documents tool."""
        docs = mcp_tools.rag_list_documents()

        assert docs == ["doc1", "doc2"]

    def test_rag_get_stats(self, mcp_tools, mock_rag_client):
        """Test rag_get_stats tool."""
        stats = mcp_tools.rag_get_stats()

        assert stats["count"] == 5

    def test_rag_delete_document(self, mcp_tools, mock_rag_client):
        """Test rag_delete_document tool."""
        result = mcp_tools.rag_delete_document("old_doc")

        mock_rag_client.delete_by_reference.assert_called_once_with("old_doc")
        assert result["status"] == "deleted"

    def test_get_tool_definitions(self, mcp_tools):
        """Test getting tool definitions."""
        definitions = mcp_tools.get_tool_definitions()

        assert len(definitions) == 5
        tool_names = [d["name"] for d in definitions]
        assert "rag_search" in tool_names
        assert "rag_add_document" in tool_names
        assert "rag_list_documents" in tool_names
        assert "rag_get_stats" in tool_names
        assert "rag_delete_document" in tool_names

    def test_execute_tool(self, mcp_tools, mock_rag_client):
        """Test executing tools by name."""
        result = mcp_tools.execute_tool("rag_search", {"query": "test"})

        mock_rag_client.search.assert_called_once()
        assert len(result) == 1

    def test_execute_tool_unknown_raises(self, mcp_tools):
        """Test executing unknown tool raises error."""
        with pytest.raises(ValueError, match="Unknown tool"):
            mcp_tools.execute_tool("unknown_tool", {})


@requires_chromadb
class TestRAGIntegration:
    """Integration tests for RAG with document registry."""

    @pytest.fixture
    def temp_persist_dir(self):
        """Create a temporary directory for ChromaDB."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_document_registry_semantic_search(self, temp_persist_dir):
        """Test DocumentRegistry.semantic_search method."""
        from src.orchestrator.document_processor import DocumentProcessor
        from src.orchestrator.document_registry import DocumentRegistry

        mock_rag = MagicMock(spec=FFRAGClient)
        mock_rag.search.return_value = [
            {
                "content": "Authentication requires API keys",
                "metadata": {"reference_name": "api_ref"},
                "score": 0.85,
            },
        ]

        with tempfile.TemporaryDirectory() as cache_dir:
            processor = DocumentProcessor(cache_dir=cache_dir, rag_client=mock_rag)
            registry = DocumentRegistry(
                documents=[],
                processor=processor,
                workbook_dir=tempfile.mkdtemp(),
                rag_client=mock_rag,
            )

            results = registry.semantic_search("authentication", n_results=5)

            mock_rag.search.assert_called_once_with(
                "authentication", n_results=5, where=None, query_expansion=None, rerank=None
            )
            assert len(results) == 1

    def test_document_registry_format_semantic_results(self):
        """Test DocumentRegistry.format_semantic_results method."""
        from src.orchestrator.document_processor import DocumentProcessor
        from src.orchestrator.document_registry import DocumentRegistry

        mock_rag = MagicMock(spec=FFRAGClient)
        mock_processor = MagicMock(spec=DocumentProcessor)

        registry = DocumentRegistry(
            documents=[],
            processor=mock_processor,
            workbook_dir=tempfile.mkdtemp(),
            rag_client=mock_rag,
        )

        results = [
            {"content": "Content 1", "metadata": {"reference_name": "doc1"}, "score": 0.9},
            {"content": "Content 2", "metadata": {"reference_name": "doc2"}, "score": 0.8},
        ]

        formatted = registry.format_semantic_results(results)

        assert "[1]" in formatted
        assert "doc1" in formatted
        assert "0.90" in formatted

    def test_document_registry_inject_semantic_query(self):
        """Test DocumentRegistry.inject_semantic_query method."""
        from src.orchestrator.document_processor import DocumentProcessor
        from src.orchestrator.document_registry import DocumentRegistry

        mock_rag = MagicMock(spec=FFRAGClient)
        mock_rag.search.return_value = [
            {"content": "Relevant content", "metadata": {"reference_name": "doc1"}, "score": 0.9},
        ]

        mock_processor = MagicMock(spec=DocumentProcessor)

        registry = DocumentRegistry(
            documents=[],
            processor=mock_processor,
            workbook_dir=tempfile.mkdtemp(),
            rag_client=mock_rag,
        )

        result = registry.inject_semantic_query(
            prompt="What is X?",
            semantic_query="search terms",
            n_results=3,
        )

        assert "<RELEVANT_CONTEXT>" in result
        assert "</RELEVANT_CONTEXT>" in result
        assert "What is X?" in result
        mock_rag.search.assert_called_once()
