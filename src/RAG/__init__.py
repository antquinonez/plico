# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""RAG (Retrieval-Augmented Generation) module for FFClients.

This module provides document chunking, embedding generation, vector storage,
and retrieval capabilities for RAG workflows.

Main Components:
    - FFRAGClient: High-level client for RAG operations
    - FFEmbeddings: LiteLLM-based embedding generation
    - FFVectorStore: ChromaDB-backed vector storage
    - TextChunk: Data class for text chunks
    - split_text: Text chunking utility
    - RAGMCPTools: MCP tool definitions for AI assistants

Example:
    >>> from src.RAG import FFRAGClient
    >>> rag = FFRAGClient()
    >>> rag.add_document("Long text content...", metadata={"source": "doc.md"})
    >>> results = rag.search("What is this about?")
    >>> print(results[0]["content"])

"""

from __future__ import annotations

from .FFEmbeddings import FFEmbeddings
from .mcp_tools import RAGMCPTools
from .text_splitter import TextChunk, split_documents, split_text

try:
    from .FFRAGClient import FFRAGClient
    from .FFVectorStore import CHROMADB_AVAILABLE, FFVectorStore
except Exception:
    FFRAGClient = None
    FFVectorStore = None
    CHROMADB_AVAILABLE = False

__all__ = [
    "FFRAGClient",
    "FFEmbeddings",
    "FFVectorStore",
    "RAGMCPTools",
    "TextChunk",
    "split_text",
    "split_documents",
    "CHROMADB_AVAILABLE",
]
