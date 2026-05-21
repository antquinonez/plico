from unittest.mock import MagicMock

from src.orchestrator.executor import Executor
from src.orchestrator.state import ExecutionState
from src.orchestrator.state.prompt_node import PromptNode


class TestSequentialExecutionAbortPath:
    """Tests for execute_sequential covering abort propagation (lines 76-90)."""

    def _make_node(self, seq, prompt_name, dependencies=None, level=0):
        prompt = {"sequence": seq, "prompt": f"prompt_{seq}", "prompt_name": prompt_name}
        return PromptNode(
            sequence=seq,
            prompt=prompt,
            dependencies=dependencies or set(),
            level=level,
        )

    def test_abort_skips_remaining_prompts(self):
        node1 = self._make_node(1, "p1", level=0)
        node2 = self._make_node(2, "p2", dependencies={1}, level=1)
        node3 = self._make_node(3, "p3", dependencies={2}, level=2)

        abort_result = {
            "sequence": 1,
            "prompt_name": "p1",
            "status": "success",
            "abort_trace": "'yes' == 'yes'",
        }
        normal_result = {
            "sequence": 2,
            "prompt_name": "p2",
            "status": "success",
        }

        def execute_prompt(prompt, results_by_name):
            if prompt["sequence"] == 1:
                return abort_result
            return normal_result

        orch = MagicMock()
        orch.prompts = [node1.prompt, node2.prompt, node3.prompt]
        orch._get_abort_response.return_value = "-1"
        orch._build_execution_graph.return_value = {1: node1, 2: node2, 3: node3}
        orch._execute_prompt.side_effect = execute_prompt
        orch.progress_callback = None

        executor = Executor()
        results = executor.execute_sequential(orch)

        assert len(results) == 3
        assert results[0]["status"] == "success"
        assert results[0]["abort_trace"] == "'yes' == 'yes'"
        assert results[1]["status"] == "aborted"
        assert results[1]["response"] == "-1"
        assert results[2]["status"] == "aborted"
        assert results[2]["response"] == "-1"

    def test_aborted_result_without_name_still_propagates(self):
        node1 = self._make_node(1, "p1", level=0)
        node2 = self._make_node(2, None, dependencies={1}, level=1)

        abort_result = {
            "sequence": 1,
            "prompt_name": "p1",
            "status": "success",
            "abort_trace": "triggered",
        }

        orch = MagicMock()
        orch.prompts = [node1.prompt, node2.prompt]
        orch._get_abort_response.return_value = "-1"
        orch._build_execution_graph.return_value = {1: node1, 2: node2}
        orch._execute_prompt.return_value = abort_result
        orch.progress_callback = None

        executor = Executor()
        results = executor.execute_sequential(orch)

        assert results[0]["status"] == "success"
        assert results[1]["status"] == "aborted"
        assert results[1]["prompt_name"] is None

    def test_progress_callback_on_abort(self):
        node1 = self._make_node(1, "p1", level=0)
        node2 = self._make_node(2, "p2", dependencies={1}, level=1)

        abort_result = {
            "sequence": 1,
            "prompt_name": "p1",
            "status": "success",
            "abort_trace": "triggered",
        }

        orch = MagicMock()
        orch.prompts = [node1.prompt, node2.prompt]
        orch._get_abort_response.return_value = "-1"
        orch._build_execution_graph.return_value = {1: node1, 2: node2}
        orch._execute_prompt.return_value = abort_result

        progress_calls = []
        orch.progress_callback = lambda *args, **kwargs: progress_calls.append(kwargs)

        executor = Executor()
        results = executor.execute_sequential(orch)

        assert len(results) == 2
        assert results[1]["status"] == "aborted"
        final_call = progress_calls[-1]
        assert final_call["running"] == 0


