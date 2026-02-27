# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Hybrid search combining vector and BM25 retrieval."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class HybridSearch:
    """Hybrid search combining vector similarity and BM25 keyword matching.

    Uses reciprocal rank fusion (RRF) to combine results from multiple
    retrieval methods.

    Args:
        vector_search_fn: Function that takes (query, n_results) and returns vector results.
        bm25_search_fn: Function that takes (query, n_results) and returns BM25 results.
        alpha: Weight for vector search (1-alpha for BM25). Default 0.6.
        rrf_k: RRF constant for rank fusion. Default 60.

    """

    def __init__(
        self,
        vector_search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
        bm25_search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
        alpha: float = 0.6,
        rrf_k: int = 60,
    ) -> None:
        self.vector_search_fn = vector_search_fn
        self.bm25_search_fn = bm25_search_fn
        self.alpha = alpha
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        n_results: int = 5,
        mode: str = "hybrid",
    ) -> list[dict[str, Any]]:
        """Perform search using the specified mode.

        Args:
            query: Search query.
            n_results: Maximum number of results.
            mode: Search mode - "vector", "bm25", or "hybrid".

        Returns:
            List of search results with merged scores.

        """
        if mode == "vector":
            return self._vector_search(query, n_results)
        elif mode == "bm25":
            return self._bm25_search(query, n_results)
        elif mode == "hybrid":
            return self._hybrid_search(query, n_results)
        else:
            raise ValueError(f"Unknown search mode: {mode}. Use 'vector', 'bm25', or 'hybrid'")

    def _vector_search(
        self,
        query: str,
        n_results: int,
    ) -> list[dict[str, Any]]:
        """Perform vector-only search."""
        if not self.vector_search_fn:
            logger.warning("Vector search function not configured")
            return []

        results = self.vector_search_fn(query, n_results)
        for r in results:
            r["search_type"] = "vector"
        return results

    def _bm25_search(
        self,
        query: str,
        n_results: int,
    ) -> list[dict[str, Any]]:
        """Perform BM25-only search."""
        if not self.bm25_search_fn:
            logger.warning("BM25 search function not configured")
            return []

        results = self.bm25_search_fn(query, n_results)
        for r in results:
            r["search_type"] = "bm25"
        return results

    def _hybrid_search(
        self,
        query: str,
        n_results: int,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search with RRF fusion."""
        fetch_count = min(n_results * 3, 50)

        vector_results = self._vector_search(query, fetch_count)
        bm25_results = self._bm25_search(query, fetch_count)

        fused = self._reciprocal_rank_fusion(vector_results, bm25_results)

        return fused[:n_results]

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Combine results using reciprocal rank fusion.

        RRF score = 1 / (k + rank)

        With alpha weighting:
        - Vector contribution: alpha / (k + vector_rank)
        - BM25 contribution: (1-alpha) / (k + bm25_rank)

        Args:
            vector_results: Results from vector search.
            bm25_results: Results from BM25 search.

        Returns:
            Fused and sorted results.

        """
        scores: dict[str, dict[str, Any]] = {}

        for rank, result in enumerate(vector_results, start=1):
            doc_id = result.get("id")
            if not doc_id:
                continue

            rrf_score = self.alpha / (self.rrf_k + rank)

            if doc_id not in scores:
                scores[doc_id] = {
                    "id": doc_id,
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "vector_score": result.get("score", result.get("distance", 0)),
                    "bm25_score": 0,
                    "vector_rank": rank,
                    "bm25_rank": None,
                    "rrf_score": 0,
                    "search_type": "hybrid",
                }
            else:
                scores[doc_id]["vector_score"] = result.get("score", result.get("distance", 0))
                scores[doc_id]["vector_rank"] = rank

            scores[doc_id]["rrf_score"] += rrf_score

        for rank, result in enumerate(bm25_results, start=1):
            doc_id = result.get("id")
            if not doc_id:
                continue

            rrf_score = (1 - self.alpha) / (self.rrf_k + rank)

            if doc_id not in scores:
                scores[doc_id] = {
                    "id": doc_id,
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "vector_score": 0,
                    "bm25_score": result.get("score", 0),
                    "vector_rank": None,
                    "bm25_rank": rank,
                    "rrf_score": 0,
                    "search_type": "hybrid",
                }
            else:
                scores[doc_id]["bm25_score"] = result.get("score", 0)
                scores[doc_id]["bm25_rank"] = rank

            scores[doc_id]["rrf_score"] += rrf_score

        fused_results = list(scores.values())
        fused_results.sort(key=lambda x: x["rrf_score"], reverse=True)

        logger.debug(
            f"RRF fusion: {len(vector_results)} vector + {len(bm25_results)} BM25 "
            f"= {len(fused_results)} unique results"
        )
        return fused_results

    def set_alpha(self, alpha: float) -> None:
        """Set the alpha parameter (vector weight).

        Args:
            alpha: Weight for vector search (0.0 to 1.0).

        """
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be between 0 and 1")
        self.alpha = alpha
        logger.debug(f"HybridSearch alpha set to {alpha}")

    def set_search_functions(
        self,
        vector_search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
        bm25_search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
    ) -> None:
        """Set or update search functions.

        Args:
            vector_search_fn: Vector search function.
            bm25_search_fn: BM25 search function.

        """
        if vector_search_fn:
            self.vector_search_fn = vector_search_fn
        if bm25_search_fn:
            self.bm25_search_fn = bm25_search_fn


def reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    k: int = 60,
    weights: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Combine multiple result lists using reciprocal rank fusion.

    Args:
        result_lists: List of result lists to fuse.
        k: RRF constant.
        weights: Optional weights for each result list.

    Returns:
        Fused and sorted results.

    """
    if weights is None:
        weights = [1.0 / len(result_lists)] * len(result_lists)

    if len(weights) != len(result_lists):
        raise ValueError("Number of weights must match number of result lists")

    scores: dict[str, dict[str, Any]] = {}

    for result_list, weight in zip(result_lists, weights):
        for rank, result in enumerate(result_list, start=1):
            doc_id = result.get("id")
            if not doc_id:
                continue

            rrf_score = weight / (k + rank)

            if doc_id not in scores:
                scores[doc_id] = {
                    "id": doc_id,
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "rrf_score": 0,
                }

            scores[doc_id]["rrf_score"] += rrf_score

    fused = list(scores.values())
    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused
