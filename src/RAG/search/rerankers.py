# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Re-ranking strategies for search result improvement."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RerankerBase:
    """Base class for re-rankers."""

    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        n_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Re-rank search results.

        Args:
            query: Original search query.
            results: Search results to re-rank.
            n_results: Number of results to return (None = all).

        Returns:
            Re-ranked results.

        """
        raise NotImplementedError


class CrossEncoderReranker(RerankerBase):
    """Re-ranker using cross-encoder models.

    Uses sentence-transformers cross-encoder models for re-ranking.
    Requires: pip install sentence-transformers

    Args:
        model_name: Cross-encoder model name.
        max_length: Maximum sequence length.

    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self.max_length = max_length
        self._model = None

    def _load_model(self) -> Any:
        """Lazily load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name, max_length=self.max_length)
                logger.info(f"Loaded cross-encoder model: {self.model_name}")
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                ) from e
        return self._model

    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        n_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Re-rank results using cross-encoder scoring.

        Args:
            query: Original search query.
            results: Search results to re-rank.
            n_results: Number of results to return.

        Returns:
            Re-ranked results with updated scores.

        """
        if not results:
            return []

        logger.info(f"Cross-encoder reranking {len(results)} results for query: {query[:50]}...")
        model = self._load_model()

        pairs = [(query, r.get("content", "")) for r in results]

        try:
            scores = model.predict(pairs)
        except Exception as e:
            logger.warning(f"Cross-encoder prediction failed: {e}")
            return results[:n_results] if n_results else results

        reranked = []
        for i, result in enumerate(results):
            reranked_result = result.copy()
            reranked_result["rerank_score"] = float(scores[i])
            reranked_result["original_score"] = result.get("score")
            reranked_result["score"] = float(scores[i])
            reranked.append(reranked_result)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

        if n_results:
            reranked = reranked[:n_results]

        logger.debug(f"Re-ranked {len(results)} results, returning {len(reranked)}")
        return reranked


class DiversityReranker(RerankerBase):
    """Re-ranker that promotes result diversity.

    Re-orders results to maximize diversity based on content similarity.
    Uses MMR (Maximal Marginal Relevance) style selection.

    Args:
        lambda_param: Balance between relevance and diversity (0-1).
                     Higher = more relevance, lower = more diversity.

    """

    def __init__(
        self,
        lambda_param: float = 0.7,
    ) -> None:
        self.lambda_param = lambda_param

    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        n_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Re-rank results for diversity.

        Args:
            query: Original search query (not used, kept for interface).
            results: Search results to re-rank.
            n_results: Number of results to return.

        Returns:
            Diversified results.

        """
        if not results or len(results) <= 1:
            return results[:n_results] if n_results else results

        n = n_results or len(results)
        selected: list[dict[str, Any]] = []
        remaining = list(results)

        if remaining:
            selected.append(remaining.pop(0))

        while remaining and len(selected) < n:
            best_idx = 0
            best_score = -float("inf")

            for i, candidate in enumerate(remaining):
                relevance = candidate.get("score", 0)

                max_sim = 0
                for s in selected:
                    sim = self._simple_similarity(
                        candidate.get("content", ""),
                        s.get("content", ""),
                    )
                    max_sim = max(max_sim, sim)

                mmr_score = self.lambda_param * relevance - (1 - self.lambda_param) * max_sim

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            if remaining:
                selected.append(remaining.pop(best_idx))

        for i, r in enumerate(selected):
            r["diversity_rank"] = i + 1

        logger.debug(f"Diversity re-ranked to {len(selected)} results")
        return selected

    def _simple_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple word overlap similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0


class NoopReranker(RerankerBase):
    """Pass-through re-ranker that does nothing.

    Used when re-ranking is disabled but a reranker interface is expected.

    """

    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        n_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return results unchanged.

        Args:
            query: Original search query (ignored).
            results: Search results.
            n_results: Number of results to return.

        Returns:
            Original results, optionally truncated.

        """
        if n_results:
            return results[:n_results]
        return results


def get_reranker(
    reranker_type: str = "none",
    **kwargs: Any,
) -> RerankerBase:
    """Get a reranker by type name.

    Args:
        reranker_type: Type of reranker ("cross_encoder", "diversity", "none").
        **kwargs: Additional arguments for the reranker.

    Returns:
        Configured reranker instance.

    """
    if reranker_type == "cross_encoder":
        return CrossEncoderReranker(**kwargs)
    elif reranker_type == "diversity":
        return DiversityReranker(**kwargs)
    else:
        return NoopReranker()
