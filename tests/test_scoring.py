# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for scoring rubric and aggregation (Phase 2)."""

import pytest

from src.orchestrator.results.builder import ResultBuilder
from src.orchestrator.results.result import PromptResult
from src.orchestrator.scoring import (
    ScoreAggregator,
    ScoringCriteria,
    ScoringRubric,
    extract_score,
)
from src.orchestrator.validation import OrchestratorValidator


def _make_prompt(seq, name, **kw):
    return {"sequence": seq, "prompt_name": name, "prompt": "test", "history": None, **kw}


def _make_criteria(**overrides):
    defaults = {
        "criteria_name": "test",
        "description": "A test criterion",
        "scale_min": 1,
        "scale_max": 10,
        "weight": 1.0,
        "source_prompt": "eval",
    }
    defaults.update(overrides)
    return ScoringCriteria(**defaults)


class TestExtractScore:
    def test_flat_json(self):
        response = '{"skills_match": 8, "education": 7}'
        score, trace = extract_score(response, "skills_match")
        assert score == 8.0
        assert "flat:" in trace
        score, trace = extract_score(response, "education")
        assert score == 7.0

    def test_nested_json_scores_key(self):
        response = '{"scores": {"skills_match": 9, "experience": 6}}'
        score, trace = extract_score(response, "skills_match")
        assert score == 9.0
        assert "nested:" in trace
        score, trace = extract_score(response, "experience")
        assert score == 6.0

    def test_flat_takes_priority_over_nested(self):
        response = '{"skills_match": 5, "scores": {"skills_match": 9}}'
        score, trace = extract_score(response, "skills_match")
        assert score == 5.0
        assert "flat:" in trace

    def test_missing_key_returns_none(self):
        response = '{"skills_match": 8}'
        score, trace = extract_score(response, "nonexistent")
        assert score is None
        assert "not found" in trace

    def test_non_numeric_value_returns_none(self):
        response = '{"skills_match": "great"}'
        score, trace = extract_score(response, "skills_match")
        assert score is None

    def test_malformed_json_returns_none(self):
        response = "not json at all"
        score, trace = extract_score(response, "skills_match")
        assert score is None

    def test_json_repair_on_malformed(self):
        response = '{"skills_match": 8, education: 7}'
        score, trace = extract_score(response, "skills_match")
        assert score == 8.0

    def test_empty_response_returns_none(self):
        score, trace = extract_score("", "test")
        assert score is None
        assert trace == "response empty"
        score, trace = extract_score(None, "test")
        assert score is None

    def test_int_value_cast_to_float(self):
        response = '{"score": 7}'
        score, trace = extract_score(response, "score")
        assert score == 7.0
        assert isinstance(score, float)

    def test_nested_score_object(self):
        response = '{"python": {"score": 9, "reasoning": "Expert level"}}'
        score, trace = extract_score(response, "python")
        assert score == 9.0
        assert "flat_object:" in trace

    def test_nested_value_key(self):
        response = '{"python": {"value": 8, "reasoning": "Strong"}}'
        score, trace = extract_score(response, "python")
        assert score == 8.0

    def test_nested_rating_key(self):
        response = '{"python": {"rating": 7, "reasoning": "Good"}}'
        score, trace = extract_score(response, "python")
        assert score == 7.0

    def test_nested_score_object_in_scores_key(self):
        response = '{"scores": {"python": {"score": 6, "reasoning": "OK"}}}'
        score, trace = extract_score(response, "python")
        assert score == 6.0
        assert "nested_object:" in trace

    def test_flat_value_takes_priority_over_nested(self):
        response = '{"python": 9}'
        score, trace = extract_score(response, "python")
        assert score == 9.0

    def test_trace_on_empty_response(self):
        score, trace = extract_score("", "test")
        assert score is None
        assert trace == "response empty"

    def test_trace_on_missing_key(self):
        response = '{"foo": 1, "bar": 2}'
        score, trace = extract_score(response, "baz")
        assert score is None
        assert "baz" in trace
        assert "foo" in trace


