# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

import json
import os
import sys
from typing import Any

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_result(
    *,
    sequence: int = 1,
    prompt_name: str = "p1",
    status: str = "success",
    attempts: int = 1,
    batch_id: int | None = None,
    batch_name: str | None = None,
    scores: dict[str, Any] | None = None,
    composite_score: float | None = None,
    scoring_status: str | None = None,
    strategy: str | None = None,
    result_type: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    duration_ms: float = 0.0,
    condition: str | None = None,
    client: str | None = None,
    response: str = "ok",
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "prompt_name": prompt_name,
        "prompt": f"prompt for {prompt_name}",
        "resolved_prompt": None,
        "history": None,
        "client": client,
        "condition": condition,
        "condition_result": None,
        "condition_error": None,
        "condition_trace": None,
        "response": response,
        "status": status,
        "attempts": attempts,
        "error": None,
        "references": None,
        "semantic_query": None,
        "semantic_filter": None,
        "query_expansion": None,
        "rerank": None,
        "batch_id": batch_id,
        "batch_name": batch_name,
        "agent_mode": False,
        "tool_calls": None,
        "total_rounds": None,
        "total_llm_calls": None,
        "validation_passed": None,
        "validation_attempts": None,
        "validation_critique": None,
        "scores": scores,
        "composite_score": composite_score,
        "scoring_status": scoring_status,
        "extraction_trace": None,
        "strategy": strategy,
        "result_type": result_type,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "duration_ms": duration_ms,
    }


class TestResultsFrameInit:
    """Tests for ResultsFrame initialization and normalization."""

    def test_empty_results(self):
        from src.orchestrator.results import ResultsFrame

        frame = ResultsFrame([])
        assert frame.is_empty
        assert frame.df.height == 0

    def test_none_results(self):
        from src.orchestrator.results import ResultsFrame

        frame = ResultsFrame(None)
        assert frame.is_empty

    def test_single_result(self):
        from src.orchestrator.results import ResultsFrame

        r = _make_result()
        frame = ResultsFrame([r])
        assert not frame.is_empty
        assert frame.df.height == 1
        assert frame.df.item(0, "status") == "success"

    def test_json_columns_serialized(self):
        from src.orchestrator.results import ResultsFrame

        r = _make_result(scores={"skills": 8.0})
        r["history"] = ["h1", "h2"]
        frame = ResultsFrame([r])
        scores_val = frame.df.item(0, "scores")
        assert isinstance(scores_val, str)
        assert json.loads(scores_val) == {"skills": 8.0}
        history_val = frame.df.item(0, "history")
        assert isinstance(history_val, str)

    def test_results_columns_match_prompt_result(self):
        from dataclasses import fields

        from src.orchestrator.results import PromptResult
        from src.orchestrator.results.frame import RESULTS_COLUMNS

        expected = [f.name for f in fields(PromptResult)]
        assert RESULTS_COLUMNS == expected

    def test_dataframe_has_all_columns(self):
        from src.orchestrator.results import ResultsFrame

        frame = ResultsFrame([_make_result()])
        for col in [
            "sequence",
            "prompt_name",
            "status",
            "batch_id",
            "scores",
            "response",
        ]:
            assert col in frame.df.columns


