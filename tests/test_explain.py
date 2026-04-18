# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for the execution plan explain module."""

from __future__ import annotations

import pytest

from src.orchestrator.explain import (
    build_explain_plan,
    format_explain,
    format_prompt_preview,
)
from src.orchestrator.graph import (
    build_execution_graph,
    build_execution_graph_with_edges,
)


def _make_prompt(seq: int, name: str, **kwargs) -> dict:
    """Build a minimal prompt dict for testing."""
    p = {"sequence": seq, "prompt_name": name, "prompt": f"Test prompt for {name}"}
    p.update(kwargs)
    return p


class TestBuildExecutionGraphWithEdges:
    """Tests for build_execution_graph_with_edges."""

    def test_no_dependencies(self):
        prompts = [
            _make_prompt(10, "a"),
            _make_prompt(20, "b"),
        ]
        graph = build_execution_graph_with_edges(prompts)

        assert len(graph.nodes) == 2
        assert graph.edges == []
        assert graph.max_level == 0

    def test_history_edges_recorded(self):
        prompts = [
            _make_prompt(10, "analyze"),
            _make_prompt(20, "summarize", history=["analyze"]),
        ]
        graph = build_execution_graph_with_edges(prompts)

        assert len(graph.edges) == 1
        edge = graph.edges[0]
        assert edge.from_seq == 10
        assert edge.to_seq == 20
        assert edge.source == "history"
        assert edge.condition_text is None

    def test_condition_edges_recorded(self):
        prompts = [
            _make_prompt(10, "fetch"),
            _make_prompt(
                20,
                "process",
                condition='{{fetch.status}} == "success"',
            ),
        ]
        graph = build_execution_graph_with_edges(prompts)

        assert len(graph.edges) == 1
        edge = graph.edges[0]
        assert edge.from_seq == 10
        assert edge.to_seq == 20
        assert edge.source == "condition"
        assert edge.condition_text == '{{fetch.status}} == "success"'

    def test_mixed_history_and_condition_edges(self):
        prompts = [
            _make_prompt(10, "analyze"),
            _make_prompt(15, "fetch"),
            _make_prompt(
                20,
                "summarize",
                history=["analyze"],
                condition='{{fetch.status}} == "success"',
            ),
        ]
        graph = build_execution_graph_with_edges(prompts)

        assert len(graph.edges) == 2
        sources = {e.source for e in graph.edges}
        assert sources == {"history", "condition"}

        history_edge = next(e for e in graph.edges if e.source == "history")
        assert history_edge.from_seq == 10
        assert history_edge.to_seq == 20

        cond_edge = next(e for e in graph.edges if e.source == "condition")
        assert cond_edge.from_seq == 15
        assert cond_edge.to_seq == 20

    def test_levels_assigned(self):
        prompts = [
            _make_prompt(10, "a"),
            _make_prompt(20, "b", history=["a"]),
            _make_prompt(20, "c", history=["a"]),
            _make_prompt(30, "d", history=["b", "c"]),
        ]
        graph = build_execution_graph_with_edges(prompts)

        assert graph.nodes[10].level == 0
        assert graph.nodes[20].level == 1
        assert graph.nodes[30].level == 2
        assert graph.max_level == 2

    def test_cycle_detection(self):
        prompts = [
            _make_prompt(10, "a", history=["b"]),
            _make_prompt(20, "b", history=["a"]),
        ]
        with pytest.raises(ValueError, match="Dependency cycle"):
            build_execution_graph_with_edges(prompts)

    def test_backward_compatible_build_execution_graph(self):
        prompts = [
            _make_prompt(10, "a"),
            _make_prompt(20, "b", history=["a"]),
        ]
        nodes = build_execution_graph(prompts)

        assert len(nodes) == 2
        assert 10 in nodes[20].dependencies
        assert nodes[10].level == 0
        assert nodes[20].level == 1


