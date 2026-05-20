# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for planning phase in the orchestrator — execution, injection, validation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.orchestrator.scoring import ScoringCriteria, ScoringRubric


class TestPlanningPhaseDetection:
    """Tests for _detect_planning_prompts() behavior."""

    def _make_orchestrator(self, prompts, batch_data=None):
        """Create a minimal mock orchestrator with planning detection."""
        from src.orchestrator.base.orchestrator_base import OrchestratorBase

        mock_client = MagicMock()
        mock_client.clone.return_value = mock_client

        with patch.object(OrchestratorBase, "__abstractmethods__", set()):
            orch = OrchestratorBase(client=mock_client)
            orch.prompts = prompts
            orch.batch_data = batch_data or []
            orch.is_batch_mode = len(orch.batch_data) > 0
            orch._detect_planning_prompts()
        return orch

    def test_no_phase_column(self):
        """Test backward compat: prompts without phase column default to execution."""
        prompts = [
            {"sequence": 10, "prompt_name": "p1", "prompt": "test"},
            {"sequence": 20, "prompt_name": "p2", "prompt": "test2"},
        ]
        orch = self._make_orchestrator(prompts)
        assert orch.has_planning is False
        assert orch.planning_prompts == []
        assert len(orch.prompts) == 2

    def test_phase_column_no_planning(self):
        """Test workbook with phase column but all execution prompts."""
        prompts = [
            {"sequence": 10, "prompt_name": "p1", "prompt": "test", "phase": "execution"},
            {"sequence": 20, "prompt_name": "p2", "prompt": "test2", "phase": "execution"},
        ]
        orch = self._make_orchestrator(prompts)
        assert orch.has_planning is False
        assert len(orch.prompts) == 2

    def test_phase_separation(self):
        """Test planning prompts are separated from execution prompts."""
        prompts = [
            {"sequence": 10, "prompt_name": "plan1", "prompt": "plan", "phase": "planning"},
            {"sequence": 100, "prompt_name": "exec1", "prompt": "exec", "phase": "execution"},
        ]
        orch = self._make_orchestrator(prompts)
        assert orch.has_planning is True
        assert len(orch.planning_prompts) == 1
        assert orch.planning_prompts[0]["prompt_name"] == "plan1"
        assert len(orch.prompts) == 1
        assert orch.prompts[0]["prompt_name"] == "exec1"

    def test_planning_prompts_sorted_by_sequence(self):
        """Test planning prompts are sorted by sequence."""
        prompts = [
            {"sequence": 30, "prompt_name": "plan2", "prompt": "p2", "phase": "planning"},
            {"sequence": 10, "prompt_name": "plan1", "prompt": "p1", "phase": "planning"},
            {"sequence": 100, "prompt_name": "exec1", "prompt": "e1", "phase": "execution"},
        ]
        orch = self._make_orchestrator(prompts)
        assert orch.planning_prompts[0]["prompt_name"] == "plan1"
        assert orch.planning_prompts[1]["prompt_name"] == "plan2"

    def test_non_batch_warning(self, caplog):
        """Test warning when planning prompts in non-batch mode."""
        prompts = [
            {"sequence": 10, "prompt_name": "plan1", "prompt": "plan", "phase": "planning"},
        ]
        self._make_orchestrator(prompts, batch_data=[])
        assert "scoring and synthesis will be skipped" in caplog.text.lower()


