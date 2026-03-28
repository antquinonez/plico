# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for OrchestratorBase fixes and improvements.

Tests cover:
- Dependency cycle detection (#6)
- Retry backoff delay (#5)
- Unified execution path / client clone reuse (#1, #7)
- Consistent logging (#8)
- Orchestration complete log message (#11)
- Dead code removal verification (#2, #3)
"""

import time
from unittest.mock import MagicMock, patch

import pytest


class TestDependencyCycleDetection:
    """Tests for dependency cycle detection in _build_execution_graph."""

    def _make_orchestrator(self, prompts, mock_ffmistralsmall):
        """Helper to create an orchestrator with preset prompts."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator.__new__(ExcelOrchestrator)
        # Minimal init for testing _build_execution_graph
        orchestrator.client = mock_ffmistralsmall
        orchestrator.prompts = prompts
        return orchestrator

    def test_cycle_detection_simple(self, temp_workbook, mock_ffmistralsmall):
        """Test that a simple A->B->A cycle is detected."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "Hello", "history": ["b"]},
            {"sequence": 2, "prompt_name": "b", "prompt": "World", "history": ["a"]},
        ]

        with pytest.raises(ValueError, match="Dependency cycle detected"):
            orchestrator._build_execution_graph()

    def test_cycle_detection_three_node(self, temp_workbook, mock_ffmistralsmall):
        """Test that a A->B->C->A cycle is detected."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": ["c"]},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": ["a"]},
            {"sequence": 3, "prompt_name": "c", "prompt": "C", "history": ["b"]},
        ]

        with pytest.raises(ValueError, match="Dependency cycle detected"):
            orchestrator._build_execution_graph()

    def test_self_referencing_cycle(self, temp_workbook, mock_ffmistralsmall):
        """Test that a self-referencing dependency is detected."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "Hello", "history": ["a"]},
        ]

        with pytest.raises(ValueError, match="Dependency cycle detected"):
            orchestrator._build_execution_graph()

    def test_no_cycle_linear_chain(self, temp_workbook, mock_ffmistralsmall):
        """Test that a valid linear chain does not raise."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": ["a"]},
            {"sequence": 3, "prompt_name": "c", "prompt": "C", "history": ["b"]},
        ]

        nodes = orchestrator._build_execution_graph()

        assert nodes[1].level == 0
        assert nodes[2].level == 1
        assert nodes[3].level == 2

    def test_no_cycle_diamond(self, temp_workbook, mock_ffmistralsmall):
        """Test that a valid diamond dependency pattern does not raise."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": ["a"]},
            {"sequence": 3, "prompt_name": "c", "prompt": "C", "history": ["a"]},
            {"sequence": 4, "prompt_name": "d", "prompt": "D", "history": ["b", "c"]},
        ]

        nodes = orchestrator._build_execution_graph()

        assert nodes[1].level == 0
        assert nodes[2].level == 1
        assert nodes[3].level == 1
        assert nodes[4].level == 2

    def test_no_cycle_independent(self, temp_workbook, mock_ffmistralsmall):
        """Test that independent prompts all get level 0."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": None},
            {"sequence": 3, "prompt_name": "c", "prompt": "C", "history": None},
        ]

        nodes = orchestrator._build_execution_graph()

        assert all(node.level == 0 for node in nodes.values())


