# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""DataFrame export and persistence for FFAI interaction histories."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from functools import wraps
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


def _auto_persist(method: Callable[..., pl.DataFrame]) -> Callable[..., pl.DataFrame]:
    """Persist DataFrame after method execution if auto_persist is enabled."""

    @wraps(method)
    def wrapper(self: HistoryExporter, *args: Any, **kwargs: Any) -> pl.DataFrame:
        df = method(self, *args, **kwargs)
        if self.auto_persist and self.persist_name and not df.is_empty():
            file_path = os.path.join(
                self.persist_dir, f"{self.persist_name}_{method.__name__}.parquet"
            )
            try:
                df.write_parquet(file_path)
                logger.info(f"Auto-persisted DataFrame to {file_path}")
            except Exception as e:
                logger.error(f"Failed to auto-persist DataFrame: {e!s}")
        return df

    return wrapper


class HistoryExporter:
    """DataFrame export and persistence for FFAI interaction histories.

    Converts the various history stores into Polars DataFrames and handles
    persistence to Parquet files.

    Args:
        history: Raw interaction history list.
        clean_history: Cleaned interaction history list.
        prompt_attr_history: Prompt-attribute-indexed history list.
        ordered_history: OrderedPromptHistory instance.
        persist_dir: Directory for persisted files.
        persist_name: Base name for persisted files.
        auto_persist: Whether to auto-persist DataFrames on creation.

    """

    def __init__(
        self,
        history: list[dict[str, Any]],
        clean_history: list[dict[str, Any]],
        prompt_attr_history: list[dict[str, Any]],
        ordered_history: Any,
        persist_dir: str,
        persist_name: str | None = None,
        auto_persist: bool = False,
    ) -> None:
        self._history = history
        self._clean_history = clean_history
        self._prompt_attr_history = prompt_attr_history
        self._ordered_history = ordered_history
        self.persist_dir = persist_dir
        self.persist_name = persist_name
        self.auto_persist = auto_persist

    @staticmethod
    def _convert_unix_seconds_to_datetime(df: pl.DataFrame) -> pl.DataFrame:
        """Convert Unix timestamps in seconds to datetime.

        Works with older versions of polars.

        Args:
            df: Polars DataFrame with a 'timestamp' column.

        Returns:
            DataFrame with added 'datetime' column.

        """
        if "timestamp" not in df.columns:
            return df

        try:
            df = df.with_columns(
                (pl.col("timestamp") * 1_000_000).cast(pl.Int64).alias("timestamp_us")
            )
            df = df.with_columns(pl.col("timestamp_us").cast(pl.Datetime).alias("datetime"))
            df = df.drop("timestamp_us")
            return df
        except Exception as e:
            logger.error(f"Error converting timestamp to datetime: {e!s}")
            return df

    def _history_to_dataframe(
        self, records: list[dict[str, Any]], *, label: str = ""
    ) -> pl.DataFrame:
        """Convert a list of history records to a Polars DataFrame.

        Args:
            records: List of interaction dicts.
            label: Label for log messages.

        Returns:
            Polars DataFrame with a 'datetime' column added.

        """
        if not records:
            logger.warning(f"{label or 'History'} is empty, returning empty DataFrame")
            return pl.DataFrame()

        try:
            cleaned = []
            for item in records:
                entry = item.copy()
                if isinstance(entry.get("response"), dict):
                    entry["response"] = str(entry["response"])
                cleaned.append(entry)

            df = pl.from_dicts(cleaned)
            df = self._convert_unix_seconds_to_datetime(df)

            logger.info(f"Successfully created DataFrame with {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Error converting {label or 'history'} to DataFrame: {e!s}")
            return pl.DataFrame()

    @_auto_persist
    def history_to_dataframe(self) -> pl.DataFrame:
        """Convert the full interaction history to a polars DataFrame."""
        return self._history_to_dataframe(self._history, label="history")

    @_auto_persist
    def clean_history_to_dataframe(self) -> pl.DataFrame:
        """Convert the clean interaction history to a polars DataFrame."""
        return self._history_to_dataframe(self._clean_history, label="clean history")

    @_auto_persist
    def prompt_attr_history_to_dataframe(self) -> pl.DataFrame:
        """Convert the prompt attribute history to a polars DataFrame."""
        return self._history_to_dataframe(self._prompt_attr_history, label="prompt attr history")

    @_auto_persist
    def ordered_history_to_dataframe(self) -> pl.DataFrame:
        """Convert the ordered interaction history to a polars DataFrame."""
        interactions = self._ordered_history.get_all_interactions()
        records = [i.to_dict() for i in interactions]
        return self._history_to_dataframe(records, label="ordered history")

    def search_history(
        self,
        text: str | None = None,
        prompt_name: str | None = None,
        model: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> pl.DataFrame:
        """Search interaction history with flexible filtering options.

        Args:
            text: Text to search for in prompts and responses
            prompt_name: Filter by prompt name
            model: Filter by model name
            start_time: Filter by timestamp (start time in epoch seconds)
            end_time: Filter by timestamp (end time in epoch seconds)

        Returns:
            pl.DataFrame: Filtered dataframe of interactions

        """
        logger.info(
            f"Searching history with filters: text={text}, prompt_name={prompt_name}, model={model}"
        )

        df = self.history_to_dataframe()

        if df.is_empty():
            return df

        if text is not None:
            text_lower = text.lower()
            df = df.filter(
                pl.col("prompt").str.contains(text_lower, literal=True)
                | pl.col("response").str.contains(text_lower, literal=True)
            )

        if prompt_name is not None:
            df = df.filter(pl.col("prompt_name") == prompt_name)

        if model is not None:
            df = df.filter(pl.col("model") == model)

        if start_time is not None:
            df = df.filter(pl.col("timestamp") >= start_time)

        if end_time is not None:
            df = df.filter(pl.col("timestamp") <= end_time)

        logger.info(f"Search returned {len(df)} results")
        return df

    def get_model_stats_df(self, model_usage_stats: dict[str, int]) -> pl.DataFrame:
        """Get statistics on model usage as a DataFrame.

        Args:
            model_usage_stats: Pre-computed model usage stats dict.

        Returns:
            pl.DataFrame: DataFrame with model usage statistics

        """
        return pl.DataFrame(
            {
                "model": list(model_usage_stats.keys()),
                "count": list(model_usage_stats.values()),
            }
        )

    def get_prompt_name_stats_df(self, prompt_name_stats: dict[str, int]) -> pl.DataFrame:
        """Get statistics on prompt name usage as a DataFrame.

        Args:
            prompt_name_stats: Pre-computed prompt name stats dict.

        Returns:
            pl.DataFrame: DataFrame with prompt name usage statistics

        """
        return pl.DataFrame(
            {
                "prompt_name": list(prompt_name_stats.keys()),
                "count": list(prompt_name_stats.values()),
            }
        )

    def get_response_length_stats(self) -> pl.DataFrame:
        """Get statistics on response lengths by prompt name.

        Returns:
            pl.DataFrame: DataFrame with response length statistics by prompt name

        """
        df = self.history_to_dataframe()

        if df.is_empty():
            return pl.DataFrame()

        try:
            return (
                df.with_columns(pl.col("response").str.len_chars().alias("response_length"))
                .group_by("prompt_name")
                .agg(
                    pl.col("response_length").mean().alias("mean_length"),
                    pl.col("response_length").min().alias("min_length"),
                    pl.col("response_length").max().alias("max_length"),
                    pl.col("response_length").count().alias("count"),
                )
                .sort("mean_length", descending=True)
            )

        except Exception as e:
            logger.error(f"Error calculating response length statistics: {e!s}")
            return pl.DataFrame()

    def interaction_counts_by_date(self) -> pl.DataFrame:
        """Get counts of interactions grouped by date.

        Returns:
            pl.DataFrame: DataFrame with interaction counts by date

        """
        df = self.history_to_dataframe()

        if df.is_empty() or "timestamp" not in df.columns:
            return pl.DataFrame({"date": [], "len": []})

        return (
            df.with_columns(
                pl.col("timestamp").cast(pl.Float64).cast(pl.Datetime).dt.date().alias("date")
            )
            .group_by("date")
            .len()
            .sort("date")
        )

    def persist_all_histories(self) -> bool:
        """Persist all histories to Parquet files in the configured directory."""
        if not self.persist_name:
            logger.warning("Persistence name not set. Skipping persistence.")
            return False
        try:
            file_map = {
                "history": self.history_to_dataframe(),
                "clean_history": self.clean_history_to_dataframe(),
                "prompt_attr": self.prompt_attr_history_to_dataframe(),
                "ordered": self.ordered_history_to_dataframe(),
            }
            for key, df in file_map.items():
                if not df.is_empty():
                    file_path = os.path.join(self.persist_dir, f"{self.persist_name}_{key}.parquet")
                    df.write_parquet(file_path)
                    logger.info(f"Persisted {key} to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error persisting histories: {e!s}")
            return False
