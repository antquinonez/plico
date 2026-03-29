# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

import pytest

from src.orchestrator.results import PromptResult, ResultBuilder


class TestPromptResult:
    """Tests for PromptResult dataclass."""

    def test_init_basic(self):
        """Test basic initialization."""
        result = PromptResult(sequence=1)
        assert result.sequence == 1
        assert result.status == "pending"
        assert result.attempts == 0

    def test_init_with_all_fields(self):
        """Test initialization with all fields."""
        result = PromptResult(
            sequence=1,
            prompt_name="test",
            prompt="Hello",
            history=["dep1"],
            client="fast",
            condition="{{dep1.status}} == 'success'",
            response="World",
            status="success",
            attempts=2,
        )
        assert result.sequence == 1
        assert result.prompt_name == "test"
        assert result.response == "World"
        assert result.status == "success"

    def test_to_dict_basic(self):
        """Test conversion to dictionary."""
        result = PromptResult(sequence=1, prompt_name="test", prompt="Hello")
        d = result.to_dict()
        assert d["sequence"] == 1
        assert d["prompt_name"] == "test"
        assert d["prompt"] == "Hello"
        assert d["status"] == "pending"
        assert d["batch_id"] is None

    def test_to_dict_with_batch(self):
        """Test conversion to dictionary with batch info."""
        result = PromptResult(sequence=1, batch_id=5, batch_name="test_batch")
        d = result.to_dict()
        assert d["batch_id"] == 5
        assert d["batch_name"] == "test_batch"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "sequence": 2,
            "prompt_name": "from_dict",
            "prompt": "Test prompt",
            "response": "Test response",
            "status": "success",
            "attempts": 3,
        }
        result = PromptResult.from_dict(data)
        assert result.sequence == 2
        assert result.prompt_name == "from_dict"
        assert result.response == "Test response"
        assert result.attempts == 3


