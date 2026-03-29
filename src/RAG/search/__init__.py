# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Search package for RAG retrieval strategies."""

from .hybrid_search import HybridSearch, reciprocal_rank_fusion
from .query_expansion import QueryExpander, fuse_search_results
from .rerankers import (
    CrossEncoderReranker,
    DiversityReranker,
    NoopReranker,
    RerankerBase,
    get_reranker,
)

__all__ = [
    "CrossEncoderReranker",
    "DiversityReranker",
    "HybridSearch",
    "NoopReranker",
    "QueryExpander",
    "RerankerBase",
    "fuse_search_results",
    "get_reranker",
    "reciprocal_rank_fusion",
]
