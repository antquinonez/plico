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
    - split_text: Text chunking utility (deprecated, use text_splitters)
    - RAGMCPTools: MCP tool definitions for AI assistants

Chunking Strategies:
    - CharacterChunker: Basic character-based chunking
    - RecursiveChunker: Hierarchical splitting by paragraphs/sentences
    - MarkdownChunker: Header-aware markdown chunking
    - CodeChunker: AST-style code chunking
    - HierarchicalChunker: Parent-child chunk relationships

Search Strategies:
    - HybridSearch: Combined vector + BM25 search
    - CrossEncoderReranker: Re-ranking with cross-encoders

Example:
    >>> from src.RAG import FFRAGClient
    >>> rag = FFRAGClient(chunking_strategy="markdown", search_mode="hybrid")
    >>> rag.add_document("Long text content...", metadata={"source": "doc.md"})
    >>> results = rag.search("What is this about?")
    >>> print(results[0]["content"])

"""

from __future__ import annotations

from .FFEmbeddings import FFEmbeddings
from .indexing import BM25Index, ContextualEmbeddings, HierarchicalIndex
from .mcp_tools import RAGMCPTools
from .search import (
    CrossEncoderReranker,
    DiversityReranker,
    HybridSearch,
    NoopReranker,
    RerankerBase,
    get_reranker,
    reciprocal_rank_fusion,
)
from .text_splitter import TextChunk, split_documents, split_text
from .text_splitters import (
    CharacterChunker,
    ChunkerBase,
    CodeChunker,
    HierarchicalChunker,
    HierarchicalTextChunk,
    MarkdownChunker,
    RecursiveChunker,
    chunk_text,
    get_chunker,
    list_chunkers,
)

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
    "ChunkerBase",
    "CharacterChunker",
    "RecursiveChunker",
    "MarkdownChunker",
    "CodeChunker",
    "HierarchicalChunker",
    "HierarchicalTextChunk",
    "get_chunker",
    "list_chunkers",
    "chunk_text",
    "BM25Index",
    "HierarchicalIndex",
    "ContextualEmbeddings",
    "HybridSearch",
    "reciprocal_rank_fusion",
    "RerankerBase",
    "CrossEncoderReranker",
    "DiversityReranker",
    "NoopReranker",
    "get_reranker",
]
