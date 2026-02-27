# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from .FFAzureClientBase import FFAzureClientBase


class FFAzureDeepSeekV3(FFAzureClientBase):
    """Azure AI Inference client for DeepSeek V3 models."""

    @property
    def _default_model(self) -> str:
        return "DeepSeek-V3-0324"

    @property
    def _default_max_tokens(self) -> int:
        return 125000

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
        return "AZURE_DEEPSEEKV3"

    @property
    def _provider_name(self) -> str:
        return "DeepSeek"