class TestResultBuilder:
    """Tests for ResultBuilder."""

    @pytest.fixture
    def sample_prompt(self):
        """Sample prompt dictionary."""
        return {
            "sequence": 1,
            "prompt_name": "test_prompt",
            "prompt": "Hello world",
            "history": ["dep1", "dep2"],
            "client": "fast",
            "condition": "{{dep1.status}} == 'success'",
            "references": ["doc1"],
            "semantic_query": "test query",
        }

    def test_init_from_prompt(self, sample_prompt):
        """Test initialization from prompt dictionary."""
        builder = ResultBuilder(sample_prompt)
        result = builder.build()
        assert result.sequence == 1
        assert result.prompt_name == "test_prompt"
        assert result.prompt == "Hello world"
        assert result.history == ["dep1", "dep2"]
        assert result.client == "fast"
        assert result.status == "pending"

    def test_with_batch(self, sample_prompt):
        """Test adding batch info."""
        result = (
            ResultBuilder(sample_prompt).with_batch(batch_id=3, batch_name="batch_three").build()
        )
        assert result.batch_id == 3
        assert result.batch_name == "batch_three"

    def test_with_response(self, sample_prompt):
        """Test setting successful response."""
        result = ResultBuilder(sample_prompt).with_response("AI response").build()
        assert result.response == "AI response"
        assert result.status == "success"

    def test_with_error(self, sample_prompt):
        """Test setting failed execution."""
        result = ResultBuilder(sample_prompt).with_error("API Error", attempts=3).build()
        assert result.error == "API Error"
        assert result.attempts == 3
        assert result.status == "failed"

    def test_with_attempts(self, sample_prompt):
        """Test setting attempts."""
        result = ResultBuilder(sample_prompt).with_attempts(5).build()
        assert result.attempts == 5

    def test_as_skipped(self, sample_prompt):
        """Test marking as skipped."""
        result = (
            ResultBuilder(sample_prompt)
            .as_skipped(condition_result=False, condition_error=None)
            .build()
        )
        assert result.status == "skipped"
        assert result.condition_result is False
        assert result.condition_error is None

    def test_with_condition_result(self, sample_prompt):
        """Test setting condition result."""
        result = (
            ResultBuilder(sample_prompt)
            .with_condition_result(condition_result=True, condition_error=None)
            .build()
        )
        assert result.condition_result is True
        assert result.condition_error is None

    def test_as_failed_exception(self, sample_prompt):
        """Test marking as failed due to exception."""
        result = ResultBuilder(sample_prompt).as_failed_exception("Unexpected error").build()
        assert result.status == "failed"
        assert result.error == "Unexpected error"
        assert result.attempts == 1

    def test_build_dict(self, sample_prompt):
        """Test building as dictionary."""
        d = (
            ResultBuilder(sample_prompt)
            .with_batch(batch_id=1, batch_name="test")
            .with_response("Response")
            .build_dict()
        )
        assert d["sequence"] == 1
        assert d["batch_id"] == 1
        assert d["response"] == "Response"
        assert d["status"] == "success"

    def test_fluent_chaining(self, sample_prompt):
        """Test fluent method chaining."""
        result = (
            ResultBuilder(sample_prompt)
            .with_batch(batch_id=1, batch_name="test")
            .with_condition_result(condition_result=True)
            .with_attempts(2)
            .with_response("Success!")
            .build()
        )
        assert result.batch_id == 1
        assert result.condition_result is True
        assert result.attempts == 2
        assert result.response == "Success!"
        assert result.status == "success"

    def test_minimal_prompt(self):
        """Test with minimal prompt data."""
        builder = ResultBuilder({"sequence": 5, "prompt": "Minimal"})
        result = builder.build()
        assert result.sequence == 5
        assert result.prompt == "Minimal"
        assert result.prompt_name is None
        assert result.status == "pending"

    def test_with_agent_result_success(self, sample_prompt):
        """Test with_agent_result for successful agent execution."""
        from src.agent.agent_result import AgentResult, ToolCallRecord

        agent_result = AgentResult(
            response="Final answer",
            tool_calls=[ToolCallRecord(round=1, tool_name="calc", tool_call_id="tc1")],
            total_rounds=2,
            total_llm_calls=2,
            status="success",
        )
        result = ResultBuilder(sample_prompt).with_agent_result(agent_result).build()
        assert result.agent_mode is True
        assert result.response == "Final answer"
        assert result.status == "success"
        assert result.total_rounds == 2
        assert result.total_llm_calls == 2
        assert len(result.tool_calls) == 1

    def test_with_agent_result_max_rounds_exceeded(self, sample_prompt):
        """Test with_agent_result maps max_rounds_exceeded correctly."""
        from src.agent.agent_result import AgentResult

        agent_result = AgentResult(
            response="partial answer",
            tool_calls=[],
            total_rounds=5,
            total_llm_calls=5,
            status="max_rounds_exceeded",
        )
        result = ResultBuilder(sample_prompt).with_agent_result(agent_result).build()
        assert result.status == "max_rounds_exceeded"
        assert result.error is not None
        assert "max rounds" in result.error.lower()

    def test_with_agent_result_failed(self, sample_prompt):
        """Test with_agent_result maps failed status correctly."""
        from src.agent.agent_result import AgentResult

        agent_result = AgentResult(
            response="",
            tool_calls=[],
            total_rounds=1,
            total_llm_calls=1,
            status="failed",
        )
        result = ResultBuilder(sample_prompt).with_agent_result(agent_result).build()
        assert result.status == "failed"

    def test_valid_statuses_includes_max_rounds_exceeded(self):
        """VALID_STATUSES should include max_rounds_exceeded."""
        assert "max_rounds_exceeded" in PromptResult.VALID_STATUSES

    def test_agent_fields_default_to_none(self):
        """Agent fields should default to None/False."""
        result = PromptResult(sequence=1)
        assert result.agent_mode is False
        assert result.tool_calls is None
        assert result.total_rounds is None
        assert result.total_llm_calls is None

    def test_to_dict_includes_agent_fields_when_set(self):
        """to_dict should include agent fields with their values."""
        result = PromptResult(sequence=1, agent_mode=True, total_rounds=3, total_llm_calls=5)
        result.tool_calls = [{"tool_name": "calc"}]
        d = result.to_dict()
        assert d["agent_mode"] is True
        assert d["total_rounds"] == 3
        assert d["total_llm_calls"] == 5

    def test_to_dict_includes_agent_fields_when_not_set(self):
        """to_dict should include agent fields with default values."""
        result = PromptResult(sequence=1)
        d = result.to_dict()
        assert d["agent_mode"] is False
        assert d["tool_calls"] is None
        assert d["total_rounds"] is None
        assert d["total_llm_calls"] is None
