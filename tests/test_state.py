# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for state management."""

import threading

from src.orchestrator.state import ExecutionState, PromptNode


class TestPromptNode:
    """Tests for PromptNode."""

    def test_init_basic(self):
        """Test basic initialization."""
        node = PromptNode(sequence=1, prompt={"prompt": "Hello"})
        assert node.sequence == 1
        assert node.prompt == {"prompt": "Hello"}
        assert node.dependencies == set()
        assert node.level == 0

    def test_init_with_dependencies(self):
        """Test initialization with dependencies."""
        node = PromptNode(
            sequence=3,
            prompt={"prompt": "Test"},
            dependencies={1, 2},
            level=1,
        )
        assert node.sequence == 3
        assert node.dependencies == {1, 2}
        assert node.level == 1

    def test_hash(self):
        """Test hashing by sequence."""
        node1 = PromptNode(sequence=1, prompt={"a": "b"})
        node2 = PromptNode(sequence=1, prompt={"c": "d"})

        assert hash(node1) == hash(node2)
        assert node1 == node2

    def test_not_equal(self):
        """Test inequality."""
        node1 = PromptNode(sequence=1, prompt={})
        node2 = PromptNode(sequence=2, prompt={})

        assert node1 != node2

    def test_is_ready_no_dependencies(self):
        """Test is_ready with no dependencies."""
        node = PromptNode(sequence=1, prompt={})
        assert node.is_ready(set()) is True
        assert node.is_ready({2, 3}) is True

    def test_is_ready_with_dependencies(self):
        """Test is_ready with dependencies."""
        node = PromptNode(sequence=3, prompt={}, dependencies={1, 2})

        assert node.is_ready(set()) is False
        assert node.is_ready({1}) is False
        assert node.is_ready({1, 2}) is True
        assert node.is_ready({1, 2, 4}) is True

    def test_add_dependency(self):
        """Test adding a dependency."""
        node = PromptNode(sequence=2, prompt={})
        node.add_dependency(1)

        assert 1 in node.dependencies

    def test_get_prompt_name(self):
        """Test getting prompt name."""
        node = PromptNode(sequence=1, prompt={"prompt_name": "test"})
        assert node.get_prompt_name() == "test"

        node2 = PromptNode(sequence=2, prompt={})
        assert node2.get_prompt_name() is None


