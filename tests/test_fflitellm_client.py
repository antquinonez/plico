# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for FFLiteLLMClient."""

from unittest.mock import MagicMock, patch

import pytest

from src.Clients.FFLiteLLMClient import FFLiteLLMClient
from src.FFAIClientBase import FFAIClientBase


class TestFFLiteLLMClientContract:
    """Test that FFLiteLLMClient implements FFAIClientBase contract."""

    def test_is_ffaclientbase_subclass(self):
        """FFLiteLLMClient should inherit from FFAIClientBase."""
        assert issubclass(FFLiteLLMClient, FFAIClientBase)

    def test_has_required_methods(self):
        """FFLiteLLMClient should have all required methods."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        assert hasattr(client, "generate_response")
        assert hasattr(client, "clear_conversation")
        assert hasattr(client, "get_conversation_history")
        assert hasattr(client, "set_conversation_history")
        assert hasattr(client, "clone")
        assert hasattr(client, "add_tool_result")

    def test_has_required_attributes(self):
        """FFLiteLLMClient should have required attributes."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        assert hasattr(client, "model")
        assert hasattr(client, "system_instructions")


class TestFFLiteLLMClientInit:
    """Test FFLiteLLMClient initialization."""

    def test_init_with_model_string(self):
        """Should initialize with model_string."""
        client = FFLiteLLMClient(model_string="anthropic/claude-3-opus")
        assert client._model_string == "anthropic/claude-3-opus"
        assert client.model == "claude-3-opus"

    def test_init_with_custom_settings(self):
        """Should accept custom settings."""
        client = FFLiteLLMClient(
            model_string="openai/gpt-4",
            temperature=0.5,
            max_tokens=2000,
            system_instructions="Be helpful",
        )
        assert client.temperature == 0.5
        assert client.max_tokens == 2000
        assert client.system_instructions == "Be helpful"

    def test_init_with_config_dict(self):
        """Should accept config dictionary."""
        client = FFLiteLLMClient(
            model_string="openai/gpt-4",
            config={"temperature": 0.3, "max_tokens": 1000},
        )
        assert client.temperature == 0.3
        assert client.max_tokens == 1000

    def test_init_with_fallbacks(self):
        """Should accept fallback models."""
        client = FFLiteLLMClient(
            model_string="anthropic/claude-3-opus",
            fallbacks=["openai/gpt-4", "mistral/mistral-large"],
        )
        assert client._fallbacks == ["openai/gpt-4", "mistral/mistral-large"]

    def test_init_empty_history(self):
        """Should start with empty conversation history."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        assert client.conversation_history == []


class TestFFLiteLLMClientHistory:
    """Test conversation history management."""

    def test_get_conversation_history(self):
        """Should return a copy of conversation history."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        client.conversation_history.append({"role": "user", "content": "test"})
        history = client.get_conversation_history()
        assert len(history) == 1
        assert history[0]["content"] == "test"

    def test_set_conversation_history(self):
        """Should set conversation history."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        new_history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        client.set_conversation_history(new_history)
        assert len(client.conversation_history) == 2

    def test_set_conversation_history_copies(self):
        """Should copy history to avoid shared references."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        new_history = [{"role": "user", "content": "test"}]
        client.set_conversation_history(new_history)
        new_history.append({"role": "assistant", "content": "response"})
        assert len(client.conversation_history) == 1

    def test_clear_conversation(self):
        """Should clear conversation history."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        client.conversation_history.append({"role": "user", "content": "test"})
        client.clear_conversation()
        assert client.conversation_history == []


class TestFFLiteLLMClientClone:
    """Test clone pattern for parallel execution."""

    def test_clone_returns_new_instance(self):
        """Clone should return new instance."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        clone = client.clone()
        assert clone is not client
        assert isinstance(clone, FFLiteLLMClient)

    def test_clone_has_same_config(self):
        """Clone should have same configuration."""
        client = FFLiteLLMClient(
            model_string="anthropic/claude-3-opus",
            temperature=0.5,
            max_tokens=2000,
            system_instructions="Be helpful",
        )
        clone = client.clone()
        assert clone._model_string == client._model_string
        assert clone.temperature == client.temperature
        assert clone.max_tokens == client.max_tokens
        assert clone.system_instructions == client.system_instructions

    def test_clone_has_empty_history(self):
        """Clone should have empty history regardless of parent."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        client.conversation_history.append({"role": "user", "content": "test"})
        clone = client.clone()
        assert len(clone.conversation_history) == 0

    def test_clone_isolation(self):
        """Clone modifications should not affect parent."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        clone = client.clone()
        clone.conversation_history.append({"role": "user", "content": "clone msg"})
        assert len(client.conversation_history) == 0
        assert len(clone.conversation_history) == 1

    def test_clone_with_fallbacks(self):
        """Clone should preserve fallbacks."""
        client = FFLiteLLMClient(
            model_string="anthropic/claude-3-opus",
            fallbacks=["openai/gpt-4"],
        )
        clone = client.clone()
        assert clone._fallbacks == ["openai/gpt-4"]