class TestExecutePlanningPhase:
    """Tests for _execute_planning_phase() method."""

    def _make_orchestrator_with_mock(self, planning_prompts, execution_prompts=None):
        """Create orchestrator with mock _execute_prompt."""
        from src.orchestrator.base.orchestrator_base import OrchestratorBase

        mock_client = MagicMock()
        mock_client.clone.return_value = mock_client

        with patch.object(OrchestratorBase, "__abstractmethods__", set()):
            orch = OrchestratorBase(client=mock_client)
            orch.planning_prompts = planning_prompts
            orch.has_planning = True
            orch.prompts = execution_prompts or []
            orch.config = {"model": "test-model"}
            orch.batch_data = []
            orch.is_batch_mode = False
        return orch

    def test_basic_execution_single_generator(self):
        """Test basic planning execution with a single generator prompt."""
        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "analyze_jd",
                "prompt": "Analyze the JD",
                "phase": "planning",
                "generator": True,
                "history": None,
            }
        ]
        orch = self._make_orchestrator_with_mock(
            planning_prompts,
            execution_prompts=[
                {"sequence": 100, "prompt_name": "existing", "prompt": "test"},
            ],
        )

        generator_response = json.dumps(
            {
                "scoring_criteria": [
                    {
                        "criteria_name": "skills",
                        "description": "Skills match",
                        "scale_min": 1,
                        "scale_max": 10,
                        "weight": 1.0,
                        "source_prompt": "eval_skills",
                    }
                ],
                "prompts": [
                    {
                        "prompt_name": "eval_skills",
                        "prompt": "Evaluate skills.",
                    }
                ],
            }
        )

        orch._execute_prompt = MagicMock(
            return_value={
                "prompt_name": "analyze_jd",
                "response": generator_response,
                "status": "success",
                "attempts": 1,
            }
        )

        with patch("src.orchestrator.base.orchestrator_base.get_config") as mock_config:
            mock_planning_config = MagicMock()
            mock_planning_config.continue_on_parse_error = True
            mock_planning_config.generated_sequence_base = "auto"
            mock_planning_config.generated_sequence_step = 10
            mock_eval_config = MagicMock()
            mock_eval_config.weight_tier_enabled = False
            mock_config.return_value.planning = mock_planning_config
            mock_config.return_value.evaluation = mock_eval_config

            orch._execute_planning_phase()

        # Planning results should be recorded
        assert len(orch.planning_results) == 1
        assert orch.planning_results[0]["result_type"] == "planning"

        # Generated prompt should be injected
        gen_prompts = [p for p in orch.prompts if p.get("_generated")]
        assert len(gen_prompts) == 1
        assert gen_prompts[0]["prompt_name"] == "eval_skills"

        # Scoring should be auto-derived
        assert orch.has_scoring is True
        assert orch.scoring_rubric is not None
        assert len(orch.scoring_rubric.criteria) == 1

    def test_non_generator_planning_prompt(self):
        """Test non-generator planning prompt records history normally."""
        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "analyze",
                "prompt": "Analyze this",
                "phase": "planning",
                "generator": False,
                "history": None,
            }
        ]
        orch = self._make_orchestrator_with_mock(planning_prompts)

        orch._execute_prompt = MagicMock(
            return_value={
                "prompt_name": "analyze",
                "response": "Analysis complete",
                "status": "success",
                "attempts": 1,
            }
        )

        with patch("src.orchestrator.base.orchestrator_base.get_config") as mock_config:
            mock_config.return_value.planning = MagicMock(
                continue_on_parse_error=True,
                generated_sequence_base="auto",
                generated_sequence_step=10,
            )
            orch._execute_planning_phase()

        assert len(orch.planning_results) == 1
        # Non-generator should NOT add to shared history manually
        # (FFAI.generate_response handles it)
        assert len(orch.shared_prompt_attr_history) == 0

    def test_generator_failure_continue(self):
        """Test generator failure continues when continue_on_parse_error=True."""
        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "gen1",
                "prompt": "Generate",
                "phase": "planning",
                "generator": True,
                "history": None,
            }
        ]
        orch = self._make_orchestrator_with_mock(planning_prompts)

        orch._execute_prompt = MagicMock(
            return_value={
                "prompt_name": "gen1",
                "response": "not valid json at all",
                "status": "success",
                "attempts": 1,
            }
        )

        with patch("src.orchestrator.base.orchestrator_base.get_config") as mock_config:
            mock_config.return_value.planning = MagicMock(
                continue_on_parse_error=True,
                generated_sequence_base="auto",
                generated_sequence_step=10,
            )
            # Should not raise
            orch._execute_planning_phase()

        assert len(orch.planning_results) == 1

    def test_progress_callback_called(self):
        """Test progress callback is called during planning phase."""
        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "p1",
                "prompt": "test",
                "phase": "planning",
                "generator": False,
                "history": None,
            }
        ]
        orch = self._make_orchestrator_with_mock(planning_prompts)
        callback = MagicMock()
        orch.progress_callback = callback

        orch._execute_prompt = MagicMock(
            return_value={
                "prompt_name": "p1",
                "response": "done",
                "status": "success",
                "attempts": 1,
            }
        )

        with patch("src.orchestrator.base.orchestrator_base.get_config") as mock_config:
            mock_config.return_value.planning = MagicMock(
                continue_on_parse_error=True,
                generated_sequence_base="auto",
                generated_sequence_step=10,
            )
            orch._execute_planning_phase()

        callback.assert_called_once()
        call_kwargs = callback.call_args
        assert "[planning]" in call_kwargs[1]["current_name"]
        assert call_kwargs[1]["total"] == 1


