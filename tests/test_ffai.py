# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from unittest.mock import patch

import pytest


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


class TestFFAIClientHistorySuspension:
    """Tests for automatic client history suspension when using declarative context."""

    def test_declarative_history_suspends_client_history(self, mock_ffmistralsmall):
        """Verify client history is empty during call when history parameter is provided."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        # First, build up some client history
        ffai.generate_response("First question")
        ffai.generate_response("Second question")
        assert len(mock_ffmistralsmall.conversation_history) == 4  # 2 user + 2 assistant

        # Now use declarative context - client history should be suspended
        ffai.generate_response(
            "Third question with context", prompt_name="contextual", history=["nonexistent"]
        )

        # After the call, client history should still have original 4 messages
        # The call with history should NOT have added to client history
        assert len(mock_ffmistralsmall.conversation_history) == 4

    def test_client_history_restored_after_declarative_call(self, mock_ffmistralsmall):
        """Verify client history is restored after a call with declarative context."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        # Build up client history
        ffai.generate_response("Question A")
        original_history = mock_ffmistralsmall.conversation_history.copy()
        assert len(original_history) == 2

        # Use declarative context
        ffai.generate_response("Question B", history=["some_context"])

        # History should be exactly the same as before the declarative call
        assert mock_ffmistralsmall.conversation_history == original_history

    def test_no_history_param_accumulates_client_history(self, mock_ffmistralsmall):
        """Verify backward compatibility: no history param means client history accumulates."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        ffai.generate_response("Question 1")
        assert len(mock_ffmistralsmall.conversation_history) == 2

        ffai.generate_response("Question 2")
        assert len(mock_ffmistralsmall.conversation_history) == 4

        ffai.generate_response("Question 3")
        assert len(mock_ffmistralsmall.conversation_history) == 6

    def test_empty_history_list_suspends_client_history(self, mock_ffmistralsmall):
        """Verify that history=[] also suspends client history (edge case)."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        ffai.generate_response("Build up history")
        assert len(mock_ffmistralsmall.conversation_history) == 2

        # Even with empty list, should suspend
        ffai.generate_response("With empty history", history=[])
        assert len(mock_ffmistralsmall.conversation_history) == 2

    def test_ffai_history_still_records_with_declarative_context(self, mock_ffmistralsmall):
        """Verify FFAI's tracking structures still record turns even when client history is suspended."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        ffai.generate_response("Question 1", prompt_name="q1")
        ffai.generate_response("Question 2", prompt_name="q2", history=["q1"])

        # FFAI should record both interactions
        assert len(ffai.history) == 2
        assert len(ffai.prompt_attr_history) == 2
        assert ffai.history[1]["history"] == ["q1"]

        # permanent_history should also have both
        assert len(ffai.permanent_history.turns) == 4  # 2 user + 2 assistant

    def test_mixed_calls_declarative_and_normal(self, mock_ffmistralsmall):
        """Test mixing calls with and without declarative context."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        # Normal call - adds to client history
        ffai.generate_response("Normal 1", prompt_name="n1")
        assert len(mock_ffmistralsmall.conversation_history) == 2

        # Declarative call - suspended
        ffai.generate_response("Declarative 1", prompt_name="d1", history=["n1"])
        assert len(mock_ffmistralsmall.conversation_history) == 2  # Still 2

        # Another normal call - adds to client history
        ffai.generate_response("Normal 2", prompt_name="n2")
        assert len(mock_ffmistralsmall.conversation_history) == 4  # Now 4

        # Another declarative call - suspended, but sees all 4 client history messages
        ffai.generate_response("Declarative 2", prompt_name="d2", history=["n2"])
        assert len(mock_ffmistralsmall.conversation_history) == 4  # Still 4

        # FFAI should have all 4 interactions recorded
        assert len(ffai.history) == 4

    def test_api_receives_no_client_history_during_suspension(self, mock_ffmistralsmall):
        """Verify the API call receives empty client history when suspended."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        # Build up client history
        ffai.generate_response("First question", prompt_name="q1")
        ffai.generate_response("Second question", prompt_name="q2")
        assert len(mock_ffmistralsmall.conversation_history) == 4

        # Track what messages were actually sent to the API
        captured_messages = []

        original_complete = mock_ffmistralsmall.client.chat.complete

        def capture_api_call(**kwargs):
            captured_messages.append(kwargs.get("messages", []))
            return original_complete(**kwargs)

        mock_ffmistralsmall.client.chat.complete = capture_api_call

        # Make declarative call - should NOT include accumulated client history
        ffai.generate_response("Third question", prompt_name="q3", history=["q1"])

        # Verify API received empty conversation (just system + current prompt)
        assert len(captured_messages) == 1
        api_messages = captured_messages[0]

        # Should have: system message + current user prompt (with injected context)
        # Should NOT have: the 4 messages from q1 and q2
        user_messages = [m for m in api_messages if m["role"] == "user"]
        assert len(user_messages) == 1, (
            "API should receive only 1 user message (the current prompt)"
        )
        assert "Third question" in user_messages[0]["content"]
        assert "conversation_history" in user_messages[0]["content"], (
            "Should include declarative context"
        )

    def test_api_receives_full_client_history_when_not_suspended(self, mock_ffmistralsmall):
        """Verify the API call receives full client history when NOT using declarative context."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        # Build up client history
        ffai.generate_response("First question")
        ffai.generate_response("Second question")

        # Track what messages were sent
        captured_messages = []

        original_complete = mock_ffmistralsmall.client.chat.complete

        def capture_api_call(**kwargs):
            captured_messages.append(kwargs.get("messages", []))
            return original_complete(**kwargs)

        mock_ffmistralsmall.client.chat.complete = capture_api_call

        # Normal call - SHOULD include all accumulated client history
        ffai.generate_response("Third question")

        api_messages = captured_messages[0]
        user_messages = [m for m in api_messages if m["role"] == "user"]

        # Should have all 3 user messages from conversation history
        assert len(user_messages) == 3, "API should receive all 3 user messages from client history"


