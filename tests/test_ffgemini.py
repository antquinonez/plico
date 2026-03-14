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

                        async def mock_generate(prompt, **kwargs):
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

            async def mock_generate(prompt, **kwargs):
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


class TestFFGeminiClone:
    """Tests for clone functionality."""

    def test_clone_returns_new_instance(self):
        """Test that clone returns a new instance."""
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

                    cloned = client.clone()

                    assert cloned is not client
                    assert isinstance(cloned, FFGemini)

    def test_clone_has_empty_history(self):
        """Test that cloned client has empty history."""
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
                    client.chat_history = [
                        {"role": "user", "content": "test"},
                        {"role": "assistant", "content": "response"},
                    ]

                    cloned = client.clone()

                    assert cloned.chat_history == []
                    assert len(client.chat_history) == 2

    def test_clone_preserves_config(self):
        """Test that clone preserves configuration."""
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
                        temperature=0.3,
                        max_tokens=1000,
                        system_instructions="Custom instructions",
                    )

                    cloned = client.clone()

                    assert cloned.model == "gemini-1.5-flash"
                    assert cloned.temperature == 0.3
                    assert cloned.max_tokens == 1000
                    assert cloned.system_instructions == "Custom instructions"


class TestFFGeminiConnectionTest:
    """Tests for connection testing."""

    def test_test_connection_success(self, mock_gemini_client):
        """Test successful connection test."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_gemini_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("src.Clients.FFGemini.AsyncOpenAI", return_value=mock_gemini_client):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini()

                    with patch.object(client, "refresh_token_if_needed"):
                        result = client.test_connection()

                    assert result is True

    def test_test_connection_failure(self, mock_gemini_client):
        """Test failed connection test."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_gemini_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            with patch("src.Clients.FFGemini.AsyncOpenAI", return_value=mock_gemini_client):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini()

                    with patch.object(client, "refresh_token_if_needed"):
                        result = client.test_connection()

                    assert result is False


class TestFFGeminiToolCalls:
    """Tests for tool calling functionality."""

    def test_generate_response_with_tool_calls(self, mock_gemini_client):
        """Test handling tool calls in response."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_tool_response = MagicMock()
            mock_tool_response.choices = [MagicMock()]
            mock_tool_response.choices[0].message.content = "Using tools"
            mock_tool_response.choices[0].message.tool_calls = [MagicMock()]
            mock_tool_response.choices[0].message.tool_calls[0].id = "call_123"
            mock_tool_response.choices[0].message.tool_calls[0].function.name = "get_weather"
            mock_tool_response.choices[0].message.tool_calls[
                0
            ].function.arguments = '{"city": "London"}'

            mock_gemini_client.chat.completions.create = AsyncMock(return_value=mock_tool_response)

            with patch("src.Clients.FFGemini.AsyncOpenAI", return_value=mock_gemini_client):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini()

                    with patch.object(client, "refresh_token_if_needed"):
                        response = client.generate_response_sync("What's the weather?")

                    assert "Tool calls detected" in response

    def test_add_tool_result(self):
        """Test adding tool result to history."""
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
                    client.add_tool_result("call_123", {"temp": 72})

                    assert len(client.chat_history) == 1
                    assert client.chat_history[0]["role"] == "tool"
                    assert client.chat_history[0]["tool_call_id"] == "call_123"

    def test_add_tool_result_string(self):
        """Test adding tool result as string."""
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
                    client.add_tool_result("call_456", "Simple string result")

                    assert len(client.chat_history) == 1
                    assert client.chat_history[0]["content"] == "Simple string result"


class TestFFGeminiParameterOverrides:
    """Tests for parameter override functionality."""

    def test_generate_response_with_temperature_override(self, mock_gemini_client):
        """Test overriding temperature."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].message.tool_calls = None

            mock_gemini_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("src.Clients.FFGemini.AsyncOpenAI", return_value=mock_gemini_client):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini()

                    with patch.object(client, "refresh_token_if_needed"):
                        client.generate_response_sync("Hello!", temperature=0.1)

                    call_args = mock_gemini_client.chat.completions.create.call_args
                    assert call_args.kwargs["temperature"] == 0.1

    def test_generate_response_with_max_tokens_override(self, mock_gemini_client):
        """Test overriding max_tokens."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].message.tool_calls = None

            mock_gemini_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("src.Clients.FFGemini.AsyncOpenAI", return_value=mock_gemini_client):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini()

                    with patch.object(client, "refresh_token_if_needed"):
                        client.generate_response_sync("Hello!", max_tokens=500)

                    call_args = mock_gemini_client.chat.completions.create.call_args
                    assert call_args.kwargs["max_tokens"] == 500

    def test_generate_response_with_system_instructions_override(self, mock_gemini_client):
        """Test overriding system instructions."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].message.tool_calls = None

            mock_gemini_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("src.Clients.FFGemini.AsyncOpenAI", return_value=mock_gemini_client):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini()

                    with patch.object(client, "refresh_token_if_needed"):
                        client.generate_response_sync("Hello!", system_instructions="Be brief.")

                    call_args = mock_gemini_client.chat.completions.create.call_args
                    messages = call_args.kwargs["messages"]

                    system_msg = next(m for m in messages if m["role"] == "system")
                    assert system_msg["content"] == "Be brief."

    def test_generate_response_with_json_format(self, mock_gemini_client):
        """Test JSON response format."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = '{"result": "success"}'
            mock_response.choices[0].message.tool_calls = None

            mock_gemini_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("src.Clients.FFGemini.AsyncOpenAI", return_value=mock_gemini_client):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini()

                    with patch.object(client, "refresh_token_if_needed"):
                        client.generate_response_sync(
                            "Give me JSON", response_format={"type": "json_object"}
                        )

                    call_args = mock_gemini_client.chat.completions.create.call_args
                    assert call_args.kwargs["response_format"] == {"type": "json_object"}

    def test_generate_response_with_top_p(self, mock_gemini_client):
        """Test top_p parameter."""
        with patch("src.Clients.FFGemini.google.auth") as mock_auth:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.token = "test-token"
            mock_auth.default.return_value = (mock_creds, "test-project")

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].message.tool_calls = None

            mock_gemini_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with patch("src.Clients.FFGemini.AsyncOpenAI", return_value=mock_gemini_client):
                with patch("src.Clients.FFGemini.subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "us-central1\n"
                    mock_run.return_value = mock_result

                    from src.Clients.FFGemini import FFGemini

                    client = FFGemini()

                    with patch.object(client, "refresh_token_if_needed"):
                        client.generate_response_sync("Hello!", top_p=0.9)

                    call_args = mock_gemini_client.chat.completions.create.call_args
                    assert call_args.kwargs["top_p"] == 0.9


class TestFFGeminiConversationHistory:
    """Tests for conversation history aliases."""

    def test_get_conversation_history_alias(self):
        """Test get_conversation_history alias."""
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
                    client.chat_history = [{"role": "user", "content": "test"}]

                    history = client.get_conversation_history()

                    assert len(history) == 1
                    assert history[0]["content"] == "test"

    def test_set_conversation_history_alias(self):
        """Test set_conversation_history alias."""
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
                    new_history = [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi!"},
                    ]

                    client.set_conversation_history(new_history)

                    assert client.chat_history == new_history

    def test_clear_conversation_alias(self):
        """Test clear_conversation clears history."""
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
                    client.chat_history = [{"role": "user", "content": "test"}]

                    client.clear_conversation()

                    assert client.chat_history == []
