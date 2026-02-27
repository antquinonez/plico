# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.

"""Embedding generation using LiteLLM for provider flexibility."""

from __future__ import annotations

import logging
import os
from typing import Any

from litellm import embedding

logger = logging.getLogger(__name__)


class FFEmbeddings:
    """Generate embeddings using LiteLLM for multi-provider support.

    Supports embedding models from:
    - Mistral (mistral/mistral-embed)
    - OpenAI (openai/text-embedding-3-small, openai/text-embedding-3-large)
    - Azure (azure/embedding-model-name)
    - And other LiteLLM-supported providers

    Args:
        model: LiteLLM model string (e.g., "mistral/mistral-embed").
        api_key: API key (defaults to environment variable based on provider).
        api_base: Optional API base URL override.
        **kwargs: Additional parameters passed to litellm.embedding().

    Example:
        >>> embeddings = FFEmbeddings(model="mistral/mistral-embed")
        >>> vectors = embeddings.embed(["Hello world", "Another text"])
        >>> len(vectors)
        2
        >>> len(vectors[0])  # embedding dimension
        1024

    """

    def __init__(
        self,
        model: str = "mistral/mistral-embed",
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self._extra_kwargs = kwargs

        self.api_key = api_key or self._get_default_api_key()
        self.api_base = api_base

        logger.info(f"FFEmbeddings initialized with model={model}")

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
            ValueError: If no API key is configured.
            RuntimeError: If embedding generation fails.

        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return []

        if not self.api_key:
            raise ValueError(f"No API key configured for model {self.model}")

        logger.debug(f"Generating embeddings for {len(texts)} texts")

        try:
            params: dict[str, Any] = {
                "model": self.model,
                "input": texts,
            }

            if self.api_key:
                params["api_key"] = self.api_key
            if self.api_base:
                params["api_base"] = self.api_base

            params.update(self._extra_kwargs)

            response = embedding(**params)

            sorted_data = sorted(response.data, key=lambda x: x["index"])
            embeddings = [item["embedding"] for item in sorted_data]

            logger.debug(
                f"Generated {len(embeddings)} embeddings of dimension {len(embeddings[0])}"
            )
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}") from e

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

    @property
    def provider(self) -> str:
        """Get the provider name from the model string."""
        return self.model.split("/")[0] if "/" in self.model else "unknown"
