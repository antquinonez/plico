# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

import os
from unittest.mock import patch

import pytest


class TestFFNvidiaDeepSeekInit:
    """Tests for FFNvidiaDeepSeek initialization."""

    def test_init_with_api_key(self, mock_openai_client):
        """Test initialization with explicit API key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFNvidiaDeepSeek.OpenAI") as MockOpenAI:
                MockOpenAI.return_value = mock_openai_client
                from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

                client = FFNvidiaDeepSeek(api_key="test-key")

                assert client.api_key == "test-key"
                assert client.max_tokens == 4096

    def test_init_with_custom_params(self, mock_openai_client):
        """Test initialization with custom parameters."""
        with patch("src.Clients.FFNvidiaDeepSeek.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

            client = FFNvidiaDeepSeek(
                api_key="test-key",
                model="custom-model",
                temperature=0.7,
                max_tokens=8000,
                system_instructions="Be concise.",
            )

            assert client.model == "custom-model"
            assert client.temperature == 0.7
            assert client.max_tokens == 8000
            assert client.system_instructions == "Be concise."

    def test_init_missing_api_key_raises(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFNvidiaDeepSeek.OpenAI"):
                from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

                with pytest.raises(ValueError, match="API key not found"):
                    FFNvidiaDeepSeek(api_key=None)


class TestFFNvidiaDeepSeekGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(self, mock_openai_client, mock_openai_response):
        """Test basic response generation."""
        with patch("src.Clients.FFNvidiaDeepSeek.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

            client = FFNvidiaDeepSeek(api_key="test-key")
            response = client.generate_response("Hello!")

            assert response == "This is a test response."
            mock_openai_client.chat.completions.create.assert_called_once()

    def test_generate_response_uses_nvidia_base_url(self, mock_openai_client):
        """Test that Nvidia API base URL is used."""
        with patch("src.Clients.FFNvidiaDeepSeek.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

            FFNvidiaDeepSeek(api_key="test-key")

            call_kwargs = MockOpenAI.call_args
            assert "nvidia" in str(call_kwargs).lower()

    def test_generate_response_adds_to_history(self, mock_openai_client):
        """Test that responses are added to conversation history."""
        with patch("src.Clients.FFNvidiaDeepSeek.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

            client = FFNvidiaDeepSeek(api_key="test-key")
            client.generate_response("Hello!")

            assert len(client.conversation_history) == 2


class TestFFNvidiaDeepSeekConversationManagement:
    """Tests for conversation management."""

    def test_get_conversation_history(self, mock_openai_client):
        """Test getting conversation history."""
        with patch("src.Clients.FFNvidiaDeepSeek.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

            client = FFNvidiaDeepSeek(api_key="test-key")
            client.conversation_history = [{"role": "user", "content": "test"}]

            history = client.get_conversation_history()

            assert len(history) == 1

    def test_set_conversation_history(self, mock_openai_client):
        """Test setting conversation history."""
        with patch("src.Clients.FFNvidiaDeepSeek.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

            client = FFNvidiaDeepSeek(api_key="test-key")
            new_history = [{"role": "user", "content": "Hello"}]

            client.set_conversation_history(new_history)

            assert client.conversation_history == new_history

    def test_clear_conversation(self, mock_openai_client):
        """Test clearing conversation history."""
        with patch("src.Clients.FFNvidiaDeepSeek.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_client
            from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

            client = FFNvidiaDeepSeek(api_key="test-key")
            client.conversation_history = [{"role": "user", "content": "test"}]
            client.clear_conversation()

            assert client.conversation_history == []


class TestFFNvidiaDeepSeekErrorHandling:
    """Tests for error handling."""

    def test_generate_response_api_error(self, mock_openai_client):
        """Test handling API errors."""
        with patch("src.Clients.FFNvidiaDeepSeek.OpenAI") as MockOpenAI:
            mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
            MockOpenAI.return_value = mock_openai_client

            from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek

            client = FFNvidiaDeepSeek(api_key="test-key")

            with pytest.raises(RuntimeError, match="Error generating response"):
                client.generate_response("Hello!")