class TestFFLiteLLMClientGenerateResponse:
    """Test generate_response method."""

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_generate_response_basic(self, mock_completion):
        """Should call LiteLLM completion and return response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello back!"
        mock_completion.return_value = mock_response

        client = FFLiteLLMClient(model_string="openai/gpt-4")
        response = client.generate_response("Hello!")

        assert response == "Hello back!"
        mock_completion.assert_called_once()

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_generate_response_adds_to_history(self, mock_completion):
        """Should add prompt and response to history."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_completion.return_value = mock_response

        client = FFLiteLLMClient(model_string="openai/gpt-4")
        client.generate_response("Question")

        assert len(client.conversation_history) == 2
        assert client.conversation_history[0]["role"] == "user"
        assert client.conversation_history[0]["content"] == "Question"
        assert client.conversation_history[1]["role"] == "assistant"

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_generate_response_with_model_override(self, mock_completion):
        """Should use model override when provided."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_completion.return_value = mock_response

        client = FFLiteLLMClient(model_string="anthropic/claude-3-opus")
        client.generate_response("Hello", model="claude-3-haiku")

        call_args = mock_completion.call_args
        assert call_args[1]["model"] == "anthropic/claude-3-haiku"

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_generate_response_with_temperature_override(self, mock_completion):
        """Should use temperature override when provided."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_completion.return_value = mock_response

        client = FFLiteLLMClient(model_string="openai/gpt-4", temperature=0.7)
        client.generate_response("Hello", temperature=0.3)

        call_args = mock_completion.call_args
        assert call_args[1]["temperature"] == 0.3

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_generate_response_with_tool_calls_adds_tool_history(self, mock_completion):
        """Tool-call responses should preserve tool_calls in history for agent mode."""
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = None

        mock_function = MagicMock()
        mock_function.name = "calculate"
        mock_function.arguments = '{"expression": "2 + 2"}'

        mock_tool_call = MagicMock()
        mock_tool_call.id = "tc_123"
        mock_tool_call.function = mock_function

        mock_message.tool_calls = [mock_tool_call]
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_completion.return_value = mock_response

        client = FFLiteLLMClient(model_string="openai/gpt-4")
        response = client.generate_response(
            "Use the calculate tool.",
            tools=[{"type": "function", "function": {"name": "calculate"}}],
            tool_choice="auto",
        )

        assert response == ""
        assert len(client.conversation_history) == 2
        assistant_message = client.conversation_history[-1]
        assert assistant_message["role"] == "assistant"
        assert "tool_calls" in assistant_message
        assert assistant_message["tool_calls"][0]["id"] == "tc_123"
        assert assistant_message["tool_calls"][0]["function"]["name"] == "calculate"
        assert (
            assistant_message["tool_calls"][0]["function"]["arguments"] == '{"expression": "2 + 2"}'
        )

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_generate_response_with_tool_calls_none_content(self, mock_completion):
        """Tool-call responses with no textual content should not crash."""
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = None
        mock_message.tool_calls = [
            {
                "id": "tc_456",
                "function": {"name": "json_extract", "arguments": '{"path": "value"}'},
            }
        ]
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_completion.return_value = mock_response

        client = FFLiteLLMClient(model_string="openai/gpt-4")
        response = client.generate_response(
            "Use a tool.",
            tools=[{"type": "function", "function": {"name": "json_extract"}}],
            tool_choice="auto",
        )

        assert response == ""
        assert client.conversation_history[-1]["tool_calls"][0]["id"] == "tc_456"

    def test_generate_response_empty_prompt_raises(self):
        """Should raise ValueError for empty prompt."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        with pytest.raises(ValueError, match="Empty prompt"):
            client.generate_response("")

    def test_generate_response_whitespace_prompt_raises(self):
        """Should raise ValueError for whitespace-only prompt."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        with pytest.raises(ValueError, match="Empty prompt"):
            client.generate_response("   ")


