import threading

from src.core.response_context import ResponseContext


class TestResponseContextInit:
    def test_creates_empty_history_when_none(self):
        ctx = ResponseContext()
        assert ctx.prompt_attr_history == []

    def test_uses_shared_history_reference(self):
        shared = []
        ctx = ResponseContext(shared_prompt_attr_history=shared)
        ctx.prompt_attr_history.append({"test": True})
        assert len(shared) == 1

    def test_no_lock_by_default(self):
        ctx = ResponseContext()
        assert ctx.history_lock is None

    def test_accepts_lock(self):
        lock = threading.Lock()
        ctx = ResponseContext(history_lock=lock)
        assert ctx.history_lock is lock


class TestResponseContextRecord:
    def test_record_string_response(self):
        ctx = ResponseContext()
        ctx.record("What is 2+2?", "4", "test-model", prompt_name="math")
        assert len(ctx.prompt_attr_history) == 1
        entry = ctx.prompt_attr_history[0]
        assert entry["prompt"] == "What is 2+2?"
        assert entry["response"] == "4"
        assert entry["prompt_name"] == "math"
        assert entry["model"] == "test-model"
        assert isinstance(entry["timestamp"], float)

    def test_record_dict_response_expands_keys(self):
        ctx = ResponseContext()
        ctx.record(
            "Analyze",
            {"score": 8, "summary": "Good"},
            "test-model",
            prompt_name="analysis",
        )
        assert len(ctx.prompt_attr_history) == 2
        names = [e["prompt_name"] for e in ctx.prompt_attr_history]
        assert "score" in names
        assert "summary" in names
        score_entry = next(e for e in ctx.prompt_attr_history if e["prompt_name"] == "score")
        assert score_entry["response"] == 8
        summary_entry = next(e for e in ctx.prompt_attr_history if e["prompt_name"] == "summary")
        assert summary_entry["response"] == "Good"

    def test_record_with_history(self):
        ctx = ResponseContext()
        ctx.record("Follow-up", "Answer", "test-model", history=["math", "intro"])
        assert ctx.prompt_attr_history[0]["history"] == ["math", "intro"]

    def test_record_without_prompt_name(self):
        ctx = ResponseContext()
        ctx.record("Hello", "Hi", "test-model")
        assert ctx.prompt_attr_history[0]["prompt_name"] is None

    def test_record_appends_multiple(self):
        ctx = ResponseContext()
        ctx.record("Q1", "A1", "m1", prompt_name="p1")
        ctx.record("Q2", "A2", "m2", prompt_name="p2")
        assert len(ctx.prompt_attr_history) == 2
        assert ctx.prompt_attr_history[0]["prompt"] == "Q1"
        assert ctx.prompt_attr_history[1]["prompt"] == "Q2"


class TestResponseContextRecordRaw:
    def test_record_raw_appends_dict(self):
        ctx = ResponseContext()
        interaction = {
            "prompt": "custom",
            "response": "result",
            "prompt_name": "raw_test",
            "model": "m",
        }
        ctx.record_raw(interaction)
        assert len(ctx.prompt_attr_history) == 1
        assert ctx.prompt_attr_history[0]["prompt_name"] == "raw_test"

    def test_record_raw_preserves_all_fields(self):
        ctx = ResponseContext()
        interaction = {
            "prompt": "p",
            "response": "r",
            "prompt_name": "pn",
            "model": "model-name",
            "extra_field": "kept",
        }
        ctx.record_raw(interaction)
        assert ctx.prompt_attr_history[0]["extra_field"] == "kept"


class TestResponseContextClear:
    def test_clear_empties_history(self):
        ctx = ResponseContext()
        ctx.record("Q", "A", "m", prompt_name="p")
        assert len(ctx.prompt_attr_history) == 1
        ctx.clear()
        assert ctx.prompt_attr_history == []

    def test_clear_with_lock(self):
        lock = threading.Lock()
        shared = []
        ctx = ResponseContext(shared_prompt_attr_history=shared, history_lock=lock)
        ctx.record("Q", "A", "m")
        ctx.clear()
        assert shared == []


class TestResponseContextThreadSafety:
    def test_concurrent_records(self):
        lock = threading.Lock()
        shared = []
        ctx = ResponseContext(shared_prompt_attr_history=shared, history_lock=lock)

        def writer(n):
            for i in range(50):
                ctx.record(f"prompt-{n}-{i}", f"resp-{n}-{i}", "model", prompt_name=f"p{n}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(shared) == 200
