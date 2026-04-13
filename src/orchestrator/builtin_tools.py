# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Built-in tool implementations for agentic execution.

Each built-in tool is a callable that accepts a dict of arguments
and returns a string result. Tools are registered by name and looked
up via ``get_builtin_tool()``.

Built-in tools available:
- ``rag_search``: Semantic search across indexed documents
- ``read_document``: Read a specific document's content
- ``list_documents``: List available document names and metadata
- ``calculate``: Evaluate a mathematical expression
- ``json_extract``: Extract fields from JSON data
- ``http_get``: Fetch content from a URL
"""

from __future__ import annotations

import ast
import json
import logging
import math
import operator
import urllib.request
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..core.prompt_utils import extract_json_field

if TYPE_CHECKING:
    from ..RAG import FFRAGClient
    from .document_registry import DocumentRegistry

logger = logging.getLogger(__name__)

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "int": int,
    "float": float,
    "len": len,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
    "log": math.log,
    "log10": math.log10,
}


def _make_rag_search(rag_client: FFRAGClient | None) -> Callable[..., str]:
    """Create a rag_search tool bound to an RAG client instance."""

    def rag_search(arguments: dict[str, Any]) -> str:
        query = arguments.get("query", "")
        n_results = arguments.get("n_results", 5)

        if not query:
            return json.dumps({"error": "query parameter is required"})

        if rag_client is None:
            return json.dumps({"error": "RAG client not available"})

        try:
            results = rag_client.search(query=query, n_results=int(n_results))
            if isinstance(results, list):
                search_results = []
                for r in results:
                    if isinstance(r, dict):
                        search_results.append(
                            {
                                "content": r.get("content", r.get("text", "")),
                                "metadata": r.get("metadata", {}),
                                "score": r.get("score", r.get("distance", None)),
                            }
                        )
                    else:
                        search_results.append({"content": str(r)})
                return json.dumps({"results": search_results})
            return json.dumps({"results": str(results)})
        except Exception as e:
            logger.error(f"RAG search failed: {e}")
            return json.dumps({"error": f"RAG search failed: {e}"})

    return rag_search


def _make_read_document(
    document_registry: DocumentRegistry | None,
) -> Callable[..., str]:
    """Create a read_document tool bound to a DocumentRegistry."""

    def read_document(arguments: dict[str, Any]) -> str:
        name = arguments.get("name", "")

        if not name:
            return json.dumps({"error": "name parameter is required"})

        if document_registry is None:
            return json.dumps({"error": "Document registry not available"})

        try:
            reference_names = document_registry.get_reference_names()
            if name not in reference_names:
                return json.dumps(
                    {
                        "error": f"Document '{name}' not found. Available: {list(reference_names)}",
                    }
                )

            content = document_registry.get_content(name)
            if content is None:
                return json.dumps({"error": f"Could not read document '{name}'"})

            max_length = arguments.get("max_length", 10000)
            if len(content) > max_length:
                content = content[:max_length] + "\n... (truncated)"

            return content
        except Exception as e:
            logger.error(f"Read document failed: {e}")
            return json.dumps({"error": f"Read document failed: {e}"})

    return read_document


def _make_list_documents(
    document_registry: DocumentRegistry | None,
) -> Callable[..., str]:
    """Create a list_documents tool bound to a DocumentRegistry."""

    def list_documents(arguments: dict[str, Any]) -> str:
        if document_registry is None:
            return json.dumps({"error": "Document registry not available"})

        try:
            names = list(document_registry.get_reference_names())
            return json.dumps({"documents": names, "count": len(names)})
        except Exception as e:
            logger.error(f"List documents failed: {e}")
            return json.dumps({"error": f"List documents failed: {e}"})

    return list_documents


def _calculate(arguments: dict[str, Any]) -> str:
    """Evaluate a mathematical expression safely using AST."""
    expression = arguments.get("expression", "")

    if not expression:
        return json.dumps({"error": "expression parameter is required"})

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval_ast_node(tree.body)
        return json.dumps({"result": result})
    except Exception as e:
        return json.dumps({"error": f"Evaluation failed: {e}"})


def _eval_ast_node(node: ast.AST) -> Any:
    """Recursively evaluate an AST node with safe operations only."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(_eval_ast_node(node.operand))
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(_eval_ast_node(node.left), _eval_ast_node(node.right))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named function calls are supported")
        func_name = node.func.id
        if func_name not in _SAFE_FUNCTIONS:
            raise ValueError(f"Function not allowed: {func_name}")
        args = [_eval_ast_node(arg) for arg in node.args]
        return _SAFE_FUNCTIONS[func_name](*args)
    if isinstance(node, ast.Name):
        if node.id in ("pi", "e"):
            return getattr(math, node.id)
        raise ValueError(f"Variable not allowed: {node.id}")

    raise ValueError(f"Unsupported AST node: {type(node).__name__}")


