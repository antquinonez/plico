from unittest.mock import MagicMock, patch

import pytest

from src.RAG.mcp_tools import RAGMCPTools


class TestRAGMCPToolsInit:
    def test_init_with_explicit_client(self):
        mock_rag = MagicMock()
        tools = RAGMCPTools(rag_client=mock_rag)
        assert tools._rag is mock_rag

    def test_init_creates_default_client(self):
        with patch("src.RAG.mcp_tools.FFRAGClient") as MockClient:
            tools = RAGMCPTools()
            MockClient.assert_called_once()


class TestRAGMCPSearchClamping:
    def test_n_results_clamped_below_minimum(self):
        mock_rag = MagicMock()
        mock_rag.search.return_value = [{"content": "x", "score": 0.5}]
        tools = RAGMCPTools(rag_client=mock_rag)

        tools.rag_search("test", n_results=-5)

        mock_rag.search.assert_called_once_with("test", n_results=1)

    def test_n_results_clamped_above_maximum(self):
        mock_rag = MagicMock()
        mock_rag.search.return_value = []
        tools = RAGMCPTools(rag_client=mock_rag)

        tools.rag_search("test", n_results=100)

        mock_rag.search.assert_called_once_with("test", n_results=20)


class TestRAGMCPAddDocument:
    def test_returns_status_and_chunk_count(self):
        mock_rag = MagicMock()
        mock_rag.add_document.return_value = 7
        tools = RAGMCPTools(rag_client=mock_rag)

        result = tools.rag_add_document(
            content="text", reference_name="ref", metadata={"key": "val"}
        )

        assert result["status"] == "success"
        assert result["chunks_added"] == 7
        assert result["reference_name"] == "ref"
        mock_rag.add_document.assert_called_once_with(
            content="text", reference_name="ref", metadata={"key": "val"}
        )

    def test_none_reference_name_passes_through(self):
        mock_rag = MagicMock()
        mock_rag.add_document.return_value = 1
        tools = RAGMCPTools(rag_client=mock_rag)

        result = tools.rag_add_document(content="text")

        assert result["reference_name"] is None


class TestRAGMCPListDocuments:
    def test_delegates_to_rag_client(self):
        mock_rag = MagicMock()
        mock_rag.list_documents.return_value = ["alpha", "beta"]
        tools = RAGMCPTools(rag_client=mock_rag)

        docs = tools.rag_list_documents()

        assert docs == ["alpha", "beta"]


class TestRAGMCPGetStats:
    def test_delegates_to_rag_client(self):
        mock_rag = MagicMock()
        mock_rag.get_stats.return_value = {"count": 42, "collection_name": "kb"}
        tools = RAGMCPTools(rag_client=mock_rag)

        stats = tools.rag_get_stats()

        assert stats["count"] == 42
        assert stats["collection_name"] == "kb"


class TestRAGMCPDeleteDocument:
    def test_returns_deleted_status(self):
        mock_rag = MagicMock()
        tools = RAGMCPTools(rag_client=mock_rag)

        result = tools.rag_delete_document("old_doc")

        mock_rag.delete_by_reference.assert_called_once_with("old_doc")
        assert result == {"status": "deleted", "reference_name": "old_doc"}


class TestRAGMCPToolDefinitions:
    def test_all_tools_have_name_and_schema(self):
        mock_rag = MagicMock()
        tools = RAGMCPTools(rag_client=mock_rag)
        defs = tools.get_tool_definitions()

        assert len(defs) == 5
        for d in defs:
            assert "name" in d
            assert "description" in d
            assert "inputSchema" in d
            assert d["inputSchema"]["type"] == "object"

    def test_search_tool_schema_requires_query(self):
        mock_rag = MagicMock()
        tools = RAGMCPTools(rag_client=mock_rag)
        defs = tools.get_tool_definitions()
        search_def = [d for d in defs if d["name"] == "rag_search"][0]

        assert search_def["inputSchema"]["required"] == ["query"]
        assert "n_results" in search_def["inputSchema"]["properties"]

    def test_add_document_schema_requires_content(self):
        mock_rag = MagicMock()
        tools = RAGMCPTools(rag_client=mock_rag)
        defs = tools.get_tool_definitions()
        add_def = [d for d in defs if d["name"] == "rag_add_document"][0]

        assert add_def["inputSchema"]["required"] == ["content"]


class TestRAGMCPExecuteTool:
    def test_execute_search_passes_arguments(self):
        mock_rag = MagicMock()
        mock_rag.search.return_value = [{"content": "found", "score": 0.9}]
        tools = RAGMCPTools(rag_client=mock_rag)

        result = tools.execute_tool("rag_search", {"query": "test", "n_results": 3})

        mock_rag.search.assert_called_once_with("test", n_results=3)
        assert result[0]["content"] == "found"

    def test_execute_add_document(self):
        mock_rag = MagicMock()
        mock_rag.add_document.return_value = 2
        tools = RAGMCPTools(rag_client=mock_rag)

        result = tools.execute_tool(
            "rag_add_document", {"content": "text", "reference_name": "ref"}
        )

        assert result["status"] == "success"
        assert result["chunks_added"] == 2

    def test_execute_delete_document(self):
        mock_rag = MagicMock()
        tools = RAGMCPTools(rag_client=mock_rag)

        result = tools.execute_tool("rag_delete_document", {"reference_name": "x"})

        assert result["status"] == "deleted"

    def test_execute_unknown_raises(self):
        mock_rag = MagicMock()
        tools = RAGMCPTools(rag_client=mock_rag)

        with pytest.raises(ValueError, match="Unknown tool: bad_name"):
            tools.execute_tool("bad_name", {})
