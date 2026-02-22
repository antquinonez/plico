import pytest
from unittest.mock import MagicMock, patch
import os


class TestFFAzureMistralInit:
    """Tests for FFAzureMistral initialization."""

    def test_init_with_api_key_and_endpoint(self, mock_azure_client):
        """Test initialization with explicit credentials."""
        with patch("src.Clients.FFAzureMistral.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureMistral import FFAzureMistral

            client = FFAzureMistral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            assert client.api_key == "test-key"
            assert client.endpoint == "https://test.endpoint.com"
            assert client.model == "mistral-large-2411"

    def test_init_missing_credentials_raises(self):
        """Test that missing credentials raise ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFAzureMistral.ChatCompletionsClient"):
                from src.Clients.FFAzureMistral import FFAzureMistral

                with pytest.raises(ValueError, match="API key not found"):
                    FFAzureMistral()


class TestFFAzureMistralGenerateResponse:
    """Tests for FFAzureMistral generate_response method."""

    def test_generate_response_basic(self, mock_azure_client, mock_azure_response):
        """Test basic response generation."""
        with patch("src.Clients.FFAzureMistral.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureMistral import FFAzureMistral

            client = FFAzureMistral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )
            response = client.generate_response("Hello!")

            assert response == "This is a test response."
            mock_azure_client.complete.assert_called_once()

    def test_generate_response_with_model_override(self, mock_azure_client):
        """Test response generation with model override."""
        with patch("src.Clients.FFAzureMistral.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureMistral import FFAzureMistral

            client = FFAzureMistral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )
            client.generate_response("Hello!", model="custom-model")

            call_kwargs = mock_azure_client.complete.call_args.kwargs
            assert "model" in call_kwargs


class TestFFAzureMistralSmallInit:
    """Tests for FFAzureMistralSmall initialization."""

    def test_init_with_api_key_and_endpoint(self, mock_azure_client):
        """Test initialization with explicit credentials."""
        with patch(
            "src.Clients.FFAzureMistralSmall.ChatCompletionsClient"
        ) as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureMistralSmall import FFAzureMistralSmall

            client = FFAzureMistralSmall(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            assert client.api_key == "test-key"
            assert client.model == "mistral-small-2503"


class TestFFAzureCodestralInit:
    """Tests for FFAzureCodestral initialization."""

    def test_init_with_api_key_and_endpoint(self, mock_azure_client):
        """Test initialization with explicit credentials."""
        with patch("src.Clients.FFAzureCodestral.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureCodestral import FFAzureCodestral

            client = FFAzureCodestral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            assert client.api_key == "test-key"
            assert client.model == "codestral-2501"

    def test_generate_code_method(self, mock_azure_client, mock_azure_response):
        """Test the generate_code helper method."""
        with patch("src.Clients.FFAzureCodestral.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureCodestral import FFAzureCodestral

            client = FFAzureCodestral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )
            response = client.generate_code("Write a hello world", language="python")

            assert response == "This is a test response."

    def test_explain_code_method(self, mock_azure_client, mock_azure_response):
        """Test the explain_code helper method."""
        with patch("src.Clients.FFAzureCodestral.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureCodestral import FFAzureCodestral

            client = FFAzureCodestral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )
            response = client.explain_code("print('hello')")

            assert response == "This is a test response."


class TestFFAzureDeepSeekInit:
    """Tests for FFAzureDeepSeek initialization."""

    def test_init_with_api_key_and_endpoint(self, mock_azure_client):
        """Test initialization with explicit credentials."""
        with patch("src.Clients.FFAzureDeepSeek.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureDeepSeek import FFAzureDeepSeek

            client = FFAzureDeepSeek(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            assert client.api_key == "test-key"
            assert client.model == "DeepSeek-R1"


class TestFFAzureDeepSeekV3Init:
    """Tests for FFAzureDeepSeekV3 initialization."""

    def test_init_with_api_key_and_endpoint(self, mock_azure_client):
        """Test initialization with explicit credentials."""
        with patch("src.Clients.FFAzureDeepSeekV3.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureDeepSeekV3 import FFAzureDeepSeekV3

            client = FFAzureDeepSeekV3(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            assert client.api_key == "test-key"
            assert "deepseek" in client.model.lower()


class TestFFAzureMSDeepSeekR1Init:
    """Tests for FFAzureMSDeepSeekR1 initialization."""

    def test_init_with_api_key_and_endpoint(self, mock_azure_client):
        """Test initialization with explicit credentials."""
        with patch(
            "src.Clients.FFAzureMSDeepSeekR1.ChatCompletionsClient"
        ) as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureMSDeepSeekR1 import FFAzureMSDeepSeekR1

            client = FFAzureMSDeepSeekR1(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            assert client.api_key == "test-key"
            assert client.model == "MAI-DS-R1"


class TestFFAzurePhiInit:
    """Tests for FFAzurePhi initialization."""

    def test_init_with_api_key_and_endpoint(self, mock_azure_client):
        """Test initialization with explicit credentials."""
        with patch("src.Clients.FFAzurePhi.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzurePhi import FFAzurePhi

            client = FFAzurePhi(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            assert client.api_key == "test-key"
            assert client.model == "phi-4"


class TestFFAzureClientCommonMethods:
    """Tests for common methods across Azure clients."""

    def test_azure_mistral_conversation_management(self, mock_azure_client):
        """Test conversation history management."""
        with patch("src.Clients.FFAzureMistral.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureMistral import FFAzureMistral

            client = FFAzureMistral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            client.set_conversation_history([{"role": "user", "content": "test"}])
            history = client.get_conversation_history()
            assert len(history) == 1

            client.clear_conversation()
            assert client.conversation_history == []

    def test_azure_client_test_connection(self, mock_azure_client, mock_azure_response):
        """Test connection testing."""
        with patch("src.Clients.FFAzureMistral.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureMistral import FFAzureMistral

            client = FFAzureMistral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            result = client.test_connection()
            assert result is True

    def test_azure_client_test_connection_failure(self, mock_azure_client):
        """Test connection test failure."""
        with patch("src.Clients.FFAzureMistral.ChatCompletionsClient") as MockClient:
            mock_azure_client.complete.side_effect = Exception("Connection failed")
            MockClient.return_value = mock_azure_client

            from src.Clients.FFAzureMistral import FFAzureMistral

            client = FFAzureMistral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            result = client.test_connection()
            assert result is False

    def test_azure_client_add_tool_result(self, mock_azure_client):
        """Test adding tool results to history."""
        with patch("src.Clients.FFAzureMistral.ChatCompletionsClient") as MockClient:
            MockClient.return_value = mock_azure_client
            from src.Clients.FFAzureMistral import FFAzureMistral

            client = FFAzureMistral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            client.add_tool_result("call_123", {"result": "success"})

            assert len(client.conversation_history) == 1
            assert client.conversation_history[0]["role"] == "tool"
            assert client.conversation_history[0]["tool_call_id"] == "call_123"


class TestFFAzureClientErrorHandling:
    """Tests for error handling in Azure clients."""

    def test_generate_response_api_error(self, mock_azure_client):
        """Test handling API errors."""
        with patch("src.Clients.FFAzureMistral.ChatCompletionsClient") as MockClient:
            mock_azure_client.complete.side_effect = Exception("API Error")
            MockClient.return_value = mock_azure_client

            from src.Clients.FFAzureMistral import FFAzureMistral

            client = FFAzureMistral(
                api_key="test-key", endpoint="https://test.endpoint.com"
            )

            with pytest.raises(RuntimeError, match="Error generating response"):
                client.generate_response("Hello!")