class TestExecutionState:
    """Tests for ExecutionState."""

    def test_init(self):
        """Test basic initialization."""
        state = ExecutionState()
        assert state.completed == set()
        assert state.in_progress == set()
        assert state.pending == {}
        assert state.results == []
        assert state.success_count == 0
        assert state.failed_count == 0
        assert state.skipped_count == 0

    def test_start_prompt(self):
        """Test starting a prompt."""
        state = ExecutionState()
        assert state.start_prompt(1) is True
        assert 1 in state.in_progress

    def test_start_prompt_twice_fails(self):
        """Test that starting a prompt twice fails."""
        state = ExecutionState()
        state.start_prompt(1)
        assert state.start_prompt(1) is False

    def test_start_completed_prompt_fails(self):
        """Test that starting a completed prompt fails."""
        state = ExecutionState()
        state.start_prompt(1)
        state.complete_prompt(1, {"sequence": 1, "status": "success"})
        assert state.start_prompt(1) is False

    def test_complete_prompt_success(self):
        """Test completing a prompt successfully."""
        state = ExecutionState()
        state.start_prompt(1)
        state.complete_prompt(1, {"sequence": 1, "status": "success", "response": "done"})

        assert 1 in state.completed
        assert 1 not in state.in_progress
        assert state.success_count == 1
        assert len(state.results) == 1

    def test_complete_prompt_failed(self):
        """Test completing a failed prompt."""
        state = ExecutionState()
        state.start_prompt(1)
        state.complete_prompt(1, {"sequence": 1, "status": "failed", "error": "oops"})

        assert state.failed_count == 1

    def test_complete_prompt_skipped(self):
        """Test completing a skipped prompt."""
        state = ExecutionState()
        state.start_prompt(1)
        state.complete_prompt(1, {"sequence": 1, "status": "skipped"})

        assert state.skipped_count == 1

    def test_complete_prompt_stores_by_name(self):
        """Test that completion stores result by name."""
        state = ExecutionState()
        state.start_prompt(1)
        state.complete_prompt(1, {"sequence": 1, "prompt_name": "test", "status": "success"})

        assert "test" in state.results_by_name
        assert state.results_by_name["test"]["sequence"] == 1

    def test_fail_prompt(self):
        """Test failing a prompt."""
        state = ExecutionState()
        state.start_prompt(1)
        state.fail_prompt(1, "API error")

        assert 1 in state.completed
        assert 1 not in state.in_progress
        assert state.failed_count == 1

    def test_get_ready_nodes(self):
        """Test getting ready nodes."""
        state = ExecutionState()
        node1 = PromptNode(sequence=1, prompt={})
        node2 = PromptNode(sequence=2, prompt={}, dependencies={1})
        state.pending = {1: node1, 2: node2}

        ready = state.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].sequence == 1

        state.complete_prompt(1, {"sequence": 1, "status": "success"})
        ready = state.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].sequence == 2

    def test_has_deadlock(self):
        """Test deadlock detection."""
        state = ExecutionState()
        node1 = PromptNode(sequence=1, prompt={}, dependencies={2})
        node2 = PromptNode(sequence=2, prompt={}, dependencies={1})
        state.pending = {1: node1, 2: node2}

        assert state.has_deadlock() is True

    def test_no_deadlock_with_progress(self):
        """Test no deadlock when in progress."""
        state = ExecutionState()
        node1 = PromptNode(sequence=1, prompt={})
        state.pending = {1: node1}
        state.start_prompt(1)

        assert state.has_deadlock() is False

    def test_is_complete(self):
        """Test completion check."""
        state = ExecutionState()
        node1 = PromptNode(sequence=1, prompt={})
        node2 = PromptNode(sequence=2, prompt={})
        state.pending = {1: node1, 2: node2}

        assert state.is_complete() is False

        state.complete_prompt(1, {"sequence": 1, "status": "success"})
        assert state.is_complete() is False

        state.complete_prompt(2, {"sequence": 2, "status": "success"})
        assert state.is_complete() is True

    def test_get_progress(self):
        """Test progress reporting."""
        state = ExecutionState()
        node1 = PromptNode(sequence=1, prompt={})
        node2 = PromptNode(sequence=2, prompt={})
        state.pending = {1: node1, 2: node2}

        state.start_prompt(1)
        state.complete_prompt(1, {"sequence": 1, "status": "success"})

        progress = state.get_progress()
        assert progress["total"] == 2
        assert progress["completed"] == 1
        assert progress["in_progress"] == 0
        assert progress["success"] == 1

    def test_get_result_by_name(self):
        """Test getting result by name."""
        state = ExecutionState()
        state.complete_prompt(1, {"sequence": 1, "prompt_name": "test", "status": "success"})

        result = state.get_result_by_name("test")
        assert result is not None
        assert result["sequence"] == 1

        assert state.get_result_by_name("nonexistent") is None

    def test_get_result_by_sequence(self):
        """Test getting result by sequence."""
        state = ExecutionState()
        state.complete_prompt(1, {"sequence": 1, "status": "success"})

        result = state.get_result_by_sequence(1)
        assert result is not None

        assert state.get_result_by_sequence(999) is None

    def test_get_sorted_results(self):
        """Test getting sorted results."""
        state = ExecutionState()
        state.complete_prompt(3, {"sequence": 3, "status": "success"})
        state.complete_prompt(1, {"sequence": 1, "status": "success"})
        state.complete_prompt(2, {"sequence": 2, "status": "success"})

        results = state.get_sorted_results()
        assert [r["sequence"] for r in results] == [1, 2, 3]

    def test_thread_safety(self):
        """Test thread safety of state operations."""
        state = ExecutionState()

        def worker(seq: int):
            state.start_prompt(seq)
            state.complete_prompt(
                seq, {"sequence": seq, "status": "success", "response": f"result_{seq}"}
            )

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(state.completed) == 10
        assert state.success_count == 10
        assert len(state.results) == 10