class TestFFLiteLLMClientFallbacks:
    """Test fallback model behavior."""

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_fallback_on_primary_failure(self, mock_completion):
        """Should try fallback when primary fails."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Fallback response"
        mock_completion.side_effect = [Exception("Primary failed"), mock_response]

        client = FFLiteLLMClient(
            model_string="anthropic/claude-3-opus",
            fallbacks=["openai/gpt-4"],
        )
        response = client.generate_response("Hello")

        assert response == "Fallback response"
        assert mock_completion.call_count == 2

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_all_fallbacks_fail_raises(self, mock_completion):
        """Should raise when all models fail."""
        mock_completion.side_effect = Exception("All failed")

        client = FFLiteLLMClient(
            model_string="anthropic/claude-3-opus",
            fallbacks=["openai/gpt-4", "mistral/mistral-large"],
        )
        with pytest.raises(RuntimeError, match="All models failed"):
            client.generate_response("Hello")


class TestFFLiteLLMClientEnvResolution:
    """Test environment variable resolution."""

    def test_resolves_anthropic_api_key(self, monkeypatch):
        """Should resolve Anthropic API key from env."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        client = FFLiteLLMClient(model_string="anthropic/claude-3-opus")
        assert client.api_key == "test-anthropic-key"

    def test_resolves_openai_api_key(self, monkeypatch):
        """Should resolve OpenAI API key from env."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        assert client.api_key == "test-openai-key"

    def test_explicit_api_key_overrides_env(self, monkeypatch):
        """Explicit api_key should override env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        client = FFLiteLLMClient(
            model_string="openai/gpt-4",
            api_key="explicit-key",
        )
        assert client.api_key == "explicit-key"


class TestFFLiteLLMClientToolResult:
    """Tests for add_tool_result method."""

    def test_add_tool_result_appends_to_history(self):
        """add_tool_result should append a tool message to conversation history."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        client.conversation_history.append({"role": "user", "content": "Hello"})
        client.conversation_history.append({"role": "assistant", "content": "Hi"})

        client.add_tool_result("tc_123", "tool result content")

        assert len(client.conversation_history) == 3
        last = client.conversation_history[-1]
        assert last["role"] == "tool"
        assert last["tool_call_id"] == "tc_123"
        assert last["content"] == "tool result content"

    def test_add_tool_result_preserves_existing_history(self):
        """add_tool_result should not overwrite existing history."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        client.conversation_history = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
        ]

        client.add_tool_result("tc_456", "result")

        assert len(client.conversation_history) == 4
        assert client.conversation_history[0]["content"] == "Q1"
        assert client.conversation_history[-1]["role"] == "tool"
