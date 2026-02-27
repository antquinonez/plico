# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from .FFAzureClientBase import FFAzureClientBase


class FFAzureMistral(FFAzureClientBase):
    """Azure AI Inference client for Mistral Large models."""

    @property
    def _default_model(self) -> str:
        return "mistral-large-2411"

    @property
    def _default_max_tokens(self) -> int:
        return 40000

    @property
    def _default_temperature(self) -> float:
        return 0.7

    @property
    def _default_instructions(self) -> str:
        return (
            "You are a helpful assistant. Respond accurately to user queries. Be concise and clear."
        )

    @property
    def _env_key_prefix(self) -> str:
        return "AZURE_MISTRAL"

    @property
    def _provider_name(self) -> str:
        return "MistralAI"
