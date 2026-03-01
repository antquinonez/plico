# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for FFAzureLiteLLM factory function."""

from unittest.mock import MagicMock, patch

from src.Clients.FFAzureLiteLLM import create_azure_client


class TestCreateAzureClientInit:
    """Tests for create_azure_client factory function."""

    def test_creates_client_with_required_params(self, monkeypatch):
        """Should create FFLiteLLMClient with required parameters."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-api-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client is not None
        assert client._model_string == "azure/mistral-small-2503"
        assert client.api_key == "test-api-key"
        assert client.api_base == "https://test.openai.azure.com"

    def test_creates_client_with_custom_settings(self, monkeypatch):
        """Should pass through custom settings."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        client = create_azure_client(
            deployment_name="gpt-4",
            env_prefix="AZURE_TEST",
            temperature=0.5,
            max_tokens=2000,
            system_instructions="Be helpful",
        )

        assert client.temperature == 0.5
        assert client.max_tokens == 2000
        assert client.system_instructions == "Be helpful"

    def test_uses_model_defaults(self, monkeypatch):
        """Should use model defaults when not overridden."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.max_tokens is not None
        assert client.temperature is not None

    def test_env_temperature_override(self, monkeypatch):
        """Should use temperature from env if set."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_TEST_TEMPERATURE", "0.9")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.temperature == 0.9

    def test_env_max_tokens_override(self, monkeypatch):
        """Should use max_tokens from env if set."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_TEST_MAX_TOKENS", "8000")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.max_tokens == 8000

    def test_env_system_instructions_override(self, monkeypatch):
        """Should use system_instructions from env if set."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_TEST_ASSISTANT_INSTRUCTIONS", "Custom instructions")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.system_instructions == "Custom instructions"

    def test_explicit_overrides_env(self, monkeypatch):
        """Explicit parameters should override env vars."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_TEST_TEMPERATURE", "0.9")
        monkeypatch.setenv("AZURE_TEST_MAX_TOKENS", "8000")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
            temperature=0.3,
            max_tokens=1000,
        )

        assert client.temperature == 0.3
        assert client.max_tokens == 1000

    def test_api_version_default(self, monkeypatch):
        """Should use default API version."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.api_version == "2024-02-01"

    def test_api_version_from_env(self, monkeypatch):
        """Should use API version from env if set."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_TEST_API_VERSION", "2024-08-01")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.api_version == "2024-08-01"

    def test_model_defaults_override(self, monkeypatch):
        """Should accept model_defaults parameter."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        client = create_azure_client(
            deployment_name="custom-model",
            env_prefix="AZURE_TEST",
            model_defaults={"temperature": 0.2, "max_tokens": 500},
        )

        assert client.temperature == 0.2
        assert client.max_tokens == 500

    def test_invalid_env_temperature_uses_default(self, monkeypatch):
        """Should fall back to default if env temperature is invalid."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_TEST_TEMPERATURE", "invalid")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.temperature is not None

    def test_invalid_env_max_tokens_uses_default(self, monkeypatch):
        """Should fall back to default if env max_tokens is invalid."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_TEST_MAX_TOKENS", "invalid")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.max_tokens is not None

    def test_missing_api_key(self, monkeypatch):
        """Should create client even without API key (validation happens at call time)."""
        monkeypatch.delenv("AZURE_TEST_KEY", raising=False)
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.api_key is None

    def test_missing_endpoint(self, monkeypatch):
        """Should create client even without endpoint (validation happens at call time)."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.delenv("AZURE_TEST_ENDPOINT", raising=False)

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        assert client.api_base is None

    def test_passes_additional_kwargs(self, monkeypatch):
        """Should pass additional kwargs to FFLiteLLMClient."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
            fallbacks=["openai/gpt-4"],
        )

        assert client._fallbacks == ["openai/gpt-4"]


class TestCreateAzureClientIntegration:
    """Integration tests for create_azure_client."""

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_generated_client_can_generate_response(self, mock_completion, monkeypatch):
        """Client from factory should work like any FFLiteLLMClient."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from Azure!"
        mock_completion.return_value = mock_response

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        response = client.generate_response("Hello!")

        assert response == "Hello from Azure!"
        mock_completion.assert_called_once()

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_client_conversation_history(self, mock_completion, monkeypatch):
        """Client should track conversation history."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_completion.return_value = mock_response

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        client.generate_response("Question 1")
        client.generate_response("Question 2")

        assert len(client.conversation_history) == 4

    def test_client_clone(self, monkeypatch):
        """Client should support cloning."""
        monkeypatch.setenv("AZURE_TEST_KEY", "test-key")
        monkeypatch.setenv("AZURE_TEST_ENDPOINT", "https://test.openai.azure.com")

        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_TEST",
        )

        clone = client.clone()

        assert clone is not client
        assert clone._model_string == client._model_string
