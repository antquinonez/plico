# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from .FFAzureClientBase import FFAzureClientBase


class FFAzurePhi(FFAzureClientBase):
    """Azure AI Inference client for Microsoft Phi models."""

    @property
    def _default_model(self) -> str:
        return "Phi-4"

    @property
    def _default_max_tokens(self) -> int:
        return 12000

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
        return "AZURE_PHI"

    @property
    def _provider_name(self) -> str:
        return "Microsoft"
