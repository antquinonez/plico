# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

import os
from unittest.mock import MagicMock, patch

import pytest


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

            with pytest.raises(ValueError, match="Empty prompt"):
                client.generate_response("   ")

    def test_generate_response_with_system_instructions_override(self, mock_openai_client):
        """Test overriding system instructions."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.generate_response("Hello!", system_instructions="Be brief.")

            call_args = mock_openai_client.chat.completions.create.call_args
            messages = call_args.kwargs["messages"]

            system_msg = next(m for m in messages if m["role"] == "system")
            assert system_msg["content"] == "Be brief."

    def test_generate_response_with_temperature_override(self, mock_openai_client):
        """Test overriding temperature."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.generate_response("Hello!", temperature=0.1)

            call_args = mock_openai_client.chat.completions.create.call_args
            assert call_args.kwargs["temperature"] == 0.1

    def test_generate_response_with_json_format(self, mock_openai_client):
        """Test JSON response format."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.generate_response("Give me JSON", response_format={"type": "json_object"})

            call_args = mock_openai_client.chat.completions.create.call_args
            assert call_args.kwargs["response_format"] == {"type": "json_object"}

    def test_generate_response_with_max_tokens_override(self, mock_openai_client):
        """Test overriding max_tokens."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.generate_response("Hello!", max_tokens=500)

            call_args = mock_openai_client.chat.completions.create.call_args
            assert call_args.kwargs["max_tokens"] == 500

    def test_generate_response_with_max_completion_tokens(self, mock_openai_client):
        """Test max_completion_tokens as alias for max_tokens."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.generate_response("Hello!", max_completion_tokens=300)

            call_args = mock_openai_client.chat.completions.create.call_args
            assert call_args.kwargs["max_tokens"] == 300


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
            assert history[0]["content"] == "test"

    def test_set_conversation_history(self, mock_openai_client):
        """Test setting conversation history."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            new_history = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]

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


class TestFFPerplexityClone:
    """Tests for clone functionality."""

    def test_clone_returns_new_instance(self, mock_openai_client):
        """Test that clone returns a new instance."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            cloned = client.clone()

            assert cloned is not client
            assert isinstance(cloned, FFPerplexity)

    def test_clone_has_empty_history(self, mock_openai_client):
        """Test that cloned client has empty history."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.conversation_history = [{"role": "user", "content": "test"}]

            cloned = client.clone()

            assert cloned.conversation_history == []
            assert len(client.conversation_history) == 1

    def test_clone_preserves_config(self, mock_openai_client):
        """Test that clone preserves configuration."""
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
            cloned = client.clone()

            assert cloned.api_key == client.api_key
            assert cloned.model == "sonar-pro"
            assert cloned.temperature == 0.7
            assert cloned.max_tokens == 8000
            assert cloned.system_instructions == "Be concise."


class TestFFPerplexityToolCalls:
    """Tests for tool calling functionality."""

    def test_generate_response_with_tool_calls(self, mock_openai_client):
        """Test handling tool calls in response."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            mock_tool_response = MagicMock()
            mock_tool_response.choices = [MagicMock()]
            mock_tool_response.choices[0].message.content = "Using tools"
            mock_tool_response.choices[0].message.tool_calls = [MagicMock()]
            mock_tool_response.choices[0].message.tool_calls[0].id = "call_123"
            mock_tool_response.choices[0].message.tool_calls[0].function.name = "get_weather"
            mock_tool_response.choices[0].message.tool_calls[
                0
            ].function.arguments = '{"city": "London"}'

            mock_openai_client.chat.completions.create.return_value = mock_tool_response
            MockOpenAI.return_value = mock_openai_client

            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            response = client.generate_response("What's the weather?")

            assert "Tool calls detected" in response

    def test_add_tool_result(self, mock_openai_client):
        """Test adding tool result to history."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")
            client.add_tool_result("call_123", {"temp": 72})

            assert len(client.conversation_history) == 1
            assert client.conversation_history[0]["role"] == "tool"
            assert client.conversation_history[0]["tool_call_id"] == "call_123"


class TestFFPerplexityConnectionTest:
    """Tests for connection testing."""

    def test_test_connection_success(self, mock_openai_client):
        """Test successful connection test."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")

            assert client.test_connection() is True

    def test_test_connection_failure(self, mock_openai_client):
        """Test failed connection test."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            mock_openai_client.chat.completions.create.side_effect = Exception("Connection failed")
            MockOpenAI.return_value = mock_openai_client

            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")

            assert client.test_connection() is False


class TestFFPerplexityErrorHandling:
    """Tests for error handling."""

    def test_generate_response_api_error(self, mock_openai_client):
        """Test handling API errors."""
        with patch("src.Clients.FFPerplexity.OpenAI") as MockOpenAI:
            mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
            MockOpenAI.return_value = mock_openai_client

            from src.Clients.FFPerplexity import FFPerplexity

            client = FFPerplexity(api_key="test-key")

            with pytest.raises(RuntimeError, match="Error generating response"):
                client.generate_response("Hello!")
