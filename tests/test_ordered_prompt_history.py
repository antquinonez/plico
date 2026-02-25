from src.OrderedPromptHistory import Interaction, OrderedPromptHistory


class TestInteraction:
    """Tests for the Interaction dataclass."""

    def test_interaction_creation(self):
        """Test basic interaction creation."""
        interaction = Interaction(
            sequence_number=1,
            model="test-model",
            timestamp=1234567890.0,
            prompt_name="test",
            prompt="Hello",
            response="Hi there!",
            history=None,
        )

        assert interaction.sequence_number == 1
        assert interaction.model == "test-model"
        assert interaction.prompt_name == "test"
        assert interaction.prompt == "Hello"
        assert interaction.response == "Hi there!"

    def test_interaction_to_dict(self):
        """Test interaction serialization."""
        interaction = Interaction(
            sequence_number=1,
            model="test-model",
            timestamp=1234567890.0,
            prompt_name="test",
            prompt="Hello",
            response="Hi there!",
            history=["prev"],
        )

        result = interaction.to_dict()

        assert isinstance(result, dict)
        assert result["sequence_number"] == 1
        assert result["model"] == "test-model"
        assert result["prompt_name"] == "test"
        assert result["prompt"] == "Hello"
        assert result["response"] == "Hi there!"
        assert result["history"] == ["prev"]
        assert "datetime" in result

    def test_interaction_with_none_prompt_name(self):
        """Test interaction without prompt_name."""
        interaction = Interaction(
            sequence_number=1,
            model="test-model",
            timestamp=1234567890.0,
            prompt_name=None,
            prompt="Hello",
            response="Hi!",
            history=None,
        )

        assert interaction.prompt_name is None