class TestResultsFrameSummary:
    """Tests for ResultsFrame.summary()."""

    def test_summary_empty(self):
        from src.orchestrator.results import ResultsFrame

        frame = ResultsFrame([])
        assert frame.summary() == {"status": "not_run"}

    def test_summary_basic_counts(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(status="success"),
            _make_result(status="success"),
            _make_result(status="failed", sequence=3),
        ]
        frame = ResultsFrame(results)
        s = frame.summary()
        assert s["total_prompts"] == 3
        assert s["successful"] == 2
        assert s["failed"] == 1
        assert s["skipped"] == 0
        assert s["total_attempts"] == 3

    def test_summary_with_tokens_and_cost(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(input_tokens=100, output_tokens=50, total_tokens=150, cost_usd=0.001),
            _make_result(
                sequence=2, input_tokens=200, output_tokens=100, total_tokens=300, cost_usd=0.002
            ),
        ]
        frame = ResultsFrame(results)
        s = frame.summary()
        assert s["tokens"]["input"] == 300
        assert s["tokens"]["output"] == 150
        assert s["tokens"]["total"] == 450
        assert s["cost_usd"] == 0.003

    def test_summary_batch_mode(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(batch_id=1, batch_name="alice"),
            _make_result(batch_id=2, batch_name="bob", sequence=2),
        ]
        frame = ResultsFrame(results)
        s = frame.summary(is_batch_mode=True)
        assert s["batch_mode"] is True
        assert s["total_batches"] == 2

    def test_summary_batch_mode_false_no_batch_fields(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(batch_id=1, batch_name="alice"),
            _make_result(batch_id=2, batch_name="bob", sequence=2),
        ]
        frame = ResultsFrame(results)
        s = frame.summary(is_batch_mode=False)
        assert "batch_mode" not in s
        assert "total_batches" not in s

    def test_summary_with_conditions(self):
        from src.orchestrator.results import ResultsFrame

        results = [_make_result(condition="status == 'success'"), _make_result(sequence=2)]
        frame = ResultsFrame(results)
        s = frame.summary()
        assert s["prompts_with_conditions"] == 1

    def test_summary_scoring(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(
                batch_id=1,
                batch_name="alice",
                scores={"skills": 8.0},
                composite_score=8.0,
                scoring_status="ok",
            ),
            _make_result(
                batch_id=2,
                batch_name="bob",
                sequence=2,
                scores={"skills": 5.0},
                composite_score=5.0,
                scoring_status="ok",
            ),
        ]
        frame = ResultsFrame(results)
        s = frame.summary(has_scoring=True)
        assert s["scoring"]["total_scored"] == 2
        assert s["scoring"]["ok"] == 2
        assert s["scoring"]["avg_composite"] == 6.5
        assert s["scoring"]["max_composite"] == 8.0
        assert s["scoring"]["min_composite"] == 5.0

    def test_summary_synthesis(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(result_type="synthesis", status="success"),
            _make_result(result_type="synthesis", status="failed", sequence=2),
        ]
        frame = ResultsFrame(results)
        s = frame.summary(has_synthesis=True)
        assert s["synthesis"]["count"] == 2
        assert s["synthesis"]["successful"] == 1
        assert s["synthesis"]["failed"] == 1

    def test_summary_batch_failures(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(batch_id=1, batch_name="alice", status="success"),
            _make_result(batch_id=1, batch_name="alice", sequence=2, status="failed"),
            _make_result(batch_id=2, batch_name="bob", sequence=3, status="failed"),
        ]
        frame = ResultsFrame(results)
        s = frame.summary(is_batch_mode=True)
        assert "batches_with_failures" in s


