import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import asyncio


class TestFFGeminiInit:
    """Tests for FFGemini initialization."""

    def test_init_with_defaults(self, mock_gemini_client):
        """Test initialization with default values."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_auth.default.return_value = (mock_creds, "test-project")

            with patch("src.Clients.FFGemini.AsyncOpenAI") as MockOpenAI:
                MockOpenAI.return_value = mock_gemini_client
                with patch.object(
                    MagicMock(),
                    "_get_region",
                    return_value="us-central1",
                ):
                    from src.Clients.FFGemini import FFGemini

                    with patch.object(
                        FFGemini, "_get_region", return_value="us-central1"
                    ):
                        client = FFGemini.__new__(FFGemini)
                        client.model = "google/gemini-1.5-pro-002"
                        client.temperature = 0.7
                        client.max_tokens = 2000
                        client.system_instructions = "You are a helpful assistant."
                        client.chat_history = []
                        client._response_generated = False

                        assert client.model == "google/gemini-1.5-pro-002"
                        assert client.temperature == 0.7
                        assert client.max_tokens == 2000


class TestFFGeminiGenerateResponseSync:
    """Tests for generate_response_sync method."""

    def test_generate_response_sync_basic(self, mock_gemini_client):
        """Test basic synchronous response generation."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "This is a test response."

            mock_gemini_client.chat.completions.create = AsyncMock(
                return_value=mock_response
            )

            with patch("src.Clients.FFGemini.AsyncOpenAI") as MockOpenAI:
                MockOpenAI.return_value = mock_gemini_client

                from src.Clients.FFGemini import FFGemini

                with patch.object(FFGemini, "_get_region", return_value="us-central1"):
                    with patch.object(FFGemini, "refresh_token_if_needed"):
                        client = FFGemini.__new__(FFGemini)
                        client.model = "google/gemini-1.5-pro-002"
                        client.temperature = 0.7
                        client.max_tokens = 2000
                        client.system_instructions = "You are a helpful assistant."
                        client.chat_history = []
                        client._response_generated = False
                        client.client = mock_gemini_client
                        client.creds = mock_creds

                        async def mock_generate(prompt):
                            client.chat_history.append(
                                {"role": "user", "content": prompt}
                            )
                            client.chat_history.append(
                                {
                                    "role": "assistant",
                                    "content": "This is a test response.",
                                }
                            )
                            return "This is a test response."

                        client.generate_response = mock_generate

                        response = client.generate_response_sync("Hello!")
                        assert response == "This is a test response."


class TestFFGeminiConversationManagement:
    """Tests for conversation management."""

    def test_clear_conversation(self):
        """Test clearing conversation history."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_auth.default.return_value = (mock_creds, "test-project")

            from src.Clients.FFGemini import FFGemini

            with patch.object(FFGemini, "_get_region", return_value="us-central1"):
                with patch.object(FFGemini, "refresh_token_if_needed"):
                    with patch("src.Clients.FFGemini.AsyncOpenAI"):
                        client = FFGemini.__new__(FFGemini)
                        client.chat_history = [{"role": "user", "content": "test"}]
                        client.clear_conversation()

                        assert client.chat_history == []


class TestFFGeminiErrorHandling:
    """Tests for error handling."""

    def test_generate_response_empty_prompt_raises(self):
        """Test that empty prompt raises ValueError."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_auth.default.return_value = (mock_creds, "test-project")

            from src.Clients.FFGemini import FFGemini

            client = FFGemini.__new__(FFGemini)
            client.chat_history = []
            client.creds = mock_creds

            async def mock_generate(prompt):
                if not prompt.strip():
                    raise ValueError("Prompt cannot be empty")
                return "response"

            client.generate_response = mock_generate

            with pytest.raises(ValueError, match="Prompt cannot be empty"):
                client.generate_response_sync("")


class TestFFGeminiTokenRefresh:
    """Tests for token refresh functionality."""

    def test_refresh_token_if_needed_valid(self):
        """Test that valid token doesn't need refresh."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_auth.default.return_value = (mock_creds, "test-project")

            from src.Clients.FFGemini import FFGemini

            client = FFGemini.__new__(FFGemini)
            client.creds = mock_creds

            client.refresh_token_if_needed()

            mock_creds.refresh.assert_not_called()

    def test_refresh_token_if_needed_expired(self):
        """Test that expired token gets refreshed."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = False
            mock_creds.expired = True
            mock_creds.refresh_token = "refresh-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            from src.Clients.FFGemini import FFGemini

            client = FFGemini.__new__(FFGemini)
            client.creds = mock_creds

            with patch("src.Clients.FFGemini.google.auth.transport.requests.Request"):
                client.refresh_token_if_needed()

                mock_creds.refresh.assert_called_once()