def _json_extract(arguments: dict[str, Any]) -> str:
    """Extract fields from JSON data."""
    data_str = arguments.get("data", "")
    path = arguments.get("path", "")

    if not data_str or not path:
        return json.dumps({"error": "data and path parameters are required"})

    try:
        data = json.loads(data_str)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON data: {e}"})

    result = extract_json_field(data, path)
    if not result:
        return json.dumps({"error": f"Path not found: {path}"})

    try:
        parsed = json.loads(result)
        return json.dumps({"result": parsed})
    except json.JSONDecodeError:
        return json.dumps({"result": result})


def _http_get(arguments: dict[str, Any]) -> str:
    """Fetch content from a URL."""
    url = arguments.get("url", "")
    max_length = arguments.get("max_length", 10000)

    if not url:
        return json.dumps({"error": "url parameter is required"})

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PlicoOrchestrator/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            if len(content) > max_length:
                content = content[:max_length] + "\n... (truncated)"
            return content
    except Exception as e:
        logger.error(f"HTTP GET failed for {url}: {e}")
        return json.dumps({"error": f"HTTP GET failed: {e}"})


_BUILTIN_STANDALONE: dict[str, Callable[..., str]] = {
    "calculate": _calculate,
    "json_extract": _json_extract,
    "http_get": _http_get,
}

BUILTIN_TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "rag_search": {
        "description": "Search indexed documents using semantic similarity.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return.",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    "read_document": {
        "description": "Read the full content of a specific document by name.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The document name to read.",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum characters to return.",
                    "default": 10000,
                },
            },
            "required": ["name"],
        },
    },
    "list_documents": {
        "description": "List all available document names.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    "calculate": {
        "description": "Evaluate a mathematical expression safely.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": 'Math expression to evaluate (e.g., "2 + 3 * 4").',
                },
            },
            "required": ["expression"],
        },
    },
    "json_extract": {
        "description": "Extract a field from a JSON string using dot notation.",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "JSON string to parse.",
                },
                "path": {
                    "type": "string",
                    "description": 'Dot-separated path (e.g., "items.0.name").',
                },
            },
            "required": ["data", "path"],
        },
    },
    "http_get": {
        "description": "Fetch text content from a URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch.",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum characters to return.",
                    "default": 10000,
                },
            },
            "required": ["url"],
        },
    },
}


def get_builtin_tool(name: str) -> Callable[..., str]:
    """Get a built-in tool executor by name.

    For context-dependent tools (rag_search, read_document, list_documents),
    returns the standalone version that reports the dependency as unavailable.
    Use ``create_context_tools()`` to get properly bound versions.

    Args:
        name: Built-in tool name.

    Returns:
        The executor callable.

    Raises:
        KeyError: If the tool name is not recognized.

    """
    if name in _BUILTIN_STANDALONE:
        return _BUILTIN_STANDALONE[name]

    if name == "rag_search":
        return _make_rag_search(None)
    if name == "read_document":
        return _make_read_document(None)
    if name == "list_documents":
        return _make_list_documents(None)

    raise KeyError(f"Unknown built-in tool: '{name}'")


def create_context_tools(
    rag_client: FFRAGClient | None = None,
    document_registry: DocumentRegistry | None = None,
) -> dict[str, Callable[..., str]]:
    """Create built-in tools bound to the orchestrator's context.

    This is called during orchestrator initialization to create tool
    executors that have access to the RAG client and document registry.

    Args:
        rag_client: Optional RAG client for semantic search.
        document_registry: Optional document registry for document access.

    Returns:
        Dictionary mapping tool names to executor callables.

    """
    tools: dict[str, Callable[..., str]] = {}

    tools.update(_BUILTIN_STANDALONE)

    tools["rag_search"] = _make_rag_search(rag_client)
    tools["read_document"] = _make_read_document(document_registry)
    tools["list_documents"] = _make_list_documents(document_registry)

    return tools
