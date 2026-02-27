# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Text splitters package for various chunking strategies.

Available strategies:
- character: Basic character-based chunking with word-boundary awareness
- recursive: Hierarchical splitting by paragraphs, sentences, words
- markdown: Header-aware markdown chunking
- code: AST-style code chunking
- hierarchical: Parent-child chunk relationships for context retrieval
"""

from .base import ChunkerBase, HierarchicalTextChunk, TextChunk
from .character import CharacterChunker
from .code import CodeChunker
from .factory import chunk_text, get_chunker, list_chunkers
from .hierarchical import HierarchicalChunker
from .markdown import MarkdownChunker
from .recursive import RecursiveChunker

__all__ = [
    "ChunkerBase",
    "TextChunk",
    "HierarchicalTextChunk",
    "CharacterChunker",
    "RecursiveChunker",
    "MarkdownChunker",
    "CodeChunker",
    "HierarchicalChunker",
    "get_chunker",
    "list_chunkers",
    "chunk_text",
]
