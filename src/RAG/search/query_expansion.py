# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Query expansion for improved retrieval recall via multi-query retrieval."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

QUERY_EXPANSION_PROMPT = """Generate {n} different search queries that could help find information about:

Original query: {query}

The queries should:
- Use different wording and synonyms
- Cover different aspects of the topic
- Be concise (1-2 sentences each)
- Be relevant to finding the same information

Return only the queries, one per line, numbered (1., 2., etc.). Do not include any explanation."""


class QueryExpander:
    """Expand queries using LLM for multi-query retrieval.

    Generates multiple reformulations of a search query to improve
    recall by catching different phrasings and aspects of the topic.

    Args:
        llm_generate_fn: Function that takes a prompt string and returns LLM response.
        n_variations: Number of query variations to generate (default: 3).
        include_original: Whether to include original query in results (default: True).

    Example:
        >>> def mock_llm(prompt): return "1. What is auth?\\n2. How to authenticate?"
        >>> expander = QueryExpander(llm_generate_fn=mock_llm, n_variations=2)
        >>> queries = expander.expand("authentication methods")
        >>> # Returns: ["authentication methods", "What is auth?", "How to authenticate?"]

    """

    def __init__(
        self,
        llm_generate_fn: Callable[[str], str] | None = None,
        n_variations: int = 3,
        include_original: bool = True,
    ) -> None:
        self.llm_generate_fn = llm_generate_fn
        self.n_variations = n_variations
        self.include_original = include_original

    def expand(self, query: str) -> list[str]:
        """Generate query variations for improved retrieval.

        Args:
            query: Original search query.

        Returns:
            List of query variations including original (if include_original=True).

        """
        if not self.llm_generate_fn:
            logger.debug("No LLM function configured, returning original query only")
            return [query]

        try:
            prompt = QUERY_EXPANSION_PROMPT.format(
                n=self.n_variations,
                query=query,
            )
            response = self.llm_generate_fn(prompt)
            variations = self._parse_response(response)

            if not variations:
                logger.warning("Query expansion returned no variations, using original only")
                return [query]

        except Exception as e:
            logger.warning(f"Query expansion failed: {e}, using original only")
            return [query]

        all_queries = [query] + variations if self.include_original else variations

        unique_queries = list(dict.fromkeys(all_queries))

        logger.debug(f"Query expansion: '{query[:50]}...' -> {len(unique_queries)} queries")
        return unique_queries

    def _parse_response(self, response: str) -> list[str]:
        """Parse numbered list from LLM response.

        Args:
            response: Raw LLM response text.

        Returns:
            List of cleaned query strings.

        """
        lines = response.strip().split("\n")
        queries = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()

            if cleaned and len(cleaned) > 3:
                if (cleaned.startswith('"') and cleaned.endswith('"')) or (
                    cleaned.startswith("'") and cleaned.endswith("'")
                ):
                    cleaned = cleaned[1:-1]

                queries.append(cleaned)

        return queries

    def set_llm_function(self, fn: Callable[[str], str]) -> None:
        """Set or update the LLM generate function.

        Args:
            fn: Function that takes a prompt and returns LLM response.

        """
        self.llm_generate_fn = fn


def fuse_search_results(
    result_lists: list[list[dict[str, Any]]],
    n_results: int = 5,
    dedupe_by: str = "id",
) -> list[dict[str, Any]]:
    """Fuse results from multiple searches with deduplication.

    Combines results from multiple query variations, removing duplicates
    while preserving relevance ordering.

    Args:
        result_lists: List of search result lists from different queries.
        n_results: Maximum number of final results to return.
        dedupe_by: Field to use for deduplication (default: "id").

    Returns:
        Fused and deduplicated list of results.

    """
    if not result_lists:
        return []

    seen: set[str] = set()
    fused: list[dict[str, Any]] = []

    for results in result_lists:
        for result in results:
            dedupe_key = str(result.get(dedupe_by, ""))
            if dedupe_key and dedupe_key not in seen:
                seen.add(dedupe_key)
                fused.append(result)

    return fused[:n_results]
