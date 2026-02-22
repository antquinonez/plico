import pytest
from unittest.mock import MagicMock, patch
import os


class TestFFMistralInit:
    """Tests for FFMistral initialization."""

    def test_init_with_api_key(self, mock_mistral_client):
        """Test initialization with explicit API key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFMistral.Mistral") as MockMistral:
                MockMistral.return_value = mock_mistral_client
                from src.Clients.FFMistral import FFMistral

                client = FFMistral(api_key="test-key", temperature=0.8)

                assert client.api_key == "test-key"
                assert client.model == "mistral-large-latest"
                assert client.temperature == 0.8
                assert client.max_tokens == 4096

    def test_init_with_custom_params(self, mock_mistral_client):
        """Test initialization with custom parameters."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(
                api_key="test-key",
                model="custom-model",
                temperature=0.5,
                max_tokens=2000,
                system_instructions="Be brief.",
            )

            assert client.model == "custom-model"
            assert client.temperature == 0.5
            assert client.max_tokens == 2000
            assert client.system_instructions == "Be brief."

    def test_init_missing_api_key_raises(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFMistral.Mistral"):
                from src.Clients.FFMistral import FFMistral

                with pytest.raises(ValueError, match="API key not found"):
                    FFMistral(api_key=None)


class TestFFMistralGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(self, mock_mistral_client, mock_mistral_response):
        """Test basic response generation."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            response = client.generate_response("Hello!")

            assert response == "This is a test response."
            mock_mistral_client.chat.complete.assert_called_once()

    def test_generate_response_adds_to_history(self, mock_mistral_client):
        """Test that responses are added to conversation history."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            client.generate_response("Hello!")

            assert len(client.conversation_history) == 2
            assert client.conversation_history[0]["role"] == "user"
            assert client.conversation_history[1]["role"] == "assistant"

    def test_generate_response_empty_prompt_raises(self, mock_mistral_client):
        """Test that empty prompt raises ValueError."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")

            with pytest.raises(ValueError, match="Empty prompt"):
                client.generate_response("")

            with pytest.raises(ValueError, match="Empty prompt"):
                client.generate_response("   ")

    def test_generate_response_with_system_instructions_override(
        self, mock_mistral_client
    ):
        """Test overriding system instructions."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            client.generate_response("Hello!", system_instructions="Be brief.")

            call_args = mock_mistral_client.chat.complete.call_args
            messages = call_args.kwargs["messages"]

            system_msg = next(m for m in messages if m["role"] == "system")
            assert system_msg["content"] == "Be brief."

    def test_generate_response_with_temperature_override(self, mock_mistral_client):
        """Test overriding temperature."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            client.generate_response("Hello!", temperature=0.1)

            call_args = mock_mistral_client.chat.complete.call_args
            assert call_args.kwargs["temperature"] == 0.1

    def test_generate_response_with_json_format(self, mock_mistral_client):
        """Test JSON response format."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            client.generate_response(
                "Give me JSON", response_format={"type": "json_object"}
            )

            call_args = mock_mistral_client.chat.complete.call_args
            assert call_args.kwargs["response_format"] == {"type": "json_object"}


class TestFFMistralConversationManagement:
    """Tests for conversation management."""

    def test_get_conversation_history(self, mock_mistral_client):
        """Test getting conversation history."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            client.conversation_history = [{"role": "user", "content": "test"}]

            history = client.get_conversation_history()

            assert len(history) == 1
            assert history[0]["content"] == "test"

    def test_set_conversation_history(self, mock_mistral_client):
        """Test setting conversation history."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            new_history = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]

            client.set_conversation_history(new_history)

            assert client.conversation_history == new_history

    def test_clear_conversation(self, mock_mistral_client):
        """Test clearing conversation history."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            client.conversation_history = [{"role": "user", "content": "test"}]

            client.clear_conversation()

            assert client.conversation_history == []


class TestFFMistralToolCalls:
    """Tests for tool calling functionality."""

    def test_generate_response_with_tool_calls(self, mock_mistral_client):
        """Test handling tool calls in response."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            mock_tool_response = MagicMock()
            mock_tool_response.choices = [MagicMock()]
            mock_tool_response.choices[0].message.content = "Using tools"
            mock_tool_response.choices[0].message.tool_calls = [MagicMock()]
            mock_tool_response.choices[0].message.tool_calls[0].id = "call_123"
            mock_tool_response.choices[0].message.tool_calls[
                0
            ].function.name = "get_weather"
            mock_tool_response.choices[0].message.tool_calls[
                0
            ].function.arguments = '{"city": "London"}'

            mock_mistral_client.chat.complete.return_value = mock_tool_response
            MockMistral.return_value = mock_mistral_client

            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            response = client.generate_response("What's the weather?")

            assert "Tool calls detected" in response

    def test_add_tool_result(self, mock_mistral_client):
        """Test adding tool result to history."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")
            client.add_tool_result("call_123", {"temp": 72})

            assert len(client.conversation_history) == 1
            assert client.conversation_history[0]["role"] == "tool"
            assert client.conversation_history[0]["tool_call_id"] == "call_123"


class TestFFMistralConnectionTest:
    """Tests for connection testing."""

    def test_test_connection_success(self, mock_mistral_client):
        """Test successful connection test."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            MockMistral.return_value = mock_mistral_client
            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")

            assert client.test_connection() is True

    def test_test_connection_failure(self, mock_mistral_client):
        """Test failed connection test."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            mock_mistral_client.chat.complete.side_effect = Exception(
                "Connection failed"
            )
            MockMistral.return_value = mock_mistral_client

            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")

            assert client.test_connection() is False


class TestFFMistralErrorHandling:
    """Tests for error handling."""

    def test_generate_response_api_error(self, mock_mistral_client):
        """Test handling API errors."""
        with patch("src.Clients.FFMistral.Mistral") as MockMistral:
            mock_mistral_client.chat.complete.side_effect = Exception("API Error")
            MockMistral.return_value = mock_mistral_client

            from src.Clients.FFMistral import FFMistral

            client = FFMistral(api_key="test-key")

            with pytest.raises(RuntimeError, match="Error generating response"):
                client.generate_response("Hello!")
