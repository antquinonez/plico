# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for src.orchestrator.agent_executor -- agent mode execution.

Migrated from:
- test_orchestrator_base.py::TestRecordAgentResult
- test_orchestrator_base.py::TestExecuteAgentMode
- test_orchestrator_base.py::TestValidateAgentResponse
"""

import threading
from unittest.mock import MagicMock, patch

from src.agent.agent_result import AgentResult
from src.orchestrator.agent_executor import AgentExecutor


def _make_executor(
    tool_registry=None,
    config=None,
    history=None,
    history_lock=None,
):
    """Create an AgentExecutor with test defaults."""
    if tool_registry is None:
        tool_registry = MagicMock()
    if config is None:
        config = {"model": "test", "temperature": 0.7, "max_tokens": 4096}
    if history is None:
        history = []
    if history_lock is None:
        history_lock = threading.Lock()

    def record_history_fn(prompt, response):
        if response is None:
            return
        interaction = {
            "prompt": prompt.get("prompt", ""),
            "response": response,
            "prompt_name": prompt.get("prompt_name"),
        }
        with history_lock:
            history.append(interaction)

    executor = AgentExecutor(
        tool_registry=tool_registry,
        config=config,
        record_history_fn=record_history_fn,
    )
    return executor, history


class TestRecordHistory:
    """Tests for the record_history_fn callback integration."""

    def test_none_response_not_recorded(self):
        executor, history = _make_executor()
        executor._record_history({"prompt": "hi"}, None)
        assert len(history) == 0

    def test_response_recorded(self):
        executor, history = _make_executor()
        executor._record_history(
            {"prompt": "hi", "prompt_name": "test"},
            "response_text",
        )
        assert len(history) == 1
        assert history[0]["response"] == "response_text"
        assert history[0]["prompt_name"] == "test"


class TestAgentExecutorOpenAIAssistant:
    """Tests for AgentExecutor fallback on unsupported clients."""

    def test_openai_assistant_returns_none(self):
        executor, _ = _make_executor()

        mock_client = MagicMock()
        mock_client.__class__.__name__ = "FFOpenAIAssistant"
        mock_ffai = MagicMock()
        mock_ffai.client = mock_client

        mock_builder = MagicMock()
        mock_builder.build_dict.return_value = {"status": "success"}

        result = executor.execute(
            prompt={
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello",
                "history": None,
                "agent_mode": True,
                "tools": ["calculate"],
            },
            ffai=mock_ffai,
            builder=mock_builder,
            seq_label="Sequence 1",
            inject_references_fn=lambda p: p.get("prompt", ""),
            get_isolated_ffai_fn=lambda name: MagicMock(),
        )
        assert result is None


class TestAgentExecutorExecute:
    """Tests for AgentExecutor.execute."""

    def test_agent_result_failed(self):
        executor, history = _make_executor()

        mock_agent_result = AgentResult(
            response="",
            total_rounds=1,
            total_llm_calls=1,
            status="failed",
        )

        mock_ffai = MagicMock()
        mock_ffai._build_prompt.return_value = ("resolved prompt", None)
        mock_ffai.last_resolved_prompt = "resolved prompt"

        mock_builder = MagicMock()
        mock_builder.build_dict.return_value = {"status": "failed"}

        mock_config = MagicMock()
        mock_config.agent.max_tool_rounds = 5
        mock_config.agent.tool_timeout = 30.0
        mock_config.agent.continue_on_tool_error = True
        mock_config.agent.validation.enabled = False

        with patch("src.orchestrator.agent_executor.get_config", return_value=mock_config):
            with patch("src.agent.agent_loop.AgentLoop") as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.execute.return_value = mock_agent_result
                mock_loop_cls.return_value = mock_loop

                executor.execute(
                    prompt={
                        "sequence": 1,
                        "prompt_name": "test",
                        "prompt": "Hello",
                        "history": None,
                        "agent_mode": True,
                        "tools": ["calculate"],
                    },
                    ffai=mock_ffai,
                    builder=mock_builder,
                    seq_label="Sequence 1",
                    inject_references_fn=lambda p: p.get("prompt", ""),
                    get_isolated_ffai_fn=lambda name: MagicMock(),
                )

        mock_builder.with_agent_result.assert_called_once_with(mock_agent_result)

    def test_agent_result_max_rounds_exceeded(self):
        executor, history = _make_executor()

        mock_agent_result = AgentResult(
            response="partial",
            total_rounds=5,
            total_llm_calls=5,
            status="max_rounds_exceeded",
        )

        mock_ffai = MagicMock()
        mock_ffai._build_prompt.return_value = ("resolved prompt", None)
        mock_ffai.last_resolved_prompt = "resolved prompt"

        mock_builder = MagicMock()
        mock_builder.build_dict.return_value = {"status": "max_rounds_exceeded"}

        mock_config = MagicMock()
        mock_config.agent.max_tool_rounds = 5
        mock_config.agent.tool_timeout = 30.0
        mock_config.agent.continue_on_tool_error = True
        mock_config.agent.validation.enabled = False

        with patch("src.orchestrator.agent_executor.get_config", return_value=mock_config):
            with patch("src.agent.agent_loop.AgentLoop") as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.execute.return_value = mock_agent_result
                mock_loop_cls.return_value = mock_loop

                executor.execute(
                    prompt={
                        "sequence": 1,
                        "prompt_name": "test",
                        "prompt": "Hello",
                        "history": None,
                        "agent_mode": True,
                        "tools": ["calculate"],
                    },
                    ffai=mock_ffai,
                    builder=mock_builder,
                    seq_label="Sequence 1",
                    inject_references_fn=lambda p: p.get("prompt", ""),
                    get_isolated_ffai_fn=lambda name: MagicMock(),
                )

        mock_builder.with_agent_result.assert_called_once_with(mock_agent_result)

    def test_agent_mode_exception(self):
        executor, _ = _make_executor()

        mock_ffai = MagicMock()
        mock_ffai._build_prompt.return_value = ("resolved prompt", None)
        mock_ffai.last_resolved_prompt = "resolved prompt"

        mock_builder = MagicMock()
        mock_builder.build_dict.return_value = {"status": "failed", "error": "boom"}

        mock_config = MagicMock()
        mock_config.agent.max_tool_rounds = 5
        mock_config.agent.tool_timeout = 30.0
        mock_config.agent.continue_on_tool_error = True
        mock_config.agent.validation.enabled = False

        with patch("src.orchestrator.agent_executor.get_config", return_value=mock_config):
            with patch("src.agent.agent_loop.AgentLoop") as mock_loop_cls:
                mock_loop_cls.return_value = MagicMock()
                mock_loop_cls.return_value.execute.side_effect = RuntimeError("agent exploded")

                executor.execute(
                    prompt={
                        "sequence": 1,
                        "prompt_name": "test",
                        "prompt": "Hello",
                        "history": None,
                        "agent_mode": True,
                        "tools": ["calculate"],
                    },
                    ffai=mock_ffai,
                    builder=mock_builder,
                    seq_label="Sequence 1",
                    inject_references_fn=lambda p: p.get("prompt", ""),
                    get_isolated_ffai_fn=lambda name: MagicMock(),
                )

        mock_builder.with_error.assert_called_once()
        assert "agent exploded" in mock_builder.with_error.call_args[0][0]

    def test_success_records_history(self):
        executor, history = _make_executor()

        mock_agent_result = AgentResult(
            response="final answer",
            total_rounds=1,
            total_llm_calls=1,
            status="success",
        )

        mock_ffai = MagicMock()
        mock_ffai._build_prompt.return_value = ("resolved prompt", None)
        mock_ffai.last_resolved_prompt = "resolved prompt"

        mock_builder = MagicMock()
        mock_builder.build_dict.return_value = {"status": "success"}

        prompt = {
            "sequence": 1,
            "prompt_name": "test",
            "prompt": "Hello",
            "history": None,
            "agent_mode": True,
            "tools": ["calculate"],
        }

        mock_config = MagicMock()
        mock_config.agent.max_tool_rounds = 5
        mock_config.agent.tool_timeout = 30.0
        mock_config.agent.continue_on_tool_error = True
        mock_config.agent.validation.enabled = False

        with patch("src.orchestrator.agent_executor.get_config", return_value=mock_config):
            with patch("src.agent.agent_loop.AgentLoop") as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.execute.return_value = mock_agent_result
                mock_loop_cls.return_value = mock_loop

                executor.execute(
                    prompt=prompt,
                    ffai=mock_ffai,
                    builder=mock_builder,
                    seq_label="Sequence 1",
                    inject_references_fn=lambda p: p.get("prompt", ""),
                    get_isolated_ffai_fn=lambda name: MagicMock(),
                )

        assert len(history) == 1
        assert history[0]["response"] == "final answer"
        assert history[0]["prompt_name"] == "test"

    def test_inject_references_fn_called(self):
        executor, _ = _make_executor()

        mock_agent_result = AgentResult(response="ok", status="success")

        mock_ffai = MagicMock()
        mock_ffai._build_prompt.return_value = ("resolved", None)
        mock_ffai.last_resolved_prompt = "resolved"

        mock_builder = MagicMock()
        mock_builder.build_dict.return_value = {"status": "success"}

        inject_calls = []

        def track_inject(prompt):
            inject_calls.append(prompt)
            return prompt.get("prompt", "")

        mock_config = MagicMock()
        mock_config.agent.max_tool_rounds = 5
        mock_config.agent.tool_timeout = 30.0
        mock_config.agent.continue_on_tool_error = True
        mock_config.agent.validation.enabled = False

        with patch("src.orchestrator.agent_executor.get_config", return_value=mock_config):
            with patch("src.agent.agent_loop.AgentLoop") as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.execute.return_value = mock_agent_result
                mock_loop_cls.return_value = mock_loop

                executor.execute(
                    prompt={
                        "sequence": 1,
                        "prompt_name": "test",
                        "prompt": "Hello",
                        "history": None,
                        "agent_mode": True,
                        "tools": ["calculate"],
                    },
                    ffai=mock_ffai,
                    builder=mock_builder,
                    seq_label="Sequence 1",
                    inject_references_fn=track_inject,
                    get_isolated_ffai_fn=lambda name: MagicMock(),
                )

        assert len(inject_calls) == 1


class TestAgentExecutorValidateResponse:
    """Tests for AgentExecutor.validate_response."""

    def test_validation_llm_fails_all_retries(self):
        executor, _ = _make_executor()

        mock_agent_result = AgentResult(response="original response", status="success")

        mock_ffai_val = MagicMock()
        mock_ffai_val.generate_response.side_effect = RuntimeError("LLM down")

        mock_builder = MagicMock()

        mock_config = MagicMock()
        mock_config.agent.max_tool_rounds = 5
        mock_config.agent.tool_timeout = 30.0
        mock_config.agent.continue_on_tool_error = True

        with patch("src.orchestrator.agent_executor.get_config", return_value=mock_config):
            with patch("src.agent.agent_loop.AgentLoop"):
                executor.validate_response(
                    prompt={"sequence": 1, "prompt_name": "test", "history": None},
                    builder=mock_builder,
                    agent_result=mock_agent_result,
                    tool_names=["calculate"],
                    validation_prompt="Must include numbers",
                    max_val_retries=2,
                    seq_label="Sequence 1",
                    original_prompt="original prompt",
                    max_rounds=5,
                    tool_timeout=30.0,
                    continue_on_tool_error=True,
                    get_isolated_ffai_fn=lambda name: mock_ffai_val,
                )

        mock_builder.with_validation_result.assert_called_once()
        call_kwargs = mock_builder.with_validation_result.call_args[1]
        assert call_kwargs["passed"] is None
        assert "Validation call failed" in call_kwargs["critique"]

    def test_validation_retry_execution_fails(self):
        executor, _ = _make_executor()

        mock_agent_result = AgentResult(response="bad response", status="success")

        call_count = [0]

        def mock_val_generate(*args, **kwargs):
            call_count[0] += 1
            return "FAIL: Not good enough"

        mock_ffai_val = MagicMock()
        mock_ffai_val.generate_response = mock_val_generate

        mock_builder = MagicMock()

        mock_config = MagicMock()
        mock_config.agent.max_tool_rounds = 5
        mock_config.agent.tool_timeout = 30.0
        mock_config.agent.continue_on_tool_error = True

        with patch("src.orchestrator.agent_executor.get_config", return_value=mock_config):
            with patch("src.agent.agent_loop.AgentLoop") as mock_loop_cls:
                mock_loop = MagicMock()
                mock_loop.execute.side_effect = RuntimeError("retry failed")
                mock_loop_cls.return_value = mock_loop

                executor.validate_response(
                    prompt={"sequence": 1, "prompt_name": "test", "history": None},
                    builder=mock_builder,
                    agent_result=mock_agent_result,
                    tool_names=["calculate"],
                    validation_prompt="Must be perfect",
                    max_val_retries=1,
                    seq_label="Sequence 1",
                    original_prompt="original prompt",
                    max_rounds=5,
                    tool_timeout=30.0,
                    continue_on_tool_error=True,
                    get_isolated_ffai_fn=lambda name: mock_ffai_val,
                )

        last_call = mock_builder.with_validation_result.call_args[1]
        assert last_call["passed"] is False
        assert last_call["critique"] is not None