class TestResultsFrameScoresPivot:
    """Tests for ResultsFrame.scores_pivot()."""

    def _criteria(self, names_with_types: list[tuple[str, str]] | None = None) -> list[dict]:
        if names_with_types is None:
            names_with_types = [
                ("skills_match", "normalized_score"),
                ("education", "normalized_score"),
            ]
        return [
            {
                "criteria_name": name,
                "description": f"{name} desc",
                "scale_min": 1,
                "scale_max": 10,
                "weight": 1.0,
                "source_prompt": "eval",
                "score_type": stype,
            }
            for name, stype in names_with_types
        ]

    def test_pivot_basic(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(
                batch_id=1,
                batch_name="alice",
                scores={"skills_match": 8.0, "education": 7.0},
                composite_score=7.5,
            ),
            _make_result(
                batch_id=2,
                batch_name="bob",
                sequence=2,
                scores={"skills_match": 5.0, "education": 6.0},
                composite_score=5.5,
            ),
        ]
        frame = ResultsFrame(results)
        pivot = frame.scores_pivot(self._criteria())
        assert pivot.height == 6  # 2 batches x 2 criteria + 2 composites
        assert "batch_name" in pivot.columns
        assert "rank" in pivot.columns
        assert "percentile" in pivot.columns

    def test_pivot_returns_empty_for_no_normalized_criteria(self):
        from src.orchestrator.results import ResultsFrame

        results = [_make_result(batch_id=1, batch_name="alice", scores={"x": 5.0})]
        frame = ResultsFrame(results)
        pivot = frame.scores_pivot(self._criteria([("skills_match", ""), ("education", "")]))
        assert pivot.height == 0

    def test_pivot_returns_empty_for_no_scores(self):
        from src.orchestrator.results import ResultsFrame

        results = [_make_result(batch_id=1, batch_name="alice")]
        frame = ResultsFrame(results)
        pivot = frame.scores_pivot(self._criteria())
        assert pivot.is_empty

    def test_pivot_returns_empty_for_empty_scores_dict(self):
        from src.orchestrator.results import ResultsFrame

        results = [_make_result(batch_id=1, batch_name="alice", scores={})]
        frame = ResultsFrame(results)
        pivot = frame.scores_pivot(self._criteria())
        assert pivot.is_empty

    def test_pivot_ranks_correctly(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(
                batch_id=1, batch_name="alice", scores={"skills": 8.0}, composite_score=8.0
            ),
            _make_result(
                batch_id=2,
                batch_name="bob",
                sequence=2,
                scores={"skills": 5.0},
                composite_score=5.0,
            ),
        ]
        frame = ResultsFrame(results)
        pivot = frame.scores_pivot(self._criteria([("skills", "normalized_score")]))
        criteria_rows = pivot.filter(pl.col("criteria_name") == "skills").sort("batch_name")
        alice_rank = criteria_rows.filter(pl.col("batch_name") == "alice")["rank"].item()
        bob_rank = criteria_rows.filter(pl.col("batch_name") == "bob")["rank"].item()
        assert alice_rank == 1
        assert bob_rank == 2

    def test_pivot_composite_rows(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(
                batch_id=1, batch_name="alice", scores={"skills": 8.0}, composite_score=8.0
            ),
            _make_result(
                batch_id=2,
                batch_name="bob",
                sequence=2,
                scores={"skills": 5.0},
                composite_score=5.0,
            ),
        ]
        frame = ResultsFrame(results)
        pivot = frame.scores_pivot(self._criteria([("skills", "normalized_score")]))
        composites = pivot.filter(pl.col("criteria_name") == "_composite")
        assert composites.height == 2

    def test_pivot_single_batch_no_divide_by_zero(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(
                batch_id=1, batch_name="alice", scores={"skills": 8.0}, composite_score=8.0
            ),
        ]
        frame = ResultsFrame(results)
        pivot = frame.scores_pivot(self._criteria([("skills", "normalized_score")]))
        assert pivot.height > 0
        criteria_row = pivot.filter(pl.col("criteria_name") == "skills")
        assert criteria_row["percentile"].item() == 100

    def test_pivot_excludes_non_matching_criteria(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(
                batch_id=1,
                batch_name="alice",
                scores={"skills_match": 8.0, "raw_years": 12.0},
                composite_score=8.0,
            ),
        ]
        frame = ResultsFrame(results)
        pivot = frame.scores_pivot(
            self._criteria([("skills_match", "normalized_score"), ("raw_years", "")])
        )
        assert pivot.height == 2  # 1 criteria + 1 composite
        names = pivot["criteria_name"].to_list()
        assert "skills_match" in names
        assert "raw_years" not in names


class TestResultsFrameByBatch:
    """Tests for ResultsFrame.by_batch()."""

    def test_by_batch_groups_correctly(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(batch_id=1, batch_name="alice"),
            _make_result(batch_id=1, batch_name="alice", sequence=2),
            _make_result(batch_id=2, batch_name="bob", sequence=3),
        ]
        frame = ResultsFrame(results)
        groups = frame.by_batch()
        assert len(groups) == 2
        heights = {g.df.height for g in groups.values()}
        assert heights == {1, 2}

    def test_by_batch_empty(self):
        from src.orchestrator.results import ResultsFrame

        frame = ResultsFrame([])
        assert frame.by_batch() == {}


class TestResultsFrameByType:
    """Tests for ResultsFrame.by_type()."""

    def test_by_type_filters(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(result_type="batch"),
            _make_result(result_type="synthesis", sequence=2),
            _make_result(result_type="batch", sequence=3),
        ]
        frame = ResultsFrame(results)
        batch = frame.by_type("batch")
        assert batch.df.height == 2
        synth = frame.by_type("synthesis")
        assert synth.df.height == 1


class TestResultsFrameConcat:
    """Tests for ResultsFrame.concat()."""

    def test_concat_stacks_frames(self):
        from src.orchestrator.results import ResultsFrame

        f1 = ResultsFrame([_make_result(prompt_name="p1")])
        f2 = ResultsFrame([_make_result(prompt_name="p2")])
        combined = f1.concat(f2)
        assert combined.df.height == 2

    def test_concat_preserves_data(self):
        from src.orchestrator.results import ResultsFrame

        f1 = ResultsFrame([_make_result(prompt_name="p1", status="success")])
        f2 = ResultsFrame([_make_result(prompt_name="p2", status="failed")])
        combined = f1.concat(f2)
        names = combined.df["prompt_name"].sort().to_list()
        assert names == ["p1", "p2"]


