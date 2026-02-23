import pytest
from unittest.mock import MagicMock, patch


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

        with patch("src.orchestrator.client_registry.FFMistralSmall") as MockClient:
            MockClient.return_value = mock_ffmistralsmall

            registry = ClientRegistry(mock_ffmistralsmall)
            registry.register("fast", "mistral-small", {"temperature": 0.3})

            client = registry.get("fast")

            assert client is not None


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
        assert env == "ANTHROPIC_TOKEN"


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