class TestScoringAutoDerivation:
    """Tests for scoring rubric auto-derivation from planning phase."""

    def _make_orchestrator(self):
        from src.orchestrator.base.orchestrator_base import OrchestratorBase

        mock_client = MagicMock()
        mock_client.clone.return_value = mock_client

        with patch.object(OrchestratorBase, "__abstractmethods__", set()):
            orch = OrchestratorBase(client=mock_client)
            orch.config = {"model": "test-model"}
            orch.batch_data = []
            orch.is_batch_mode = False
        return orch

    def test_manual_sheet_takes_priority(self, caplog):
        """Test manual scoring sheet overrides generated criteria."""
        from src.orchestrator.planning import GeneratedArtifact, PlanningArtifactParser

        orch = self._make_orchestrator()
        orch.has_scoring = True
        orch.scoring_rubric = ScoringRubric(
            [
                ScoringCriteria(criteria_name="manual", description="Manual criteria"),
            ]
        )
        orch.prompts = [{"prompt_name": "exec1", "prompt": "test", "sequence": 100}]

        parser = PlanningArtifactParser()
        artifacts = [
            GeneratedArtifact(
                scoring_criteria=[{"criteria_name": "auto", "description": "Auto"}],
                generated_prompts=[],
                source="gen",
            )
        ]

        with patch("src.orchestrator.base.orchestrator_base.get_config") as mock_config:
            mock_config.return_value.planning = MagicMock(
                continue_on_parse_error=True,
                generated_sequence_base="auto",
                generated_sequence_step=10,
            )
            orch._parse_generated_artifacts(artifacts, parser, mock_config.return_value.planning)

        # Manual scoring should still be in place
        assert orch.scoring_rubric.criteria[0].criteria_name == "manual"
        assert "using scoring sheet" in caplog.text.lower()

    def test_no_valid_criteria_skips_rubric(self, caplog):
        """Test all criteria failing validation skips rubric creation."""
        from src.orchestrator.planning import GeneratedArtifact, PlanningArtifactParser

        orch = self._make_orchestrator()
        orch.has_scoring = False
        orch.prompts = [{"prompt_name": "exec1", "prompt": "test", "sequence": 100}]

        parser = PlanningArtifactParser()
        # Criteria with invalid source_prompt
        artifacts = [
            GeneratedArtifact(
                scoring_criteria=[
                    {
                        "criteria_name": "bad",
                        "description": "Bad",
                        "source_prompt": "nonexistent",
                    }
                ],
                generated_prompts=[],
                source="gen",
            )
        ]

        with patch("src.orchestrator.base.orchestrator_base.get_config") as mock_config:
            mock_config.return_value.planning = MagicMock(
                continue_on_parse_error=True,
                generated_sequence_base="auto",
                generated_sequence_step=10,
            )
            orch._parse_generated_artifacts(artifacts, parser, mock_config.return_value.planning)

        assert orch.has_scoring is False
        assert "all generated scoring criteria failed" in caplog.text.lower()


