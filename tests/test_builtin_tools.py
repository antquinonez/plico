# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""Tests for built-in tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator.builtin_tools import (
    BUILTIN_TOOL_DEFINITIONS,
    _calculate,
    _http_get,
    _json_extract,
    _make_list_documents,
    _make_rag_search,
    _make_read_document,
    create_context_tools,
    get_builtin_tool,
)


class TestCalculateTool:
    """Tests for the calculate built-in tool."""

    def test_basic_arithmetic(self):
        result = json.loads(_calculate({"expression": "2 + 3"}))
        assert result["result"] == 5

    def test_complex_expression(self):
        result = json.loads(_calculate({"expression": "(10 + 5) * 2 - 3"}))
        assert result["result"] == 27

    def test_float_division(self):
        result = json.loads(_calculate({"expression": "10 / 3"}))
        assert abs(result["result"] - 3.3333333333333335) < 1e-10

    def test_floor_division(self):
        result = json.loads(_calculate({"expression": "10 // 3"}))
        assert result["result"] == 3

    def test_modulo(self):
        result = json.loads(_calculate({"expression": "10 % 3"}))
        assert result["result"] == 1

    def test_power(self):
        result = json.loads(_calculate({"expression": "2 ** 10"}))
        assert result["result"] == 1024

    def test_unary_negation(self):
        result = json.loads(_calculate({"expression": "-5"}))
        assert result["result"] == -5

    def test_functions(self):
        result = json.loads(_calculate({"expression": "abs(-10)"}))
        assert result["result"] == 10

    def test_min_max(self):
        result = json.loads(_calculate({"expression": "max(1, 5, 3)"}))
        assert result["result"] == 5

    def test_sqrt(self):
        result = json.loads(_calculate({"expression": "sqrt(16)"}))
        assert result["result"] == 4.0

    def test_pi_constant(self):
        result = json.loads(_calculate({"expression": "pi"}))
        assert abs(result["result"] - 3.141592653589793) < 1e-10

    def test_empty_expression(self):
        result = json.loads(_calculate({"expression": ""}))
        assert "error" in result

    def test_dangerous_expression_blocked(self):
        result = json.loads(_calculate({"expression": '__import__("os").system("ls")'}))
        assert "error" in result

    def test_variable_blocked(self):
        result = json.loads(_calculate({"expression": "x = 5"}))
        assert "error" in result


class TestJsonExtractTool:
    """Tests for the json_extract built-in tool."""

    def test_simple_field(self):
        data = json.dumps({"name": "Alice", "age": 30})
        result = json.loads(_json_extract({"data": data, "path": "name"}))
        assert result["result"] == "Alice"

    def test_nested_field(self):
        data = json.dumps({"user": {"profile": {"name": "Bob"}}})
        result = json.loads(_json_extract({"data": data, "path": "user.profile.name"}))
        assert result["result"] == "Bob"

    def test_array_index(self):
        data = json.dumps({"items": ["a", "b", "c"]})
        result = json.loads(_json_extract({"data": data, "path": "items.0"}))
        assert result["result"] == "a"

    def test_missing_path(self):
        data = json.dumps({"name": "Alice"})
        result = json.loads(_json_extract({"data": data, "path": "missing.field"}))
        assert "error" in result

    def test_invalid_json(self):
        result = json.loads(_json_extract({"data": "not json", "path": "field"}))
        assert "error" in result

    def test_missing_params(self):
        result = json.loads(_json_extract({"data": "", "path": ""}))
        assert "error" in result


class TestGetBuiltinTool:
    """Tests for get_builtin_tool function."""

    def test_get_calculate(self):
        tool = get_builtin_tool("calculate")
        assert callable(tool)
        result = tool({"expression": "1+1"})
        assert json.loads(result)["result"] == 2

    def test_get_json_extract(self):
        tool = get_builtin_tool("json_extract")
        assert callable(tool)

    def test_get_http_get(self):
        tool = get_builtin_tool("http_get")
        assert callable(tool)

    def test_get_rag_search_standalone(self):
        tool = get_builtin_tool("rag_search")
        assert callable(tool)
        result = tool({"query": "test"})
        parsed = json.loads(result)
        assert "error" in parsed

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown built-in tool"):
            get_builtin_tool("nonexistent_tool")


