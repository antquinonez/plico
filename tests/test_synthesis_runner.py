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


class TestAggregateScoresWithResults:
    """Tests for aggregate_scores that exercise batch grouping and scoring mutation."""

    def _make_rubric(self):
        from src.orchestrator.scoring import ScoringCriteria

        rubric = MagicMock()
        rubric.criteria = [
            ScoringCriteria(
                criteria_name="skills",
                description="Skills score",
                source_prompt="evaluate",
                scale_max=10,
                weight=1.0,
            )
        ]
        rubric.resolve_weights.return_value = {"skills": 1.0}
        return rubric

    def _make_eval_config(self, threshold=0.5):
        mock_strategy = MagicMock()
        mock_strategy.criteria_overrides = {}
        mock_eval = MagicMock()
        mock_eval.scoring_failure_threshold = threshold
        mock_eval.strategies = {"balanced": mock_strategy}
        return mock_eval

    def _make_batch_results(self, n_batches=2, prompts_per_batch=2):
        results = []
        for bid in range(1, n_batches + 1):
            for pidx in range(prompts_per_batch):
                results.append(
                    {
                        "prompt_name": f"prompt_{pidx}",
                        "batch_id": bid,
                        "batch_name": f"batch_{bid}",
                        "response": f'{{"skills": {7 + bid}}}',
                        "status": "success",
                    }
                )
        return results

    @patch("src.orchestrator.synthesis_runner.get_config")
    @patch("src.orchestrator.synthesis_runner.ScoreAggregator")
    def test_aggregate_mutates_results_in_place(self, mock_agg_cls, mock_gc):
        mock_gc.return_value.evaluation = self._make_eval_config()
        scoring_result = {
            "scores": {"skills": 8.0},
            "composite_score": 8.0,
            "scoring_status": "ok",
            "strategy": "balanced",
        }
        mock_agg_cls.return_value.aggregate_entry.return_value = scoring_result

        rubric = self._make_rubric()
        results = self._make_batch_results()

        orch = MagicMock()
        orch.scoring_rubric = rubric
        orch.is_batch_mode = True
        orch.evaluation_strategy = "balanced"
        orch.results = results

        runner = SynthesisRunner()
        runner.aggregate_scores(orch)

        for r in orch.results:
            assert r["scores"] == {"skills": 8.0}
            assert r["composite_score"] == 8.0
            assert r["scoring_status"] == "ok"
            assert r["strategy"] == "balanced"
            assert r["result_type"] == "batch"

    @patch("src.orchestrator.synthesis_runner.get_config")
    @patch("src.orchestrator.synthesis_runner.ScoreAggregator")
    def test_aggregate_groups_by_batch_id(self, mock_agg_cls, mock_gc):
        mock_gc.return_value.evaluation = self._make_eval_config()
        mock_agg_cls.return_value.aggregate_entry.return_value = {
            "scores": {"skills": 5.0},
            "composite_score": 5.0,
            "scoring_status": "ok",
            "strategy": "balanced",
        }

        rubric = self._make_rubric()
        results = self._make_batch_results(n_batches=3)

        orch = MagicMock()
        orch.scoring_rubric = rubric
        orch.is_batch_mode = True
        orch.evaluation_strategy = "balanced"
        orch.results = results

        runner = SynthesisRunner()
        runner.aggregate_scores(orch)

        assert mock_agg_cls.return_value.aggregate_entry.call_count == 3

    @patch("src.orchestrator.synthesis_runner.get_config")
    @patch("src.orchestrator.synthesis_runner.ScoreAggregator")
    def test_aggregate_skips_results_without_batch_id(self, mock_agg_cls, mock_gc):
        mock_gc.return_value.evaluation = self._make_eval_config()
        mock_agg_cls.return_value.aggregate_entry.return_value = {
            "scores": {},
            "composite_score": None,
            "scoring_status": "ok",
            "strategy": "balanced",
        }

        rubric = self._make_rubric()
        results = [
            {
                "prompt_name": "p1",
                "batch_id": 1,
                "batch_name": "b1",
                "response": "{}",
                "status": "success",
            },
            {"prompt_name": "p_no_batch", "response": "{}", "status": "success"},
        ]

        orch = MagicMock()
        orch.scoring_rubric = rubric
        orch.is_batch_mode = True
        orch.evaluation_strategy = "balanced"
        orch.results = results

        runner = SynthesisRunner()
        runner.aggregate_scores(orch)

        assert mock_agg_cls.return_value.aggregate_entry.call_count == 1
        assert "scores" not in results[1]

    @patch("src.orchestrator.synthesis_runner.get_config")
    @patch("src.orchestrator.synthesis_runner.ScoreAggregator")
    def test_aggregate_passes_strategy_overrides(self, mock_agg_cls, mock_gc):
        mock_strategy = MagicMock()
        mock_strategy.criteria_overrides = {"skills": 2.0}
        mock_eval = MagicMock()
        mock_eval.scoring_failure_threshold = 0.5
        mock_eval.strategies = {"strict": mock_strategy}
        mock_gc.return_value.evaluation = mock_eval

        mock_agg_cls.return_value.aggregate_entry.return_value = {
            "scores": {"skills": 9.0},
            "composite_score": 9.0,
            "scoring_status": "ok",
            "strategy": "strict",
        }

        rubric = self._make_rubric()
        results = [
            {
                "prompt_name": "p1",
                "batch_id": 1,
                "batch_name": "b1",
                "response": "{}",
                "status": "success",
            },
        ]

        orch = MagicMock()
        orch.scoring_rubric = rubric
        orch.is_batch_mode = True
        orch.evaluation_strategy = "strict"
        orch.results = results

        runner = SynthesisRunner()
        runner.aggregate_scores(orch)

        mock_agg_cls.assert_called_once_with(
            rubric=rubric,
            strategy="strict",
            strategy_overrides={"skills": 2.0},
            failure_threshold=0.5,
        )