class TestScoringRubric:
    def test_extract_scores_all_ok(self):
        criteria = [_make_criteria(criteria_name="a", source_prompt="p1")]
        rubric = ScoringRubric(criteria)
        results = {
            "p1": {"response": '{"a": 8}', "status": "success"},
        }
        extracted, skipped, failed = rubric.extract_scores(results)
        assert extracted == {"a": 8.0}
        assert skipped == []
        assert failed == []

    def test_extract_scores_partial_failure(self):
        criteria = [
            _make_criteria(criteria_name="a", source_prompt="p1"),
            _make_criteria(criteria_name="b", source_prompt="p2"),
        ]
        rubric = ScoringRubric(criteria)
        results = {
            "p1": {"response": '{"a": 8}', "status": "success"},
            "p2": {"response": "no json here", "status": "success"},
        }
        extracted, skipped, failed = rubric.extract_scores(results)
        assert extracted == {"a": 8.0}
        assert skipped == []
        assert failed == ["b"]

    def test_extract_scores_skipped_prompt(self):
        criteria = [
            _make_criteria(criteria_name="a", source_prompt="p1"),
            _make_criteria(criteria_name="b", source_prompt="p2"),
        ]
        rubric = ScoringRubric(criteria)
        results = {
            "p1": {"response": '{"a": 8}', "status": "success"},
            "p2": {"response": "", "status": "skipped"},
        }
        extracted, skipped, failed = rubric.extract_scores(results)
        assert extracted == {"a": 8.0}
        assert skipped == ["b"]
        assert failed == []

    def test_extract_scores_missing_prompt(self):
        criteria = [_make_criteria(criteria_name="a", source_prompt="p_missing")]
        rubric = ScoringRubric(criteria)
        results = {
            "p1": {"response": '{"a": 8}', "status": "success"},
        }
        extracted, skipped, failed = rubric.extract_scores(results)
        assert extracted == {}
        assert skipped == ["a"]
        assert failed == []

    def test_resolve_weights_no_overrides(self):
        criteria = [
            _make_criteria(criteria_name="a", weight=2.0),
            _make_criteria(criteria_name="b", weight=3.0),
        ]
        rubric = ScoringRubric(criteria)
        weights = rubric.resolve_weights(None)
        assert weights == {"a": 2.0, "b": 3.0}

    def test_resolve_weights_with_overrides(self):
        criteria = [
            _make_criteria(criteria_name="a", weight=2.0),
            _make_criteria(criteria_name="b", weight=3.0),
        ]
        rubric = ScoringRubric(criteria)
        weights = rubric.resolve_weights({"a": 0.5, "c": 10.0})
        assert weights == {"a": 1.0, "b": 3.0}

    def test_compute_composite_basic(self):
        criteria = [
            _make_criteria(criteria_name="a", weight=1.0),
            _make_criteria(criteria_name="b", weight=2.0),
        ]
        rubric = ScoringRubric(criteria)
        scores = {"a": 8.0, "b": 6.0}
        weights = {"a": 1.0, "b": 2.0}
        composite = rubric.compute_composite(scores, weights)
        assert composite == pytest.approx(6.667, abs=0.01)

    def test_compute_composite_with_none(self):
        criteria = [
            _make_criteria(criteria_name="a"),
            _make_criteria(criteria_name="b"),
        ]
        rubric = ScoringRubric(criteria)
        scores = {"a": 8.0, "b": None}
        weights = {"a": 1.0, "b": 1.0}
        composite = rubric.compute_composite(scores, weights)
        assert composite == 8.0

    def test_compute_composite_all_none(self):
        rubric = ScoringRubric([])
        scores = {"a": None}
        weights = {"a": 1.0}
        assert rubric.compute_composite(scores, weights) is None


