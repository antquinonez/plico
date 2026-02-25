from unittest.mock import patch


class TestFFAIInit:
    """Tests for FFAI initialization."""

    def test_init_basic(self, mock_ffmistralsmall):
        """Test basic FFAI initialization."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        assert ffai.client == mock_ffmistralsmall
        assert ffai.history == []
        assert ffai.clean_history == []
        assert ffai.prompt_attr_history == []

    def test_init_with_persistence(self, mock_ffmistralsmall, tmp_path):
        """Test FFAI initialization with persistence options."""
        from src.FFAI import FFAI

        ffai = FFAI(
            mock_ffmistralsmall,
            persist_dir=str(tmp_path),
            persist_name="test",
            auto_persist=True,
        )

        assert ffai.persist_dir == str(tmp_path)
        assert ffai.persist_name == "test"
        assert ffai.auto_persist is True

    def test_init_creates_persist_dir(self, mock_ffmistralsmall, tmp_path):
        """Test that persist_dir is created if it doesn't exist."""
        from src.FFAI import FFAI

        new_dir = str(tmp_path / "new_persist_dir")

        ffai = FFAI(
            mock_ffmistralsmall,
            persist_dir=new_dir,
        )

        import os

        assert os.path.exists(new_dir)


class TestFFAIGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(self, mock_ffmistralsmall):
        """Test basic response generation."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        response = ffai.generate_response("Hello!")

        assert response == "This is a test response."
        assert len(ffai.history) == 1

    def test_generate_response_with_prompt_name(self, mock_ffmistralsmall):
        """Test response generation with prompt_name."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        response = ffai.generate_response("Hello!", prompt_name="greeting")

        assert ffai.history[0]["prompt_name"] == "greeting"

    def test_generate_response_with_history(self, mock_ffmistralsmall):
        """Test response generation with history dependencies."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        ffai.generate_response("What is 2+2?", prompt_name="math")
        ffai.generate_response("How are you?", prompt_name="greeting")
        ffai.generate_response(
            "What was my math question?",
            prompt_name="followup",
            history=["math", "greeting"],
        )

        assert len(ffai.history) == 3
        assert ffai.history[2]["history"] == ["math", "greeting"]

    def test_generate_response_adds_to_permanent_history(self, mock_ffmistralsmall):
        """Test that responses are added to permanent history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Hello!")

        assert len(ffai.permanent_history.turns) == 2
        assert ffai.permanent_history.turns[0]["role"] == "user"
        assert ffai.permanent_history.turns[1]["role"] == "assistant"

    def test_generate_response_with_model_override(self, mock_ffmistralsmall):
        """Test overriding model."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Hello!", model="custom-model")

        assert ffai.history[0]["model"] == "custom-model"


class TestFFAIHistoryAccess:
    """Tests for history access methods."""

    def test_get_interaction_history(self, mock_ffmistralsmall):
        """Test getting interaction history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="a")
        ffai.generate_response("Q2", prompt_name="b")

        history = ffai.get_interaction_history()

        assert len(history) == 2
        assert history[0]["prompt_name"] == "a"

    def test_get_clean_interaction_history(self, mock_ffmistralsmall):
        """Test getting clean interaction history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Hello!", prompt_name="test")

        clean_history = ffai.get_clean_interaction_history()

        assert len(clean_history) == 1

    def test_get_prompt_attr_history(self, mock_ffmistralsmall):
        """Test getting prompt attribute history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Hello!", prompt_name="test")

        attr_history = ffai.get_prompt_attr_history()

        assert len(attr_history) == 1

    def test_get_latest_interaction(self, mock_ffmistralsmall):
        """Test getting latest interaction."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("First", prompt_name="a")
        ffai.generate_response("Second", prompt_name="b")

        latest = ffai.get_latest_interaction()

        assert latest["prompt_name"] == "b"

    def test_get_latest_interaction_empty(self, mock_ffmistralsmall):
        """Test getting latest interaction when history is empty."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        latest = ffai.get_latest_interaction()

        assert latest is None

    def test_get_latest_interaction_by_prompt_name(self, mock_ffmistralsmall):
        """Test getting latest interaction by prompt name."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="qa")
        ffai.generate_response("Q2", prompt_name="qa")
        ffai.generate_response("Q3", prompt_name="other")

        latest_qa = ffai.get_latest_interaction_by_prompt_name("qa")

        assert latest_qa["prompt"] == "Q2"

    def test_get_last_n_interactions(self, mock_ffmistralsmall):
        """Test getting last N interactions."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        for i in range(5):
            ffai.generate_response(f"Q{i}", prompt_name=f"p{i}")

        last_3 = ffai.get_last_n_interactions(3)

        assert len(last_3) == 3
        assert last_3[2]["prompt_name"] == "p4"


