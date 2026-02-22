import pytest
from unittest.mock import MagicMock, patch
import os


class TestFFPerplexityInit:
    """Tests for FFPerplexity initialization."""

    def test_init_with_api_key(self, mock_openai_client):
        """Test initialization with explicit API key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
                MockOpenAI.return_value = mock_openai_client
                from src.Clients.FFPerplexity import FFPerplexity

                client = FFPerplexity(api_key="test-key")

                assert client.api_key == "test-key"
                assert client.temperature == 0.5
                assert client.max_tokens == 4000

    def test_init_with_custom_params(self, mock_openai_client):
        """Test initialization with custom parameters."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(
                api_key="test-key",
                model="sonar-pro",
                temperature=0.7,
                max_tokens=8000,
                system_instructions="Be concise.",
            )

            assert client.model == "sonar-pro"
            assert client.temperature == 0.7
            assert client.max_tokens == 8000
            assert client.system_instructions == "Be concise."

    def test_init_missing_api_key_raises(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFPerplexity.OpenAI"):
                from src.Clients.FFPerplexity import FFPerplexity

                with pytest.raises(ValueError, match="API key not found"):
                    FFPerplexity(api_key=None)


class TestFFPerplexityGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(self, mock_openai_client, mock_openai_response):
        """Test basic response generation."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            response = client.generate_response("Hello!")

            assert response == "This is a test response."
            mock_openai_client.chat.completions.create.assert_called_once()

    def test_generate_response_uses_correct_base_url(self, mock_openai_client):
        """Test that Perplexity API base URL is used."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            FFPerplexity(api_key="test-key")

            call_kwargs = MockOpenAI.call_args
            assert "https://api.perplexity.ai" in str(call_kwargs)

    def test_generate_response_adds_to_history(self, mock_openai_client):
        """Test that responses are added to conversation history."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.generate_response("Hello!")

            assert len(client.conversation_history) == 2
            assert client.conversation_history[0]["role"] == "user"
            assert client.conversation_history[1]["role"] == "assistant"

    def test_generate_response_empty_prompt_raises(self, mock_openai_client):
        """Test that empty prompt raises ValueError."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")

            with pytest.raises(ValueError, match="Empty prompt"):
                client.generate_response("")


class TestFFPerplexityConversationManagement:
    """Tests for conversation management."""

    def test_get_conversation_history(self, mock_openai_client):
        """Test getting conversation history."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.conversation_history = [{"role": "user", "content": "test"}]

            history = client.get_conversation_history()

            assert len(history) == 1

    def test_set_conversation_history(self, mock_openai_client):
        """Test setting conversation history."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            new_history = [{"role": "user", "content": "Hello"}]

            client.set_conversation_history(new_history)

            assert client.conversation_history == new_history

    def test_clear_conversation(self, mock_openai_client):
        """Test clearing conversation history."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.conversation_history = [{"role": "user", "content": "test"}]
            client.clear_conversation()

            assert client.conversation_history == []


class TestFFPerplexityErrorHandling:
    """Tests for error handling."""

    def test_generate_response_api_error(self, mock_openai_client):
        """Test handling API errors."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            mock_openai_client.chat.completions.create.side_effect = Exception(
                "API Error"
            )
            MockOpenAI.return_value = mock_openai_client

            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")

            with pytest.raises(RuntimeError, match="Error generating response"):
                client.generate_response("Hello!")