class TestValidationSplit:
    """Tests for pre/post planning validation split."""

    def test_pre_planning_skips_scoring_source(self):
        """Test pre-planning validation skips scoring source_prompt check."""
        from src.orchestrator.validation import OrchestratorValidator

        prompts = [{"sequence": 100, "prompt_name": "exec", "prompt": "test"}]
        # Criteria referencing a not-yet-generated prompt
        scoring_criteria = [
            {
                "criteria_name": "skills",
                "source_prompt": "generated_prompt",
                "weight": 1.0,
                "scale_min": 1,
                "scale_max": 10,
            }
        ]

        validator = OrchestratorValidator(
            prompts=prompts,
            config={},
            scoring_criteria=scoring_criteria,
            skip_scoring_source_check=True,
        )
        result = validator.validate()
        # Should NOT have INVALID_SCORING_SOURCE error
        error_codes = [e.code for e in result.errors if e.severity == "error"]
        assert "INVALID_SCORING_SOURCE" not in error_codes

    def test_post_planning_checks_scoring_source(self):
        """Test post-planning validation checks scoring source_prompt."""
        from src.orchestrator.validation import OrchestratorValidator

        prompts = [{"sequence": 100, "prompt_name": "exec", "prompt": "test"}]
        scoring_criteria = [
            {
                "criteria_name": "skills",
                "source_prompt": "nonexistent",
                "weight": 1.0,
                "scale_min": 1,
                "scale_max": 10,
            }
        ]

        validator = OrchestratorValidator(
            prompts=prompts,
            config={},
            scoring_criteria=scoring_criteria,
            skip_scoring_source_check=False,
        )
        result = validator.validate()
        error_codes = [e.code for e in result.errors if e.severity == "error"]
        assert "INVALID_SCORING_SOURCE" in error_codes

    def test_synthesis_without_scoring_suppressed(self):
        """Test SYNTHESIS_WITHOUT_SCORING is suppressed during pre-planning."""
        from src.orchestrator.validation import OrchestratorValidator

        prompts = [{"sequence": 100, "prompt_name": "exec", "prompt": "test"}]
        synthesis = [{"sequence": 1, "prompt_name": "synth", "prompt": "Summarize"}]

        validator = OrchestratorValidator(
            prompts=prompts,
            config={},
            synthesis_prompts=synthesis,
            skip_scoring_source_check=True,
        )
        result = validator.validate()
        warning_codes = [e.code for e in result.errors if e.severity == "warning"]
        assert "SYNTHESIS_WITHOUT_SCORING" not in warning_codes


