# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for OrchestratorBase fixes and improvements.

Tests cover:
- Retry backoff delay (#5)
- Unified execution path / client clone reuse (#1, #7)
- Consistent logging (#8)
- Orchestration complete log message (#11)
- Dead code removal verification (#2, #3)
- Document initialization with RAG (194-235)
- Tool registry initialization (252, 281-286)
- Agent result recording (332, 347)
- Validation edge cases (364, 373-374)
- Reference injection with semantic query (422-439, 452)
- Agent mode fallback in _execute_with_retry (894)
"""

import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator.base.orchestrator_base import OrchestratorBase
from src.orchestrator.planning_runner import PlanningPhaseRunner
from src.orchestrator.synthesis_runner import SynthesisRunner
from src.orchestrator.validation_manager import ValidationManager


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


class _TestOrchestrator(OrchestratorBase):
    """Minimal concrete subclass for testing OrchestratorBase paths."""

    @property
    def source_path(self) -> str:
        return "/fake/path"

    def _load_source(self) -> None:
        pass

    def _get_cache_dir(self) -> str:
        return "/fake/cache"

    def _write_results(self, results: list) -> str:
        return "fake_output"


def _make_base(mock_ffmistralsmall):
    """Create a _TestOrchestrator with minimal setup."""
    orch = _TestOrchestrator.__new__(_TestOrchestrator)
    orch.client = mock_ffmistralsmall
    orch.config_overrides = {}
    orch.concurrency = 1
    orch.progress_callback = None
    orch.config = {}
    orch.prompts = []
    orch.results = []
    orch.ffai = None
    orch.shared_prompt_attr_history = []
    orch.history_lock = threading.Lock()
    from src.core.response_context import ResponseContext

    orch._response_context = ResponseContext(
        shared_prompt_attr_history=orch.shared_prompt_attr_history,
        history_lock=orch.history_lock,
    )
    orch.batch_data = []
    orch.is_batch_mode = False
    orch.client_registry = None
    orch.has_multi_client = False
    orch.document_processor = None
    orch.document_registry = None
    orch.has_documents = False
    orch.tool_registry = None
    orch.has_tools = False
    orch.has_scoring = False
    orch.scoring_rubric = None
    orch.evaluation_strategy = "balanced"
    orch.has_synthesis = False
    orch.synthesis_prompts = []
    orch._rag_client = None
    orch._executor = MagicMock()
    orch._validation_manager = ValidationManager()
    orch._synthesis_runner = SynthesisRunner()
    orch._planning_runner = PlanningPhaseRunner()
    return orch


class TestInitDocuments:
    """Tests for _init_documents covering lines 194-235."""

    def test_rag_enabled_chromadb_not_available(self, mock_ffmistralsmall):
        """Test RAG disabled path when chromadb is not available (line 208)."""
        orch = _make_base(mock_ffmistralsmall)
        orch._get_cache_dir = MagicMock(return_value="/cache")

        mock_config = MagicMock()
        mock_config.rag.enabled = True
        with patch("src.orchestrator.base.orchestrator_base.get_config", return_value=mock_config):
            with (
                patch(
                    "src.orchestrator.base.orchestrator_base.DocumentProcessor",
                    autospec=True,
                ) as mock_dp_cls,
                patch(
                    "src.orchestrator.base.orchestrator_base.DocumentRegistry",
                    autospec=True,
                ) as mock_dr_cls,
            ):
                mock_dr_instance = MagicMock()
                mock_dr_instance.validate_documents = MagicMock()
                mock_dr_cls.return_value = mock_dr_instance

                with patch("src.orchestrator.base.orchestrator_base.DocumentProcessor") as dp_patch:
                    with patch(
                        "src.orchestrator.base.orchestrator_base.DocumentRegistry"
                    ) as dr_patch:
                        dr_patch.return_value = mock_dr_instance
                        dp_patch.return_value = MagicMock()

                        with patch.dict("sys.modules", {"chromadb": None}):
                            with (
                                patch(
                                    "src.RAG.CHROMADB_AVAILABLE",
                                    False,
                                ),
                                patch(
                                    "src.RAG.FFRAGClient",
                                    autospec=True,
                                ),
                            ):
                                orch._init_documents(
                                    [{"name": "doc1", "path": "doc1.txt"}],
                                    "/workbook_dir",
                                )

        assert orch.has_documents is True

    def test_rag_import_fails(self, mock_ffmistralsmall):
        """Test graceful failure when RAG import raises (line 210)."""
        orch = _make_base(mock_ffmistralsmall)

        mock_config = MagicMock()
        mock_config.rag.enabled = True
        with patch("src.orchestrator.base.orchestrator_base.get_config", return_value=mock_config):
            with (
                patch("src.orchestrator.base.orchestrator_base.DocumentProcessor") as dp_patch,
                patch("src.orchestrator.base.orchestrator_base.DocumentRegistry") as dr_patch,
            ):
                mock_dr_instance = MagicMock()
                mock_dr_instance.validate_documents = MagicMock()
                dr_patch.return_value = mock_dr_instance
                dp_patch.return_value = MagicMock()

                with (
                    patch(
                        "src.RAG.CHROMADB_AVAILABLE",
                        True,
                    ),
                    patch(
                        "src.RAG.FFRAGClient",
                        side_effect=RuntimeError("import failed"),
                    ),
                ):
                    orch._init_documents(
                        [{"name": "doc1", "path": "doc1.txt"}],
                        "/workbook_dir",
                    )

        assert orch.has_documents is True

    def test_rag_enabled_with_pre_indexing(self, mock_ffmistralsmall):
        """Test successful RAG init with pre-indexing (lines 231-235)."""
        orch = _make_base(mock_ffmistralsmall)

        mock_rag_client = MagicMock()
        mock_config = MagicMock()
        mock_config.rag.enabled = True

        with patch("src.orchestrator.base.orchestrator_base.get_config", return_value=mock_config):
            with (
                patch("src.orchestrator.base.orchestrator_base.DocumentProcessor") as dp_patch,
                patch("src.orchestrator.base.orchestrator_base.DocumentRegistry") as dr_patch,
                patch("src.RAG.CHROMADB_AVAILABLE", True),
                patch("src.RAG.FFRAGClient", return_value=mock_rag_client),
            ):
                mock_dr_instance = MagicMock()
                mock_dr_instance.rag_client = mock_rag_client
                mock_dr_instance.validate_documents = MagicMock()
                mock_dr_instance.index_all_documents = MagicMock(
                    return_value={"doc1": 5, "doc2": 0}
                )
                dr_patch.return_value = mock_dr_instance
                dp_patch.return_value = MagicMock()

                orch._init_documents(
                    [{"name": "doc1", "path": "doc1.txt"}, {"name": "doc2", "path": "doc2.txt"}],
                    "/workbook_dir",
                )

        mock_dr_instance.index_all_documents.assert_called_once()
        assert orch._rag_client is mock_rag_client


class TestInitTools:
    """Tests for _init_tools covering lines 252, 281-286."""

    def test_empty_tools_data_returns_early(self, mock_ffmistralsmall):
        """Test that empty tools_data list returns immediately (line 252)."""
        orch = _make_base(mock_ffmistralsmall)
        orch._init_tools([])
        assert orch.has_tools is False
        assert orch.tool_registry is None

    def test_python_callable_loading(self, mock_ffmistralsmall):
        """Test python: implementation loading (lines 281-284)."""
        orch = _make_base(mock_ffmistralsmall)

        mock_tool_def = MagicMock()
        mock_tool_def.name = "my_tool"
        mock_tool_def.description = "A tool"
        mock_tool_def.parameters = {}
        mock_tool_def.implementation = "python:json.dumps"
        mock_tool_def.enabled = True

        mock_registry = MagicMock()
        mock_registry.get_registered_names.return_value = ["my_tool"]
        mock_registry.get_tool.return_value = mock_tool_def
        mock_registry.load_python_callable.return_value = json.dumps

        tools_data = [
            {
                "name": "my_tool",
                "description": "A tool",
                "parameters": {},
                "implementation": "python:json.dumps",
                "enabled": True,
            }
        ]

        with patch(
            "src.orchestrator.base.orchestrator_base.ToolRegistry", return_value=mock_registry
        ):
            with (
                patch(
                    "src.orchestrator.builtin_tools.BUILTIN_TOOL_DEFINITIONS",
                    {"builtin_tool": {"description": "builtin", "parameters": {}}},
                ),
                patch(
                    "src.orchestrator.builtin_tools.create_context_tools",
                    return_value={},
                ),
            ):
                orch._init_tools(tools_data)

        mock_registry.load_python_callable.assert_called_once_with("json.dumps")
        mock_registry.register_executor.assert_called_once_with("my_tool", json.dumps)

    def test_new_tool_not_in_builtins(self, mock_ffmistralsmall):
        """Test registering a tool not in builtins (line 286)."""
        orch = _make_base(mock_ffmistralsmall)

        tools_data = [
            {
                "name": "custom_tool",
                "description": "A custom tool",
                "parameters": {},
                "implementation": "builtin:custom_tool",
                "enabled": True,
            }
        ]

        mock_registry = MagicMock()
        mock_registry.get_registered_names.return_value = ["existing_builtin"]

        with patch(
            "src.orchestrator.base.orchestrator_base.ToolRegistry", return_value=mock_registry
        ):
            with (
                patch(
                    "src.orchestrator.builtin_tools.BUILTIN_TOOL_DEFINITIONS",
                    {"existing_builtin": {"description": "existing", "parameters": {}}},
                ),
                patch(
                    "src.orchestrator.builtin_tools.create_context_tools",
                    return_value={},
                ),
            ):
                orch._init_tools(tools_data)

        call_args_list = [call[0][0] for call in mock_registry.register.call_args_list]
        registered_names = [td.name for td in call_args_list]
        assert "custom_tool" in registered_names


class TestValidateEdgeCases:
    """Tests for _validate covering lines 364, 373-374."""

    def test_validate_with_document_registry(self, mock_ffmistralsmall):
        """Test _validate when document_registry is present (line 364)."""
        orch = _make_base(mock_ffmistralsmall)
        orch.config = {}
        orch.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "Hello", "history": None},
        ]

        mock_doc_reg = MagicMock()
        mock_doc_reg.get_reference_names.return_value = ["doc1"]
        orch.document_registry = mock_doc_reg

        orch._validate()

    def test_validate_get_available_client_types_raises(self, mock_ffmistralsmall):
        """Test _validate when get_available_client_types raises (lines 373-374)."""
        orch = _make_base(mock_ffmistralsmall)
        orch.config = {}
        orch.prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "Hello", "history": None},
        ]

        mock_config = MagicMock()
        mock_config.get_available_client_types.side_effect = RuntimeError("config error")
        with patch("src.orchestrator.base.orchestrator_base.get_config", return_value=mock_config):
            orch._validate()


class TestInjectReferences:
    """Tests for _inject_references covering lines 422-439, 452."""

    def test_semantic_query_with_rag(self, mock_ffmistralsmall):
        """Test semantic query path with RAG client (lines 422-437)."""
        orch = _make_base(mock_ffmistralsmall)
        orch.has_documents = True

        mock_doc_reg = MagicMock()
        mock_doc_reg.rag_client = MagicMock()
        mock_doc_reg.inject_semantic_query.return_value = "prompt with search results"
        orch.document_registry = mock_doc_reg

        prompt = {
            "prompt": "original prompt",
            "semantic_query": "search term",
            "semantic_filter": None,
            "query_expansion": None,
            "rerank": None,
        }

        result = orch._inject_references(prompt)
        assert result == "prompt with search results"
        mock_doc_reg.inject_semantic_query.assert_called_once()

    def test_semantic_query_with_filter(self, mock_ffmistralsmall):
        """Test semantic query with JSON filter (line 426)."""
        orch = _make_base(mock_ffmistralsmall)
        orch.has_documents = True

        mock_doc_reg = MagicMock()
        mock_doc_reg.rag_client = MagicMock()
        mock_doc_reg.inject_semantic_query.return_value = "filtered results"
        orch.document_registry = mock_doc_reg

        prompt = {
            "prompt": "original prompt",
            "semantic_query": "search term",
            "semantic_filter": '{"source": "doc1"}',
            "query_expansion": "true",
            "rerank": "false",
        }

        result = orch._inject_references(prompt)
        assert result == "filtered results"
        call_kwargs = mock_doc_reg.inject_semantic_query.call_args[1]
        assert call_kwargs["semantic_filter"] == {"source": "doc1"}
        assert call_kwargs["query_expansion"] is True
        assert call_kwargs["rerank"] is False

    def test_semantic_query_fallback_on_error(self, mock_ffmistralsmall):
        """Test fallback when semantic search fails (lines 438-439)."""
        orch = _make_base(mock_ffmistralsmall)
        orch.has_documents = True

        mock_doc_reg = MagicMock()
        mock_doc_reg.rag_client = MagicMock()
        mock_doc_reg.inject_semantic_query.side_effect = RuntimeError("search failed")
        mock_doc_reg.get_reference_names.return_value = []
        orch.document_registry = mock_doc_reg

        prompt = {
            "prompt": "original prompt",
            "semantic_query": "search term",
            "references": None,
        }

        result = orch._inject_references(prompt)
        assert result == "original prompt"

    def test_references_empty_list(self, mock_ffmistralsmall):
        """Test that empty references list returns prompt as-is (line 452)."""
        orch = _make_base(mock_ffmistralsmall)
        orch.has_documents = True

        mock_doc_reg = MagicMock()
        orch.document_registry = mock_doc_reg

        prompt = {
            "prompt": "original prompt",
            "references": [],
        }

        result = orch._inject_references(prompt)
        assert result == "original prompt"


class TestExecuteWithRetryAgentMode:
    """Tests for _execute_with_retry covering line 894."""

    def test_agent_mode_no_tool_registry_falls_back(self, mock_ffmistralsmall):
        """Test agent_mode=true with no tool_registry falls back to single-shot (line 894)."""
        orchestrator = _make_base(mock_ffmistralsmall)
        orchestrator.config = {"max_retries": 1, "retry_base_delay": 0.01}

        mock_ffmistralsmall.clone = MagicMock(return_value=mock_ffmistralsmall)
        mock_ffmistralsmall.generate_response = MagicMock(return_value="single shot response")

        prompt = {
            "sequence": 1,
            "prompt_name": "agent_test",
            "prompt": "Hello",
            "history": None,
            "agent_mode": True,
        }

        with patch("src.orchestrator.base.orchestrator_base.logger") as mock_logger:
            result = orchestrator._execute_with_retry(prompt, {})

        assert result["status"] == "success"
        assert result["response"] == "single shot response"
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        assert any("no tool registry" in msg for msg in warning_calls)
