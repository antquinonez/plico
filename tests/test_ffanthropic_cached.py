# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for FFAnthropicCached client."""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestFFAnthropicCachedInit:
    """Tests for FFAnthropicCached initialization."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")

            assert client.api_key == "test-key"
            assert client.model == "claude-3-5-sonnet-20240620"
            MockAnthropic.assert_called_once_with(api_key="test-key")

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(
                config={
                    "api_key": "test-key",
                    "model": "claude-3-opus-20240229",
                    "temperature": 0.3,
                    "max_tokens": 4000,
                    "system_instructions": "Custom instructions",
                }
            )

            assert client.model == "claude-3-opus-20240229"
            assert client.temperature == 0.3
            assert client.max_tokens == 4000
            assert client.system_instructions == "Custom instructions"

    def test_init_with_config_dict(self):
        """Test initialization with config dictionary."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(
                config={
                    "api_key": "test-key",
                    "model": "claude-3-haiku-20240307",
                    "temperature": 0.5,
                    "max_tokens": 1000,
                }
            )

            assert client.model == "claude-3-haiku-20240307"
            assert client.temperature == 0.5
            assert client.max_tokens == 1000

    def test_init_missing_api_key_raises(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFAnthropicCached.Anthropic"):
                from src.Clients.FFAnthropicCached import FFAnthropicCached

                with pytest.raises(ValueError, match="API key not found"):
                    FFAnthropicCached(api_key=None)

    def test_init_from_env(self, monkeypatch):
        """Test initialization from environment variables."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-api-key")
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        monkeypatch.setenv("ANTHROPIC_TEMPERATURE", "0.6")
        monkeypatch.setenv("ANTHROPIC_MAX_TOKENS", "2000")

        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached()

            assert client.api_key == "env-api-key"
            assert client.model == "claude-3-haiku-20240307"
            assert client.temperature == 0.6
            assert client.max_tokens == 2000

    def test_init_initializes_histories(self):
        """Test that histories are initialized."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")

            assert client.conversation_history is not None
            assert client.permanent_history is not None
            assert client.ordered_history is not None


class TestFFAnthropicCachedGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(self):
        """Test basic response generation."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "This is a test response."
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            response = client.generate_response("Hello!")

            assert response == "This is a test response."
            mock_client.messages.create.assert_called_once()

    def test_generate_response_uses_caching_headers(self):
        """Test that prompt caching headers are sent."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Hello!")

            call_args = mock_client.messages.create.call_args
            assert "extra_headers" in call_args.kwargs
            assert "anthropic-beta" in call_args.kwargs["extra_headers"]

    def test_generate_response_uses_cache_control(self):
        """Test that system prompt has cache_control."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Hello!")

            call_args = mock_client.messages.create.call_args
            system = call_args.kwargs["system"]
            assert isinstance(system, list)
            assert system[0]["cache_control"]["type"] == "ephemeral"

    def test_generate_response_adds_to_histories(self):
        """Test that responses are added to histories."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Hello!", prompt_name="greeting")

            history = client.get_interaction_history()
            assert len(history) == 1
            assert history[0]["prompt"] == "Hello!"
            assert history[0]["response"] == "Response"
            assert history[0]["prompt_name"] == "greeting"

    def test_generate_response_with_model_override(self):
        """Test model override in generate_response."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key", model="claude-3-opus")
            client.generate_response("Hello!", model="claude-3-haiku")

            call_args = mock_client.messages.create.call_args
            assert call_args.kwargs["model"] == "claude-3-haiku"

    def test_generate_response_api_error_raises_runtime_error(self):
        """Test that API errors raise RuntimeError."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = Exception("API Error")
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")

            with pytest.raises(RuntimeError, match="Error generating response"):
                client.generate_response("Hello!")