class TestPlanningValidation:
    """Tests for planning-specific validation checks."""

    def test_planning_has_variables_error(self):
        """Test planning prompt with actual batch variable produces error."""
        from src.orchestrator.validation import OrchestratorValidator

        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "plan",
                "prompt": "Analyze {{candidate_name}}",
                "phase": "planning",
            }
        ]

        validator = OrchestratorValidator(
            prompts=[],
            config={},
            planning_prompts=planning_prompts,
            batch_data_keys=["candidate_name"],
        )
        result = validator.validate()
        error_codes = [e.code for e in result.errors if e.severity == "error"]
        assert "PLANNING_HAS_VARIABLES" in error_codes

    def test_planning_mention_variable_syntax_ok(self):
        """Test planning prompt mentioning {{var}} as instruction is allowed.

        Planning prompts often instruct the LLM to generate prompts that
        use {{variable}} syntax. This is not an error — only actual batch
        data keys should be flagged.
        """
        from src.orchestrator.validation import OrchestratorValidator

        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "plan",
                "prompt": "Generate prompts that use {{candidate_name}} as a variable.",
                "phase": "planning",
            }
        ]

        # candidate_name is NOT in batch_data_keys (or keys are different)
        validator = OrchestratorValidator(
            prompts=[],
            config={},
            planning_prompts=planning_prompts,
            batch_data_keys=["applicant_name"],  # different key
        )
        result = validator.validate()
        error_codes = [e.code for e in result.errors if e.severity == "error"]
        assert "PLANNING_HAS_VARIABLES" not in error_codes

    def test_planning_no_batch_data_allows_variables(self):
        """Test planning prompt with {{var}} is allowed when no batch data exists."""
        from src.orchestrator.validation import OrchestratorValidator

        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "plan",
                "prompt": "Use {{candidate_name}} in generated prompts.",
                "phase": "planning",
            }
        ]

        validator = OrchestratorValidator(
            prompts=[],
            config={},
            planning_prompts=planning_prompts,
            # No batch_data_keys — non-batch mode or just not provided
        )
        result = validator.validate()
        error_codes = [e.code for e in result.errors if e.severity == "error"]
        assert "PLANNING_HAS_VARIABLES" not in error_codes

    def test_generator_on_execution_phase_error(self):
        """Test generator=true on execution phase produces error."""
        from src.orchestrator.validation import OrchestratorValidator

        prompts = [
            {
                "sequence": 100,
                "prompt_name": "exec",
                "prompt": "test",
                "phase": "execution",
                "generator": True,
            }
        ]

        validator = OrchestratorValidator(
            prompts=prompts,
            config={},
            planning_prompts=[],
        )
        result = validator.validate()
        error_codes = [e.code for e in result.errors if e.severity == "error"]
        assert "GENERATOR_ON_EXECUTION_PHASE" in error_codes

    def test_valid_planning_prompt_no_errors(self):
        """Test valid planning prompt produces no planning-specific errors."""
        from src.orchestrator.validation import OrchestratorValidator

        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "plan",
                "prompt": "Analyze this job description.",
                "phase": "planning",
                "generator": True,
            }
        ]

        validator = OrchestratorValidator(
            prompts=[{"sequence": 100, "prompt_name": "exec", "prompt": "test"}],
            config={},
            planning_prompts=planning_prompts,
        )
        result = validator.validate()
        planning_errors = [
            e.code
            for e in result.errors
            if e.code in ("PLANNING_HAS_VARIABLES", "GENERATOR_ON_EXECUTION_PHASE")
        ]
        assert planning_errors == []

    def test_generator_prompt_with_batch_variable_ok(self):
        """Test generator prompt mentioning batch variable is allowed.

        Generator prompts produce prompts that will later use batch variables,
        so {{candidate_name}} in instructions to the LLM is legitimate.
        """
        from src.orchestrator.validation import OrchestratorValidator

        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "analyze_jd",
                "prompt": "Create prompts that include {{candidate_name}} for each skill.",
                "phase": "planning",
                "generator": True,
            }
        ]

        validator = OrchestratorValidator(
            prompts=[],
            config={},
            planning_prompts=planning_prompts,
            batch_data_keys=["candidate_name"],
        )
        result = validator.validate()
        error_codes = [e.code for e in result.errors if e.severity == "error"]
        assert "PLANNING_HAS_VARIABLES" not in error_codes


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing workbooks."""

    def test_run_flow_no_planning(self):
        """Test run() flow when no planning prompts exist."""
        from src.orchestrator.base.orchestrator_base import OrchestratorBase

        mock_client = MagicMock()
        mock_client.clone.return_value = mock_client

        with patch.object(OrchestratorBase, "__abstractmethods__", set()):
            orch = OrchestratorBase(client=mock_client)
            orch.has_planning = False

            # Mock all methods in the run flow
            orch._load_source = MagicMock()
            orch._validate = MagicMock()
            orch._init_client = MagicMock()
            orch._write_results = MagicMock(return_value="results_sheet")
            orch.is_batch_mode = False
            orch.has_scoring = False
            orch.has_synthesis = False
            orch.execute = MagicMock(return_value=[])
            orch.concurrency = 1

            result = orch.run()

        # Should call _validate (not _validate_pre_planning)
        orch._validate.assert_called_once()
        assert result == "results_sheet"


class TestPlanningRunnerGeneratorParseError:
    """Tests for PlanningPhaseRunner.execute() parse-error re-raise path (line 131)."""

    def _make_orchestrator(self, planning_prompts):
        from src.orchestrator.base.orchestrator_base import OrchestratorBase

        mock_client = MagicMock()
        mock_client.clone.return_value = mock_client

        with patch.object(OrchestratorBase, "__abstractmethods__", set()):
            orch = OrchestratorBase(client=mock_client)
            orch.planning_prompts = planning_prompts
            orch.has_planning = True
            orch.prompts = []
            orch.config = {"model": "test-model"}
            orch.batch_data = []
            orch.is_batch_mode = False
        return orch

    def test_generator_parse_error_raises_when_continue_disabled(self):
        """Generator parse error re-raises ValueError when continue_on_parse_error is False."""
        from src.orchestrator.planning_runner import PlanningPhaseRunner

        planning_prompts = [
            {
                "sequence": 10,
                "prompt_name": "gen1",
                "prompt": "Generate criteria",
                "phase": "planning",
                "generator": True,
                "history": None,
            }
        ]
        orch = self._make_orchestrator(planning_prompts)
        orch._execute_prompt = MagicMock(
            return_value={
                "prompt_name": "gen1",
                "response": "this is not valid json",
                "status": "success",
                "attempts": 1,
            }
        )

        runner = PlanningPhaseRunner()
        with patch("src.orchestrator.planning_runner.get_config") as mock_config:
            mock_planning = MagicMock()
            mock_planning.continue_on_parse_error = False
            mock_config.return_value.planning = mock_planning

            with pytest.raises(ValueError, match="response is not a JSON object"):
                runner.execute(orch)


class TestPlanningRunnerParseAndInject:
    """Tests for PlanningPhaseRunner.parse_and_inject() uncovered paths."""

    def _make_orchestrator(self):
        from src.orchestrator.base.orchestrator_base import OrchestratorBase

        mock_client = MagicMock()
        mock_client.clone.return_value = mock_client

        with patch.object(OrchestratorBase, "__abstractmethods__", set()):
            orch = OrchestratorBase(client=mock_client)
            orch.config = {"model": "test-model"}
            orch.batch_data = [{"name": "Alice"}, {"name": "Bob"}]
            orch.is_batch_mode = True
            orch.has_scoring = False
            orch.evaluation_strategy = "balanced"
        return orch

    def test_inject_with_document_registry(self):
        """parse_and_inject uses document_registry.get_reference_names when present (line 171)."""
        from src.orchestrator.planning import GeneratedArtifact, PlanningArtifactParser
        from src.orchestrator.planning_runner import PlanningPhaseRunner

        orch = self._make_orchestrator()
        orch.prompts = [{"prompt_name": "exec1", "prompt": "test", "sequence": 100}]
        orch.document_registry = MagicMock()
        orch.document_registry.get_reference_names.return_value = ["doc1.pdf"]

        parser = PlanningArtifactParser()
        artifacts = [
            GeneratedArtifact(
                scoring_criteria=[],
                generated_prompts=[
                    {"prompt_name": "gen_eval", "prompt": "Evaluate the candidate."},
                ],
                source="gen1",
            )
        ]

        planning_config = MagicMock()
        planning_config.continue_on_parse_error = True
        planning_config.generated_sequence_base = "auto"
        planning_config.generated_sequence_step = 10

        with patch("src.orchestrator.planning_runner.OrchestratorValidator") as mock_validator_cls:
            mock_validator_cls.extract_batch_keys.return_value = ["name"]
            runner = PlanningPhaseRunner()
            runner.parse_and_inject(orch, artifacts, parser, planning_config)

        gen_prompts = [p for p in orch.prompts if p.get("_generated")]
        assert len(gen_prompts) == 1
        assert gen_prompts[0]["prompt_name"] == "gen_eval"

    def test_inject_with_batch_keys(self):
        """parse_and_inject extracts batch_keys for validation (line 174)."""
        from src.orchestrator.planning import GeneratedArtifact, PlanningArtifactParser
        from src.orchestrator.planning_runner import PlanningPhaseRunner

        orch = self._make_orchestrator()
        orch.prompts = [{"prompt_name": "exec1", "prompt": "test", "sequence": 100}]

        parser = PlanningArtifactParser()
        artifacts = [
            GeneratedArtifact(
                scoring_criteria=[],
                generated_prompts=[
                    {"prompt_name": "gen_eval", "prompt": "Evaluate candidate."},
                ],
                source="gen1",
            )
        ]

        planning_config = MagicMock()
        planning_config.continue_on_parse_error = True
        planning_config.generated_sequence_base = "auto"
        planning_config.generated_sequence_step = 10

        runner = PlanningPhaseRunner()
        runner.parse_and_inject(orch, artifacts, parser, planning_config)

        assert any(p.get("_generated") for p in orch.prompts)

    def test_inject_validation_errors_raise_when_continue_disabled(self):
        """Validation errors in generated prompts raise when continue_on_parse_error is False (lines 180-186)."""
        from src.orchestrator.planning import GeneratedArtifact, PlanningArtifactParser
        from src.orchestrator.planning_runner import PlanningPhaseRunner

        orch = self._make_orchestrator()
        orch.prompts = [{"prompt_name": "exec1", "prompt": "test", "sequence": 100}]

        parser = PlanningArtifactParser()
        parser.merge_artifacts = MagicMock(
            return_value=(
                [],
                [{"prompt_name": "", "prompt": ""}],
            )
        )
        parser.validate_prompts = MagicMock(return_value=["Duplicate prompt name: 'gen1'"])
        parser.assign_sequences = MagicMock()

        artifacts = [
            GeneratedArtifact(
                scoring_criteria=[],
                generated_prompts=[{"prompt_name": "gen1", "prompt": "test"}],
                source="gen1",
            )
        ]

        planning_config = MagicMock()
        planning_config.continue_on_parse_error = False
        planning_config.generated_sequence_base = "auto"
        planning_config.generated_sequence_step = 10

        runner = PlanningPhaseRunner()
        with pytest.raises(ValueError, match="Generated prompt validation failed"):
            runner.parse_and_inject(orch, artifacts, parser, planning_config)


class TestPlanningArtifactParserEdgeCases:
    """Tests for PlanningArtifactParser lines 78-80, 158, 169, 201, 232-233, 250-251, 305, 314, 372, 401-410."""

    def _make_parser(self):
        from src.orchestrator.planning import PlanningArtifactParser

        return PlanningArtifactParser()

    def test_parse_json_repair_raises_value_error(self):
        from src.orchestrator.planning import PlanningArtifactParser

        parser = PlanningArtifactParser()
        with patch("src.orchestrator.planning.json_repair_loads", side_effect=RuntimeError("boom")):
            with pytest.raises(ValueError, match="response is not valid JSON.*boom"):
                parser.parse("some content", "gen1")

    def test_merge_artifacts_skips_non_dict_criteria(self):
        from src.orchestrator.planning import GeneratedArtifact, PlanningArtifactParser

        parser = PlanningArtifactParser()
        artifacts = [
            GeneratedArtifact(
                scoring_criteria=["not_a_dict", {"criteria_name": "valid", "description": "ok"}],
                generated_prompts=[],
                source="gen1",
            )
        ]
        criteria, prompts = parser.merge_artifacts(artifacts)
        assert len(criteria) == 1
        assert criteria[0]["criteria_name"] == "valid"

    def test_merge_artifacts_skips_non_dict_prompts(self):
        from src.orchestrator.planning import GeneratedArtifact, PlanningArtifactParser

        parser = PlanningArtifactParser()
        artifacts = [
            GeneratedArtifact(
                scoring_criteria=[],
                generated_prompts=["not_a_dict", {"prompt_name": "valid", "prompt": "ok"}],
                source="gen1",
            )
        ]
        criteria, prompts = parser.merge_artifacts(artifacts)
        assert len(prompts) == 1
        assert prompts[0]["prompt_name"] == "valid"

    def test_validate_criteria_empty_list_returns_empty_errors(self):
        parser = self._make_parser()
        errors = parser.validate_criteria([], set())
        assert errors == []

    def test_validate_criteria_non_numeric_weight(self):
        parser = self._make_parser()
        criteria = [{"criteria_name": "c1", "description": "d", "weight": "not_a_number"}]
        errors = parser.validate_criteria(criteria, {"exec1"})
        assert len(errors) == 1
        assert "weight is not a number" in errors[0]

    def test_validate_criteria_non_integer_scale(self):
        parser = self._make_parser()
        criteria = [
            {"criteria_name": "c1", "description": "d", "scale_min": "abc", "scale_max": "xyz"}
        ]
        errors = parser.validate_criteria(criteria, {"exec1"})
        assert len(errors) == 1
        assert "scale_min/scale_max must be integers" in errors[0]

    def test_validate_prompts_string_references(self):
        parser = self._make_parser()
        prompts = [{"prompt_name": "p1", "prompt": "test", "references": "unknown_doc"}]
        errors = parser.validate_prompts(
            prompts, existing_names=set(), doc_refs={"doc_a"}, batch_keys=set()
        )
        assert len(errors) == 1
        assert "references unknown document 'unknown_doc'" in errors[0]

    def test_validate_prompts_string_history(self):
        parser = self._make_parser()
        prompts = [{"prompt_name": "p1", "prompt": "test", "history": "unknown_prompt"}]
        errors = parser.validate_prompts(
            prompts, existing_names=set(), doc_refs=set(), batch_keys=set()
        )
        assert len(errors) == 1
        assert "history references unknown prompt 'unknown_prompt'" in errors[0]

    def test_assign_sequences_collision_avoidance(self):
        parser = self._make_parser()
        prompts = [
            {"prompt_name": "p1", "prompt": "a"},
            {"prompt_name": "p2", "prompt": "b"},
        ]
        existing = {1000, 1010}
        result = parser.assign_sequences(prompts, existing, base=1000, step=10)
        assert result[0]["sequence"] == 1001
        assert result[1]["sequence"] == 1011

    def test_build_scoring_criteria_unparseable_weight_falls_back(self):
        parser = self._make_parser()
        criteria = [{"criteria_name": "c1", "description": "d", "weight": "bad"}]
        result = parser.build_scoring_criteria(criteria)
        assert len(result) == 1
        assert result[0].weight == 1.0

    def test_build_scoring_criteria_unparseable_scale_min_falls_back(self):
        parser = self._make_parser()
        criteria = [{"criteria_name": "c1", "description": "d", "scale_min": "bad"}]
        result = parser.build_scoring_criteria(criteria)
        assert result[0].scale_min == 1

    def test_build_scoring_criteria_unparseable_scale_max_falls_back(self):
        parser = self._make_parser()
        criteria = [{"criteria_name": "c1", "description": "d", "scale_max": "bad"}]
        result = parser.build_scoring_criteria(criteria)
        assert result[0].scale_max == 10
