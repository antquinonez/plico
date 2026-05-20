from unittest.mock import MagicMock, patch

from src.orchestrator.synthesis_runner import SynthesisRunner, _build_synthesis_result


class TestBuildSynthesisResult:
    def _make_prompt(self, name="synth1", prompt_text="Summarize"):
        return {"sequence": 99, "prompt_name": name, "prompt": prompt_text}

    def test_success_result_has_response(self):
        result = _build_synthesis_result(
            self._make_prompt("synth1", "Summarize"),
            status="success",
            evaluation_strategy="balanced",
            has_scoring=True,
            response="The summary",
            resolved_prompt="full prompt text",
        )
        assert result["prompt_name"] == "synth1"
        assert result["response"] == "The summary"
        assert result["resolved_prompt"] == "full prompt text"
        assert result["status"] == "success"
        assert result["attempts"] == 1
        assert result["result_type"] == "synthesis"

    def test_failed_result_has_error(self):
        result = _build_synthesis_result(
            self._make_prompt("synth_fail", "Summarize"),
            status="failed",
            evaluation_strategy="balanced",
            has_scoring=False,
            error="LLM timeout",
        )
        assert result["status"] == "failed"
        assert result["response"] == ""
        assert result["resolved_prompt"] == ""
        assert result["attempts"] == 1
        assert result["error"] == "LLM timeout"

    def test_success_includes_usage(self):
        result = _build_synthesis_result(
            self._make_prompt("s1", "p"),
            status="success",
            evaluation_strategy="balanced",
            has_scoring=False,
            response="ok",
            resolved_prompt="p",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.002,
            duration_ms=1200.0,
        )
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150
        assert result["cost_usd"] == 0.002
        assert result["duration_ms"] == 1200.0

    def test_with_scoring_includes_scoring_fields(self):
        result = _build_synthesis_result(
            self._make_prompt("s2", "p"),
            status="success",
            evaluation_strategy="strict",
            has_scoring=True,
            response="ok",
            resolved_prompt="p",
        )
        assert result["scoring_status"] == ""
        assert result["strategy"] == "strict"
        assert result["scores"] is None
        assert result["composite_score"] is None

    def test_without_scoring_has_none_scoring_fields(self):
        result = _build_synthesis_result(
            self._make_prompt("s3", "p"),
            status="success",
            evaluation_strategy="balanced",
            has_scoring=False,
            response="ok",
            resolved_prompt="p",
        )
        assert result["scores"] is None
        assert result["strategy"] is None
        assert result["composite_score"] is None