class TestCreateContextTools:
    """Tests for create_context_tools function."""

    def test_all_standalone_tools_included(self):
        tools = create_context_tools()
        assert "calculate" in tools
        assert "json_extract" in tools
        assert "http_get" in tools
        assert "rag_search" in tools
        assert "read_document" in tools
        assert "list_documents" in tools

    def test_rag_search_with_mock_client(self):
        mock_rag = MagicMock()
        mock_rag.search.return_value = [
            {"content": "doc content", "metadata": {"source": "test"}, "score": 0.9},
        ]
        tools = create_context_tools(rag_client=mock_rag)
        result = tools["rag_search"]({"query": "test query", "n_results": 3})
        parsed = json.loads(result)
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["content"] == "doc content"

    def test_rag_search_handles_exception(self):
        mock_rag = MagicMock()
        mock_rag.search.side_effect = Exception("Search failed")
        tools = create_context_tools(rag_client=mock_rag)
        result = tools["rag_search"]({"query": "test"})
        parsed = json.loads(result)
        assert "error" in parsed

    def test_list_documents_with_mock_registry(self):
        mock_registry = MagicMock()
        mock_registry.get_reference_names.return_value = {"doc_a", "doc_b"}
        tools = create_context_tools(document_registry=mock_registry)
        result = tools["list_documents"]({})
        parsed = json.loads(result)
        assert parsed["count"] == 2
        assert set(parsed["documents"]) == {"doc_a", "doc_b"}

    def test_read_document_with_mock_registry(self):
        mock_registry = MagicMock()
        mock_registry.get_reference_names.return_value = {"policy_doc"}
        mock_registry.get_content.return_value = "Document content here"
        tools = create_context_tools(document_registry=mock_registry)
        result = tools["read_document"]({"name": "policy_doc"})
        assert result == "Document content here"

    def test_read_document_not_found(self):
        mock_registry = MagicMock()
        mock_registry.get_reference_names.return_value = {"other_doc"}
        tools = create_context_tools(document_registry=mock_registry)
        result = tools["read_document"]({"name": "missing_doc"})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "not found" in parsed["error"].lower()


class TestBuiltinToolDefinitions:
    """Tests for BUILTIN_TOOL_DEFINITIONS dictionary."""

    def test_all_expected_tools_defined(self):
        expected = {
            "rag_search",
            "read_document",
            "list_documents",
            "calculate",
            "json_extract",
            "http_get",
        }
        assert expected == set(BUILTIN_TOOL_DEFINITIONS.keys())

    def test_each_has_description(self):
        for name, defn in BUILTIN_TOOL_DEFINITIONS.items():
            assert defn["description"], f"Tool '{name}' missing description"

    def test_each_has_parameters(self):
        for name, defn in BUILTIN_TOOL_DEFINITIONS.items():
            assert "parameters" in defn, f"Tool '{name}' missing parameters"
            assert defn["parameters"]["type"] == "object"


class TestHttpGetTool:
    """Tests for the http_get built-in tool."""

    @patch("src.orchestrator.builtin_tools.urllib.request.urlopen")
    def test_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>hello</html>"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        result = _http_get({"url": "http://example.com"})
        assert result == "<html>hello</html>"

    @patch("src.orchestrator.builtin_tools.urllib.request.urlopen")
    def test_error(self, mock_urlopen):
        mock_urlopen.side_effect = RuntimeError("timeout")
        result = json.loads(_http_get({"url": "http://error.com"}))
        assert "HTTP GET failed" in result["error"]

    def test_missing_url(self):
        result = json.loads(_http_get({}))
        assert "required" in result["error"].lower()


class TestUnavailableContextTools:
    """Tests for context-bound tools when no context is provided."""

    def test_rag_search_unavailable(self):
        rag_tool = _make_rag_search(None)
        result = json.loads(rag_tool({"query": "test"}))
        assert "not available" in result["error"]

    def test_list_documents_unavailable(self):
        list_tool = _make_list_documents(None)
        result = json.loads(list_tool({}))
        assert "not available" in result["error"]

    def test_read_document_unavailable(self):
        read_tool = _make_read_document(None)
        result = json.loads(read_tool({"name": "test"}))
        assert "not available" in result["error"]