class TestBuildExplainPlan:
    """Tests for build_explain_plan."""

    def test_basic_plan(self):
        prompts = [
            _make_prompt(10, "analyze"),
            _make_prompt(20, "summarize", history=["analyze"]),
            _make_prompt(25, "themes", history=["analyze"]),
            _make_prompt(30, "compare", history=["summarize", "themes"]),
        ]
        plan = build_explain_plan(prompts)

        assert plan.total_prompts == 4
        assert plan.total_levels == 3
        assert plan.has_batch is False
        assert plan.batch_count == 0
        assert len(plan.levels) == 3

        assert len(plan.levels[0].prompts) == 1
        assert len(plan.levels[1].prompts) == 2
        assert len(plan.levels[2].prompts) == 1

    def test_plan_with_batch_data(self):
        prompts = [_make_prompt(10, "a"), _make_prompt(20, "b")]
        batch = [{"id": 1, "name": "x"}, {"id": 2, "name": "y"}]

        plan = build_explain_plan(prompts, batch_data=batch)

        assert plan.has_batch is True
        assert plan.batch_count == 2

    def test_plan_with_condition_edges(self):
        prompts = [
            _make_prompt(10, "fetch"),
            _make_prompt(
                20,
                "process",
                condition='{{fetch.status}} == "success"',
            ),
        ]
        plan = build_explain_plan(prompts)

        condition_edges = [e for e in plan.graph.edges if e.source == "condition"]
        assert len(condition_edges) == 1
        assert condition_edges[0].condition_text == '{{fetch.status}} == "success"'

    def test_empty_prompts(self):
        plan = build_explain_plan([])

        assert plan.total_prompts == 0
        assert plan.total_levels == 0
        assert plan.levels == []


class TestFormatExplain:
    """Tests for format_explain output."""

    def test_basic_format(self):
        prompts = [
            _make_prompt(10, "analyze", prompt="Analyze the document"),
            _make_prompt(20, "summarize", history=["analyze"]),
        ]
        plan = build_explain_plan(prompts)
        output = format_explain(plan, title="test.xlsx", concurrency=3)

        assert "test.xlsx" in output
        assert "Prompts: 2" in output
        assert "Levels: 2" in output
        assert "Concurrency: 3" in output
        assert "Execution DAG" in output
        assert "Dependency Edges" in output
        assert "analyze" in output
        assert "summarize" in output

    def test_shows_history_annotations(self):
        prompts = [
            _make_prompt(10, "analyze"),
            _make_prompt(20, "summarize", history=["analyze"]),
        ]
        plan = build_explain_plan(prompts)
        output = format_explain(plan)

        assert "hist: analyze" in output

    def test_shows_condition_edge_with_warning(self):
        prompts = [
            _make_prompt(10, "fetch"),
            _make_prompt(
                20,
                "process",
                condition='{{fetch.status}} == "success"',
            ),
        ]
        plan = build_explain_plan(prompts)
        output = format_explain(plan)

        assert "⚠" in output
        assert "[condition]" in output
        assert '{{fetch.status}} == "success"' in output
        assert "references:" in output
        assert "{{fetch.status}}" in output
        assert 'prompt "fetch"' in output

    def test_shows_batch_info(self):
        prompts = [_make_prompt(10, "a")]
        batch = [{"id": 1}, {"id": 2}, {"id": 3}]
        plan = build_explain_plan(prompts, batch_data=batch)
        output = format_explain(plan)

        assert "Batch rows: 3" in output
        assert "3 LLM calls" in output

    def test_shows_client_annotations(self):
        prompts = [
            _make_prompt(10, "fast_task", client="fast"),
            _make_prompt(20, "smart_task", client="smart"),
        ]
        plan = build_explain_plan(prompts)
        output = format_explain(plan)

        assert "client: fast" in output
        assert "client: smart" in output

    def test_shows_agent_mode(self):
        prompts = [
            _make_prompt(
                10,
                "research",
                agent_mode=True,
                tools=["rag_search", "calculate"],
            ),
        ]
        plan = build_explain_plan(prompts)
        output = format_explain(plan)

        assert "agent [rag_search, calculate]" in output

    def test_shows_references(self):
        prompts = [
            _make_prompt(10, "evaluate", references=["resume", "job_description"]),
        ]
        plan = build_explain_plan(prompts)
        output = format_explain(plan)

        assert "refs: resume, job_description" in output

    def test_no_edges_message(self):
        prompts = [_make_prompt(10, "standalone")]
        plan = build_explain_plan(prompts)
        output = format_explain(plan)

        assert "(no dependencies)" in output

    def test_cost_estimate_no_batch(self):
        prompts = [_make_prompt(10, "a", prompt="A" * 400)]
        plan = build_explain_plan(prompts)
        output = format_explain(plan)

        assert "Cost Estimate" in output
        assert "1 prompts = 1 LLM calls" in output
        assert "No API calls made" in output

    def test_long_condition_truncated(self):
        prompts = [
            _make_prompt(10, "fetch"),
            _make_prompt(
                20,
                "process",
                condition=(
                    "{{fetch.status}} == 'success' and "
                    "len({{fetch.response}}) > 100 and "
                    "{{fetch.response}}.startswith('OK') and "
                    "'error' not in {{fetch.response}}.lower()"
                ),
            ),
        ]
        plan = build_explain_plan(prompts)
        output = format_explain(plan)

        assert "cond:" in output
        assert "..." in output