class TestResultsFrameFilterSelectSort:
    """Tests for ResultsFrame filter/select/sort operations."""

    def test_filter(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(status="success"),
            _make_result(status="failed", sequence=2),
        ]
        frame = ResultsFrame(results)
        failed = frame.filter(pl.col("status") == "failed")
        assert failed.df.height == 1

    def test_select(self):
        from src.orchestrator.results import ResultsFrame

        frame = ResultsFrame([_make_result()])
        selected = frame.select("prompt_name", "status")
        assert selected.df.columns == ["prompt_name", "status"]

    def test_sort(self):
        from src.orchestrator.results import ResultsFrame

        results = [_make_result(sequence=3), _make_result(sequence=1), _make_result(sequence=2)]
        frame = ResultsFrame(results)
        sorted_frame = frame.sort("sequence")
        assert sorted_frame.df["sequence"].to_list() == [1, 2, 3]


class TestResultsFrameScoresDf:
    """Tests for ResultsFrame.scores_df property."""

    def test_scores_df_deduplicates(self):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(
                batch_id=1,
                batch_name="alice",
                scores={"skills": 8.0},
                composite_score=8.0,
                scoring_status="ok",
            ),
            _make_result(
                batch_id=1,
                batch_name="alice",
                sequence=2,
                scores={"skills": 8.0},
                composite_score=8.0,
                scoring_status="ok",
            ),
            _make_result(
                batch_id=2,
                batch_name="bob",
                sequence=3,
                scores={"skills": 5.0},
                composite_score=5.0,
                scoring_status="ok",
            ),
        ]
        frame = ResultsFrame(results)
        sdf = frame.scores_df
        assert sdf.height == 2
        assert set(sdf["batch_name"].to_list()) == {"alice", "bob"}


class TestResultsFrameParquet:
    """Tests for ResultsFrame parquet I/O."""

    def test_to_parquet_and_from_parquet(self, tmp_path):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(prompt_name="p1", status="success"),
            _make_result(prompt_name="p2", status="failed", sequence=2),
        ]
        frame = ResultsFrame(results)
        path = frame.to_parquet(tmp_path / "test.parquet")

        loaded = ResultsFrame.from_parquet(path)
        assert loaded.df.height == 2
        assert set(loaded.df["prompt_name"].to_list()) == {"p1", "p2"}

    def test_to_parquet_with_metadata(self, tmp_path):
        import pyarrow.parquet as pq

        from src.orchestrator.results import ResultsFrame

        results = [_make_result()]
        frame = ResultsFrame(results)
        path = frame.to_parquet(
            tmp_path / "test_meta.parquet",
            metadata={"run_id": "abc123", "source": "test"},
        )

        meta = pq.read_schema(path).metadata
        assert meta[b"run_id"] == b"abc123"
        assert meta[b"source"] == b"test"

    def test_from_parquet_preserves_data(self, tmp_path):
        from src.orchestrator.results import ResultsFrame

        results = [
            _make_result(
                prompt_name="eval",
                status="success",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost_usd=0.001,
            ),
        ]
        frame = ResultsFrame(results)
        path = frame.to_parquet(tmp_path / "roundtrip.parquet")

        loaded = ResultsFrame.from_parquet(path)
        assert loaded.df.item(0, "prompt_name") == "eval"
        assert loaded.df.item(0, "input_tokens") == 100


class TestSerializeValue:
    """Tests for _serialize_value and _serialize_for_excel."""

    def test_serialize_value_none_passthrough(self):
        from src.orchestrator.results.frame import _serialize_value

        assert _serialize_value("status", None) is None
        assert _serialize_value("scores", None) is None

    def test_serialize_value_json_columns(self):
        from src.orchestrator.results.frame import _serialize_value

        result = _serialize_value("scores", {"skills": 8.0})
        assert isinstance(result, str)
        assert json.loads(result) == {"skills": 8.0}

    def test_serialize_value_history(self):
        from src.orchestrator.results.frame import _serialize_value

        result = _serialize_value("history", ["h1", "h2"])
        assert isinstance(result, str)

    def test_serialize_value_response_dict(self):
        from src.orchestrator.results.frame import _serialize_value

        result = _serialize_value("response", {"key": "val"})
        assert isinstance(result, str)

    def test_serialize_for_excel_converts_none(self):
        from src.orchestrator.results.frame import _serialize_for_excel

        assert _serialize_for_excel("status", None) == ""

    def test_serialize_for_excel_keeps_strings(self):
        from src.orchestrator.results.frame import _serialize_for_excel

        assert _serialize_for_excel("status", "success") == "success"

    def test_serialize_for_excel_json_columns(self):
        from src.orchestrator.results.frame import _serialize_for_excel

        result = _serialize_for_excel("scores", {"skills": 8.0})
        assert isinstance(result, str)
        assert json.loads(result) == {"skills": 8.0}