class TestFFAIExtractJson:
    """Tests for _extract_json method.

    Note: The method only extracts JSON if valid JSON is found within the first 20 characters.
    """

    def test_extract_json_plain_json(self, mock_ffmistralsmall):
        """Test extracting plain JSON (starts with valid JSON in first 20 chars)."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        result = ffai._extract_json('{"key": "value"}')

        assert result == {"key": "value"}

    def test_extract_json_short_object(self, mock_ffmistralsmall):
        """Test extracting short JSON object."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        result = ffai._extract_json('{"a": 1}')

        assert result == {"a": 1}

    def test_extract_json_no_json_in_first_20(self, mock_ffmistralsmall):
        """Test returns None when no JSON in first 20 chars."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        # Markdown doesn't have JSON in first 20 chars
        result = ffai._extract_json('```json\n{"key": "value"}\n```')

        assert result is None

    def test_extract_json_no_json(self, mock_ffmistralsmall):
        """Test returns None when no JSON found."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        result = ffai._extract_json("This is just plain text")

        assert result is None


class TestFFAICleanResponseExtended:
    """Extended tests for _clean_response method."""

    def test_clean_response_removes_think_tags(self, mock_ffmistralsmall):
        """Test removing think tags from response."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        # Use proper think tag format with closing >
        result = ffai._clean_response("<think internal thoughts</think >Real answer")

        assert "<think" not in result
        assert "Real answer" in result

    def test_clean_response_non_string(self, mock_ffmistralsmall):
        """Test non-string response is returned as-is."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        result = ffai._clean_response({"already": "dict"})

        assert result == {"already": "dict"}

    def test_clean_response_dict_with_think_tags(self, mock_ffmistralsmall):
        """Test cleaning think tags from dict values."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        # JSON with think tags in value (short enough to be in first 20 chars)
        result = ffai._clean_response('{"a":"<think x</think >y"}')

        assert result == {"a": "y"}

    def test_clean_response_json_array(self, mock_ffmistralsmall):
        """Test response with JSON array returns as-is."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        # JSON arrays starting in first 20 chars
        result = ffai._clean_response("[1, 2, 3]")

        assert result == [1, 2, 3]

    def test_clean_response_no_json(self, mock_ffmistralsmall):
        """Test plain text response without JSON."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        result = ffai._clean_response("Just plain text")

        assert result == "Just plain text"


class TestFFAIBuildPrompt:
    """Tests for _build_prompt method."""

    def test_build_prompt_no_history(self, mock_ffmistralsmall):
        """Test building prompt without history returns original."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        result = ffai._build_prompt("Test prompt", history=None)

        assert result == "Test prompt"

    def test_build_prompt_empty_history_list(self, mock_ffmistralsmall):
        """Test building prompt with empty history list."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        result = ffai._build_prompt("Test prompt", history=[])

        assert result == "Test prompt"

    def test_build_prompt_with_matching_history(self, mock_ffmistralsmall):
        """Test building prompt with matching history entries."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.prompt_attr_history = [
            {"prompt_name": "prev", "prompt": "Previous Q", "response": "Previous A"}
        ]

        result = ffai._build_prompt("New question", history=["prev"])

        assert "<conversation_history>" in result
        assert "Previous Q" in result
        assert "Previous A" in result

    def test_build_prompt_missing_history_entry(self, mock_ffmistralsmall):
        """Test building prompt with missing history entry."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.prompt_attr_history = []

        result = ffai._build_prompt("New question", history=["missing"])

        assert result == "New question"

    def test_build_prompt_multiple_history_entries(self, mock_ffmistralsmall):
        """Test building prompt with multiple history entries."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.prompt_attr_history = [
            {"prompt_name": "q1", "prompt": "Q1", "response": "A1"},
            {"prompt_name": "q2", "prompt": "Q2", "response": "A2"},
        ]

        result = ffai._build_prompt("New", history=["q1", "q2"])

        assert "Q1" in result
        assert "A1" in result
        assert "Q2" in result
        assert "A2" in result

    def test_build_prompt_uses_latest_matching(self, mock_ffmistralsmall):
        """Test uses latest entry when multiple matches exist."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.prompt_attr_history = [
            {"prompt_name": "q1", "prompt": "Q1 old", "response": "A1 old"},
            {"prompt_name": "q1", "prompt": "Q1 new", "response": "A1 new"},
        ]

        result = ffai._build_prompt("New", history=["q1"])

        assert "Q1 new" in result
        assert "A1 new" in result


class TestFFAIGenerateResponseExtended:
    """Extended tests for generate_response method."""

    def test_generate_response_with_dependencies_dedup(self, mock_ffmistralsmall):
        """Test dependencies are deduplicated."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="a")
        ffai.generate_response("Q2", dependencies=["a", "a", "b", "b"])

        assert ffai.history[1]["history"] is None

    def test_generate_response_json_response_stores_attrs(self, mock_ffmistralsmall):
        """Test JSON response stores attributes separately."""
        from src.FFAI import FFAI

        # Return JSON that starts immediately (in first 20 chars)
        mock_ffmistralsmall.generate_response = lambda prompt, **kwargs: '{"a":"1","b":"2"}'

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Test")

        # Should store 2 entries: one for each JSON attribute
        # (the original interaction is NOT stored separately when response is JSON)
        assert len(ffai.prompt_attr_history) == 2
        assert ffai.prompt_attr_history[0]["prompt"] == "a"
        assert ffai.prompt_attr_history[1]["prompt"] == "b"

    def test_generate_response_with_system_instructions(self, mock_ffmistralsmall):
        """Test system instructions are passed to client."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Test", system_instructions="Be helpful")

        assert len(ffai.history) == 1

    def test_generate_response_with_thread_lock(self, mock_ffmistralsmall):
        """Test thread lock is used when provided."""
        import threading

        from src.FFAI import FFAI

        lock = threading.Lock()
        ffai = FFAI(mock_ffmistralsmall, history_lock=lock)
        ffai.generate_response("Test")

        assert len(ffai.prompt_attr_history) == 1


class TestFFAIHistoryAccessExtended:
    """Extended tests for history access methods."""

    def test_get_interaction(self, mock_ffmistralsmall):
        """Test getting interaction by sequence number."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="a")
        ffai.generate_response("Q2", prompt_name="b")

        interaction = ffai.get_interaction(1)

        assert interaction is not None
        assert interaction["prompt_name"] == "a"

    def test_get_interaction_not_found(self, mock_ffmistralsmall):
        """Test getting non-existent interaction."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")

        interaction = ffai.get_interaction(999)

        assert interaction is None

    def test_get_model_interactions(self, mock_ffmistralsmall):
        """Test getting interactions by model."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")
        ffai.generate_response("Q2", model="other-model")

        interactions = ffai.get_model_interactions("other-model")

        assert len(interactions) == 1

    def test_get_interactions_by_prompt_name_ordered(self, mock_ffmistralsmall):
        """Test getting interactions by prompt name from ordered history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="qa")
        ffai.generate_response("Q2", prompt_name="other")
        ffai.generate_response("Q3", prompt_name="qa")

        interactions = ffai.get_interactions_by_prompt_name("qa")

        assert len(interactions) == 2

    def test_get_prompt_history(self, mock_ffmistralsmall):
        """Test getting all prompts."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")
        ffai.generate_response("Q2")

        prompts = ffai.get_prompt_history()

        assert prompts == ["Q1", "Q2"]

    def test_get_response_history(self, mock_ffmistralsmall):
        """Test getting all responses."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")
        ffai.generate_response("Q2")

        responses = ffai.get_response_history()

        assert len(responses) == 2

    def test_get_all_interactions(self, mock_ffmistralsmall):
        """Test getting all interactions."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")
        ffai.generate_response("Q2")

        interactions = ffai.get_all_interactions()

        assert len(interactions) == 2

    def test_get_prompt_dict(self, mock_ffmistralsmall):
        """Test getting history as dictionary keyed by prompts."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="a")
        ffai.generate_response("Q2", prompt_name="b")

        result = ffai.get_prompt_dict()

        assert "a" in result
        assert "b" in result

    def test_get_latest_responses_by_prompt_names(self, mock_ffmistralsmall):
        """Test getting latest responses by prompt names."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="a")
        ffai.generate_response("Q2", prompt_name="b")

        result = ffai.get_latest_responses_by_prompt_names(["a", "b"])

        assert "a" in result
        assert "b" in result

    def test_get_formatted_responses(self, mock_ffmistralsmall):
        """Test getting formatted responses."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="a")

        result = ffai.get_formatted_responses(["a"])

        assert "<prompt:" in result


class TestFFAIClientConversationHistoryErrors:
    """Tests for client conversation history error handling."""

    def test_get_client_conversation_history_no_method(self, mock_ffmistralsmall):
        """Test getting history when client lacks method."""
        from unittest.mock import MagicMock

        from src.FFAI import FFAI

        # Create a client without the method
        client = MagicMock(spec=[])  # Empty spec means no attributes
        ffai = FFAI(client)

        history = ffai.get_client_conversation_history()

        assert history == []

    def test_get_client_conversation_history_exception(self, mock_ffmistralsmall):
        """Test getting history when exception occurs."""
        from src.FFAI import FFAI

        def raise_error():
            raise Exception("Error")

        mock_ffmistralsmall.get_conversation_history = raise_error
        ffai = FFAI(mock_ffmistralsmall)

        history = ffai.get_client_conversation_history()

        assert history == []

    def test_set_client_conversation_history_no_method(self, mock_ffmistralsmall):
        """Test setting history when client lacks method."""
        from unittest.mock import MagicMock

        from src.FFAI import FFAI

        # Create a client without the method
        client = MagicMock(spec=[])
        ffai = FFAI(client)

        result = ffai.set_client_conversation_history([])

        assert result is False

    def test_set_client_conversation_history_exception(self, mock_ffmistralsmall):
        """Test setting history when exception occurs."""
        from src.FFAI import FFAI

        def raise_error(history):
            raise Exception("Error")

        mock_ffmistralsmall.set_conversation_history = raise_error
        ffai = FFAI(mock_ffmistralsmall)

        result = ffai.set_client_conversation_history([{"role": "user", "content": "test"}])

        assert result is False

    def test_add_client_message_exception(self, mock_ffmistralsmall):
        """Test adding message when exception occurs."""
        from src.FFAI import FFAI

        def raise_error(history):
            raise Exception("Error")

        mock_ffmistralsmall.set_conversation_history = raise_error
        ffai = FFAI(mock_ffmistralsmall)

        result = ffai.add_client_message("user", "test")

        assert result is False


class TestFFAIDataFrameExtended:
    """Extended tests for DataFrame methods."""

    def test_clean_history_to_dataframe(self, mock_ffmistralsmall):
        """Test converting clean history to DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Hello!")

        df = ffai.clean_history_to_dataframe()

        assert not df.is_empty()
        assert len(df) == 1

    def test_clean_history_to_dataframe_empty(self, mock_ffmistralsmall):
        """Test converting empty clean history to DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        df = ffai.clean_history_to_dataframe()

        assert df.is_empty()

    def test_prompt_attr_history_to_dataframe(self, mock_ffmistralsmall):
        """Test converting prompt attr history to DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Hello!")

        df = ffai.prompt_attr_history_to_dataframe()

        assert not df.is_empty()

    def test_prompt_attr_history_to_dataframe_empty(self, mock_ffmistralsmall):
        """Test converting empty prompt attr history to DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        df = ffai.prompt_attr_history_to_dataframe()

        assert df.is_empty()

    def test_ordered_history_to_dataframe(self, mock_ffmistralsmall):
        """Test converting ordered history to DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Hello!")

        df = ffai.ordered_history_to_dataframe()

        assert not df.is_empty()

    def test_ordered_history_to_dataframe_empty(self, mock_ffmistralsmall):
        """Test converting empty ordered history to DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        df = ffai.ordered_history_to_dataframe()

        assert df.is_empty()

    def test_search_history_by_model(self, mock_ffmistralsmall):
        """Test searching history by model."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")
        ffai.generate_response("Q2", model="other-model")

        results = ffai.search_history(model="other-model")

        assert len(results) == 1

    def test_search_history_by_time_range(self, mock_ffmistralsmall):
        """Test searching history by time range."""
        import time

        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        start = time.time()
        ffai.generate_response("Q1")
        end = time.time()

        results = ffai.search_history(start_time=start, end_time=end)

        assert len(results) == 1

    def test_search_history_empty_result(self, mock_ffmistralsmall):
        """Test searching history with no matches."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")

        results = ffai.search_history(text="nonexistent")

        assert len(results) == 0

    def test_get_model_stats_df(self, mock_ffmistralsmall):
        """Test getting model stats as DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")
        ffai.generate_response("Q2")

        df = ffai.get_model_stats_df()

        assert not df.is_empty()
        assert "model" in df.columns
        assert "count" in df.columns

    def test_get_prompt_name_stats_df(self, mock_ffmistralsmall):
        """Test getting prompt name stats as DataFrame."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="a")
        ffai.generate_response("Q2", prompt_name="a")

        df = ffai.get_prompt_name_stats_df()

        assert not df.is_empty()
        assert "prompt_name" in df.columns

    def test_get_response_length_stats(self, mock_ffmistralsmall):
        """Test getting response length stats."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", prompt_name="a")
        ffai.generate_response("Q2", prompt_name="b")

        df = ffai.get_response_length_stats()

        assert not df.is_empty()
        assert "prompt_name" in df.columns
        assert "mean_length" in df.columns

    def test_get_response_length_stats_empty(self, mock_ffmistralsmall):
        """Test getting response length stats with empty history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        df = ffai.get_response_length_stats()

        assert df.is_empty()

    def test_interaction_counts_by_date(self, mock_ffmistralsmall):
        """Test getting interaction counts by date."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1")
        ffai.generate_response("Q2")

        df = ffai.interaction_counts_by_date()

        assert not df.is_empty()
        assert "date" in df.columns
        assert "count" in df.columns

    def test_interaction_counts_by_date_empty(self, mock_ffmistralsmall):
        """Test getting interaction counts with empty history."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        df = ffai.interaction_counts_by_date()

        assert df.is_empty()

    def test_history_to_dataframe_with_dict_response(self, mock_ffmistralsmall):
        """Test converting history with dict response."""
        from src.FFAI import FFAI

        mock_ffmistralsmall.generate_response = lambda prompt, **kwargs: '{"key": "value"}'
        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Test")

        df = ffai.history_to_dataframe()

        assert not df.is_empty()
        assert "response" in df.columns


class TestFFAIPersistence:
    """Tests for persistence functionality."""

    def test_persist_all_histories(self, mock_ffmistralsmall, tmp_path):
        """Test persisting all histories."""
        from src.FFAI import FFAI

        ffai = FFAI(
            mock_ffmistralsmall,
            persist_dir=str(tmp_path),
            persist_name="test",
        )
        ffai.generate_response("Q1")

        result = ffai.persist_all_histories()

        assert result is True
        assert (tmp_path / "test_history.parquet").exists()
        assert (tmp_path / "test_clean_history.parquet").exists()

    def test_persist_all_histories_no_name(self, mock_ffmistralsmall, tmp_path):
        """Test persisting without name returns False."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall, persist_dir=str(tmp_path))
        ffai.generate_response("Q1")

        result = ffai.persist_all_histories()

        assert result is False

    def test_auto_persist_enabled(self, mock_ffmistralsmall, tmp_path):
        """Test auto-persist writes file."""
        from src.FFAI import FFAI

        ffai = FFAI(
            mock_ffmistralsmall,
            persist_dir=str(tmp_path),
            persist_name="test",
            auto_persist=True,
        )
        ffai.generate_response("Q1")

        df = ffai.history_to_dataframe()

        assert (tmp_path / "test_history_to_dataframe.parquet").exists()


