# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Polars DataFrame wrapper for orchestrator results.

Provides a single point of conversion from list[dict] results to a typed
DataFrame, with convenience methods for summarization, pivoting, and parquet
output.
"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

import polars as pl

from .result import PromptResult

logger = logging.getLogger(__name__)

JSON_SERIALIZE_COLUMNS = frozenset(
    {"history", "references", "tool_calls", "scores", "extraction_trace"}
)


def _deserialize_json_columns(
    rows: list[dict[str, Any]], columns: frozenset[str] | None = None
) -> list[dict[str, Any]]:
    """Parse JSON-serialized columns back to native Python objects.

    Used when converting DataFrame rows back to dicts for code that
    expects native types (e.g., synthesis sorting and context formatting).
    """
    cols = columns or JSON_SERIALIZE_COLUMNS
    for row in rows:
        for col in cols:
            val = row.get(col)
            if isinstance(val, str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    row[col] = json.loads(val)
    return rows


RESULTS_COLUMNS: list[str] = [f.name for f in dataclass_fields(PromptResult)]

PIVOT_COLUMNS = [
    "batch_name",
    "criteria_name",
    "label_1",
    "label_2",
    "label_3",
    "normalized_score",
    "weight",
    "weight_tier",
    "weighted_score",
    "rank",
    "percentile",
    "percent_rank",
    "scale_min",
    "scale_max",
    "description",
]


def _serialize_value(col: str, value: Any) -> Any:
    if col in JSON_SERIALIZE_COLUMNS and value is not None:
        return json.dumps(value)
    if col == "response" and isinstance(value, list | dict):
        return json.dumps(value)
    return value


def _serialize_for_excel(col: str, value: Any) -> Any:
    if value is None:
        return ""
    return _serialize_value(col, value)


class ResultsFrame:
    """Polars DataFrame wrapper for orchestrator execution results.

    Converts the raw list[dict] results produced during execution into a
    normalized DataFrame and provides methods for summarization, scoring
    pivots, and output to Excel or Parquet.
    """

    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self._df = self._normalize(results or [])

    @staticmethod
    def _normalize(results: list[dict[str, Any]]) -> pl.DataFrame:
        if not results:
            return pl.DataFrame(schema=dict.fromkeys(RESULTS_COLUMNS, pl.Utf8))

        rows: list[dict[str, Any]] = []
        for r in results:
            row = {col: _serialize_value(col, r.get(col)) for col in RESULTS_COLUMNS}
            rows.append(row)

        try:
            return pl.DataFrame(rows)
        except pl.ComputeError:
            logger.debug("Polars schema inference failed, falling back to full scan")
            return pl.DataFrame(rows, infer_schema_length=None)

    @property
    def df(self) -> pl.DataFrame:
        return self._df

    @property
    def is_empty(self) -> bool:
        return self._df.is_empty()

    def filter(self, *predicates: pl.Expr) -> ResultsFrame:
        return ResultsFrame.from_df(self._df.filter(*predicates))

    def select(self, *exprs: pl.Expr | str) -> ResultsFrame:
        return ResultsFrame.from_df(self._df.select(*exprs))

    def sort(self, by: str | list[str], *, descending: bool | list[bool] = False) -> ResultsFrame:
        return ResultsFrame.from_df(self._df.sort(by, descending=descending))

    @classmethod
    def from_df(cls, df: pl.DataFrame) -> ResultsFrame:
        frame = cls.__new__(cls)
        frame._df = df
        return frame

    def concat(self, other: ResultsFrame) -> ResultsFrame:
        return ResultsFrame.from_df(pl.concat([self._df, other._df], how="diagonal"))

    def by_batch(self) -> dict[int, ResultsFrame]:
        if "batch_id" not in self._df.columns:
            return {}
        groups: dict[int, ResultsFrame] = {}
        for bid, sub_df in self._df.partition_by("batch_id", as_dict=True).items():
            groups[bid] = ResultsFrame.from_df(sub_df)
        return groups

    def by_type(self, result_type: str) -> ResultsFrame:
        return self.filter(pl.col("result_type") == result_type)

    @property
    def scores_df(self) -> pl.DataFrame:
        batch_level = self._df.filter(
            pl.col("batch_name").is_not_null() & pl.col("scores").is_not_null()
        ).unique(subset=["batch_name"])
        return batch_level.select(
            "batch_name", "scores", "composite_score", "scoring_status", "strategy"
        )

    def summary(
        self,
        *,
        is_batch_mode: bool = False,
        evaluation_strategy: str = "",
        has_scoring: bool = False,
        has_synthesis: bool = False,
    ) -> dict[str, Any]:
        if self._df.is_empty():
            return {"status": "not_run"}

        df = self._df
        total = len(df)

        status_counts = df.group_by("status").len().rows()
        status_map = dict(status_counts)

        summary: dict[str, Any] = {
            "total_prompts": total,
            "successful": status_map.get("success", 0),
            "failed": status_map.get("failed", 0),
            "skipped": status_map.get("skipped", 0),
            "total_attempts": df.select(pl.col("attempts").sum()).item() or 0,
        }

        total_tokens = df.select(pl.col("total_tokens").sum()).item() or 0
        total_cost = df.select(pl.col("cost_usd").sum()).item() or 0.0

        if total_tokens > 0 or total_cost > 0:
            total_input = df.select(pl.col("input_tokens").sum()).item() or 0
            total_output = df.select(pl.col("output_tokens").sum()).item() or 0
            summary["tokens"] = {
                "input": total_input,
                "output": total_output,
                "total": total_tokens,
            }
            summary["cost_usd"] = round(total_cost, 6)

        condition_count = df.filter(pl.col("condition").is_not_null()).height
        if condition_count > 0:
            summary["prompts_with_conditions"] = condition_count

        if is_batch_mode and "batch_id" in df.columns:
            batch_ids = df.select(pl.col("batch_id").n_unique()).item() or 0
            summary["total_batches"] = batch_ids
            summary["batch_mode"] = True

            failures = df.filter(pl.col("status") == "failed").group_by("batch_id").len()
            if not failures.is_empty():
                batch_failures: dict[int, int] = {}
                for row in failures.iter_rows():
                    batch_failures[row[0]] = row[1]
                summary["batches_with_failures"] = batch_failures

        if has_scoring:
            scoring_col = "scoring_status"
            if scoring_col in df.columns:
                scored = df.filter(pl.col(scoring_col).is_not_null() & (pl.col(scoring_col) != ""))
                if not scored.is_empty():
                    scoring_counts = scored.group_by(scoring_col).len().rows()
                    sc_map = dict(scoring_counts)

                    scoring_block: dict[str, Any] = {
                        "total_scored": scored.height,
                        "ok": sc_map.get("ok", 0),
                        "partial": sc_map.get("partial", 0),
                        "failed": sc_map.get("failed", 0),
                        "skipped": sc_map.get("skipped", 0),
                    }

                    if evaluation_strategy:
                        scoring_block["strategy"] = evaluation_strategy

                    composites = (
                        scored.filter(pl.col("composite_score").is_not_null())
                        .select("composite_score")
                        .to_series()
                        .to_list()
                    )

                    if composites:
                        scoring_block["avg_composite"] = round(sum(composites) / len(composites), 2)
                        scoring_block["max_composite"] = max(composites)
                        scoring_block["min_composite"] = min(composites)

                    summary["scoring"] = scoring_block

        if has_synthesis:
            synth = df.filter(pl.col("result_type") == "synthesis")
            if not synth.is_empty():
                synth_counts = synth.group_by("status").len().rows()
                synth_map = dict(synth_counts)
                summary["synthesis"] = {
                    "count": synth.height,
                    "successful": synth_map.get("success", 0),
                    "failed": synth_map.get("failed", 0),
                }

        return summary

    def scores_pivot(self, criteria: list[dict[str, Any]]) -> pl.DataFrame:
        pivot_criteria = [c for c in criteria if c.get("score_type") == "normalized_score"]
        if not pivot_criteria:
            return pl.DataFrame()

        criteria_map = {c["criteria_name"]: c for c in pivot_criteria}
        criteria_names = list(criteria_map.keys())

        scored = self._df.filter(
            pl.col("batch_name").is_not_null() & pl.col("scores").is_not_null()
        ).unique(subset=["batch_name"])

        if scored.is_empty():
            return pl.DataFrame()

        rows: list[dict[str, Any]] = []
        composites: dict[str, float | None] = {}

        for row_data in scored.iter_rows(named=True):
            batch_name = row_data["batch_name"]
            scores_raw = row_data.get("scores")
            if not isinstance(scores_raw, str):
                continue
            try:
                scores_dict = json.loads(scores_raw)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(scores_dict, dict):
                continue

            composites[batch_name] = row_data.get("composite_score")

            for cname in criteria_names:
                if cname not in scores_dict:
                    continue
                value = scores_dict.get(cname)
                crit = criteria_map[cname]
                weight = crit.get("weight", 1.0)
                numeric = value if isinstance(value, int | float) else None
                rows.append(
                    {
                        "batch_name": batch_name,
                        "criteria_name": cname,
                        "label_1": crit.get("label_1", ""),
                        "label_2": crit.get("label_2", ""),
                        "label_3": crit.get("label_3", ""),
                        "normalized_score": numeric,
                        "weight": weight,
                        "weight_tier": crit.get("weight_tier", ""),
                        "weighted_score": numeric * weight if numeric is not None else None,
                        "scale_min": crit.get("scale_min", 1),
                        "scale_max": crit.get("scale_max", 10),
                        "description": crit.get("description", ""),
                    }
                )

        if not rows:
            return pl.DataFrame()

        pivot_df = pl.DataFrame(rows)

        pivot_df = pivot_df.with_columns(
            pl.col("normalized_score")
            .rank(method="dense", descending=True)
            .over("criteria_name")
            .alias("rank")
        )

        pivot_df = pivot_df.with_columns(
            pl.when(pl.col("normalized_score").is_not_null() & pl.col("rank").is_not_null())
            .then(
                pl.when(pl.col("normalized_score").count().over("criteria_name") == 1)
                .then(pl.lit(100))
                .otherwise(
                    (
                        (pl.col("normalized_score").count().over("criteria_name") - pl.col("rank"))
                        / pl.max_horizontal(
                            pl.col("normalized_score").count().over("criteria_name") - 1,
                            pl.lit(1),
                        )
                        * 100
                    ).cast(pl.Int64)
                )
            )
            .otherwise(pl.lit(0))
            .alias("percentile")
        )

        pivot_df = pivot_df.with_columns(
            pl.when(pl.col("normalized_score").is_not_null())
            .then(
                pl.when(pl.col("normalized_score").count().over("criteria_name") == 1)
                .then(pl.lit(100))
                .otherwise(
                    (
                        (pl.col("normalized_score").rank(method="min").over("criteria_name") - 1)
                        / pl.max_horizontal(
                            pl.col("normalized_score").count().over("criteria_name") - 1,
                            pl.lit(1),
                        )
                        * 100
                    ).cast(pl.Int64)
                )
            )
            .otherwise(pl.lit(0))
            .alias("percent_rank")
        )

        scored_composites = {
            name: score for name, score in composites.items() if isinstance(score, int | float)
        }
        if scored_composites:
            composite_df = (
                pl.DataFrame(
                    {
                        "batch_name": list(scored_composites.keys()),
                        "weighted_score": list(scored_composites.values()),
                    }
                )
                .with_columns(
                    pl.lit("_composite").alias("criteria_name"),
                    pl.lit("").alias("label_1"),
                    pl.lit("").alias("label_2"),
                    pl.lit("").alias("label_3"),
                    pl.lit(None).cast(pl.Float64).alias("normalized_score"),
                    pl.lit(None).cast(pl.Float64).alias("weight"),
                    pl.lit("").alias("weight_tier"),
                    pl.lit(None).cast(pl.Int64).alias("scale_min"),
                    pl.lit(None).cast(pl.Int64).alias("scale_max"),
                    pl.lit(
                        "Weighted composite score (sum of weighted scores / sum of weights)"
                    ).alias("description"),
                )
                .with_columns(
                    pl.col("weighted_score").rank(method="dense", descending=True).alias("rank"),
                )
                .with_columns(
                    pl.when(pl.col("weighted_score").count() == 1)
                    .then(pl.lit(100))
                    .otherwise(
                        (
                            (pl.col("weighted_score").count() - pl.col("rank"))
                            / pl.max_horizontal(pl.col("weighted_score").count() - 1, pl.lit(1))
                            * 100
                        ).cast(pl.Int64)
                    )
                    .alias("percentile"),
                    pl.when(pl.col("weighted_score").count() == 1)
                    .then(pl.lit(100))
                    .otherwise(
                        (
                            (pl.col("weighted_score").rank(method="min") - 1)
                            / pl.max_horizontal(pl.col("weighted_score").count() - 1, pl.lit(1))
                            * 100
                        ).cast(pl.Int64)
                    )
                    .alias("percent_rank"),
                )
            )
            pivot_df = pl.concat([pivot_df, composite_df], how="diagonal")

        result = pivot_df.select(PIVOT_COLUMNS).with_columns(
            pl.when(pl.col("criteria_name") == "_composite")
            .then(pl.lit(1))
            .otherwise(pl.lit(0))
            .alias("_sort_key")
        )
        return result.sort(["_sort_key", "batch_name"]).drop("_sort_key")

    def to_parquet(self, path: str | Path, metadata: dict[str, str] | None = None) -> str:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if metadata:
            import pyarrow.parquet as pq

            table = self._df.to_arrow()
            existing_meta = dict(table.schema.metadata or {})
            for k, v in metadata.items():
                key = k if isinstance(k, bytes) else k.encode("utf-8")
                val = v if isinstance(v, bytes) else v.encode("utf-8")
                existing_meta[key] = val
            table = table.replace_schema_metadata(existing_meta)
            pq.write_table(table, output_path)
        else:
            self._df.write_parquet(output_path)

        logger.info(f"Results written to parquet: {output_path}")
        return str(output_path)

    @classmethod
    def from_parquet(cls, path: str | Path) -> ResultsFrame:
        """Load a ResultsFrame from a parquet file.

        Args:
            path: Path to the parquet file.

        Returns:
            ResultsFrame wrapping the loaded DataFrame.

        """
        df = pl.read_parquet(path)
        return cls.from_df(df)
