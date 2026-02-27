# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Tests for RAG module functionality."""

from __future__ import annotations

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.RAG import CHROMADB_AVAILABLE, FFEmbeddings, RAGMCPTools, split_text
from src.RAG.text_splitter import TextChunk, split_documents

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
        chunks = split_text(text, chunk_size=50, chunk_overlap=10)

        assert len(chunks) > 1
        assert all(isinstance(c, TextChunk) for c in chunks)
        assert all(len(c.content) <= 60 for c in chunks)  # Allow some overflow for word boundaries

    def test_split_text_empty(self):
        """Test splitting empty text."""
        chunks = split_text("", chunk_size=100, chunk_overlap=20)
        assert chunks == []

    def test_split_text_single_chunk(self):
        """Test text shorter than chunk size."""
        text = "Short text"
        chunks = split_text(text, chunk_size=100, chunk_overlap=20)

        assert len(chunks) == 1
        assert chunks[0].content == text

    def test_split_text_invalid_params(self):
        """Test invalid parameters raise errors."""
        text = "Some text"

        with pytest.raises(ValueError, match="chunk_size must be positive"):
            split_text(text, chunk_size=0)

        with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
            split_text(text, chunk_size=100, chunk_overlap=-1)

        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            split_text(text, chunk_size=50, chunk_overlap=50)

    def test_split_text_metadata(self):
        """Test metadata is attached to chunks."""
        text = "Test content"
        metadata = {"source": "test.txt", "author": "test"}
        chunks = split_text(text, chunk_size=100, chunk_overlap=20, metadata=metadata)

        assert len(chunks) == 1
        assert chunks[0].metadata == metadata

    def test_split_text_overlap(self):
        """Test that overlap works correctly."""
        text = "A" * 50 + "B" * 50 + "C" * 50
        chunks = split_text(text, chunk_size=60, chunk_overlap=20)

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
        chunks = split_documents(documents, chunk_size=50, chunk_overlap=10)

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

            mock_rag.search.assert_called_once_with("authentication", n_results=5)
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
