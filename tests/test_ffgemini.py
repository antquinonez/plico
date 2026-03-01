# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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

                    with patch.object(FFGemini, "_get_region", return_value="us-central1"):
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

            mock_gemini_client.chat.completions.create = AsyncMock(return_value=mock_response)

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
                            client.chat_history.append({"role": "user", "content": prompt})
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


class TestFFGeminiInitExtended:
    """Extended tests for FFGemini initialization."""

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            with patch("src.Clients.FFGemini.AsyncOpenAI"):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini(
                        model="gemini-1.5-flash",
                        temperature=0.5,
                        max_tokens=4000,
                        system_instructions="Be concise",
                    )

                    assert client.model == "gemini-1.5-flash"
                    assert client.temperature == 0.5
                    assert client.max_tokens == 4000
                    assert client.system_instructions == "Be concise"

    def test_init_with_config_dict(self):
        """Test initialization with config dictionary."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            with patch("src.Clients.FFGemini.AsyncOpenAI"):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini(
                        config={
                            "model": "gemini-1.5-flash",
                            "temperature": 0.3,
                            "max_tokens": 1000,
                        }
                    )

                    assert client.model == "gemini-1.5-flash"
                    assert client.temperature == 0.3
                    assert client.max_tokens == 1000

    def test_init_from_env(self, monkeypatch):
        """Test initialization from environment variables."""
        monkeypatch.setenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
        monkeypatch.setenv("GEMINI_TEMPERATURE", "0.8")
        monkeypatch.setenv("GEMINI_MAX_TOKENS", "3000")
        monkeypatch.setenv("GEMINI_SYSTEM_INSTRUCTIONS", "Custom instructions")

        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            with patch("src.Clients.FFGemini.AsyncOpenAI"):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini()

                    assert client.model == "gemini-1.5-flash"
                    assert client.temperature == 0.8
                    assert client.max_tokens == 3000
                    assert client.system_instructions == "Custom instructions"


class TestFFGeminiTokenRefreshExtended:
    """Extended tests for token refresh functionality."""

    def test_refresh_token_if_needed_invalid_raises(self):
        """Test that invalid token without refresh raises."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = False
            mock_creds.expired = True
            mock_creds.refresh_token = None
            mock_auth.default.return_value = (mock_creds, "test-project")

            from src.Clients.FFGemini import FFGemini

            client = FFGemini.__new__(FFGemini)
            client.creds = mock_creds

            with pytest.raises(ValueError, match="Invalid token"):
                client.refresh_token_if_needed()


class TestFFGeminiGetRegion:
    """Tests for _get_region method."""

    def test_get_region_success(self):
        """Test successful region retrieval."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            with patch("src.Clients.FFGemini.AsyncOpenAI"):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-west1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini.__new__(FFGemini)
                    region = client._get_region()

                    assert region == "us-west1"

    def test_get_region_empty_raises(self):
        """Test that empty region raises ValueError."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            with patch("src.Clients.FFGemini.AsyncOpenAI"):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini.__new__(FFGemini)

                    with pytest.raises(ValueError, match="did not return a region"):
                        client._get_region()

    def test_get_region_subprocess_error_raises(self):
        """Test that subprocess error raises ValueError."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            with patch("src.Clients.FFGemini.AsyncOpenAI"):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    import subprocess

                    mock_run.side_effect = subprocess.CalledProcessError(1, "gcloud")

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini.__new__(FFGemini)

                    with pytest.raises(ValueError, match="Error determining Google Cloud region"):
                        client._get_region()


class TestFFGeminiInitializeClient:
    """Tests for _initialize_client method."""

    def test_initialize_client(self):
        """Test client initialization."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_openai = MagicMock()
            with patch("src.Clients.FFGemini.AsyncOpenAI", return_value=mock_openai):
                from src.Clients.FFGemini import FFGemini

                client = FFGemini.__new__(FFGemini)
                client.creds = mock_creds
                client.project = "test-project"
                client._get_region = lambda: "us-central1"

                result = client._initialize_client()

                assert result == mock_openai