class TestScoreAggregator:
    def test_aggregate_entry_ok(self):
        criteria = [
            _make_criteria(criteria_name="a", source_prompt="p1"),
            _make_criteria(criteria_name="b", source_prompt="p2"),
        ]
        rubric = ScoringRubric(criteria)
        agg = ScoreAggregator(rubric, "balanced")
        results = {
            "p1": {"response": '{"a": 8}', "status": "success"},
            "p2": {"response": '{"b": 6}', "status": "success"},
        }
        result = agg.aggregate_entry(results)
        assert result["scoring_status"] == "ok"
        assert result["composite_score"] == pytest.approx(7.0)
        assert result["strategy"] == "balanced"

    def test_aggregate_entry_partial(self):
        criteria = [
            _make_criteria(criteria_name="a", source_prompt="p1"),
            _make_criteria(criteria_name="b", source_prompt="p2"),
            _make_criteria(criteria_name="c", source_prompt="p3"),
        ]
        rubric = ScoringRubric(criteria)
        agg = ScoreAggregator(rubric, "balanced", failure_threshold=0.5)
        results = {
            "p1": {"response": '{"a": 8}', "status": "success"},
            "p2": {"response": "no json", "status": "success"},
            "p3": {"response": '{"c": 5}', "status": "success"},
        }
        result = agg.aggregate_entry(results)
        assert result["scoring_status"] == "partial"
        assert result["composite_score"] == pytest.approx(6.5)

    def test_aggregate_entry_failed(self):
        criteria = [
            _make_criteria(criteria_name="a", source_prompt="p1"),
            _make_criteria(criteria_name="b", source_prompt="p2"),
            _make_criteria(criteria_name="c", source_prompt="p3"),
        ]
        rubric = ScoringRubric(criteria)
        agg = ScoreAggregator(rubric, "balanced", failure_threshold=0.5)
        results = {
            "p1": {"response": '{"a": 8}', "status": "success"},
            "p2": {"response": "no json", "status": "success"},
            "p3": {"response": "also no json", "status": "success"},
        }
        result = agg.aggregate_entry(results)
        assert result["scoring_status"] == "failed"
        assert result["composite_score"] is None

    def test_aggregate_entry_partial_with_majority_succeeded(self):
        criteria = [
            _make_criteria(criteria_name="a", source_prompt="p1"),
            _make_criteria(criteria_name="b", source_prompt="p2"),
            _make_criteria(criteria_name="c", source_prompt="p3"),
            _make_criteria(criteria_name="d", source_prompt="p4"),
            _make_criteria(criteria_name="e", source_prompt="p5"),
        ]
        rubric = ScoringRubric(criteria)
        agg = ScoreAggregator(rubric, "balanced", failure_threshold=0.5)
        results = {
            "p1": {"response": '{"a": 8}', "status": "success"},
            "p2": {"response": "no json", "status": "success"},
            "p3": {"response": '{"c": 6}', "status": "success"},
            "p4": {"response": "no json", "status": "success"},
            "p5": {"response": '{"e": 4}', "status": "success"},
        }
        result = agg.aggregate_entry(results)
        assert result["scoring_status"] == "partial"
        assert result["composite_score"] == pytest.approx(6.0)

    def test_aggregate_entry_skipped(self):
        criteria = [
            _make_criteria(criteria_name="a", source_prompt="p1"),
            _make_criteria(criteria_name="b", source_prompt="p2"),
        ]
        rubric = ScoringRubric(criteria)
        agg = ScoreAggregator(rubric, "balanced")
        results = {
            "p1": {"response": "", "status": "skipped"},
            "p2": {"response": "", "status": "skipped"},
        }
        result = agg.aggregate_entry(results)
        assert result["scoring_status"] == "skipped"
        assert result["composite_score"] is None

    def test_aggregate_with_strategy_overrides(self):
        criteria = [
            _make_criteria(criteria_name="a", source_prompt="p1", weight=1.0),
            _make_criteria(criteria_name="b", source_prompt="p2", weight=1.0),
        ]
        rubric = ScoringRubric(criteria)
        agg = ScoreAggregator(rubric, "potential", strategy_overrides={"a": 3.0, "b": 0.5})
        results = {
            "p1": {"response": '{"a": 4}', "status": "success"},
            "p2": {"response": '{"b": 8}', "status": "success"},
        }
        result = agg.aggregate_entry(results)
        assert result["composite_score"] == pytest.approx(4.571, abs=0.01)

    def test_aggregate_batch_results(self):
        criteria = [_make_criteria(criteria_name="a", source_prompt="p1")]
        rubric = ScoringRubric(criteria)
        agg = ScoreAggregator(rubric, "balanced")
        batch_results = [
            [{"prompt_name": "p1", "response": '{"a": 8}', "status": "success", "batch_name": "x"}],
            [{"prompt_name": "p1", "response": '{"a": 5}', "status": "success", "batch_name": "y"}],
        ]
        results = agg.aggregate_batch_results(batch_results)
        assert len(results) == 2
        assert results[0]["composite_score"] == 8.0
        assert results[1]["composite_score"] == 5.0


