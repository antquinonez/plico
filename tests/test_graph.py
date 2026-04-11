# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for src.orchestrator.graph -- dependency graph and condition evaluation.

Migrated from:
- test_orchestrator_base.py::TestDependencyCycleDetection
- test_excel_orchestrator.py::TestExcelOrchestratorParallelExecution (graph tests)
- test_excel_orchestrator.py::test_condition_dependencies_in_graph

These are pure function tests -- no orchestrator instance needed.
"""

import pytest

from src.orchestrator.graph import build_execution_graph, evaluate_condition, get_ready_prompts
from src.orchestrator.state import ExecutionState


class TestBuildExecutionGraph:
    """Tests for build_execution_graph."""

    def test_cycle_detection_simple(self):
        prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "Hello", "history": ["b"]},
            {"sequence": 2, "prompt_name": "b", "prompt": "World", "history": ["a"]},
        ]

        with pytest.raises(ValueError, match="Dependency cycle detected"):
            build_execution_graph(prompts)

    def test_cycle_detection_three_node(self):
        prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": ["c"]},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": ["a"]},
            {"sequence": 3, "prompt_name": "c", "prompt": "C", "history": ["b"]},
        ]

        with pytest.raises(ValueError, match="Dependency cycle detected"):
            build_execution_graph(prompts)

    def test_self_referencing_cycle(self):
        prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "Hello", "history": ["a"]},
        ]

        with pytest.raises(ValueError, match="Dependency cycle detected"):
            build_execution_graph(prompts)

    def test_no_cycle_linear_chain(self):
        prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": ["a"]},
            {"sequence": 3, "prompt_name": "c", "prompt": "C", "history": ["b"]},
        ]

        nodes = build_execution_graph(prompts)

        assert nodes[1].level == 0
        assert nodes[2].level == 1
        assert nodes[3].level == 2

    def test_no_cycle_diamond(self):
        prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": ["a"]},
            {"sequence": 3, "prompt_name": "c", "prompt": "C", "history": ["a"]},
            {"sequence": 4, "prompt_name": "d", "prompt": "D", "history": ["b", "c"]},
        ]

        nodes = build_execution_graph(prompts)

        assert nodes[1].level == 0
        assert nodes[2].level == 1
        assert nodes[3].level == 1
        assert nodes[4].level == 2

    def test_no_cycle_independent(self):
        prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": None},
            {"sequence": 3, "prompt_name": "c", "prompt": "C", "history": None},
        ]

        nodes = build_execution_graph(prompts)

        assert all(node.level == 0 for node in nodes.values())

    def test_empty_prompts(self):
        nodes = build_execution_graph([])
        assert nodes == {}

    def test_condition_creates_dependency(self):
        """Test that condition references are added to dependency graph."""
        prompts = [
            {
                "sequence": 1,
                "prompt_name": "first",
                "prompt": "Hello",
                "history": None,
                "condition": "",
            },
            {
                "sequence": 2,
                "prompt_name": "second",
                "prompt": "World",
                "history": None,
                "condition": '{{first.status}} == "success"',
            },
        ]

        nodes = build_execution_graph(prompts)

        assert 1 in nodes[2].dependencies

    def test_three_nodes_dependency_levels(self):
        """Test graph with two independent and one dependent node."""
        prompts = [
            {"sequence": 1, "prompt_name": "first", "prompt": "Task A", "history": None},
            {"sequence": 2, "prompt_name": "second", "prompt": "Task B", "history": None},
            {
                "sequence": 3,
                "prompt_name": "third",
                "prompt": "Task C depends on first",
                "history": ["first"],
            },
        ]

        nodes = build_execution_graph(prompts)

        assert nodes[1].level == 0
        assert nodes[2].level == 0
        assert nodes[3].level == 1


class TestGetReadyPrompts:
    """Tests for get_ready_prompts."""

    def _make_nodes(self, prompts):
        return build_execution_graph(prompts)

    def test_returns_root_nodes_initially(self):
        prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": ["a"]},
        ]
        nodes = self._make_nodes(prompts)
        state = ExecutionState(pending=dict(nodes))

        ready = get_ready_prompts(state, nodes)

        assert len(ready) == 1
        assert ready[0].sequence == 1

    def test_returns_dependent_after_dep_completed(self):
        prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": ["a"]},
        ]
        nodes = self._make_nodes(prompts)
        state = ExecutionState(pending=dict(nodes))
        state.completed = {1}

        ready = get_ready_prompts(state, nodes)

        assert len(ready) == 1
        assert ready[0].sequence == 2

    def test_excludes_in_progress(self):
        prompts = [
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": None},
        ]
        nodes = self._make_nodes(prompts)
        state = ExecutionState(pending=dict(nodes))
        state.in_progress = {1}

        ready = get_ready_prompts(state, nodes)

        assert len(ready) == 1
        assert ready[0].sequence == 2

    def test_sorted_by_level_then_sequence(self):
        prompts = [
            {"sequence": 3, "prompt_name": "c", "prompt": "C", "history": None},
            {"sequence": 1, "prompt_name": "a", "prompt": "A", "history": None},
            {"sequence": 2, "prompt_name": "b", "prompt": "B", "history": None},
        ]
        nodes = self._make_nodes(prompts)
        state = ExecutionState(pending=dict(nodes))

        ready = get_ready_prompts(state, nodes)

        assert [n.sequence for n in ready] == [1, 2, 3]


class TestEvaluateCondition:
    """Tests for evaluate_condition."""

    def test_empty_condition(self):
        should_exec, result, error = evaluate_condition({"condition": ""}, {})
        assert should_exec is True
        assert result is None
        assert error is None

    def test_whitespace_condition(self):
        should_exec, result, error = evaluate_condition({"condition": "   "}, {})
        assert should_exec is True

    def test_none_condition(self):
        should_exec, result, error = evaluate_condition({"condition": None}, {})
        assert should_exec is True

    def test_true_condition(self):
        results_by_name = {"step": {"status": "success", "response": "ok"}}
        should_exec, result, error = evaluate_condition(
            {"condition": '{{step.status}} == "success"'},
            results_by_name,
        )
        assert should_exec is True
        assert result is True

    def test_false_condition(self):
        results_by_name = {"step": {"status": "failed", "response": ""}}
        should_exec, result, error = evaluate_condition(
            {"condition": '{{step.status}} == "success"'},
            results_by_name,
        )
        assert should_exec is False
        assert result is False
