# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Client instantiation utilities for CLI scripts."""

from __future__ import annotations

import importlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def get_client_class(client_class_name: str) -> type:
    """Dynamically import and return a client class by name.

    Args:
        client_class_name: Name of the client class (e.g., 'FFMistralSmall').


    Returns:
        The client class type.

    Raises:
        ImportError: If the client class cannot be imported.

    """
    module_path = f"src.Clients.{client_class_name}"
    try:
        module = importlib.import_module(module_path)
        return getattr(module, client_class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Could not import client class '{client_class_name}': {e}")


def get_client(client_type: str, workbook_config: dict[str, Any]) -> Any:
    """Instantiate the appropriate client from config.

    Args:
        client_type: Name of the client type from config.
        workbook_config: Config dict with optional overrides (model, api_key_env, etc.).

    Returns:
        Instantiated client object.

    Raises:
        ValueError: If client type is unknown or API key is missing.

    """
    from src.config import get_config

    app_config = get_config()
    client_type_config = app_config.get_client_type_config(client_type)

    if client_type_config is None:
        available = app_config.get_available_client_types()
        raise ValueError(f"Unknown client type: '{client_type}'. Available types: {available}")
    client_class = get_client_class(client_type_config.client_class)
    api_key_env = workbook_config.get("api_key_env") or client_type_config.api_key_env
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise ValueError(f"API key not found in environment variable: {api_key_env}")
    model = workbook_config.get("model") or client_type_config.default_model
    temperature = workbook_config.get("temperature")
    max_tokens = workbook_config.get("max_tokens")
    system_instructions = workbook_config.get("system_instructions")
    if client_type_config.type == "litellm":
        provider_prefix = client_type_config.provider_prefix
        model_string = f"{provider_prefix}{model}" if provider_prefix else model
        return client_class(
            model_string=model_string,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            system_instructions=system_instructions,
        )
    else:
        return client_class(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_instructions=system_instructions,
        )
