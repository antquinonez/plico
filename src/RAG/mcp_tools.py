# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""MCP tool definitions for RAG functionality.

These tools can be exposed to AI assistants via MCP (Model Context Protocol)
to enable them to search and interact with the knowledge base.
"""

from __future__ import annotations

import logging
from typing import Any

from .FFRAGClient import FFRAGClient

logger = logging.getLogger(__name__)


class RAGMCPTools:
    """MCP tools for RAG operations.

    Provides a set of tools that can be exposed to AI assistants
    for interacting with the RAG knowledge base.

    Args:
        rag_client: FFRAGClient instance or config to create one.

    Example:
        >>> tools = RAGMCPTools()
        >>> tools.rag_search("authentication methods")
        [{"content": "...", "score": 0.85, ...}]

    """

    def __init__(self, rag_client: FFRAGClient | None = None) -> None:
        self._rag = rag_client or FFRAGClient()

    def rag_search(
        self,
        query: str,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search the knowledge base for relevant information.

        Args:
            query: The search query describing what information to find.
            n_results: Maximum number of results to return (1-20).

        Returns:
            List of relevant document chunks with content, metadata, and scores.

        Example:
            >>> rag_search("How do I authenticate with the API?")
            [{"content": "Authentication requires API keys...", "score": 0.92, ...}]

        """
        n_results = max(1, min(20, n_results))
        return self._rag.search(query, n_results=n_results)

    def rag_add_document(
        self,
        content: str,
        reference_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add a document to the knowledge base.

        Args:
            content: The text content to add to the knowledge base.
            reference_name: Optional name to identify this document.
            metadata: Optional additional metadata.

        Returns:
            Dict with status and number of chunks added.

        Example:
            >>> rag_add_document("API documentation...", reference_name="api_docs")
            {"status": "success", "chunks_added": 5}

        """
        chunks_added = self._rag.add_document(
            content=content,
            reference_name=reference_name,
            metadata=metadata,
        )

        return {
            "status": "success",
            "chunks_added": chunks_added,
            "reference_name": reference_name,
        }

    def rag_list_documents(self) -> list[str]:
        """List all documents in the knowledge base.

        Returns:
            List of document reference names.

        Example:
            >>> rag_list_documents()
            ["api_reference", "product_spec", "troubleshooting"]

        """
        return self._rag.list_documents()

    def rag_get_stats(self) -> dict[str, Any]:
        """Get statistics about the knowledge base.

        Returns:
            Dict with collection name, chunk count, and config info.

        Example:
            >>> rag_get_stats()
            {"collection_name": "ffclients_kb", "count": 150, ...}

        """
        return self._rag.get_stats()

    def rag_delete_document(self, reference_name: str) -> dict[str, str]:
        """Delete a document from the knowledge base.

        Args:
            reference_name: The name of the document to delete.

        Returns:
            Dict with status confirmation.

        Example:
            >>> rag_delete_document("old_docs")
            {"status": "deleted", "reference_name": "old_docs"}

        """
        self._rag.delete_by_reference(reference_name)
        return {
            "status": "deleted",
            "reference_name": reference_name,
        }

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get MCP tool definitions for registration.

        Returns:
            List of tool definition dicts compatible with MCP protocol.

        """
        return [
            {
                "name": "rag_search",
                "description": "Search the knowledge base for relevant information. Use this when you need to find specific information from indexed documents.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query describing what information to find.",
                        },
                        "n_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (1-20).",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 20,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "rag_add_document",
                "description": "Add a new document to the knowledge base for future searches.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The text content to add to the knowledge base.",
                        },
                        "reference_name": {
                            "type": "string",
                            "description": "Optional name to identify this document.",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Optional additional metadata as key-value pairs.",
                        },
                    },
                    "required": ["content"],
                },
            },
            {
                "name": "rag_list_documents",
                "description": "List all documents currently in the knowledge base.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "rag_get_stats",
                "description": "Get statistics about the knowledge base including chunk count and configuration.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "rag_delete_document",
                "description": "Delete a document from the knowledge base by its reference name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "reference_name": {
                            "type": "string",
                            "description": "The name of the document to delete.",
                        },
                    },
                    "required": ["reference_name"],
                },
            },
        ]

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name with given arguments.

        Args:
            name: Tool name (e.g., "rag_search").
            arguments: Tool arguments.

        Returns:
            Tool execution result.

        Raises:
            ValueError: If tool name is unknown.

        """
        tool_methods = {
            "rag_search": self.rag_search,
            "rag_add_document": self.rag_add_document,
            "rag_list_documents": self.rag_list_documents,
            "rag_get_stats": self.rag_get_stats,
            "rag_delete_document": self.rag_delete_document,
        }

        if name not in tool_methods:
            raise ValueError(f"Unknown tool: {name}")

        method = tool_methods[name]
        return method(**arguments)