class TestExecuteSynthesisWithPrompts:
    """Tests for execute_synthesis that exercise the full LLM call path."""

    def _make_orchestrator(self, synthesis_prompts, results=None):
        from src.orchestrator.scoring import ScoringCriteria

        rubric = MagicMock()
        rubric.criteria = [
            ScoringCriteria(
                criteria_name="skills",
                description="Skills",
                source_prompt="evaluate",
                scale_max=10,
                weight=1.0,
            )
        ]

        orch = MagicMock()
        orch.synthesis_prompts = synthesis_prompts
        orch.is_batch_mode = True
        orch.scoring_rubric = rubric
        orch.evaluation_strategy = "balanced"
        orch.has_scoring = True
        orch.results = results or [
            {
                "sequence": 1,
                "prompt_name": "evaluate",
                "prompt": "eval prompt",
                "response": '{"skills": 8}',
                "status": "success",
                "batch_id": 1,
                "batch_name": "candidate_a",
                "scores": {"skills": 8.0},
                "composite_score": 8.0,
                "scoring_status": "ok",
                "strategy": "balanced",
            }
        ]
        orch._response_context = MagicMock()
        orch._get_isolated_ffai.return_value = MagicMock()
        return orch

    @patch("src.orchestrator.synthesis_runner.get_config")
    def test_execute_synthesis_appends_results(self, mock_gc):
        mock_eval = MagicMock()
        mock_eval.max_synthesis_context_chars = 50000
        mock_gc.return_value.evaluation = mock_eval

        synth_prompt = {
            "sequence": 99,
            "prompt_name": "synth_rank",
            "prompt": "Rank the candidates",
            "source_scope": "all",
            "source_prompts": ["evaluate"],
            "include_scores": True,
        }

        mock_usage = MagicMock()
        mock_usage.input_tokens = 200
        mock_usage.output_tokens = 100
        mock_usage.total_tokens = 300
        mock_response = MagicMock()
        mock_response.response = "Candidate A ranks first"
        mock_response.usage = mock_usage
        mock_response.cost_usd = 0.005

        orch = self._make_orchestrator([synth_prompt])
        orch._get_isolated_ffai.return_value.generate_response.return_value = mock_response

        initial_count = len(orch.results)
        runner = SynthesisRunner()
        runner.execute_synthesis(orch)

        assert len(orch.results) == initial_count + 1
        synth_result = orch.results[-1]
        assert synth_result["prompt_name"] == "synth_rank"
        assert synth_result["response"] == "Candidate A ranks first"
        assert synth_result["status"] == "success"
        assert synth_result["input_tokens"] == 200
        assert synth_result["output_tokens"] == 100
        assert synth_result["total_tokens"] == 300
        assert synth_result["cost_usd"] == 0.005
        assert synth_result["result_type"] == "synthesis"
        assert synth_result["batch_id"] == -1

    @patch("src.orchestrator.synthesis_runner.get_config")
    def test_execute_synthesis_clears_response_context(self, mock_gc):
        mock_eval = MagicMock()
        mock_eval.max_synthesis_context_chars = 50000
        mock_gc.return_value.evaluation = mock_eval

        synth_prompt = {
            "sequence": 99,
            "prompt_name": "synth1",
            "prompt": "Summarize",
            "source_scope": "all",
            "source_prompts": [],
            "include_scores": True,
        }

        mock_usage = MagicMock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 10
        mock_usage.total_tokens = 20
        mock_response = MagicMock()
        mock_response.response = "Summary"
        mock_response.usage = mock_usage
        mock_response.cost_usd = 0.0

        orch = self._make_orchestrator([synth_prompt])
        orch._get_isolated_ffai.return_value.generate_response.return_value = mock_response

        runner = SynthesisRunner()
        runner.execute_synthesis(orch)

        orch._response_context.clear.assert_called_once()


