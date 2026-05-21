import polars as pl

from src.core.history_exporter import HistoryExporter
from src.OrderedPromptHistory import OrderedPromptHistory


def _make_records(n=3):
    return [
        {
            "prompt": f"prompt-{i}",
            "response": f"response-{i}",
            "prompt_name": f"p{i}",
            "model": "test-model",
            "timestamp": 1700000000.0 + i,
        }
        for i in range(n)
    ]


def _make_exporter(
    history=None,
    clean_history=None,
    prompt_attr_history=None,
    ordered_history=None,
    persist_dir="/tmp",
    persist_name=None,
    auto_persist=False,
):
    return HistoryExporter(
        history=history if history is not None else _make_records(),
        clean_history=clean_history if clean_history is not None else _make_records(2),
        prompt_attr_history=prompt_attr_history
        if prompt_attr_history is not None
        else _make_records(2),
        ordered_history=ordered_history if ordered_history is not None else OrderedPromptHistory(),
        persist_dir=persist_dir,
        persist_name=persist_name,
        auto_persist=auto_persist,
    )


class TestHistoryExporterHistoryToDataFrame:
    def test_converts_to_dataframe(self):
        exporter = _make_exporter()
        df = exporter.history_to_dataframe()
        assert isinstance(df, pl.DataFrame)
        assert df.height == 3
        assert df["prompt"][0] == "prompt-0"
        assert df["response"][1] == "response-1"

    def test_empty_history_returns_empty(self):
        exporter = _make_exporter(history=[])
        df = exporter.history_to_dataframe()
        assert df.is_empty()

    def test_timestamp_converted_to_datetime(self):
        exporter = _make_exporter()
        df = exporter.history_to_dataframe()
        assert "datetime" in df.columns

    def test_dict_response_stringified(self):
        records = [
            {
                "prompt": "p",
                "response": {"key": "val"},
                "prompt_name": "test",
                "model": "m",
                "timestamp": 1700000000.0,
            },
        ]
        exporter = _make_exporter(history=records)
        df = exporter.history_to_dataframe()
        assert df.height == 1
        assert isinstance(df["response"][0], str)
        assert "key" in df["response"][0]


class TestHistoryExporterCleanHistory:
    def test_clean_history_to_dataframe(self):
        records = _make_records(2)
        exporter = _make_exporter(clean_history=records)
        df = exporter.clean_history_to_dataframe()
        assert df.height == 2


class TestHistoryExporterPromptAttrHistory:
    def test_prompt_attr_history_to_dataframe(self):
        records = _make_records(2)
        exporter = _make_exporter(prompt_attr_history=records)
        df = exporter.prompt_attr_history_to_dataframe()
        assert df.height == 2


class TestHistoryExporterOrderedHistory:
    def test_ordered_history_to_dataframe(self):
        oh = OrderedPromptHistory()
        oh.add_interaction("test-model", "Hello", "Hi!", prompt_name="greet")
        exporter = _make_exporter(ordered_history=oh)
        df = exporter.ordered_history_to_dataframe()
        assert df.height == 1
        assert df["prompt_name"][0] == "greet"

    def test_ordered_history_empty(self):
        exporter = _make_exporter(ordered_history=OrderedPromptHistory())
        df = exporter.ordered_history_to_dataframe()
        assert df.is_empty()


class TestHistoryExporterSearchHistory:
    def test_search_by_text(self):
        records = [
            {
                "prompt": "What is AI?",
                "response": "ai is artificial intelligence",
                "prompt_name": "q1",
                "model": "m1",
                "timestamp": 1700000000.0,
            },
            {
                "prompt": "What is math?",
                "response": "math is numbers",
                "prompt_name": "q2",
                "model": "m2",
                "timestamp": 1700000001.0,
            },
        ]
        exporter = _make_exporter(history=records)
        df = exporter.search_history(text="ai")
        assert df.height == 1
        assert df["prompt_name"][0] == "q1"

    def test_search_by_prompt_name(self):
        exporter = _make_exporter()
        df = exporter.search_history(prompt_name="p1")
        assert df.height == 1

    def test_search_by_model(self):
        exporter = _make_exporter()
        df = exporter.search_history(model="test-model")
        assert df.height == 3

    def test_search_by_time_range(self):
        exporter = _make_exporter()
        df = exporter.search_history(start_time=1700000001.0, end_time=1700000002.0)
        assert df.height == 2

    def test_search_empty_history(self):
        exporter = _make_exporter(history=[])
        df = exporter.search_history(text="anything")
        assert df.is_empty()

    def test_search_no_filters_returns_all(self):
        exporter = _make_exporter()
        df = exporter.search_history()
        assert df.height == 3


class TestHistoryExporterModelStats:
    def test_model_stats(self):
        exporter = _make_exporter()
        df = exporter.get_model_stats_df({"mistral-small": 10, "gemini": 5})
        assert df.height == 2
        assert df["model"].to_list() == ["mistral-small", "gemini"]
        assert df["count"].to_list() == [10, 5]

    def test_model_stats_empty(self):
        exporter = _make_exporter()
        df = exporter.get_model_stats_df({})
        assert df.height == 0


class TestHistoryExporterPromptNameStats:
    def test_prompt_name_stats(self):
        exporter = _make_exporter()
        df = exporter.get_prompt_name_stats_df({"intro": 3, "analysis": 7})
        assert df.height == 2
        assert "prompt_name" in df.columns
        assert "count" in df.columns