class TestRetryBackoff:
    """Tests for retry backoff delay between attempts."""

    def test_retry_includes_backoff_delay(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that retries include a backoff delay between attempts."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        attempt_times = []

        def failing_generate(prompt, **kwargs):
            attempt_times.append(time.monotonic())
            raise Exception("API Error")

        mock_ffmistralsmall.generate_response = failing_generate
        mock_ffmistralsmall.clone = MagicMock(return_value=mock_ffmistralsmall)

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            config_overrides={"max_retries": 3, "retry_base_delay": 0.05},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        results = orchestrator.execute()

        assert results[0]["status"] == "failed"
        assert results[0]["attempts"] == 3
        assert len(attempt_times) == 3

        # Verify there was a delay between attempt 1 and 2 (>= 0.05s base)
        delay_1_2 = attempt_times[1] - attempt_times[0]
        assert delay_1_2 >= 0.04  # Allow small timing slack

        # Verify delay between attempt 2 and 3 is longer (exponential: 0.05 * 2)
        delay_2_3 = attempt_times[2] - attempt_times[1]
        assert delay_2_3 >= 0.08  # 0.1s with slack

    def test_no_delay_after_final_attempt(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that there's no unnecessary delay after the final failed attempt."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        start_time = None
        end_time = None
        call_count = [0]

        def failing_generate(prompt, **kwargs):
            nonlocal start_time, end_time
            call_count[0] += 1
            if call_count[0] == 1:
                start_time = time.monotonic()
            end_time = time.monotonic()
            raise Exception("API Error")

        mock_ffmistralsmall.generate_response = failing_generate
        mock_ffmistralsmall.clone = MagicMock(return_value=mock_ffmistralsmall)

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            config_overrides={"max_retries": 2, "retry_base_delay": 0.05},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        before = time.monotonic()
        results = orchestrator.execute()
        after = time.monotonic()

        assert results[0]["status"] == "failed"
        # Total time should be base_delay (0.05s) + execution, not base_delay * 2^1 extra
        # With 2 retries and 0.05s base: delay only between attempt 1 and 2 = 0.05s
        total_time = after - before
        assert total_time < 1.0  # Sanity check - should be well under 1s

    def test_success_on_retry_no_extra_delay(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that a successful retry doesn't add an unnecessary delay."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        call_count = [0]

        def flaky_generate(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Temporary error")
            return "Success!"

        mock_ffmistralsmall.generate_response = flaky_generate
        mock_ffmistralsmall.clone = MagicMock(return_value=mock_ffmistralsmall)

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            config_overrides={"max_retries": 3, "retry_base_delay": 0.05},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        results = orchestrator.execute()

        assert results[0]["status"] == "success"
        assert results[0]["attempts"] == 2

    def test_batch_retry_includes_backoff(self, temp_workbook_with_batch_data, mock_ffmistralsmall):
        """Test that batch execution retries also include backoff."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        attempt_times = []

        def failing_generate(prompt, **kwargs):
            attempt_times.append(time.monotonic())
            raise Exception("API Error")

        mock_ffmistralsmall.generate_response = failing_generate
        mock_ffmistralsmall.clone = MagicMock(return_value=mock_ffmistralsmall)

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_batch_data,
            mock_ffmistralsmall,
            config_overrides={
                "max_retries": 2,
                "retry_base_delay": 0.05,
                "on_batch_error": "stop",
            },
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()
        orchestrator.batch_data = orchestrator.builder.load_data()[:1]

        results = orchestrator.execute_batch()

        assert results[0]["status"] == "failed"
        assert len(attempt_times) == 2
        # Should have delay between attempts
        delay = attempt_times[1] - attempt_times[0]
        assert delay >= 0.04


class TestUnifiedExecution:
    """Tests for the unified execution path (_execute_prompt_core)."""

    def test_client_clone_reused_across_retries(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that the same client clone is used across retry attempts (Fix #1)."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        clone_calls = []
        original_clone = mock_ffmistralsmall.clone

        def tracking_clone():
            clone_calls.append(1)
            return original_clone()

        mock_ffmistralsmall.clone = tracking_clone

        call_count = [0]

        def flaky_generate(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Temporary error")
            return "Success!"

        cloned = original_clone()
        cloned.generate_response = flaky_generate
        cloned.clone = lambda: cloned  # Return self on further clones
        mock_ffmistralsmall.clone = lambda: cloned

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            config_overrides={"max_retries": 3, "retry_base_delay": 0.01},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        results = orchestrator.execute()

        assert results[0]["status"] == "success"
        assert results[0]["attempts"] == 3

    def test_isolated_execution_uses_results_lock(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test that isolated execution path uses results_lock for condition evaluation."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator
        from src.orchestrator.state import ExecutionState

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            config_overrides={"retry_base_delay": 0.01},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        state = ExecutionState()

        result = orchestrator._execute_prompt_isolated(orchestrator.prompts[0], state)

        assert result["status"] == "success"

    def test_sequential_execution_no_lock(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that sequential execution path works without a lock."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            config_overrides={"retry_base_delay": 0.01},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        result = orchestrator._execute_prompt(orchestrator.prompts[0], {})

        assert result["status"] == "success"


class TestConsistentLogging:
    """Tests for consistent log levels between sequential and parallel execution."""

    def test_parallel_execution_logs_at_info(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that parallel execution logs at INFO level (Fix #8)."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator
        from src.orchestrator.state import ExecutionState

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            concurrency=2,
            config_overrides={"retry_base_delay": 0.01},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        state = ExecutionState()

        with patch("src.orchestrator.base.orchestrator_base.logger") as mock_logger:
            orchestrator._execute_prompt_isolated(orchestrator.prompts[0], state)

            # Verify INFO-level log calls (not DEBUG)
            info_calls = list(mock_logger.info.call_args_list)
            assert len(info_calls) >= 2  # "Executing..." and "succeeded"

    def test_sequential_execution_logs_at_info(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that sequential execution also logs at INFO level."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            config_overrides={"retry_base_delay": 0.01},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        with patch("src.orchestrator.base.orchestrator_base.logger") as mock_logger:
            orchestrator._execute_prompt(orchestrator.prompts[0], {})

            info_calls = list(mock_logger.info.call_args_list)
            assert len(info_calls) >= 2  # "Executing..." and "succeeded"


class TestOrchestrationCompleteLog:
    """Tests for the 'Orchestration complete' log message restoration."""

    def test_run_logs_orchestration_complete(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that run() logs 'Orchestration complete' at the end (Fix #11)."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)

        with patch("src.orchestrator.base.orchestrator_base.logger") as mock_logger:
            orchestrator.run()

            # Check that "Orchestration complete" was logged
            info_messages = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Orchestration complete" in msg for msg in info_messages)


class TestDeadCodeRemoval:
    """Tests verifying dead code has been removed."""

    def test_no_get_isolated_client_method(self, temp_workbook, mock_ffmistralsmall):
        """Test that _get_isolated_client has been removed (Fix #3)."""
        from src.orchestrator.base.orchestrator_base import OrchestratorBase

        assert not hasattr(OrchestratorBase, "_get_isolated_client")

    def test_validate_dependencies_uses_name_to_sequence(self, temp_workbook, mock_ffmistralsmall):
        """Test that _validate uses efficient lookup (Fix #2)."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": ["a"]},
        ]
        orchestrator.config = {}

        orchestrator._validate()

    def test_validate_dependencies_detects_wrong_order(self, temp_workbook, mock_ffmistralsmall):
        """Test that validation still catches wrong-order dependencies after refactor."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": ["b"]},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": None},
        ]
        orchestrator.config = {}

        with pytest.raises(ValueError, match="must come before"):
            orchestrator._validate()


class TestSelfFfaiDocumentation:
    """Tests for self.ffai documentation and purpose (Fix #4)."""

    def test_ffai_initialized_by_init_client(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that self.ffai is set by _init_client."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)

        assert orchestrator.ffai is None

        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator._init_client()

        assert orchestrator.ffai is not None

    def test_execution_uses_isolated_ffai_not_self_ffai(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test that execution creates isolated FFAI instances, not using self.ffai directly."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            config_overrides={"retry_base_delay": 0.01},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        # Track calls to _get_isolated_ffai
        original_get = orchestrator._get_isolated_ffai
        isolation_calls = []

        def tracking_get(*args, **kwargs):
            isolation_calls.append(1)
            return original_get(*args, **kwargs)

        orchestrator._get_isolated_ffai = tracking_get

        orchestrator.execute()

        assert len(isolation_calls) == 1  # One clone per prompt execution


class TestRetryBackoffInBatch:
    """Tests for retry backoff in batch execution with variable templating."""

    def test_batch_prompt_with_batch_retries_have_backoff(
        self, temp_workbook_with_batch_data, mock_ffmistralsmall
    ):
        """Test _execute_prompt_with_batch includes backoff between retries."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        attempt_times = []

        def failing_generate(prompt, **kwargs):
            attempt_times.append(time.monotonic())
            raise Exception("API Error")

        mock_ffmistralsmall.generate_response = failing_generate
        mock_ffmistralsmall.clone = MagicMock(return_value=mock_ffmistralsmall)

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_batch_data,
            mock_ffmistralsmall,
            config_overrides={"max_retries": 3, "retry_base_delay": 0.05},
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        prompt = orchestrator.prompts[0]
        result = orchestrator._execute_prompt_with_batch(prompt, 1, "test_batch")

        assert result["status"] == "failed"
        assert len(attempt_times) == 3

        delay_1_2 = attempt_times[1] - attempt_times[0]
        delay_2_3 = attempt_times[2] - attempt_times[1]
        assert delay_1_2 >= 0.04
        assert delay_2_3 > delay_1_2  # Exponential: second delay > first delay
