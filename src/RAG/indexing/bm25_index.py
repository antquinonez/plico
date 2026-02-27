# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""BM25 sparse index for hybrid search."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)


class BM25Index:
    """BM25 sparse index for keyword-based retrieval.

    Implements the Okapi BM25 algorithm for text relevance scoring.
    Used alongside vector search for hybrid retrieval.

    Args:
        k1: BM25 k1 parameter (term frequency saturation).
        b: BM25 b parameter (document length normalization).
        epsilon: Small value to avoid division by zero.

    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        epsilon: float = 0.25,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.epsilon = epsilon

        self._documents: dict[str, dict[str, Any]] = {}
        self._doc_lengths: dict[str, int] = {}
        self._term_doc_freqs: dict[str, int] = Counter()
        self._avg_doc_length: float = 0.0
        self._total_docs: int = 0
        self._doc_term_freqs: dict[str, Counter] = {}

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text into terms.

        Args:
            text: Text to tokenize.

        Returns:
            List of lowercase tokens.

        """
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        tokens = text.split()
        return [t for t in tokens if len(t) > 1]

    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a document to the index.

        Args:
            doc_id: Unique document identifier.
            content: Document text content.
            metadata: Optional metadata dictionary.

        """
        tokens = self.tokenize(content)
        term_freqs = Counter(tokens)
        doc_length = len(tokens)

        self._documents[doc_id] = {
            "content": content,
            "metadata": metadata or {},
        }
        self._doc_lengths[doc_id] = doc_length
        self._doc_term_freqs[doc_id] = term_freqs

        for term in set(tokens):
            self._term_doc_freqs[term] += 1

        self._total_docs += 1
        total_length = sum(self._doc_lengths.values())
        self._avg_doc_length = total_length / self._total_docs if self._total_docs > 0 else 0

        logger.debug(f"Added document {doc_id} to BM25 index (length={doc_length})")

    def add_documents(
        self,
        documents: list[dict[str, Any]],
        id_key: str = "id",
        content_key: str = "content",
    ) -> int:
        """Add multiple documents to the index.

        Args:
            documents: List of document dictionaries.
            id_key: Key for document ID in each dict.
            content_key: Key for document content in each dict.

        Returns:
            Number of documents added.

        """
        count = 0
        for doc in documents:
            doc_id = doc.get(id_key)
            content = doc.get(content_key, "")
            metadata = {k: v for k, v in doc.items() if k not in [id_key, content_key]}

            if doc_id and content:
                self.add_document(doc_id, content, metadata)
                count += 1

        logger.info(f"Added {count} documents to BM25 index")
        return count

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the index.

        Args:
            doc_id: Document ID to delete.

        Returns:
            True if document was deleted, False if not found.

        """
        if doc_id not in self._documents:
            return False

        term_freqs = self._doc_term_freqs.get(doc_id, Counter())
        for term in set(term_freqs.keys()):
            if term in self._term_doc_freqs:
                self._term_doc_freqs[term] -= 1
                if self._term_doc_freqs[term] <= 0:
                    del self._term_doc_freqs[term]

        del self._documents[doc_id]
        del self._doc_lengths[doc_id]
        del self._doc_term_freqs[doc_id]
        self._total_docs -= 1

        if self._total_docs > 0:
            total_length = sum(self._doc_lengths.values())
            self._avg_doc_length = total_length / self._total_docs
        else:
            self._avg_doc_length = 0.0

        logger.debug(f"Deleted document {doc_id} from BM25 index")
        return True

    def search(
        self,
        query: str,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for documents using BM25 scoring.

        Args:
            query: Search query.
            n_results: Maximum number of results.

        Returns:
            List of result dicts with doc_id, score, content, metadata.

        """
        if not self._documents:
            return []

        query_terms = self.tokenize(query)
        scores: dict[str, float] = {}

        for term in query_terms:
            if term not in self._term_doc_freqs:
                continue

            idf = self._compute_idf(term)

            for doc_id, term_freqs in self._doc_term_freqs.items():
                if term not in term_freqs:
                    continue

                tf = term_freqs[term]
                doc_length = self._doc_lengths.get(doc_id, 0)

                tf_component = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * (doc_length / self._avg_doc_length))
                )

                if doc_id not in scores:
                    scores[doc_id] = 0.0
                scores[doc_id] += idf * tf_component

        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results: list[dict[str, Any]] = []

        for doc_id, score in sorted_results[:n_results]:
            doc_data = self._documents.get(doc_id, {})
            results.append(
                {
                    "id": doc_id,
                    "score": score,
                    "content": doc_data.get("content", ""),
                    "metadata": doc_data.get("metadata", {}),
                }
            )

        logger.debug(f"BM25 search returned {len(results)} results for query: {query[:50]}...")
        return results

    def _compute_idf(self, term: str) -> float:
        """Compute inverse document frequency for a term."""
        doc_freq = self._term_doc_freqs.get(term, 0)
        if doc_freq == 0:
            return 0.0

        return math.log((self._total_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)

    def clear(self) -> None:
        """Clear all documents from the index."""
        self._documents.clear()
        self._doc_lengths.clear()
        self._term_doc_freqs.clear()
        self._doc_term_freqs.clear()
        self._avg_doc_length = 0.0
        self._total_docs = 0
        logger.info("BM25 index cleared")

    def count(self) -> int:
        """Get the number of documents in the index."""
        return self._total_docs

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        return {
            "total_docs": self._total_docs,
            "avg_doc_length": self._avg_doc_length,
            "unique_terms": len(self._term_doc_freqs),
            "k1": self.k1,
            "b": self.b,
        }