class TestFFAIClientManagement:
    """Tests for client management."""

    def test_set_client(self, mock_ffmistralsmall):
        """Test switching clients."""
        from src.Clients.FFMistral import FFMistral
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        with patch("src.Clients.FFMistral.Mistral"):
            new_client = FFMistral(api_key="new-key")
            ffai.set_client(new_client)

            assert ffai.client == new_client

    def test_clear_conversation(self, mock_ffmistralsmall):
        """Test clearing conversation."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Hello!")
        ffai.clear_conversation()

        assert mock_ffmistralsmall.conversation_history == []


class TestFFAIClientConversationHistory:
    """Tests for raw client conversation history access."""

    def test_get_client_conversation_history(self, mock_ffmistralsmall):
        """Test getting raw client conversation history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        mock_ffmistralsmall.conversation_history = [{"role": "user", "content": "test"}]

        history = ffai.get_client_conversation_history()

        assert history == [{"role": "user", "content": "test"}]

    def test_set_client_conversation_history(self, mock_ffmistralsmall):
        """Test setting raw client conversation history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        new_history = [{"role": "user", "content": "new"}]

        result = ffai.set_client_conversation_history(new_history)

        assert result is True
        assert mock_ffmistralsmall.conversation_history == new_history

    def test_add_client_message(self, mock_ffmistralsmall):
        """Test adding a message to client conversation history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        result = ffai.add_client_message("user", "New message")

        assert result is True
        assert len(mock_ffmistralsmall.conversation_history) == 1


class TestFFAIDataFrameExport:
    """Tests for DataFrame export functionality."""

    def test_history_to_dataframe(self, mock_ffmistralsmall):
        """Test converting history to DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Hello!", prompt_name="test")

        df = ffai.history_to_dataframe()

        assert not df.is_empty()
        assert len(df) == 1
        assert "prompt" in df.columns
        assert "response" in df.columns

    def test_history_to_dataframe_empty(self, mock_ffmistralsmall):
        """Test converting empty history to DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        df = ffai.history_to_dataframe()

        assert df.is_empty()

    def test_search_history_by_text(self, mock_ffmistralsmall):
        """Test searching history by text."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("What is machine learning?", prompt_name="ml")
        ffai.generate_response("What is for dinner?", prompt_name="food")

        results = ffai.search_history(text="machine")

        assert len(results) == 1
        assert results["prompt_name"][0] == "ml"

    def test_search_history_by_prompt_name(self, mock_ffmistralsmall):
        """Test searching history by prompt name."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="qa")
        ffai.generate_response("Q2", prompt_name="other")

        results = ffai.search_history(prompt_name="qa")

        assert len(results) == 1

    def test_get_model_usage_stats(self, mock_ffmistralsmall):
        """Test getting model usage statistics."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")
        ffai.generate_response("Q2")

        stats = ffai.get_model_usage_stats()

        assert "mistral-small-2503" in stats
        assert stats["mistral-small-2503"] == 2

    def test_get_prompt_name_usage_stats(self, mock_ffmistralsmall):
        """Test getting prompt name usage statistics."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="qa")
        ffai.generate_response("Q2", prompt_name="qa")
        ffai.generate_response("Q3", prompt_name="other")

        stats = ffai.get_prompt_name_usage_stats()

        assert stats["qa"] == 2
        assert stats["other"] == 1


class TestFFAICleanResponse:
    """Tests for response cleaning functionality."""

    def test_clean_response_preserves_normal_text(self, mock_ffmistralsmall):
        """Test that normal text is preserved in responses."""
        from src.FFAI import FFAI

        mock_ffmistralsmall.generate_response = lambda prompt, **kwargs: "Normal response text"

        ffai = FFAI(mock_ffmistralsmall)
        response = ffai.generate_response("Hello!")

        assert response == "Normal response text"


class TestFFAISystemInstructions:
    """Tests for system instructions handling."""

    def test_get_system_instructions(self, mock_ffmistralsmall):
        """Test getting system instructions from client."""
        from src.FFAI import FFAI

        mock_ffmistralsmall.system_instructions = "Be helpful."
        ffai = FFAI(mock_ffmistralsmall)

        instructions = ffai.get_system_instructions()

        assert instructions == "Be helpful."

    def test_get_system_instructions_none(self, mock_ffmistralsmall):
        """Test getting system instructions when client has none."""
        from src.FFAI import FFAI

        delattr(mock_ffmistralsmall, "system_instructions")
        ffai = FFAI(mock_ffmistralsmall)

        instructions = ffai.get_system_instructions()

        assert instructions is None
