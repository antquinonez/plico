from src.ConversationHistory import ConversationHistory


class TestConversationHistoryInit:
    def test_starts_empty(self):
        ch = ConversationHistory()
        assert ch.turns == []


class TestAddTurnAssistant:
    def test_single_assistant_turn(self):
        ch = ConversationHistory()
        ch.add_turn_assistant("Hello there")
        assert len(ch.turns) == 1
        assert ch.turns[0]["role"] == "assistant"
        assert ch.turns[0]["content"][0]["type"] == "text"
        assert ch.turns[0]["content"][0]["text"] == "Hello there"

    def test_multiple_assistant_turns(self):
        ch = ConversationHistory()
        ch.add_turn_assistant("First")
        ch.add_turn_assistant("Second")
        assert len(ch.turns) == 2
        assert ch.turns[0]["content"][0]["text"] == "First"
        assert ch.turns[1]["content"][0]["text"] == "Second"


class TestAddTurnUser:
    def test_single_user_turn(self):
        ch = ConversationHistory()
        ch.add_turn_user("Hi")
        assert len(ch.turns) == 1
        assert ch.turns[0]["role"] == "user"
        assert ch.turns[0]["content"][0]["text"] == "Hi"

    def test_consecutive_user_turns_merge(self):
        ch = ConversationHistory()
        ch.add_turn_user("Line one")
        ch.add_turn_user("Line two")
        assert len(ch.turns) == 1
        assert ch.turns[0]["content"][0]["text"] == "Line one\nLine two"

    def test_user_after_assistant_starts_new_turn(self):
        ch = ConversationHistory()
        ch.add_turn_assistant("Reply")
        ch.add_turn_user("Follow-up")
        assert len(ch.turns) == 2
        assert ch.turns[0]["role"] == "assistant"
        assert ch.turns[1]["role"] == "user"
        assert ch.turns[1]["content"][0]["text"] == "Follow-up"


class TestGetTurns:
    def test_empty_returns_empty_list(self):
        ch = ConversationHistory()
        assert ch.get_turns() == []

    def test_returns_copy_not_reference(self):
        ch = ConversationHistory()
        ch.add_turn_user("Hello")
        turns = ch.get_turns()
        turns[0]["content"][0]["text"] = "modified"
        assert ch.turns[0]["content"][0]["text"] == "Hello"

    def test_user_turns_are_deep_copied(self):
        ch = ConversationHistory()
        ch.add_turn_user("Original")
        turns = ch.get_turns()
        turns[0]["content"].append({"type": "text", "text": "extra"})
        assert len(ch.turns[0]["content"]) == 1

    def test_assistant_turns_are_same_object(self):
        ch = ConversationHistory()
        ch.add_turn_assistant("Response")
        turns = ch.get_turns()
        assert turns[0] is ch.turns[0]

    def test_roundtrip_preserves_content(self):
        ch = ConversationHistory()
        ch.add_turn_user("Question")
        ch.add_turn_assistant("Answer")
        ch.add_turn_user("Follow-up")
        turns = ch.get_turns()
        assert len(turns) == 3
        assert turns[0]["role"] == "user"
        assert turns[0]["content"][0]["text"] == "Question"
        assert turns[1]["role"] == "assistant"
        assert turns[1]["content"][0]["text"] == "Answer"
        assert turns[2]["role"] == "user"
        assert turns[2]["content"][0]["text"] == "Follow-up"


class TestShimImport:
    def test_import_from_shim_module(self):
        from src.core.history.conversation import ConversationHistory as Direct

        assert ConversationHistory is Direct