class TestHistoryExporterResponseLengthStats:
    def test_response_length_stats(self):
        records = [
            {
                "prompt": "p1",
                "response": "short",
                "prompt_name": "brief",
                "model": "m",
                "timestamp": 1700000000.0,
            },
            {
                "prompt": "p2",
                "response": "a much longer response here",
                "prompt_name": "verbose",
                "model": "m",
                "timestamp": 1700000001.0,
            },
        ]
        exporter = _make_exporter(history=records)
        df = exporter.get_response_length_stats()
        assert df.height == 2
        assert "mean_length" in df.columns
        assert "min_length" in df.columns
        assert "max_length" in df.columns
        assert "count" in df.columns

    def test_response_length_empty(self):
        exporter = _make_exporter(history=[])
        df = exporter.get_response_length_stats()
        assert df.is_empty()


class TestHistoryExporterInteractionCountsByDate:
    def test_counts_by_date(self):
        records = _make_records(3)
        exporter = _make_exporter(history=records)
        df = exporter.interaction_counts_by_date()
        assert "date" in df.columns
        assert "len" in df.columns

    def test_counts_by_date_empty(self):
        exporter = _make_exporter(history=[])
        df = exporter.interaction_counts_by_date()
        assert df.height == 0

    def test_counts_by_date_single_day(self):
        records = [
            {
                "prompt": "p1",
                "response": "r1",
                "prompt_name": "a",
                "model": "m",
                "timestamp": 1700000000.0,
            },
            {
                "prompt": "p2",
                "response": "r2",
                "prompt_name": "b",
                "model": "m",
                "timestamp": 1700000001.0,
            },
        ]
        exporter = _make_exporter(history=records)
        df = exporter.interaction_counts_by_date()
        assert df.height == 1
        assert df["len"][0] == 2


class TestHistoryExporterTimestampConversion:
    def test_timestamp_conversion_error_returns_original_df(self):
        import polars as pl

        df = pl.DataFrame({"timestamp": ["not_a_number"]})
        result = HistoryExporter._convert_unix_seconds_to_datetime(df)
        assert "datetime" not in result.columns

    def test_timestamp_conversion_skips_when_no_timestamp_column(self):
        import polars as pl

        df = pl.DataFrame({"prompt": ["hello"]})
        result = HistoryExporter._convert_unix_seconds_to_datetime(df)
        assert "datetime" not in result.columns


class TestHistoryExporterAutoPersistError:
    def test_auto_persist_logs_error_on_write_failure(self, tmp_path):
        bad_dir = tmp_path / "nonexistent_dir"
        exporter = _make_exporter(
            persist_dir=str(bad_dir),
            persist_name="fail",
            auto_persist=True,
        )
        df = exporter.history_to_dataframe()
        assert df.height == 3
        assert not (bad_dir / "fail_history_to_dataframe.parquet").exists()


class TestHistoryExporterResponseLengthStatsError:
    def test_response_length_stats_returns_empty_on_error(self):
        exporter = HistoryExporter(
            history=[{"bad": "data"}],
            clean_history=[],
            prompt_attr_history=[],
            ordered_history=OrderedPromptHistory(),
            persist_dir="/tmp",
        )
        df = exporter.get_response_length_stats()
        assert df.is_empty()


class TestHistoryExporterPersistAllError:
    def test_persist_all_returns_false_on_bad_dir(self, tmp_path):
        exporter = _make_exporter(
            persist_dir=str(tmp_path / "nonexistent"),
            persist_name="test",
        )
        assert exporter.persist_all_histories() is False


class TestHistoryExporterResponseLengthExactValues:
    def test_response_length_stats_exact_values(self):
        records = [
            {
                "prompt": "p1",
                "response": "short",
                "prompt_name": "brief",
                "model": "m",
                "timestamp": 1700000000.0,
            },
            {
                "prompt": "p2",
                "response": "a much longer response",
                "prompt_name": "verbose",
                "model": "m",
                "timestamp": 1700000001.0,
            },
        ]
        exporter = _make_exporter(history=records)
        df = exporter.get_response_length_stats()
        assert df.height == 2
        brief_row = df.filter(pl.col("prompt_name") == "brief")
        verbose_row = df.filter(pl.col("prompt_name") == "verbose")
        assert brief_row["min_length"][0] == 5
        assert verbose_row["min_length"][0] == 22


class TestHistoryExporterPersistence:
    def test_persist_all_requires_name(self, tmp_path):
        exporter = _make_exporter(persist_dir=str(tmp_path))
        assert exporter.persist_all_histories() is False

    def test_persist_all_succeeds(self, tmp_path):
        exporter = _make_exporter(
            persist_dir=str(tmp_path),
            persist_name="test",
        )
        assert exporter.persist_all_histories() is True
        assert (tmp_path / "test_history.parquet").exists()
        assert (tmp_path / "test_clean_history.parquet").exists()

    def test_auto_persist_enabled(self, tmp_path):
        exporter = _make_exporter(
            persist_dir=str(tmp_path),
            persist_name="auto",
            auto_persist=True,
        )
        exporter.history_to_dataframe()
        assert (tmp_path / "auto_history_to_dataframe.parquet").exists()

    def test_auto_persist_disabled_no_file(self, tmp_path):
        exporter = _make_exporter(
            persist_dir=str(tmp_path),
            persist_name="auto",
            auto_persist=False,
        )
        exporter.history_to_dataframe()
        assert not (tmp_path / "auto_history_to_dataframe.parquet").exists()

    def test_auto_persist_skips_empty_df(self, tmp_path):
        exporter = _make_exporter(
            history=[],
            clean_history=[],
            prompt_attr_history=[],
            persist_dir=str(tmp_path),
            persist_name="auto",
            auto_persist=True,
        )
        exporter.history_to_dataframe()
        assert not (tmp_path / "auto_history_to_dataframe.parquet").exists()
