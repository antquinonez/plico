"""Model defaults registry for LiteLLM-based clients.

Provides default configuration values (max_tokens, temperature, system_instructions)
for various AI models to simplify client configuration.
"""

from typing import Any

GENERIC_DEFAULTS: dict[str, Any] = {
    "max_tokens": 4096,
    "temperature": 0.7,
    "system_instructions": "You are a helpful assistant. Respond accurately to user queries.",
}

MODEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "azure/mistral-small-2503": {
        "max_tokens": 40000,
        "temperature": 0.7,
        "system_instructions": "You are a helpful assistant. Respond accurately to user queries. Be concise and clear.",
    },
    "azure/mistral-large-2411": {
        "max_tokens": 40000,
        "temperature": 0.7,
    },
    "azure/codestral": {
        "max_tokens": 32000,
        "temperature": 0.3,
        "system_instructions": "You are an expert programmer. Write clean, efficient, well-documented code.",
    },
    "azure/deepseek-v3": {
        "max_tokens": 32000,
        "temperature": 0.7,
    },
    "azure/deepseek-r1": {
        "max_tokens": 32000,
        "temperature": 0.7,
    },
    "azure/phi-4": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "mistral/mistral-small-latest": {
        "max_tokens": 32000,
        "temperature": 0.7,
    },
    "mistral/mistral-large-latest": {
        "max_tokens": 40000,
        "temperature": 0.7,
    },
    "mistral/codestral-latest": {
        "max_tokens": 32000,
        "temperature": 0.3,
    },
    "anthropic/claude-3-opus-20240229": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "anthropic/claude-3-sonnet-20240229": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "anthropic/claude-3-haiku-20240307": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "anthropic/claude-3-5-sonnet-20241022": {
        "max_tokens": 8192,
        "temperature": 0.7,
    },
    "openai/gpt-4": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "openai/gpt-4-turbo": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "openai/gpt-4o": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "openai/gpt-4o-mini": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "gemini/gemini-pro": {
        "max_tokens": 8192,
        "temperature": 0.7,
    },
    "gemini/gemini-1.5-pro": {
        "max_tokens": 8192,
        "temperature": 0.7,
    },
    "perplexity/llama-3.1-sonar-large-128k-online": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "nvidia_nim/deepseek-ai/deepseek-r1": {
        "max_tokens": 32000,
        "temperature": 0.7,
    },
}


def get_model_defaults(model_string: str) -> dict[str, Any]:
    """Get defaults for a model string.

    Args:
        model_string: LiteLLM model identifier (e.g., "azure/mistral-small-2503")

    Returns:
        Dictionary with default settings

    """
    if model_string in MODEL_DEFAULTS:
        return MODEL_DEFAULTS[model_string].copy()

    model_name = model_string.split("/")[-1] if "/" in model_string else model_string
    for key, defaults in MODEL_DEFAULTS.items():
        if model_name in key:
            return defaults.copy()

    return GENERIC_DEFAULTS.copy()


def register_model_defaults(model_string: str, defaults: dict[str, Any]) -> None:
    """Register custom defaults for a model.

    Args:
        model_string: LiteLLM model identifier
        defaults: Dictionary of default settings

    """
    MODEL_DEFAULTS[model_string] = defaults
