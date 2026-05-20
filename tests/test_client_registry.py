# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from unittest.mock import MagicMock, patch

import pytest


class TestClientRegistryInit:
    """Tests for ClientRegistry initialization."""

    def test_init_with_default_client(self, mock_ffmistralsmall):
        """Test initialization with default client."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)

        assert registry.get() == mock_ffmistralsmall

    def test_init_empty_registry(self, mock_ffmistralsmall):
        """Test that registry starts empty."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)

        assert registry.get_registered_names() == []


class TestClientRegistryRegister:
    """Tests for client registration."""

    def test_register_client(self, mock_ffmistralsmall):
        """Test registering a client configuration."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)
        registry.register("fast", "mistral-small", {"temperature": 0.3})

        assert "fast" in registry.get_registered_names()

    def test_register_unknown_client_type_raises(self, mock_ffmistralsmall):
        """Test that unknown client type raises ValueError."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)

        with pytest.raises(ValueError, match="Unknown client type"):
            registry.register("test", "unknown-type", {})

    def test_register_multiple_clients(self, mock_ffmistralsmall):
        """Test registering multiple clients."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)
        registry.register("fast", "mistral-small", {"temperature": 0.3})
        registry.register("smart", "anthropic", {"model": "claude-3-5-sonnet"})

        names = registry.get_registered_names()
        assert "fast" in names
        assert "smart" in names
        assert len(names) == 2


class TestClientRegistryGet:
    """Tests for getting clients from registry."""

    def test_get_default_client(self, mock_ffmistralsmall):
        """Test getting default client when no name specified."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)
        client = registry.get()

        assert client == mock_ffmistralsmall

    def test_get_unknown_client_falls_back(self, mock_ffmistralsmall):
        """Test that unknown client name falls back to default."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)
        client = registry.get("unknown")

        assert client == mock_ffmistralsmall

    def test_get_registered_client(self, mock_ffmistralsmall):
        """Test getting a registered client by name."""
        from src.orchestrator.client_registry import ClientRegistry

        with patch("src.orchestrator.client_registry._get_client_class") as mock_get_class:
            mock_get_class.return_value = MagicMock(return_value=mock_ffmistralsmall)

            registry = ClientRegistry(mock_ffmistralsmall)
            registry.register("fast", "mistral-small", {"temperature": 0.3})

            client = registry.get("fast")

            assert client is not None
            assert client == mock_ffmistralsmall


class TestClientRegistryClone:
    """Tests for cloning clients."""

    def test_clone_default_client(self, mock_ffmistralsmall):
        """Test cloning default client."""
        from src.orchestrator.client_registry import ClientRegistry

        mock_ffmistralsmall.clone = MagicMock(return_value=mock_ffmistralsmall)

        registry = ClientRegistry(mock_ffmistralsmall)
        cloned = registry.clone()

        mock_ffmistralsmall.clone.assert_called_once()
        assert cloned == mock_ffmistralsmall


class TestClientRegistryClassMethods:
    """Tests for class methods."""

    def test_get_available_client_types(self):
        """Test getting available client types."""
        from src.orchestrator.client_registry import ClientRegistry

        types = ClientRegistry.get_available_client_types()

        assert "mistral-small" in types
        assert "anthropic" in types
        assert "gemini" in types

    def test_get_default_api_key_env(self):
        """Test getting default API key env var."""
        from src.orchestrator.client_registry import ClientRegistry

        env = ClientRegistry.get_default_api_key_env("mistral-small")
        assert env == "MISTRALSMALL_KEY"

        env = ClientRegistry.get_default_api_key_env("anthropic")
        assert env == "ANTHROPIC_API_KEY"


class TestClientRegistryHasClient:
    """Tests for has_client method."""

    def test_has_client_true(self, mock_ffmistralsmall):
        """Test has_client returns True for registered client."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)
        registry.register("fast", "mistral-small", {})

        assert registry.has_client("fast") is True

    def test_has_client_false(self, mock_ffmistralsmall):
        """Test has_client returns False for unregistered client."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)

        assert registry.has_client("unknown") is False


class TestGetClientClassImportError:
    """Tests for _get_client_class ImportError path (lines 29-30)."""

    def test_nonexistent_module_raises_import_error(self):
        """_get_client_class raises ImportError for nonexistent client class."""
        from src.orchestrator.client_registry import _get_client_class

        with pytest.raises(ImportError, match="Could not import client class"):
            _get_client_class("NonexistentClientXYZ")


class TestCreateClientEdgeCases:
    """Tests for ClientRegistry._create_client uncovered config paths."""

    def test_create_client_missing_type_raises_value_error(self, mock_ffmistralsmall):
        """_create_client raises ValueError when client type disappears from config (line 142)."""
        from src.orchestrator.client_registry import ClientRegistry

        registry = ClientRegistry(mock_ffmistralsmall)
        registry._client_configs["ghost"] = {
            "client_type": "nonexistent-type-xyz",
            "config": {},
        }

        with pytest.raises(ValueError, match="Client type.*not found in config"):
            registry._create_client("ghost")

    def test_create_client_litellm_api_base(self, mock_ffmistralsmall):
        """_create_client passes api_base for litellm type (line 162)."""
        from src.orchestrator.client_registry import ClientRegistry

        mock_client_instance = MagicMock()
        mock_client_cls = MagicMock(return_value=mock_client_instance)

        with patch(
            "src.orchestrator.client_registry._get_client_class", return_value=mock_client_cls
        ):
            with patch("src.orchestrator.client_registry.get_config") as mock_get_config:
                mock_type_config = MagicMock()
                mock_type_config.type = "litellm"
                mock_type_config.client_class = "FFLiteLLM"
                mock_type_config.default_model = "gpt-4"
                mock_type_config.api_key_env = "OPENAI_KEY"
                mock_type_config.provider_prefix = "openai/"
                mock_type_config.fallbacks = None
                mock_get_config.return_value.get_client_type_config.return_value = mock_type_config

                registry = ClientRegistry(mock_ffmistralsmall)
                registry._client_configs["myclient"] = {
                    "client_type": "litellm-openai",
                    "config": {"api_base": "https://custom.api.com/v1"},
                }

                client = registry._create_client("myclient")

                call_kwargs = mock_client_cls.call_args[1]
                assert call_kwargs["api_base"] == "https://custom.api.com/v1"

    def test_create_client_litellm_api_version(self, mock_ffmistralsmall):
        """_create_client passes api_version for litellm type (line 164)."""
        from src.orchestrator.client_registry import ClientRegistry

        mock_client_cls = MagicMock(return_value=MagicMock())

        with patch(
            "src.orchestrator.client_registry._get_client_class", return_value=mock_client_cls
        ):
            with patch("src.orchestrator.client_registry.get_config") as mock_get_config:
                mock_type_config = MagicMock()
                mock_type_config.type = "litellm"
                mock_type_config.client_class = "FFLiteLLM"
                mock_type_config.default_model = "gpt-4"
                mock_type_config.api_key_env = "OPENAI_KEY"
                mock_type_config.provider_prefix = "openai/"
                mock_type_config.fallbacks = None
                mock_get_config.return_value.get_client_type_config.return_value = mock_type_config

                registry = ClientRegistry(mock_ffmistralsmall)
                registry._client_configs["myclient"] = {
                    "client_type": "litellm-openai",
                    "config": {"api_version": "2024-02-01"},
                }

                registry._create_client("myclient")

                call_kwargs = mock_client_cls.call_args[1]
                assert call_kwargs["api_version"] == "2024-02-01"

    def test_create_client_litellm_config_fallbacks(self, mock_ffmistralsmall):
        """_create_client passes fallbacks from config for litellm type (line 166)."""
        from src.orchestrator.client_registry import ClientRegistry

        mock_client_cls = MagicMock(return_value=MagicMock())

        with patch(
            "src.orchestrator.client_registry._get_client_class", return_value=mock_client_cls
        ):
            with patch("src.orchestrator.client_registry.get_config") as mock_get_config:
                mock_type_config = MagicMock()
                mock_type_config.type = "litellm"
                mock_type_config.client_class = "FFLiteLLM"
                mock_type_config.default_model = "gpt-4"
                mock_type_config.api_key_env = "OPENAI_KEY"
                mock_type_config.provider_prefix = "openai/"
                mock_type_config.fallbacks = None
                mock_get_config.return_value.get_client_type_config.return_value = mock_type_config

                registry = ClientRegistry(mock_ffmistralsmall)
                registry._client_configs["myclient"] = {
                    "client_type": "litellm-openai",
                    "config": {"fallbacks": ["gpt-3.5-turbo"]},
                }

                registry._create_client("myclient")

                call_kwargs = mock_client_cls.call_args[1]
                assert call_kwargs["fallbacks"] == ["gpt-3.5-turbo"]

    def test_create_client_litellm_type_config_fallbacks(self, mock_ffmistralsmall):
        """_create_client uses fallbacks from type_config when config has none (line 168)."""
        from src.orchestrator.client_registry import ClientRegistry

        mock_client_cls = MagicMock(return_value=MagicMock())

        with patch(
            "src.orchestrator.client_registry._get_client_class", return_value=mock_client_cls
        ):
            with patch("src.orchestrator.client_registry.get_config") as mock_get_config:
                mock_type_config = MagicMock()
                mock_type_config.type = "litellm"
                mock_type_config.client_class = "FFLiteLLM"
                mock_type_config.default_model = "gpt-4"
                mock_type_config.api_key_env = "OPENAI_KEY"
                mock_type_config.provider_prefix = "openai/"
                mock_type_config.fallbacks = ["gpt-3.5-turbo"]
                mock_get_config.return_value.get_client_type_config.return_value = mock_type_config

                registry = ClientRegistry(mock_ffmistralsmall)
                registry._client_configs["myclient"] = {
                    "client_type": "litellm-openai",
                    "config": {},
                }

                registry._create_client("myclient")

                call_kwargs = mock_client_cls.call_args[1]
                assert call_kwargs["fallbacks"] == ["gpt-3.5-turbo"]

    def test_create_client_passes_system_instructions(self, mock_ffmistralsmall):
        """_create_client passes system_instructions when provided (line 178)."""
        from src.orchestrator.client_registry import ClientRegistry

        mock_client_cls = MagicMock(return_value=MagicMock())

        with patch(
            "src.orchestrator.client_registry._get_client_class", return_value=mock_client_cls
        ):
            with patch("src.orchestrator.client_registry.get_config") as mock_get_config:
                mock_type_config = MagicMock()
                mock_type_config.type = "native"
                mock_type_config.client_class = "FFMistralSmall"
                mock_type_config.default_model = "mistral-small-latest"
                mock_type_config.api_key_env = "MISTRALSMALL_KEY"
                mock_get_config.return_value.get_client_type_config.return_value = mock_type_config

                registry = ClientRegistry(mock_ffmistralsmall)
                registry._client_configs["myclient"] = {
                    "client_type": "mistral-small",
                    "config": {"system_instructions": "Be precise."},
                }

                registry._create_client("myclient")

                call_kwargs = mock_client_cls.call_args[1]
                assert call_kwargs["system_instructions"] == "Be precise."