class TestScoringValidation:
    def test_valid_scoring(self):
        prompts = [_make_prompt(1, "eval"), _make_prompt(2, "assess")]
        criteria = [
            {
                "criteria_name": "a",
                "source_prompt": "eval",
                "weight": 1.0,
                "scale_min": 1,
                "scale_max": 10,
                "description": "Test",
            },
        ]
        result = OrchestratorValidator(prompts, {}, scoring_criteria=criteria).validate()
        assert not result.has_errors

    def test_unknown_source_prompt(self):
        prompts = [_make_prompt(1, "eval")]
        criteria = [
            {
                "criteria_name": "a",
                "source_prompt": "nonexistent",
                "weight": 1.0,
                "scale_min": 1,
                "scale_max": 10,
                "description": "Test",
            },
        ]
        result = OrchestratorValidator(prompts, {}, scoring_criteria=criteria).validate()
        assert result.error_count >= 1
        assert any(e.code == "INVALID_SCORING_SOURCE" for e in result.errors)

    def test_inconsistent_scale(self):
        prompts = [_make_prompt(1, "eval"), _make_prompt(2, "assess")]
        criteria = [
            {
                "criteria_name": "a",
                "source_prompt": "eval",
                "weight": 1.0,
                "scale_min": 1,
                "scale_max": 5,
                "description": "Test",
            },
            {
                "criteria_name": "b",
                "source_prompt": "assess",
                "weight": 1.0,
                "scale_min": 0,
                "scale_max": 100,
                "description": "Test",
            },
        ]
        result = OrchestratorValidator(prompts, {}, scoring_criteria=criteria).validate()
        assert any(e.code == "INCONSISTENT_SCORING_SCALE" for e in result.errors)

    def test_duplicate_criteria_name(self):
        prompts = [_make_prompt(1, "eval"), _make_prompt(2, "assess")]
        criteria = [
            {
                "criteria_name": "a",
                "source_prompt": "eval",
                "weight": 1.0,
                "scale_min": 1,
                "scale_max": 10,
                "description": "Test",
            },
            {
                "criteria_name": "a",
                "source_prompt": "assess",
                "weight": 1.0,
                "scale_min": 1,
                "scale_max": 10,
                "description": "Test",
            },
        ]
        result = OrchestratorValidator(prompts, {}, scoring_criteria=criteria).validate()
        assert any(e.code == "DUPLICATE_CRITERIA_NAME" for e in result.errors)

    def test_invalid_weight_zero(self):
        prompts = [_make_prompt(1, "eval")]
        criteria = [
            {
                "criteria_name": "a",
                "source_prompt": "eval",
                "weight": 0,
                "scale_min": 1,
                "scale_max": 10,
                "description": "Test",
            },
        ]
        result = OrchestratorValidator(prompts, {}, scoring_criteria=criteria).validate()
        assert any(e.code == "INVALID_SCORING_WEIGHT" for e in result.errors)

    def test_invalid_weight_negative(self):
        prompts = [_make_prompt(1, "eval")]
        criteria = [
            {
                "criteria_name": "a",
                "source_prompt": "eval",
                "weight": -1,
                "scale_min": 1,
                "scale_max": 10,
                "description": "Test",
            },
        ]
        result = OrchestratorValidator(prompts, {}, scoring_criteria=criteria).validate()
        assert any(e.code == "INVALID_SCORING_WEIGHT" for e in result.errors)

    def test_unknown_strategy(self):
        prompts = [_make_prompt(1, "eval")]
        result = OrchestratorValidator(
            prompts,
            {"evaluation_strategy": "nonexistent"},
            available_strategies=["balanced", "potential"],
        ).validate()
        assert any(e.code == "UNKNOWN_EVALUATION_STRATEGY" for e in result.errors)

    def test_valid_strategy_passes(self):
        prompts = [_make_prompt(1, "eval")]
        result = OrchestratorValidator(
            prompts,
            {"evaluation_strategy": "balanced"},
            available_strategies=["balanced", "potential"],
        ).validate()
        assert not any(e.code == "UNKNOWN_EVALUATION_STRATEGY" for e in result.errors)

    def test_no_scoring_no_errors(self):
        prompts = [_make_prompt(1, "eval")]
        result = OrchestratorValidator(prompts, {}).validate()
        assert not result.has_errors