class TestResolveEvaluationStrategy:
    def test_returns_config_strategy_when_valid(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.config = {"evaluation_strategy": "strict"}

        eval_config = MagicMock()
        eval_config.strategies = {"strict": MagicMock(), "balanced": MagicMock()}
        eval_config.default_strategy = "balanced"

        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            mock_gc.return_value.evaluation = eval_config
            result = runner.resolve_evaluation_strategy(orch)

        assert result == "strict"

    def test_returns_default_when_config_strategy_empty(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.config = {"evaluation_strategy": ""}

        eval_config = MagicMock()
        eval_config.strategies = {"balanced": MagicMock()}
        eval_config.default_strategy = "balanced"

        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            mock_gc.return_value.evaluation = eval_config
            result = runner.resolve_evaluation_strategy(orch)

        assert result == "balanced"

    def test_returns_balanced_fallback_on_exception(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.config = {"evaluation_strategy": "strict"}

        with patch("src.orchestrator.synthesis_runner.get_config", side_effect=Exception):
            result = runner.resolve_evaluation_strategy(orch)

        assert result == "balanced"

    def test_returns_balanced_when_no_eval_config(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.config = {}

        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            mock_gc.return_value.evaluation = None
            result = runner.resolve_evaluation_strategy(orch)

        assert result == "balanced"


class TestAggregateScores:
    def test_skips_when_no_scoring_rubric(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.scoring_rubric = None
        orch.is_batch_mode = True
        orch.results = [{"prompt_name": "p1", "batch_id": 1}]

        runner.aggregate_scores(orch)
        assert orch.results[0].get("scores") is None

    def test_skips_when_not_batch_mode(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.scoring_rubric = MagicMock()
        orch.is_batch_mode = False
        orch.results = [{"prompt_name": "p1", "batch_id": 1}]

        runner.aggregate_scores(orch)
        assert orch.results[0].get("scores") is None

    def test_adds_scores_to_batch_results(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.scoring_rubric = MagicMock()
        orch.is_batch_mode = True
        orch.evaluation_strategy = "balanced"

        orch.results = [
            {
                "prompt_name": "score_p1",
                "batch_id": 1,
                "batch_name": "batch_a",
                "response": '{"relevance": 8}',
            },
            {
                "prompt_name": "score_p2",
                "batch_id": 1,
                "batch_name": "batch_a",
                "response": '{"clarity": 7}',
            },
        ]

        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            eval_config = MagicMock()
            eval_config.scoring_failure_threshold = 0.5
            eval_config.strategies = {}
            mock_gc.return_value.evaluation = eval_config

            with patch("src.orchestrator.synthesis_runner.ScoreAggregator") as MockAgg:
                mock_agg_instance = MagicMock()
                mock_agg_instance.aggregate_entry.return_value = {
                    "scores": {"relevance": 8.0},
                    "composite_score": 8.0,
                    "scoring_status": "complete",
                    "strategy": "balanced",
                }
                MockAgg.return_value = mock_agg_instance

                runner.aggregate_scores(orch)

        for r in orch.results:
            assert r["scores"] == {"relevance": 8.0}
            assert r["composite_score"] == 8.0
            assert r["scoring_status"] == "complete"
            assert r["result_type"] == "batch"

    def test_skips_results_without_batch_id(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.scoring_rubric = MagicMock()
        orch.is_batch_mode = True
        orch.evaluation_strategy = "balanced"

        orch.results = [
            {"prompt_name": "non_batch", "response": "no batch"},
        ]

        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            eval_config = MagicMock()
            eval_config.scoring_failure_threshold = 0.5
            eval_config.strategies = {}
            mock_gc.return_value.evaluation = eval_config

            with patch("src.orchestrator.synthesis_runner.ScoreAggregator") as MockAgg:
                mock_agg_instance = MagicMock()
                MockAgg.return_value = mock_agg_instance

                runner.aggregate_scores(orch)

        mock_agg_instance.aggregate_entry.assert_not_called()


class TestExecuteSynthesis:
    def test_skips_when_no_synthesis_prompts(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.synthesis_prompts = []
        orch.is_batch_mode = True

        runner.execute_synthesis(orch)
        orch._response_context.clear.assert_not_called()

    def test_skips_when_not_batch_mode(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.synthesis_prompts = [{"prompt_name": "s1", "prompt": "p"}]
        orch.is_batch_mode = False

        runner.execute_synthesis(orch)
        orch._response_context.clear.assert_not_called()

    def test_executes_synthesis_prompt(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.synthesis_prompts = [
            {
                "sequence": 99,
                "prompt_name": "final_summary",
                "prompt": "Summarize all",
                "source_scope": "all",
            }
        ]
        orch.is_batch_mode = True
        orch.has_scoring = False
        orch.evaluation_strategy = "balanced"
        orch.scoring_rubric = None
        orch.results = []
        orch._response_context = MagicMock()

        mock_ffai = MagicMock()
        mock_result = MagicMock()
        mock_result.response = "Overall summary"
        mock_result.usage = MagicMock(input_tokens=50, output_tokens=30, total_tokens=80)
        mock_result.cost_usd = 0.001
        mock_ffai.generate_response.return_value = mock_result
        orch._get_isolated_ffai.return_value = mock_ffai

        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            eval_config = MagicMock()
            eval_config.max_synthesis_context_chars = 30000
            mock_gc.return_value.evaluation = eval_config

            runner.execute_synthesis(orch)

        assert len(orch.results) == 1
        assert orch.results[0]["prompt_name"] == "final_summary"
        assert orch.results[0]["response"] == "Overall summary"
        assert orch.results[0]["status"] == "success"

    def test_handles_synthesis_failure_gracefully(self):
        runner = SynthesisRunner()
        orch = MagicMock()
        orch.synthesis_prompts = [
            {
                "sequence": 99,
                "prompt_name": "bad_synth",
                "prompt": "Fail please",
                "source_scope": "all",
            }
        ]
        orch.is_batch_mode = True
        orch.has_scoring = False
        orch.evaluation_strategy = "balanced"
        orch.scoring_rubric = None
        orch.results = []
        orch._response_context = MagicMock()

        mock_ffai = MagicMock()
        mock_ffai.generate_response.side_effect = RuntimeError("API error")
        orch._get_isolated_ffai.return_value = mock_ffai

        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            eval_config = MagicMock()
            eval_config.max_synthesis_context_chars = 30000
            mock_gc.return_value.evaluation = eval_config

            runner.execute_synthesis(orch)

        assert len(orch.results) == 1
        assert orch.results[0]["status"] == "failed"
        assert "API error" in orch.results[0]["error"]