class TestParallelExecutionErrorPath:
    """Tests for execute_parallel covering exception handling (lines 222-224)."""

    def _make_node(self, seq, prompt_name, dependencies=None, level=0):
        prompt = {"sequence": seq, "prompt": f"prompt_{seq}", "prompt_name": prompt_name}
        return PromptNode(
            sequence=seq,
            prompt=prompt,
            dependencies=dependencies or set(),
            level=level,
        )

    def test_parallel_future_exception_creates_failed_result(self):
        node1 = self._make_node(1, "p1", level=0)

        orch = MagicMock()
        orch.prompts = [node1.prompt]
        orch._get_abort_response.return_value = "-1"
        orch._build_execution_graph.return_value = {1: node1}
        orch.concurrency = 1

        def get_ready_prompts(state, nodes):
            if 1 not in state.completed and 1 not in state.in_progress:
                return [nodes[1]]
            return []

        orch._get_ready_prompts.side_effect = get_ready_prompts

        def execute_isolated(prompt, state):
            raise RuntimeError("Thread crash")

        orch._execute_prompt_isolated.side_effect = execute_isolated
        orch.progress_callback = None

        executor = Executor()
        results = executor.execute_parallel(orch)

        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "Thread crash" in results[0]["error"]
        assert results[0]["prompt_name"] == "p1"

    def test_parallel_deadlock_detection(self):
        node1 = self._make_node(1, "p1", level=0)

        orch = MagicMock()
        orch.prompts = [node1.prompt]
        orch._get_abort_response.return_value = "-1"
        orch._build_execution_graph.return_value = {1: node1}
        orch.concurrency = 1
        orch._get_ready_prompts.return_value = []
        orch.progress_callback = None

        executor = Executor()
        results = executor.execute_parallel(orch)

        assert results == []


class TestBatchExecutionProgressCallback:
    """Tests for execute_batch covering progress callback (line 277)."""

    def test_batch_progress_callback_called(self):
        prompt = {"sequence": 1, "prompt": "test", "prompt_name": "p1"}

        batch_results = [
            {
                "sequence": 1,
                "prompt_name": "p1",
                "status": "success",
                "batch_id": 1,
                "batch_name": "b1",
            },
        ]

        orch = MagicMock()
        orch.prompts = [prompt]
        orch.batch_data = [{"name": "candidate_a"}]
        orch.config = {}
        orch._resolve_batch_name.return_value = "candidate_a"
        orch.shared_prompt_attr_history = []
        orch._execute_single_batch.return_value = batch_results

        progress_calls = []
        orch.progress_callback = lambda *args, **kwargs: progress_calls.append(
            {"args": args, "kwargs": kwargs}
        )

        executor = Executor()
        results = executor.execute_batch(orch)

        assert len(results) == 1
        assert len(progress_calls) == 1
        assert progress_calls[0]["kwargs"]["current_name"] == "batch_1"
        assert progress_calls[0]["kwargs"]["running"] == 1