class TestExecuteSynthesisPrompt:
    """Tests for _execute_synthesis_prompt covering success, failure, and history."""

    def _make_synth_prompt(self, **overrides):
        prompt = {
            "sequence": 50,
            "prompt_name": "synth_final",
            "prompt": "Write final analysis",
            "source_scope": "all",
            "source_prompts": ["evaluate"],
            "include_scores": True,
            "history": None,
        }
        prompt.update(overrides)
        return prompt

    def _make_orchestrator(self):
        from src.orchestrator.scoring import ScoringCriteria

        rubric = MagicMock()
        rubric.criteria = [
            ScoringCriteria(
                criteria_name="skills",
                description="Skills",
                source_prompt="evaluate",
                scale_max=10,
                weight=1.0,
            )
        ]

        mock_usage = MagicMock()
        mock_usage.input_tokens = 150
        mock_usage.output_tokens = 80
        mock_usage.total_tokens = 230

        mock_response = MagicMock()
        mock_response.response = "Analysis complete"
        mock_response.usage = mock_usage
        mock_response.cost_usd = 0.003

        mock_ffai = MagicMock()
        mock_ffai.generate_response.return_value = mock_response

        orch = MagicMock()
        orch.scoring_rubric = rubric
        orch.evaluation_strategy = "balanced"
        orch.has_scoring = True
        orch._get_isolated_ffai.return_value = mock_ffai
        orch._response_context = MagicMock()
        return orch

    @patch("src.orchestrator.synthesis_runner.get_config")
    def test_success_path_records_result(self, mock_gc):
        mock_eval = MagicMock()
        mock_eval.max_synthesis_context_chars = 50000
        mock_gc.return_value.evaluation = mock_eval

        synth_prompt = self._make_synth_prompt()
        orch = self._make_orchestrator()
        orch.synthesis_prompts = [synth_prompt]
        orch.is_batch_mode = True
        orch.results = [
            {
                "sequence": 1,
                "prompt_name": "evaluate",
                "prompt": "eval",
                "response": '{"skills": 7}',
                "status": "success",
                "batch_id": 1,
                "batch_name": "candidate_a",
                "scores": {"skills": 7.0},
                "composite_score": 7.0,
                "scoring_status": "ok",
                "strategy": "balanced",
            }
        ]

        runner = SynthesisRunner()
        runner.execute_synthesis(orch)

        synth_result = orch.results[-1]
        assert synth_result["prompt_name"] == "synth_final"
        assert synth_result["response"] == "Analysis complete"
        assert synth_result["status"] == "success"
        assert synth_result["input_tokens"] == 150
        assert synth_result["output_tokens"] == 80
        assert synth_result["total_tokens"] == 230
        assert synth_result["cost_usd"] == 0.003
        assert synth_result["duration_ms"] > 0

    @patch("src.orchestrator.synthesis_runner.get_config")
    def test_failure_path_records_error(self, mock_gc):
        mock_eval = MagicMock()
        mock_eval.max_synthesis_context_chars = 50000
        mock_gc.return_value.evaluation = mock_eval

        synth_prompt = self._make_synth_prompt()
        orch = self._make_orchestrator()
        orch._get_isolated_ffai.return_value.generate_response.side_effect = RuntimeError(
            "API timeout"
        )
        orch.synthesis_prompts = [synth_prompt]
        orch.is_batch_mode = True
        orch.results = [
            {
                "sequence": 1,
                "prompt_name": "evaluate",
                "prompt": "eval",
                "response": '{"skills": 7}',
                "status": "success",
                "batch_id": 1,
                "batch_name": "candidate_a",
                "scores": {"skills": 7.0},
                "composite_score": 7.0,
                "scoring_status": "ok",
                "strategy": "balanced",
            }
        ]

        runner = SynthesisRunner()
        runner.execute_synthesis(orch)

        synth_result = orch.results[-1]
        assert synth_result["prompt_name"] == "synth_final"
        assert synth_result["status"] == "failed"
        assert synth_result["error"] == "API timeout"
        assert synth_result["response"] == ""

    @patch("src.orchestrator.synthesis_runner.get_config")
    def test_history_dependency_includes_prior_synthesis(self, mock_gc):
        mock_eval = MagicMock()
        mock_eval.max_synthesis_context_chars = 50000
        mock_gc.return_value.evaluation = mock_eval

        synth_prompt = self._make_synth_prompt(
            history=["synth_first"],
        )

        orch = self._make_orchestrator()
        orch.synthesis_prompts = [synth_prompt]
        orch.is_batch_mode = True
        orch.results = [
            {
                "sequence": 1,
                "prompt_name": "evaluate",
                "prompt": "eval",
                "response": '{"skills": 7}',
                "status": "success",
                "batch_id": 1,
                "batch_name": "candidate_a",
                "scores": {"skills": 7.0},
                "composite_score": 7.0,
                "scoring_status": "ok",
                "strategy": "balanced",
            }
        ]

        results_by_name = {
            "synth_first": {
                "prompt_name": "synth_first",
                "response": "First pass analysis",
                "status": "success",
            }
        }

        from src.orchestrator.synthesis import SynthesisExecutor

        mock_ffai = orch._get_isolated_ffai.return_value
        runner = SynthesisRunner()

        call_args = {}

        original_generate = mock_ffai.generate_response

        def capture_generate(**kwargs):
            call_args["prompt"] = kwargs.get("prompt", "")
            return original_generate.return_value

        mock_ffai.generate_response.side_effect = capture_generate

        synthesis_results = []
        executor = SynthesisExecutor(max_context_chars=50000)

        sorted_entries = [
            {
                "batch_id": 1,
                "batch_name": "candidate_a",
                "scores": {"skills": 7.0},
                "composite_score": 7.0,
                "prompt_name": "evaluate",
                "response": '{"skills": 7}',
            }
        ]

        runner._execute_synthesis_prompt(
            synth_prompt,
            orch,
            executor,
            sorted_entries,
            {1: {"evaluate": orch.results[0]}},
            [{"criteria_name": "skills"}],
            results_by_name,
            synthesis_results,
        )

        assert len(synthesis_results) == 1
        assert "First pass analysis" in call_args["prompt"]

    @patch("src.orchestrator.synthesis_runner.get_config")
    def test_failed_dependency_logs_warning(self, mock_gc):
        mock_eval = MagicMock()
        mock_eval.max_synthesis_context_chars = 50000
        mock_gc.return_value.evaluation = mock_eval

        synth_prompt = self._make_synth_prompt(history=["failed_dep"])

        orch = self._make_orchestrator()
        orch.synthesis_prompts = [synth_prompt]
        orch.is_batch_mode = True
        orch.results = [
            {
                "sequence": 1,
                "prompt_name": "evaluate",
                "prompt": "eval",
                "response": '{"skills": 7}',
                "status": "success",
                "batch_id": 1,
                "batch_name": "candidate_a",
                "scores": {"skills": 7.0},
                "composite_score": 7.0,
                "scoring_status": "ok",
                "strategy": "balanced",
            }
        ]

        results_by_name = {
            "failed_dep": {
                "prompt_name": "failed_dep",
                "response": "error output",
                "status": "failed",
            }
        }

        from src.orchestrator.synthesis import SynthesisExecutor

        runner = SynthesisRunner()
        synthesis_results = []
        executor = SynthesisExecutor(max_context_chars=50000)

        runner._execute_synthesis_prompt(
            synth_prompt,
            orch,
            executor,
            [{"batch_id": 1, "batch_name": "candidate_a", "scores": {}, "composite_score": 7.0}],
            {1: {"evaluate": orch.results[0]}},
            [],
            results_by_name,
            synthesis_results,
        )

        assert len(synthesis_results) == 1
        orch._response_context.record_raw.assert_called_with(results_by_name["failed_dep"])

    @patch("src.orchestrator.synthesis_runner.get_config")
    def test_no_scoring_skips_criteria_list(self, mock_gc):
        mock_eval = MagicMock()
        mock_eval.max_synthesis_context_chars = 50000
        mock_gc.return_value.evaluation = mock_eval

        synth_prompt = self._make_synth_prompt()

        orch = self._make_orchestrator()
        orch.scoring_rubric = None
        orch.has_scoring = False
        orch.synthesis_prompts = [synth_prompt]
        orch.is_batch_mode = True
        orch.results = [
            {
                "sequence": 1,
                "prompt_name": "evaluate",
                "prompt": "eval",
                "response": "Good candidate",
                "status": "success",
                "batch_id": 1,
                "batch_name": "candidate_a",
            }
        ]

        runner = SynthesisRunner()
        runner.execute_synthesis(orch)

        synth_result = orch.results[-1]
        assert synth_result["status"] == "success"
        assert synth_result["response"] == "Analysis complete"