class TestOrderedPromptHistory:
    """Tests for OrderedPromptHistory class."""

    def test_initialization(self):
        """Test that OrderedPromptHistory initializes correctly."""
        history = OrderedPromptHistory()

        assert history.prompt_dict == {}
        assert history._current_sequence == 0

    def test_add_interaction_basic(self):
        """Test adding a basic interaction."""
        history = OrderedPromptHistory()

        interaction = history.add_interaction(
            model="test-model",
            prompt="Hello",
            response="Hi there!",
            prompt_name="greeting",
        )

        assert history._current_sequence == 1
        assert interaction.sequence_number == 1
        assert interaction.prompt_name == "greeting"
        assert "greeting" in history.prompt_dict
        assert len(history.prompt_dict["greeting"]) == 1

    def test_add_interaction_with_history(self):
        """Test adding interaction with history chain."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="First",
            response="Response 1",
            prompt_name="first",
        )

        history.add_interaction(
            model="test-model",
            prompt="Second",
            response="Response 2",
            prompt_name="second",
            history=["first"],
        )

        interactions = history.get_all_interactions()
        assert len(interactions) == 2
        assert interactions[1].history == ["first"]

    def test_add_multiple_same_prompt_name(self):
        """Test adding multiple interactions with same prompt_name."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="Question 1",
            response="Answer 1",
            prompt_name="qa",
        )

        history.add_interaction(
            model="test-model",
            prompt="Question 2",
            response="Answer 2",
            prompt_name="qa",
        )

        assert len(history.prompt_dict["qa"]) == 2

    def test_get_interactions_by_prompt_name(self):
        """Test retrieving interactions by prompt name."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="Hello",
            response="Hi!",
            prompt_name="greeting",
        )

        history.add_interaction(
            model="test-model",
            prompt="Bye",
            response="Goodbye!",
            prompt_name="farewell",
        )

        greetings = history.get_interactions_by_prompt_name("greeting")
        assert len(greetings) == 1
        assert greetings[0].prompt_name == "greeting"

    def test_get_latest_interaction_by_prompt_name(self):
        """Test getting the latest interaction for a prompt name."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="Q1",
            response="A1",
            prompt_name="qa",
        )

        history.add_interaction(
            model="test-model",
            prompt="Q2",
            response="A2",
            prompt_name="qa",
        )

        latest = history.get_latest_interaction_by_prompt_name("qa")
        assert latest.prompt == "Q2"
        assert latest.response == "A2"

    def test_get_latest_interaction_nonexistent(self):
        """Test getting latest interaction for nonexistent prompt name."""
        history = OrderedPromptHistory()

        result = history.get_latest_interaction_by_prompt_name("nonexistent")
        assert result is None

    def test_get_all_prompt_names(self):
        """Test getting all prompt names."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="Hello",
            response="Hi!",
            prompt_name="greeting",
        )

        history.add_interaction(
            model="test-model",
            prompt="Bye",
            response="Bye!",
            prompt_name="farewell",
        )

        names = history.get_all_prompt_names()
        assert "greeting" in names
        assert "farewell" in names

    def test_get_all_interactions_ordered(self):
        """Test that all interactions are returned in sequence order."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="First",
            response="1",
            prompt_name="a",
        )

        history.add_interaction(
            model="test-model",
            prompt="Second",
            response="2",
            prompt_name="b",
        )

        history.add_interaction(
            model="test-model",
            prompt="Third",
            response="3",
            prompt_name="a",
        )

        interactions = history.get_all_interactions()
        assert len(interactions) == 3
        assert interactions[0].sequence_number == 1
        assert interactions[1].sequence_number == 2
        assert interactions[2].sequence_number == 3

    def test_get_prompt_name_usage_stats(self):
        """Test usage statistics."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="Q1",
            response="A1",
            prompt_name="qa",
        )

        history.add_interaction(
            model="test-model",
            prompt="Q2",
            response="A2",
            prompt_name="qa",
        )

        history.add_interaction(
            model="test-model",
            prompt="Hello",
            response="Hi!",
            prompt_name="greeting",
        )

        stats = history.get_prompt_name_usage_stats()
        assert stats["qa"] == 2
        assert stats["greeting"] == 1

    def test_clean_text_removes_rag(self):
        """Test that _clean_text removes RAG sections."""
        history = OrderedPromptHistory()

        text = "Hello <RAG>some context</RAG> world"
        cleaned = history._clean_text(text)

        assert "<RAG>" not in cleaned
        assert "some context" not in cleaned
        assert "Hello" in cleaned
        assert "world" in cleaned

    def test_clean_text_removes_prompt_section(self):
        """Test that _clean_text removes PROMPT sections."""
        history = OrderedPromptHistory()

        text = "Hello ======== PROMPT ======== some prompt text"
        cleaned = history._clean_text(text)

        assert "PROMPT" not in cleaned
        assert "some prompt text" not in cleaned

    def test_get_effective_prompt_name_string(self):
        """Test get_effective_prompt_name with string input."""
        history = OrderedPromptHistory()

        result = history.get_effective_prompt_name("  test prompt  ")
        assert result == "test prompt"

    def test_to_dict(self):
        """Test converting entire history to dictionary."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="Hello",
            response="Hi!",
            prompt_name="greeting",
        )

        result = history.to_dict()

        assert "greeting" in result
        assert len(result["greeting"]) == 1
        assert isinstance(result["greeting"][0], dict)

    def test_get_latest_responses_by_prompt_names(self):
        """Test getting latest responses for multiple prompt names."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="Hello",
            response="Hi!",
            prompt_name="greeting",
        )

        history.add_interaction(
            model="test-model",
            prompt="What is 2+2?",
            response="4",
            prompt_name="math",
        )

        result = history.get_latest_responses_by_prompt_names(["greeting", "math"])

        assert "greeting" in result
        assert "math" in result
        assert result["greeting"]["response"] == "Hi!"
        assert result["math"]["response"] == "4"

    def test_get_formatted_responses(self):
        """Test formatted output of responses."""
        history = OrderedPromptHistory()

        history.add_interaction(
            model="test-model",
            prompt="What is 2+2?",
            response="4",
            prompt_name="math",
        )

        result = history.get_formatted_responses(["math"])

        assert "<prompt:" in result
        assert "</prompt:" in result
        assert "4" in result

    def test_merge_histories(self):
        """Test merging two histories."""
        history1 = OrderedPromptHistory()
        history2 = OrderedPromptHistory()

        history1.add_interaction(
            model="test-model",
            prompt="A",
            response="1",
            prompt_name="a",
        )

        history2.add_interaction(
            model="test-model",
            prompt="B",
            response="2",
            prompt_name="b",
        )

        history1.merge_histories(history2)

        assert len(history1.get_all_interactions()) == 2