class TestBatchParallelExecutionEdgeCases:
    """Tests for execute_batch_parallel covering exception and abort paths."""

    def test_batch_parallel_exception_in_batch(self):
        prompt = {"sequence": 1, "prompt": "test", "prompt_name": "p1"}

        orch = MagicMock()
        orch.prompts = [prompt]
        orch.batch_data = [{"name": "candidate_a"}]
        orch.config = {"on_batch_error": "continue"}
        orch.concurrency = 1
        orch._get_abort_response.return_value = "-1"
        orch.shared_prompt_attr_history = []

        def resolve_prompt_variables(prompt, data_row):
            return dict(prompt)

        orch._resolve_prompt_variables.side_effect = resolve_prompt_variables

        def execute_with_batch(resolved_prompt, batch_idx, batch_name, results_by_name, **kwargs):
            raise RuntimeError("Batch execution failed")

        orch._execute_prompt_with_batch.side_effect = execute_with_batch

        batch_results = [
            {
                "sequence": 1,
                "prompt_name": "p1",
                "status": "failed",
                "batch_id": 1,
                "batch_name": "b1",
                "response": "",
            }
        ]

        def resolve_name(data_row, batch_idx):
            return f"batch_{batch_idx}"

        orch._resolve_batch_name.side_effect = resolve_name

        success_result = {
            "sequence": 1,
            "prompt_name": "p1",
            "status": "success",
            "batch_id": 1,
            "batch_name": "b1",
        }
        orch._execute_prompt_with_batch.side_effect = lambda *a, **k: {
            "sequence": 1,
            "prompt_name": "p1",
            "status": "success",
            "batch_id": 1,
            "batch_name": "b1",
        }

        executor = Executor()
        results = executor.execute_batch_parallel(orch)

        assert len(results) == 1
        assert results[0]["status"] == "success"

    def test_batch_parallel_abort_in_batch_skips_remaining(self):
        p1 = {"sequence": 1, "prompt": "p1", "prompt_name": "evaluate"}
        p2 = {"sequence": 2, "prompt": "p2", "prompt_name": "summarize"}

        orch = MagicMock()
        orch.prompts = [p1, p2]
        orch.batch_data = [{"name": "candidate_a"}]
        orch.config = {"on_batch_error": "continue"}
        orch.concurrency = 1
        orch._get_abort_response.return_value = "-1"
        orch.shared_prompt_attr_history = []

        call_count = {"n": 0}

        def execute_with_batch(resolved_prompt, batch_idx, batch_name, results_by_name, **kwargs):
            call_count["n"] += 1
            if resolved_prompt["sequence"] == 1:
                return {
                    "sequence": 1,
                    "prompt_name": "evaluate",
                    "status": "success",
                    "batch_id": batch_idx,
                    "batch_name": batch_name,
                    "abort_trace": "triggered",
                }
            return {
                "sequence": 2,
                "prompt_name": "summarize",
                "status": "success",
                "batch_id": batch_idx,
                "batch_name": batch_name,
            }

        orch._execute_prompt_with_batch.side_effect = execute_with_batch
        orch._resolve_prompt_variables.side_effect = lambda p, d: dict(p)
        orch._resolve_batch_name.side_effect = lambda d, i: f"batch_{i}"

        executor = Executor()
        results = executor.execute_batch_parallel(orch)

        assert len(results) == 2
        assert results[0]["status"] == "success"
        assert results[0]["abort_trace"] == "triggered"
        assert results[1]["status"] == "aborted"

    def test_batch_parallel_on_error_stop(self):
        p1 = {"sequence": 1, "prompt": "p1", "prompt_name": "evaluate"}
        p2 = {"sequence": 2, "prompt": "p2", "prompt_name": "summarize"}
        p3 = {"sequence": 3, "prompt": "p3", "prompt_name": "conclude"}

        orch = MagicMock()
        orch.prompts = [p1, p2, p3]
        orch.batch_data = [{"name": "candidate_a"}]
        orch.config = {"on_batch_error": "stop"}
        orch.concurrency = 1
        orch._get_abort_response.return_value = "-1"
        orch.shared_prompt_attr_history = []

        def execute_with_batch(resolved_prompt, batch_idx, batch_name, results_by_name, **kwargs):
            if resolved_prompt["sequence"] == 1:
                return {
                    "sequence": 1,
                    "prompt_name": "evaluate",
                    "status": "failed",
                    "batch_id": batch_idx,
                    "batch_name": batch_name,
                    "error": "API error",
                }
            return {
                "sequence": resolved_prompt["sequence"],
                "prompt_name": resolved_prompt["prompt_name"],
                "status": "success",
                "batch_id": batch_idx,
                "batch_name": batch_name,
            }

        orch._execute_prompt_with_batch.side_effect = execute_with_batch
        orch._resolve_prompt_variables.side_effect = lambda p, d: dict(p)
        orch._resolve_batch_name.side_effect = lambda d, i: f"batch_{i}"

        executor = Executor()
        results = executor.execute_batch_parallel(orch)

        assert len(results) == 1
        assert results[0]["status"] == "failed"

    def test_batch_parallel_progress_callback(self):
        p1 = {"sequence": 1, "prompt": "p1", "prompt_name": "evaluate"}

        orch = MagicMock()
        orch.prompts = [p1]
        orch.batch_data = [{"name": "candidate_a"}]
        orch.config = {}
        orch.concurrency = 1
        orch._get_abort_response.return_value = "-1"
        orch.shared_prompt_attr_history = []

        orch._execute_prompt_with_batch.side_effect = lambda rp, bi, bn, rbn, **kw: {
            "sequence": 1,
            "prompt_name": "evaluate",
            "status": "success",
            "batch_id": bi,
            "batch_name": bn,
        }
        orch._resolve_prompt_variables.side_effect = lambda p, d: dict(p)
        orch._resolve_batch_name.side_effect = lambda d, i: f"batch_{i}"

        progress_calls = []
        orch.progress_callback = lambda *a, **kw: progress_calls.append(kw)

        executor = Executor()
        results = executor.execute_batch_parallel(orch)

        assert len(results) == 1
        assert len(progress_calls) == 1
        assert progress_calls[0]["current_name"] == "batch_1"


