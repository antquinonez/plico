from unittest.mock import MagicMock, patch

from src.orchestrator.synthesis_runner import SynthesisRunner, _build_synthesis_result


class TestBuildSynthesisResult:
    def test_success_path_with_scoring(self):
        prompt = {"sequence": 10, "prompt": "test", "prompt_name": "synth1"}
        result = _build_synthesis_result(
            prompt,
            status="success",
            evaluation_strategy="balanced",
            has_scoring=True,
            response="Final answer",
            resolved_prompt="resolved",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
            duration_ms=500.0,
        )
        assert result["status"] == "success"
        assert result["response"] == "Final answer"
        assert result["resolved_prompt"] == "resolved"
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150
        assert result["cost_usd"] == 0.001
        assert result["duration_ms"] == 500.0
        assert result["strategy"] == "balanced"
        assert result["scoring_status"] == ""
        assert result["attempts"] == 1

    def test_failure_path(self):
        prompt = {"sequence": 10, "prompt": "test", "prompt_name": "synth1"}
        result = _build_synthesis_result(
            prompt,
            status="failed",
            evaluation_strategy="balanced",
            has_scoring=False,
            error="timeout",
        )
        assert result["status"] == "failed"
        assert result["response"] == ""
        assert result["resolved_prompt"] == ""
        assert result["error"] == "timeout"
        assert result["attempts"] == 1

    def test_no_scoring_no_strategy_fields(self):
        prompt = {"sequence": 10, "prompt": "test", "prompt_name": "synth1"}
        result = _build_synthesis_result(
            prompt,
            status="success",
            evaluation_strategy="",
            has_scoring=False,
            response="no scoring",
        )
        assert result["response"] == "no scoring"
        assert result.get("strategy") is None or result.get("strategy") == ""

    def test_failure_default_error_message(self):
        prompt = {"sequence": 10, "prompt": "test", "prompt_name": "synth1"}
        result = _build_synthesis_result(
            prompt,
            status="failed",
            evaluation_strategy="balanced",
            has_scoring=False,
        )
        assert result["error"] == "unknown error"

    def test_no_usage_no_cost_no_duration(self):
        prompt = {"sequence": 10, "prompt": "test", "prompt_name": "synth1"}
        result = _build_synthesis_result(
            prompt,
            status="success",
            evaluation_strategy="",
            has_scoring=False,
            response="ok",
        )
        assert result.get("input_tokens", 0) == 0
        assert result.get("cost_usd", 0) == 0
        assert result.get("duration_ms", 0) == 0


class TestResolveEvaluationStrategy:
    def test_config_strategy_in_available(self):
        mock_eval = MagicMock()
        mock_eval.strategies = {"strict": MagicMock(), "balanced": MagicMock()}
        mock_eval.default_strategy = "balanced"
        orch = MagicMock()
        orch.config = {"evaluation_strategy": "strict"}

        runner = SynthesisRunner()
        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            mock_gc.return_value.evaluation = mock_eval
            result = runner.resolve_evaluation_strategy(orch)
        assert result == "strict"

    def test_unknown_strategy_falls_to_default(self):
        mock_eval = MagicMock()
        mock_eval.strategies = {"strict": MagicMock(), "balanced": MagicMock()}
        mock_eval.default_strategy = "balanced"
        orch = MagicMock()
        orch.config = {"evaluation_strategy": "nonexistent"}

        runner = SynthesisRunner()
        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            mock_gc.return_value.evaluation = mock_eval
            result = runner.resolve_evaluation_strategy(orch)
        assert result == "balanced"

    def test_empty_config_strategy_falls_to_default(self):
        mock_eval = MagicMock()
        mock_eval.strategies = {"balanced": MagicMock()}
        mock_eval.default_strategy = "balanced"
        orch = MagicMock()
        orch.config = {"evaluation_strategy": ""}

        runner = SynthesisRunner()
        with patch("src.orchestrator.synthesis_runner.get_config") as mock_gc:
            mock_gc.return_value.evaluation = mock_eval
            result = runner.resolve_evaluation_strategy(orch)
        assert result == "balanced"

    def test_config_exception_returns_balanced(self):
        orch = MagicMock()
        orch.config = {"evaluation_strategy": "strict"}

        runner = SynthesisRunner()
        with patch("src.orchestrator.synthesis_runner.get_config", side_effect=Exception("boom")):
            result = runner.resolve_evaluation_strategy(orch)
        assert result == "balanced"


class TestAggregateScores:
    def test_skips_when_no_rubric(self):
        orch = MagicMock()
        orch.scoring_rubric = None
        orch.is_batch_mode = True

        runner = SynthesisRunner()
        runner.aggregate_scores(orch)

    def test_skips_when_not_batch_mode(self):
        orch = MagicMock()
        orch.scoring_rubric = MagicMock()
        orch.is_batch_mode = False

        runner = SynthesisRunner()
        runner.aggregate_scores(orch)

    def test_config_exception_uses_default_threshold(self):
        from dataclasses import dataclass

        @dataclass
        class FakeCriteria:
            criteria_name: str
            source_prompt: str = "p1"
            scale_max: int = 10
            weight: float = 1.0
            normalized: bool = True
            score_extraction: str = "json_get(response, 'score')"
            description: str = ""

        rubric = MagicMock()
        rubric.criteria = [FakeCriteria("skills")]
        orch = MagicMock()
        orch.scoring_rubric = rubric
        orch.is_batch_mode = True
        orch.evaluation_strategy = "balanced"
        orch.results = []

        runner = SynthesisRunner()
        with patch("src.orchestrator.synthesis_runner.get_config", side_effect=Exception("boom")):
            runner.aggregate_scores(orch)


class TestExecuteSynthesis:
    def test_skips_when_no_synthesis_prompts(self):
        orch = MagicMock()
        orch.synthesis_prompts = []
        orch.is_batch_mode = True

        runner = SynthesisRunner()
        runner.execute_synthesis(orch)

    def test_skips_when_not_batch_mode(self):
        orch = MagicMock()
        orch.synthesis_prompts = [{"prompt": "test"}]
        orch.is_batch_mode = False

        runner = SynthesisRunner()
        runner.execute_synthesis(orch)

    def test_config_exception_uses_default_max_context(self):
        orch = MagicMock()
        orch.synthesis_prompts = []
        orch.is_batch_mode = True

        runner = SynthesisRunner()
        with patch("src.orchestrator.synthesis_runner.get_config", side_effect=Exception("boom")):
            runner.execute_synthesis(orch)
