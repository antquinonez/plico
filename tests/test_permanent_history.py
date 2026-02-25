import time

from src.PermanentHistory import PermanentHistory


class TestPermanentHistory:
    """Tests for PermanentHistory class."""

    def test_initialization(self):
        """Test that PermanentHistory initializes correctly."""
        history = PermanentHistory()

        assert history.turns == []
        assert hasattr(history, "timestamp")

    def test_add_turn_user(self):
        """Test adding a user turn."""
        history = PermanentHistory()

        history.add_turn_user("Hello!")

        assert len(history.turns) == 1
        assert history.turns[0]["role"] == "user"
        assert history.turns[0]["content"][0]["text"] == "Hello!"
        assert "timestamp" in history.turns[0]

    def test_add_turn_assistant(self):
        """Test adding an assistant turn."""
        history = PermanentHistory()

        history.add_turn_assistant("Hi there!")

        assert len(history.turns) == 1
        assert history.turns[0]["role"] == "assistant"
        assert history.turns[0]["content"][0]["text"] == "Hi there!"

    def test_consecutive_user_turns_merged(self):
        """Test that consecutive user turns are merged."""
        history = PermanentHistory()

        history.add_turn_user("First message")
        history.add_turn_user("Second message")

        assert len(history.turns) == 1
        assert history.turns[0]["role"] == "user"
        assert "First message" in history.turns[0]["content"][0]["text"]
        assert "Second message" in history.turns[0]["content"][0]["text"]

    def test_alternating_turns_not_merged(self):
        """Test that alternating turns are not merged."""
        history = PermanentHistory()

        history.add_turn_user("Question")
        history.add_turn_assistant("Answer")
        history.add_turn_user("Follow-up")

        assert len(history.turns) == 3
        assert history.turns[0]["role"] == "user"
        assert history.turns[1]["role"] == "assistant"
        assert history.turns[2]["role"] == "user"

    def test_get_all_turns(self):
        """Test retrieving all turns."""
        history = PermanentHistory()

        history.add_turn_user("Q1")
        history.add_turn_assistant("A1")
        history.add_turn_user("Q2")

        turns = history.get_all_turns()

        assert len(turns) == 3
        assert turns[0]["role"] == "user"
        assert turns[1]["role"] == "assistant"

    def test_get_all_turns_returns_copy(self):
        """Test that get_all_turns returns a copy."""
        history = PermanentHistory()
        history.add_turn_user("Test")

        turns = history.get_all_turns()
        turns.append({"fake": "turn"})

        assert len(history.turns) == 1
        assert len(turns) == 2

    def test_get_turns_since(self):
        """Test retrieving turns since a timestamp."""
        history = PermanentHistory()

        history.add_turn_user("First")
        history.add_turn_assistant("Response 1")
        time.sleep(0.01)
        cutoff = time.time()
        time.sleep(0.01)
        history.add_turn_user("Second")
        history.add_turn_assistant("Response 2")

        recent = history.get_turns_since(cutoff)

        assert len(recent) == 2
        assert recent[0]["content"][0]["text"] == "Second"

    def test_content_structure(self):
        """Test that content follows expected structure."""
        history = PermanentHistory()

        history.add_turn_user("Test message")

        turn = history.turns[0]
        assert "content" in turn
        assert isinstance(turn["content"], list)
        assert len(turn["content"]) == 1
        assert turn["content"][0]["type"] == "text"
        assert turn["content"][0]["text"] == "Test message"
