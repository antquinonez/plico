from src.core.prompt_builder import PromptBuilder


class TestPromptBuilderNoHistory:
    def test_plain_prompt_no_history(self):
        pb = PromptBuilder([])
        result, names = pb.build_prompt("Just a prompt")
        assert result == "Just a prompt"
        assert names == set()

    def test_interpolation_only(self):
        pb = PromptBuilder(
            [
                {"prompt_name": "math", "prompt": "What is 2+2?", "response": "4"},
            ]
        )
        result, names = pb.build_prompt("Answer: {{math.response}}")
        assert result == "Answer: 4"
        assert names == {"math"}


class TestPromptBuilderWithHistory:
    def _make_builder(self):
        history = [
            {"prompt_name": "intro", "prompt": "Say hello", "response": "Hello!"},
            {"prompt_name": "math", "prompt": "What is 2+2?", "response": "4"},
        ]
        return PromptBuilder(history)

    def test_history_context_included(self):
        pb = self._make_builder()
        result, names = pb.build_prompt("Follow up", history=["math"])
        assert "<conversation_history>" in result
        assert "<interaction prompt_name='math'>" in result
        assert "USER: What is 2+2?" in result
        assert "SYSTEM: 4" in result
        assert "</conversation_history>" in result
        assert "Based on the conversation history above, please answer: Follow up" in result
        assert names == set()

    def test_interpolated_names_excluded_from_context(self):
        pb = self._make_builder()
        result, names = pb.build_prompt(
            "Summarize: {{math.response}}",
            history=["math"],
        )
        assert names == {"math"}
        assert "<conversation_history>" not in result
        assert "Summarize: 4" == result

    def test_mixed_history_and_interpolation(self):
        pb = self._make_builder()
        result, names = pb.build_prompt(
            "Given {{math.response}}, now elaborate",
            history=["math", "intro"],
        )
        assert names == {"math"}
        assert "<interaction prompt_name='intro'>" in result
        assert "<interaction prompt_name='math'>" not in result
        assert "Given 4, now elaborate" in result

    def test_empty_history_list_returns_resolved_prompt(self):
        pb = self._make_builder()
        result, names = pb.build_prompt("Hello", history=[])
        assert result == "Hello"
        assert names == set()


class TestPromptBuilderReferencesStripped:
    def test_references_removed_from_history_prompts(self):
        history = [
            {
                "prompt_name": "context",
                "prompt": "Read this <REFERENCES>doc1, doc2</REFERENCES> and answer",
                "response": "Done",
            },
        ]
        pb = PromptBuilder(history)
        result, _ = pb.build_prompt("Follow up", history=["context"])
        assert "<REFERENCES>" not in result
        assert "doc1, doc2" not in result
        assert "Read this" in result


class TestPromptBuilderDictResponse:
    def test_dict_response_serialized(self):
        history = [
            {"prompt_name": "analysis", "prompt": "Analyze", "response": {"score": 8}},
        ]
        pb = PromptBuilder(history)
        result, names = pb.build_prompt("Score is {{analysis.response}}")
        assert "8" in result
        assert names == {"analysis"}

    def test_dict_response_in_history_context(self):
        history = [
            {"prompt_name": "analysis", "prompt": "Analyze", "response": {"score": 8}},
        ]
        pb = PromptBuilder(history)
        result, _ = pb.build_prompt("Elaborate", history=["analysis"])
        assert "SYSTEM: {'score': 8}" in result