class TestFFAnthropicCachedHistoryMethods:
    """Tests for history access methods."""

    def test_get_interaction_history(self):
        """Test getting all interactions."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Prompt 1", prompt_name="first")
            client.generate_response("Prompt 2", prompt_name="second")

            history = client.get_interaction_history()
            assert len(history) == 2

    def test_get_last_n_interactions(self):
        """Test getting last N interactions."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Prompt 1")
            client.generate_response("Prompt 2")
            client.generate_response("Prompt 3")

            last_two = client.get_last_n_interactions(2)
            assert len(last_two) == 2

    def test_get_interaction_by_sequence(self):
        """Test getting interaction by sequence number."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("First prompt")
            client.generate_response("Second prompt")

            interaction = client.get_interaction(2)
            assert interaction is not None
            assert interaction["prompt"] == "Second prompt"

    def test_get_interaction_not_found_returns_none(self):
        """Test that missing interaction returns None."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            interaction = client.get_interaction(999)
            assert interaction is None

    def test_get_model_interactions(self):
        """Test filtering by model."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key", model="claude-3-opus")
            client.generate_response("Prompt 1")
            client.generate_response("Prompt 2")

            model_interactions = client.get_model_interactions("claude-3-opus")
            assert len(model_interactions) == 2

    def test_get_interactions_by_prompt_name(self):
        """Test filtering by prompt name."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Prompt", prompt_name="greeting")
            client.generate_response("Prompt", prompt_name="question")

            greetings = client.get_interactions_by_prompt_name("greeting")
            assert len(greetings) == 1

    def test_get_latest_interaction(self):
        """Test getting latest interaction."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Latest response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("First")
            client.generate_response("Latest prompt")

            latest = client.get_latest_interaction()
            assert latest["prompt"] == "Latest prompt"

    def test_get_latest_interaction_empty_returns_none(self):
        """Test that empty history returns None."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            latest = client.get_latest_interaction()
            assert latest is None

    def test_get_prompt_history(self):
        """Test getting all prompts."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Prompt 1")
            client.generate_response("Prompt 2")

            prompts = client.get_prompt_history()
            assert prompts == ["Prompt 1", "Prompt 2"]

    def test_get_response_history(self):
        """Test getting all responses."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response1 = MagicMock()
            mock_response1.content = [MagicMock()]
            mock_response1.content[0].text = "Response 1"
            mock_response2 = MagicMock()
            mock_response2.content = [MagicMock()]
            mock_response2.content[0].text = "Response 2"
            mock_client.messages.create.side_effect = [mock_response1, mock_response2]
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Prompt 1")
            client.generate_response("Prompt 2")

            responses = client.get_response_history()
            assert responses == ["Response 1", "Response 2"]


class TestFFAnthropicCachedStats:
    """Tests for usage statistics methods."""

    def test_get_model_usage_stats(self):
        """Test model usage statistics."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key", model="claude-3-opus")
            client.generate_response("Prompt 1")
            client.generate_response("Prompt 2")

            stats = client.get_model_usage_stats()
            assert stats == {"claude-3-opus": 2}

    def test_get_prompt_name_usage_stats(self):
        """Test prompt name usage statistics."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Prompt", prompt_name="greeting")
            client.generate_response("Prompt", prompt_name="greeting")
            client.generate_response("Prompt", prompt_name="question")

            stats = client.get_prompt_name_usage_stats()
            assert stats == {"greeting": 2, "question": 1}


class TestFFAnthropicCachedClearConversation:
    """Tests for conversation clearing."""

    def test_clear_conversation(self):
        """Test clearing conversation history."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Prompt")
            client.clear_conversation()

            turns = client.conversation_history.get_turns()
            assert len(turns) == 0

    def test_clear_conversation_preserves_ordered_history(self):
        """Test that clear preserves ordered history."""
        with patch("src.Clients.FFAnthropicCached.Anthropic") as MockAnthropic:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.content = [MagicMock()]
            mock_response.content[0].text = "Response"
            mock_client.messages.create.return_value = mock_response
            MockAnthropic.return_value = mock_client

            from src.Clients.FFAnthropicCached import FFAnthropicCached

            client = FFAnthropicCached(api_key="test-key")
            client.generate_response("Prompt", prompt_name="first")
            client.clear_conversation()

            ordered = client.get_interaction_history()
            assert len(ordered) == 1  # Ordered history preserved
