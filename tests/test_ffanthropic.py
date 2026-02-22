import pytest
from unittest.mock import MagicMock, patch
import os


class TestFFAnthropicInit:
    """Tests for FFAnthropic initialization."""

    def test_init_with_api_key(self, mock_anthropic_client):
        """Test initialization with explicit API key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFAnthropic.Anthropic") as MockAnthropic:
                MockAnthropic.return_value = mock_anthropic_client
                from src.Clients.FFAnthropic import FFAnthropic

                client = FFAnthropic(api_key="test-key")

                assert client.api_key == "test-key"
                assert client.temperature == 0.5

    def test_init_with_custom_params(self, mock_anthropic_client):
        """Test initialization with custom parameters."""
        with patch("src.Clients.FFAnthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value = mock_anthropic_client
            from src.Clients.FFAnthropic import FFAnthropic

            client = FFAnthropic(
                api_key="test-key",
                model="claude-3-opus-20240229",
                temperature=0.7,
                max_tokens=4000,
                system_instructions="Be brief.",
            )

            assert client.model == "claude-3-opus-20240229"
            assert client.temperature == 0.7
            assert client.max_tokens == 4000
            assert client.system_instructions == "Be brief."

    def test_init_missing_api_key_raises(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFAnthropic.Anthropic"):
                from src.Clients.FFAnthropic import FFAnthropic

                with pytest.raises(ValueError, match="API key not found"):
                    FFAnthropic(api_key=None)


class TestFFAnthropicGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(
        self, mock_anthropic_client, mock_anthropic_response
    ):
        """Test basic response generation."""
        with patch("src.Clients.FFAnthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value = mock_anthropic_client
            from src.Clients.FFAnthropic import FFAnthropic

            client = FFAnthropic(api_key="test-key")
            response = client.generate_response("Hello!")

            assert response == "This is a test response."
            mock_anthropic_client.messages.create.assert_called_once()

    def test_generate_response_adds_to_history(self, mock_anthropic_client):
        """Test that responses are added to conversation history."""
        with patch("src.Clients.FFAnthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value = mock_anthropic_client
            from src.Clients.FFAnthropic import FFAnthropic

            client = FFAnthropic(api_key="test-key")
            client.generate_response("Hello!")

            assert len(client.conversation_history) == 2
            assert client.conversation_history[0]["role"] == "user"
            assert client.conversation_history[1]["role"] == "assistant"

    def test_generate_response_with_max_model(self, mock_anthropic_client):
        """Test response generation with max model enabled."""
        with patch("src.Clients.FFAnthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value = mock_anthropic_client
            from src.Clients.FFAnthropic import FFAnthropic

            client = FFAnthropic(
                api_key="test-key", max_model=True, max_model_max_tokens=8192
            )

            assert client.max_model is not None


class TestFFAnthropicConversationManagement:
    """Tests for conversation management."""

    def test_clear_conversation(self, mock_anthropic_client):
        """Test clearing conversation history."""
        with patch("src.Clients.FFAnthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value = mock_anthropic_client
            from src.Clients.FFAnthropic import FFAnthropic

            client = FFAnthropic(api_key="test-key")
            client.conversation_history = [{"role": "user", "content": "test"}]
            client.clear_conversation()

            assert client.conversation_history == []


class TestFFAnthropicErrorHandling:
    """Tests for error handling."""

    def test_generate_response_api_error(self, mock_anthropic_client):
        """Test handling API errors."""
        with patch("src.Clients.FFAnthropic.Anthropic") as MockAnthropic:
            mock_anthropic_client.messages.create.side_effect = Exception("API Error")
            MockAnthropic.return_value = mock_anthropic_client

            from src.Clients.FFAnthropic import FFAnthropic

            client = FFAnthropic(api_key="test-key")

            with pytest.raises(RuntimeError, match="Error generating response"):
                client.generate_response("Hello!")