class TestFFAIInitExtended:
    """Extended tests for FFAI initialization."""

    def test_init_with_shared_prompt_attr_history(self, mock_ffmistralsmall):
        """Test initialization with shared prompt_attr_history."""
        import threading

        from src.FFAI import FFAI

        shared_history = []
        lock = threading.Lock()

        ffai = FFAI(
            mock_ffmistralsmall,
            shared_prompt_attr_history=shared_history,
            history_lock=lock,
        )

        assert ffai.prompt_attr_history is shared_history
        assert ffai._history_lock is lock


class TestFFAIGenerateResponseException:
    """Tests for exception handling in generate_response."""

    def test_generate_response_exception(self, mock_ffmistralsmall):
        """Test exception during response generation."""
        from src.FFAI import FFAI

        def raise_error(prompt, **kwargs):
            raise Exception("API error")

        mock_ffmistralsmall.generate_response = raise_error

        ffai = FFAI(mock_ffmistralsmall)

        with pytest.raises(Exception, match="API error"):
            ffai.generate_response("Test")

    def test_generate_response_with_dependencies(self, mock_ffmistralsmall):
        """Test generate_response with dependencies parameter."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        ffai.generate_response("Q1", dependencies=["dep1", "dep2"])

        assert len(ffai.history) == 1


class TestFFAITimestampConversion:
    """Tests for timestamp conversion."""

    def test_convert_unix_seconds_to_datetime(self, mock_ffmistralsmall):
        """Test timestamp conversion."""
        import polars as pl

        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        df = pl.DataFrame({"timestamp": [1700000000.0], "other": ["a"]})

        result = ffai._convert_unix_seconds_to_datetime(df)

        assert "datetime" in result.columns

    def test_convert_unix_seconds_no_timestamp_column(self, mock_ffmistralsmall):
        """Test conversion when no timestamp column."""
        import polars as pl

        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        df = pl.DataFrame({"other": ["a"]})

        result = ffai._convert_unix_seconds_to_datetime(df)

        assert "datetime" not in result.columns


class TestFFAIAddClientMessageWithKwargs:
    """Tests for add_client_message with additional kwargs."""

    def test_add_client_message_with_kwargs(self, mock_ffmistralsmall):
        """Test adding message with additional kwargs."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)

        result = ffai.add_client_message("user", "test", extra_field="value")

        assert result is True
        assert mock_ffmistralsmall.conversation_history[-1]["extra_field"] == "value"