class TestUpdateStateCounts:
    """Tests for _update_state_counts covering all status branches (lines 418-425)."""

    def test_success_count(self):
        executor = Executor()
        state = ExecutionState()
        result = {"status": "success"}
        executor._update_state_counts(state, result)
        assert state.success_count == 1
        assert state.failed_count == 0

    def test_skipped_count(self):
        executor = Executor()
        state = ExecutionState()
        result = {"status": "skipped"}
        executor._update_state_counts(state, result)
        assert state.skipped_count == 1
        assert state.failed_count == 0

    def test_aborted_count(self):
        executor = Executor()
        state = ExecutionState()
        result = {"status": "aborted"}
        executor._update_state_counts(state, result)
        assert state.aborted_count == 1
        assert state.failed_count == 0

    def test_failed_count(self):
        executor = Executor()
        state = ExecutionState()
        result = {"status": "failed"}
        executor._update_state_counts(state, result)
        assert state.failed_count == 1
        assert state.success_count == 0

    def test_max_rounds_exceeded_counts_as_failed(self):
        executor = Executor()
        state = ExecutionState()
        result = {"status": "max_rounds_exceeded"}
        executor._update_state_counts(state, result)
        assert state.failed_count == 1


class TestHandleExecutionError:
    """Tests for _handle_execution_error (lines 429-434)."""

    def test_creates_failed_result(self):
        prompt = {"sequence": 5, "prompt": "test", "prompt_name": "broken"}
        node = PromptNode(sequence=5, prompt=prompt, dependencies=set(), level=0)

        executor = Executor()
        state = ExecutionState()
        executor._handle_execution_error(state, node, "connection refused")

        assert 5 in state.completed
        assert state.failed_count == 1
        assert state.current_name == "broken"
        assert len(state.results) == 1
        assert state.results[0]["status"] == "failed"
        assert state.results[0]["error"] == "connection refused"
        assert state.results[0]["sequence"] == 5

    def test_node_without_name_uses_seq(self):
        prompt = {"sequence": 7, "prompt": "test", "prompt_name": None}
        node = PromptNode(sequence=7, prompt=prompt, dependencies=set(), level=0)

        executor = Executor()
        state = ExecutionState()
        executor._handle_execution_error(state, node, "timeout")

        assert state.current_name == "seq_7"


class TestBatchExecutionOnErrorStop:
    """Tests for execute_batch covering on_batch_error='stop' (lines 271-274)."""

    def test_batch_stops_on_failure(self):
        p1 = {"sequence": 1, "prompt": "p1", "prompt_name": "eval"}
        p2 = {"sequence": 2, "prompt": "p2", "prompt_name": "summarize"}

        orch = MagicMock()
        orch.prompts = [p1]
        orch.batch_data = [{"name": "a"}, {"name": "b"}]
        orch.config = {"on_batch_error": "stop"}
        orch.shared_prompt_attr_history = []
        orch._resolve_batch_name.side_effect = lambda d, i: f"batch_{i}"

        failed_batch = [
            {
                "sequence": 1,
                "prompt_name": "eval",
                "status": "failed",
                "batch_id": 1,
                "batch_name": "batch_1",
            },
        ]
        success_batch = [
            {
                "sequence": 1,
                "prompt_name": "eval",
                "status": "success",
                "batch_id": 2,
                "batch_name": "batch_2",
            },
        ]

        call_count = {"n": 0}

        def execute_single_batch(batch_idx, data_row, batch_name, **kwargs):
            call_count["n"] += 1
            if batch_idx == 1:
                return failed_batch
            return success_batch

        orch._execute_single_batch.side_effect = execute_single_batch
        orch.progress_callback = None

        executor = Executor()
        results = executor.execute_batch(orch)

        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert call_count["n"] == 1
