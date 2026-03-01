# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Embedding generation using LiteLLM for provider flexibility or local models."""

from __future__ import annotations

import logging
import math
import os
from collections import OrderedDict
from typing import Any

from litellm import embedding

logger = logging.getLogger(__name__)


class FFEmbeddings:
    """Generate embeddings using LiteLLM or local sentence-transformers.

    Supports embedding models from:
    - LiteLLM providers (mistral, openai, azure, anthropic, etc.)
    - Local sentence-transformers models (via "local/" prefix)

    Features:
    - Embedding caching for repeated queries (LRU cache)
    - Local model support for zero API cost
    - Automatic provider detection from model string

    Args:
        model: Model string (e.g., "mistral/mistral-embed" or "local/all-MiniLM-L6-v2").
        api_key: API key (defaults to environment variable based on provider).
        api_base: Optional API base URL override.
        cache_enabled: Enable embedding caching (default: True).
        cache_size: Maximum cache entries (default: 256).
        device: Device for local models ("cpu", "cuda", default: "cpu").
        **kwargs: Additional parameters passed to embedding backend.

    Example:
        >>> embeddings = FFEmbeddings(model="mistral/mistral-embed")
        >>> vectors = embeddings.embed(["Hello world", "Another text"])
        >>> len(vectors)
        2
        >>> len(vectors[0])  # embedding dimension
        1024

        >>> # Local model
        >>> local = FFEmbeddings(model="local/all-MiniLM-L6-v2")
        >>> vectors = local.embed(["Hello world"])

    """

    def __init__(
        self,
        model: str = "mistral/mistral-embed",
        api_key: str | None = None,
        api_base: str | None = None,
        cache_enabled: bool = True,
        cache_size: int = 256,
        device: str = "cpu",
        **kwargs: Any,
    ) -> None:
        self.model = model
        self._extra_kwargs = kwargs
        self._device = device

        self._is_local = model.startswith("local/")
        self._local_model: Any = None
        self.api_key: str | None = None
        self.api_base: str | None = None

        if self._is_local:
            self._init_local_model(model)
        else:
            self.api_key = api_key or self._get_default_api_key()
            self.api_base = api_base

        self._cache_enabled = cache_enabled
        self._cache_size = cache_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()

        logger.info(
            f"FFEmbeddings initialized: model={model}, "
            f"local={self._is_local}, cache={cache_enabled}"
        )

    def _init_local_model(self, model: str) -> None:
        """Initialize local sentence-transformers model."""
        model_name = model.replace("local/", "")
        try:
            from sentence_transformers import SentenceTransformer

            self._local_model = SentenceTransformer(model_name, device=self._device)
            logger.info(f"Loaded local embedding model: {model_name} on {self._device}")
        except ImportError as e:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            ) from e

    def _get_default_api_key(self) -> str | None:
        """Get default API key based on provider prefix."""
        provider = self.model.split("/")[0] if "/" in self.model else "openai"

        env_mappings = {
            "mistral": "MISTRAL_API_KEY",
            "openai": "OPENAI_API_KEY",
            "azure": "AZURE_OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }

        env_var = env_mappings.get(provider, f"{provider.upper()}_API_KEY")
        return os.getenv(env_var)

    def embed(self, texts: str | list[str]) -> list[list[float]]:
        """Generate embeddings for text(s).

        Args:
            texts: Single text string or list of texts to embed.

        Returns:
            List of embedding vectors (list of floats).

        Raises:
            ValueError: If no API key is configured (for API models).
            RuntimeError: If embedding generation fails.

        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return []

        if self._is_local:
            return self._embed_local(texts)
        else:
            return self._embed_api(texts)

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local sentence-transformers model."""
        if self._local_model is None:
            raise RuntimeError("Local model not initialized")

        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            if self._cache_enabled and text in self._cache:
                self._cache.move_to_end(text)
                results.append((i, self._cache[text]))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            logger.debug(f"Generating local embeddings for {len(uncached_texts)} texts")
            embeddings = self._local_model.encode(uncached_texts, convert_to_numpy=True)

            for j, (idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
                emb = embeddings[j].tolist()
                results.append((idx, emb))

                if self._cache_enabled:
                    self._cache[text] = emb
                    self._cache.move_to_end(text)
                    if len(self._cache) > self._cache_size:
                        self._cache.popitem(last=False)

        results.sort(key=lambda x: x[0])
        return [emb for _, emb in results]

    def _embed_api(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using LiteLLM API."""
        if not self.api_key:
            raise ValueError(f"No API key configured for model {self.model}")

        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            if self._cache_enabled and text in self._cache:
                self._cache.move_to_end(text)
                results.append((i, self._cache[text]))
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            logger.debug(f"Generating API embeddings for {len(uncached_texts)} texts")

            try:
                params: dict[str, Any] = {
                    "model": self.model,
                    "input": uncached_texts,
                }

                if self.api_key:
                    params["api_key"] = self.api_key
                if self.api_base:
                    params["api_base"] = self.api_base

                params.update(self._extra_kwargs)

                response = embedding(**params)

                sorted_data = sorted(response.data, key=lambda x: x["index"])
                api_embeddings = [item["embedding"] for item in sorted_data]

                for j, (idx, text) in enumerate(zip(uncached_indices, uncached_texts)):
                    emb = api_embeddings[j]
                    results.append((idx, emb))

                    if self._cache_enabled:
                        self._cache[text] = emb
                        self._cache.move_to_end(text)
                        if len(self._cache) > self._cache_size:
                            self._cache.popitem(last=False)

            except Exception as e:
                logger.error(f"Failed to generate embeddings: {e}")
                raise RuntimeError(f"Embedding generation failed: {e}") from e

        results.sort(key=lambda x: x[0])
        return [emb for _, emb in results]

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector (list of floats).

        """
        return self.embed(text)[0]

    def get_dimension(self) -> int:
        """Get the dimension of embeddings for this model.

        Returns:
            Number of dimensions in the embedding vector.

        """
        sample_embedding = self.embed_single("test")
        return len(sample_embedding)

    def clear_cache(self) -> int:
        """Clear the embedding cache.

        Returns:
            Number of entries cleared.

        """
        count = len(self._cache)
        self._cache.clear()
        logger.debug(f"Cleared embedding cache ({count} entries)")
        return count

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache_enabled, cache_size, entries.

        """
        return {
            "cache_enabled": self._cache_enabled,
            "max_size": self._cache_size,
            "current_entries": len(self._cache),
        }

    @property
    def provider(self) -> str:
        """Get the provider name from the model string."""
        if self._is_local:
            return "local"
        return self.model.split("/")[0] if "/" in self.model else "unknown"

    @property
    def is_local(self) -> bool:
        """Check if using local embeddings."""
        return self._is_local

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First vector.
            b: Second vector.

        Returns:
            Cosine similarity score (-1 to 1).

        """
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
