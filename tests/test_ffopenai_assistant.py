import pytest
from unittest.mock import MagicMock, patch
import os


@pytest.fixture
def mock_openai_assistant_client():
    """Mock OpenAI client for Assistant API."""
    client = MagicMock()

    mock_assistant = MagicMock()
    mock_assistant.id = "asst_test123"
    mock_assistant.name = "default"

    mock_thread = MagicMock()
    mock_thread.id = "thread_test123"

    mock_run = MagicMock()
    mock_run.id = "run_test123"
    mock_run.status = "completed"

    mock_message = MagicMock()
    mock_message.content = [MagicMock()]
    mock_message.content[0].text.value = "This is a test response."

    mock_messages = MagicMock()
    mock_messages.data = [mock_message]

    client.beta.assistants.retrieve.return_value = mock_assistant
    client.beta.assistants.list.return_value = MagicMock(data=[])
    client.beta.assistants.create.return_value = mock_assistant
    client.beta.threads.create.return_value = mock_thread
    client.beta.threads.messages.create.return_value = MagicMock()
    client.beta.threads.messages.list.return_value = mock_messages
    client.beta.threads.runs.create.return_value = mock_run
    client.beta.threads.runs.retrieve.return_value = mock_run

    return client


class TestFFOpenAIAssistantInit:
    """Tests for FFOpenAIAssistant initialization."""

    def test_init_with_api_key(self, mock_openai_assistant_client):
        """Test initialization with explicit API key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
                MockOpenAI.return_value = mock_openai_assistant_client
                from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

                client = FFOpenAIAssistant(api_key="test-key")

                assert client.api_key == "test-key"
                assert client.temperature == 0.5
                assert client.assistant_name == "default"

    def test_init_with_custom_params(self, mock_openai_assistant_client):
        """Test initialization with custom parameters."""
        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(
                api_key="test-key",
                model="gpt-4o",
                temperature=0.7,
                max_tokens=2000,
                assistant_name="custom-assistant",
                system_instructions="Be helpful.",
            )

            assert client.model == "gpt-4o"
            assert client.temperature == 0.7
            assert client.max_tokens == 2000
            assert client.assistant_name == "custom-assistant"
            assert client.system_instructions == "Be helpful."

    def test_init_missing_api_key_raises(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFOpenAIAssistant.OpenAI"):
                from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

                with pytest.raises(ValueError, match="API key not found"):
                    FFOpenAIAssistant()

    def test_init_with_existing_assistant_id(self, mock_openai_assistant_client):
        """Test initialization with existing assistant ID."""
        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(
                api_key="test-key", assistant_id="existing-assistant-id"
            )

            assert client.assistant_id == "asst_test123"
            mock_openai_assistant_client.beta.assistants.retrieve.assert_called_once()


class TestFFOpenAIAssistantGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(self, mock_openai_assistant_client):
        """Test basic response generation."""
        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(api_key="test-key")
            response = client.generate_response("Hello!")

            assert response == "This is a test response."

    def test_generate_response_creates_thread(self, mock_openai_assistant_client):
        """Test that response generation creates a thread if needed."""
        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(api_key="test-key")
            client.thread_id = None
            client.generate_response("Hello!")

            mock_openai_assistant_client.beta.threads.create.assert_called_once()
            assert client.thread_id == "thread_test123"

    def test_generate_response_uses_existing_thread(self, mock_openai_assistant_client):
        """Test that existing thread is reused."""
        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(api_key="test-key")
            client.thread_id = "existing-thread-id"
            client.generate_response("Hello!")

            mock_openai_assistant_client.beta.threads.create.assert_not_called()

    def test_generate_response_adds_message_to_thread(
        self, mock_openai_assistant_client
    ):
        """Test that user message is added to thread."""
        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(api_key="test-key")
            client.generate_response("Hello!")

            mock_openai_assistant_client.beta.threads.messages.create.assert_called_once()

    def test_generate_response_creates_run(self, mock_openai_assistant_client):
        """Test that a run is created for the thread."""
        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(api_key="test-key")
            client.generate_response("Hello!")

            mock_openai_assistant_client.beta.threads.runs.create.assert_called_once()


class TestFFOpenAIAssistantCreation:
    """Tests for assistant creation."""

    def test_creates_assistant_if_not_found(self, mock_openai_assistant_client):
        """Test that a new assistant is created if not found."""
        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(api_key="test-key")

            mock_openai_assistant_client.beta.assistants.create.assert_called_once()

    def test_reuses_existing_assistant_by_name(self, mock_openai_assistant_client):
        """Test that existing assistant is reused if name matches."""
        mock_assistant = MagicMock()
        mock_assistant.id = "existing-asst-id"
        mock_assistant.name = "my-assistant"

        mock_openai_assistant_client.beta.assistants.list.return_value = MagicMock(
            data=[mock_assistant]
        )

        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(
                api_key="test-key", assistant_name="my-assistant"
            )

            assert client.assistant_id == "existing-asst-id"
            mock_openai_assistant_client.beta.assistants.create.assert_not_called()


class TestFFOpenAIAssistantErrorHandling:
    """Tests for error handling."""

    def test_generate_response_api_error(self, mock_openai_assistant_client):
        """Test handling API error during response generation."""
        mock_openai_assistant_client.beta.threads.runs.create.side_effect = Exception(
            "API Error"
        )

        with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
            MockOpenAI.return_value = mock_openai_assistant_client
            from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

            client = FFOpenAIAssistant(api_key="test-key")

            with pytest.raises(RuntimeError, match="Error in OpenAI conversation"):
                client.generate_response("Hello!")

    def test_create_assistant_error(self, mock_openai_assistant_client):
        """Test handling assistant creation error."""
        mock_openai_assistant_client.beta.assistants.create.side_effect = Exception(
            "Creation failed"
        )

        with patch.dict(os.environ, {}, clear=True):
            with patch("src.Clients.FFOpenAIAssistant.OpenAI") as MockOpenAI:
                MockOpenAI.return_value = mock_openai_assistant_client
                from src.Clients.FFOpenAIAssistant import FFOpenAIAssistant

                with pytest.raises(
                    RuntimeError, match="Error creating OpenAI assistant"
                ):
                    FFOpenAIAssistant(api_key="test-key")