class TestFormatPromptPreview:
    """Tests for format_prompt_preview."""

    def test_basic_preview(self):
        prompt = _make_prompt(10, "greet", prompt="Hello, how are you?")
        output = format_prompt_preview(prompt)

        assert "greet" in output
        assert "seq 10" in output
        assert "Hello, how are you?" in output
        assert "No API call made" in output

    def test_with_batch_variables(self):
        prompt = _make_prompt(10, "analyze", prompt="Analyze {{region}} for {{product}}.")
        batch_row = {"id": 1, "region": "North America", "product": "Widget A"}
        output = format_prompt_preview(prompt, batch_row=batch_row)

        assert "Template Variables" in output
        assert "{{region}}  →  North America" in output
        assert "{{product}}  →  Widget A" in output
        assert "Analyze North America for Widget A." in output

    def test_unresolved_variables_warning(self):
        prompt = _make_prompt(10, "analyze", prompt="Analyze {{region}} for {{unknown_var}}.")
        batch_row = {"id": 1, "region": "North"}
        output = format_prompt_preview(prompt, batch_row=batch_row)

        assert "Unresolved" in output

    def test_with_upstream_references(self):
        prompt = _make_prompt(
            20,
            "process",
            prompt="Based on {{fetch.response}}, proceed.",
        )
        upstream = {"fetch": {"response": "Data loaded successfully", "status": "success"}}
        output = format_prompt_preview(prompt, upstream_results=upstream)

        assert "Upstream References" in output
        assert "fetch.response" in output
        assert "Data loaded successfully" in output

    def test_with_history(self):
        prompt = _make_prompt(
            20, "summarize", prompt="Summarize the above.", history=["context", "problem"]
        )
        upstream = {
            "context": {"response": "We run a coffee shop."},
            "problem": {"response": "The espresso machine is broken."},
        }
        output = format_prompt_preview(prompt, upstream_results=upstream)

        assert "History Context" in output
        assert "<interaction prompt_name='context'>" in output
        assert "We run a coffee shop." in output
        assert "<interaction prompt_name='problem'>" in output

    def test_with_references(self):
        prompt = _make_prompt(
            10, "answer", prompt="Answer based on docs.", references=["spec", "api"]
        )
        output = format_prompt_preview(prompt)

        assert "Injected Document References" in output
        assert "[spec]" in output
        assert "[api]" in output

    def test_long_prompt_truncated(self):
        prompt = _make_prompt(10, "long", prompt="A" * 600)
        output = format_prompt_preview(prompt)

        assert "more characters" in output

    def test_no_batch_skips_variables_section(self):
        prompt = _make_prompt(10, "simple", prompt="Just a prompt.")
        output = format_prompt_preview(prompt)

        assert "Template Variables" not in output
        assert "Final Prompt" in output


class TestConditionTrace:
    """Tests for condition evaluation trace."""

    def test_evaluate_with_trace_returns_resolved(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        results = {
            "fetch": {
                "status": "success",
                "response": "Data loaded",
                "attempts": 1,
                "error": "",
                "has_response": True,
            }
        }
        evaluator = ConditionEvaluator(results)
        result, error, trace = evaluator.evaluate_with_trace('{{fetch.status}} == "success"')

        assert result is True
        assert error is None
        assert trace is not None
        assert '"success"' in trace
        assert "{{fetch.status}}" not in trace

    def test_evaluate_with_trace_false_condition(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        results = {
            "fetch": {
                "status": "failed",
                "response": "",
                "attempts": 3,
                "error": "timeout",
                "has_response": False,
            }
        }
        evaluator = ConditionEvaluator(results)
        result, error, trace = evaluator.evaluate_with_trace('{{fetch.status}} == "success"')

        assert result is False
        assert trace is not None
        assert '"failed"' in trace

    def test_evaluate_with_trace_no_condition(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        evaluator = ConditionEvaluator({})
        result, error, trace = evaluator.evaluate_with_trace("")

        assert result is True
        assert error is None
        assert trace is None

    def test_condition_trace_in_result_dict(self):
        from src.orchestrator.results.builder import ResultBuilder

        prompt = {
            "sequence": 10,
            "prompt_name": "test",
            "prompt": "test",
            "condition": '{{fetch.status}} == "success"',
        }
        builder = ResultBuilder(prompt)
        builder.with_condition_trace('"success" == "success"')
        result = builder.build_dict()

        assert result["condition_trace"] == '"success" == "success"'

    def test_condition_trace_none_by_default(self):
        from src.orchestrator.results.builder import ResultBuilder

        prompt = {"sequence": 10, "prompt_name": "test", "prompt": "test"}
        builder = ResultBuilder(prompt)
        result = builder.build_dict()

        assert result["condition_trace"] is None
