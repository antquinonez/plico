# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Client registry for multi-client AI orchestration.

Provides lazy instantiation and configuration of AI clients based on
definitions in the workbook's 'clients' sheet and the config system.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from ..config import get_config
from ..core.client_base import FFAIClientBase

logger = logging.getLogger(__name__)


def _get_client_class(client_class_name: str) -> type[FFAIClientBase]:
    """Dynamically import and return a client class by name."""
    module_path = f"src.Clients.{client_class_name}"
    try:
        module = importlib.import_module(module_path)
        return getattr(module, client_class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Could not import client class '{client_class_name}': {e}")


class ClientRegistry:
    """Registry for AI clients with lazy instantiation.

    Supports per-prompt client selection via named client configurations
    defined in the workbook's 'clients' sheet.

    Usage:
        registry = ClientRegistry(default_client)
        registry.register("fast", "mistral-small", {"temperature": 0.3})
        registry.register("smart", "litellm-claude-3-5-sonnet", {})

        client = registry.get("fast")  # Returns mistral-small client
        client = registry.get()  # Returns default client
    """

    def __init__(self, default_client: FFAIClientBase) -> None:
        """Initialize registry with a default client.

        Args:
            default_client: The default client to use when no name specified.

        """
        self._default_client = default_client
        self._clients: dict[str, FFAIClientBase] = {}
        self._client_configs: dict[str, dict[str, Any]] = {}

    def register(self, name: str, client_type: str, config: dict[str, Any] | None = None) -> None:
        """Register a named client configuration.

        Args:
            name: Unique identifier for this client
            client_type: Client type from config (e.g., "mistral-small", "litellm-mistral-large")
            config: Optional configuration (api_key_env, model, temperature, max_tokens, etc.)

        Raises:
            ValueError: If client_type is not recognized in config

        """
        app_config = get_config()
        client_type_config = app_config.get_client_type_config(client_type)

        if client_type_config is None:
            available = app_config.get_available_client_types()
            raise ValueError(f"Unknown client type: '{client_type}'. Available types: {available}")

        self._client_configs[name] = {
            "client_type": client_type,
            "config": config or {},
        }

        logger.info(f"Registered client '{name}' of type '{client_type}'")

    def get(self, name: str | None = None) -> FFAIClientBase:
        """Get client by name, creating it lazily if needed.

        Args:
            name: Client name, or None for default client

        Returns:
            The requested client instance

        Note:
            If name is not found, returns default client with a warning.

        """
        if name is None:
            return self._default_client

        if name not in self._client_configs:
            logger.warning(f"Client '{name}' not found in registry, falling back to default client")
            return self._default_client

        if name not in self._clients:
            self._clients[name] = self._create_client(name)

        return self._clients[name]

    def clone(self, name: str | None = None) -> FFAIClientBase:
        """Get a fresh clone of a client for parallel execution.

        Args:
            name: Client name, or None for default client

        Returns:
            A cloned client with empty history

        """
        return self.get(name).clone()

    def _create_client(self, name: str) -> FFAIClientBase:
        """Create a client instance from registered configuration.

        Args:
            name: The registered client name

        Returns:
            A new client instance

        """
        import os

        registration = self._client_configs[name]
        client_type = registration["client_type"]
        config = registration["config"]

        app_config = get_config()
        client_type_config = app_config.get_client_type_config(client_type)

        if client_type_config is None:
            raise ValueError(f"Client type '{client_type}' not found in config")

        client_class = _get_client_class(client_type_config.client_class)

        api_key = config.get("api_key")
        if not api_key:
            api_key_env = config.get("api_key_env") or client_type_config.api_key_env
            if api_key_env:
                api_key = os.getenv(api_key_env)

        kwargs: dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key

        model = config.get("model") or client_type_config.default_model

        if client_type_config.type == "litellm":
            provider_prefix = client_type_config.provider_prefix
            kwargs["model_string"] = f"{provider_prefix}{model}" if provider_prefix else model
            if config.get("api_base"):
                kwargs["api_base"] = config["api_base"]
            if config.get("api_version"):
                kwargs["api_version"] = config["api_version"]
            if config.get("fallbacks"):
                kwargs["fallbacks"] = config["fallbacks"]
        else:
            if model:
                kwargs["model"] = model

        if config.get("temperature") is not None:
            kwargs["temperature"] = float(config["temperature"])
        if config.get("max_tokens"):
            kwargs["max_tokens"] = int(config["max_tokens"])
        if config.get("system_instructions"):
            kwargs["system_instructions"] = config["system_instructions"]

        logger.debug(f"Creating client '{name}' of type '{client_type}' with config: {kwargs}")

        return client_class(**kwargs)

    def has_client(self, name: str) -> bool:
        """Check if a client name is registered."""
        return name in self._client_configs

    def get_registered_names(self) -> list:
        """Get list of registered client names."""
        return list(self._client_configs.keys())

    @classmethod
    def get_available_client_types(cls) -> list:
        """Get list of available client types from config."""
        config = get_config()
        return config.get_available_client_types()

    @classmethod
    def get_default_api_key_env(cls, client_type: str) -> str | None:
        """Get the default API key environment variable for a client type."""
        config = get_config()
        client_type_config = config.get_client_type_config(client_type)
        return client_type_config.api_key_env if client_type_config else None
