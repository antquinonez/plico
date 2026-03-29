# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Model defaults registry for LiteLLM-based clients.

Provides default configuration values (max_tokens, temperature, system_instructions)
for various AI models to simplify client configuration. Values are loaded from
config.yaml.
"""

from typing import Any

from ..config import get_config


def _get_generic_defaults() -> dict[str, Any]:
    """Get generic defaults from config."""
    config = get_config()
    return config.model_defaults.generic.copy()


def _get_model_defaults() -> dict[str, dict[str, Any]]:
    """Get model-specific defaults from config."""
    config = get_config()
    return config.model_defaults.models.copy()


GENERIC_DEFAULTS: dict[str, Any] = {}
MODEL_DEFAULTS: dict[str, dict[str, Any]] = {}


def _ensure_defaults_loaded() -> None:
    """Load defaults from config if not already loaded."""
    global GENERIC_DEFAULTS, MODEL_DEFAULTS
    if not GENERIC_DEFAULTS:
        GENERIC_DEFAULTS = _get_generic_defaults()
    if not MODEL_DEFAULTS:
        MODEL_DEFAULTS = _get_model_defaults()


def get_model_defaults(model_string: str) -> dict[str, Any]:
    """Get defaults for a model string.

    Args:
        model_string: LiteLLM model identifier (e.g., "azure/mistral-small-2503")

    Returns:
        Dictionary with default settings

    """
    _ensure_defaults_loaded()

    if model_string in MODEL_DEFAULTS:
        return MODEL_DEFAULTS[model_string].copy()

    model_name = model_string.rsplit("/", maxsplit=1)[-1] if "/" in model_string else model_string
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
    _ensure_defaults_loaded()
    MODEL_DEFAULTS[model_string] = defaults