class TestPromptResultScoringFields:
    def test_default_values(self):
        pr = PromptResult(sequence=1)
        assert pr.scores is None
        assert pr.composite_score is None
        assert pr.scoring_status is None
        assert pr.strategy is None
        assert pr.result_type == "batch"

    def test_from_dict_with_scoring(self):
        data = {
            "sequence": 1,
            "scores": {"a": 8, "b": 6},
            "composite_score": 7.0,
            "scoring_status": "ok",
            "strategy": "potential",
            "result_type": "batch",
        }
        pr = PromptResult.from_dict(data)
        assert pr.scores == {"a": 8, "b": 6}
        assert pr.composite_score == 7.0
        assert pr.scoring_status == "ok"
        assert pr.strategy == "potential"
        assert pr.result_type == "batch"

    def test_to_dict_includes_scoring(self):
        pr = PromptResult(
            sequence=1,
            scores={"a": 8},
            composite_score=8.0,
            scoring_status="ok",
            strategy="balanced",
            result_type="batch",
        )
        d = pr.to_dict()
        assert d["scores"] == {"a": 8}
        assert d["composite_score"] == 8.0
        assert d["scoring_status"] == "ok"
        assert d["strategy"] == "balanced"
        assert d["result_type"] == "batch"

    def test_roundtrip(self):
        pr = PromptResult(
            sequence=1,
            scores={"a": 8},
            composite_score=8.0,
            scoring_status="ok",
            strategy="balanced",
        )
        d = pr.to_dict()
        pr2 = PromptResult.from_dict(d)
        assert pr2.scores == pr.scores
        assert pr2.composite_score == pr.composite_score
        assert pr2.scoring_status == pr.scoring_status
        assert pr2.strategy == pr.strategy
        assert pr2.result_type == pr.result_type


class TestResultBuilderScoring:
    def test_with_scoring(self):
        prompt = {"sequence": 1, "prompt_name": "eval", "prompt": "go", "history": None}
        result = (
            ResultBuilder(prompt)
            .with_response("ok")
            .with_scoring({"a": 8}, 8.0, "ok", "balanced")
            .build_dict()
        )
        assert result["scores"] == {"a": 8}
        assert result["composite_score"] == 8.0
        assert result["scoring_status"] == "ok"
        assert result["strategy"] == "balanced"

    def test_as_synthesis(self):
        prompt = {"sequence": 1, "prompt_name": "rank", "prompt": "rank", "history": None}
        result = ResultBuilder(prompt).as_synthesis().build()
        assert result.result_type == "synthesis"
        assert result.batch_id == -1
        assert result.batch_name == ""

    def test_with_scoring_chaining(self):
        prompt = {"sequence": 1, "prompt_name": "eval", "prompt": "go", "history": None}
        result = (
            ResultBuilder(prompt)
            .with_batch(1, "test")
            .with_response("ok")
            .with_scoring({"a": 9}, 9.0, "ok", "potential")
            .build()
        )
        assert result.batch_id == 1
        assert result.response == "ok"
        assert result.scores == {"a": 9}
        assert result.strategy == "potential"
