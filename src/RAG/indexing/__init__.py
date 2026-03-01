# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Indexing package for RAG multi-strategy support."""

from .bm25_index import BM25Index
from .contextual_embeddings import ContextualEmbeddings, LateChunkingEmbeddings
from .deduplication import ChunkDeduplicator
from .hierarchical_index import HierarchicalIndex

__all__ = [
    "BM25Index",
    "HierarchicalIndex",
    "ContextualEmbeddings",
    "LateChunkingEmbeddings",
    "ChunkDeduplicator",
]
