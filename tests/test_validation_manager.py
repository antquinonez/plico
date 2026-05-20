from unittest.mock import MagicMock, patch

from src.orchestrator.validation_manager import ValidationManager


def _make_minimal_orchestrator(**overrides):
    orch = MagicMock()
    orch.config = {}
    orch.prompts = []
    orch.client_registry = None
    orch.is_batch_mode = False
    orch.batch_data = None
    orch.document_registry = None
    orch.tool_registry = None
    orch.has_scoring = False
    orch.scoring_rubric = None
    orch.has_synthesis = False
    orch.synthesis_prompts = []
    orch.evaluation_strategy = "balanced"
    orch.planning_prompts = []
    orch._manifest_meta = None
    for k, v in overrides.items():
        setattr(orch, k, v)
    return orch


class TestBuildParams:
    def test_batch_data_with_documents(self):
        mock_registry = MagicMock()
        mock_registry.get_reference_names.return_value = ["doc1"]
        mock_tool_registry = MagicMock()
        mock_tool_registry.get_registered_names.return_value = ["tool1"]

        orch = _make_minimal_orchestrator(
            is_batch_mode=True,
            batch_data=[
                {"_documents": "resume.pdf", "name": "candidate1"},
                {"name": "candidate2"},
            ],
            client_registry=MagicMock(get_registered_names=MagicMock(return_value=["client1"])),
            document_registry=mock_registry,
            tool_registry=mock_tool_registry,
        )

        vm = ValidationManager()
        params = vm._build_params(orch)

        assert params["row_doc_refs"] == {0: ["resume.pdf"]}
        assert 1 not in params["row_doc_refs"]

    def test_batch_data_documents_empty_string(self):
        orch = _make_minimal_orchestrator(
            is_batch_mode=True,
            batch_data=[{"_documents": "", "name": "c1"}],
        )

        vm = ValidationManager()
        params = vm._build_params(orch)

        assert params["row_doc_refs"] == {}

    def test_config_exception_falls_back_to_empty_types(self):
        orch = _make_minimal_orchestrator()

        vm = ValidationManager()
        with patch("src.orchestrator.validation_manager.get_config", side_effect=Exception("boom")):
            params = vm._build_params(orch)

        assert params["available_client_types"] == []

    def test_eval_config_exception_falls_back(self):
        orch = _make_minimal_orchestrator(
            has_scoring=True,
            scoring_rubric=MagicMock(criteria=[]),
        )

        vm = ValidationManager()
        with patch("src.orchestrator.validation_manager.get_config", side_effect=Exception("boom")):
            params = vm._build_params(orch)

        assert params["scoring_criteria"] == []
        assert params["available_strategies"] == []

    def test_non_batch_mode_skips_batch_keys(self):
        orch = _make_minimal_orchestrator(is_batch_mode=False, batch_data=None)
        vm = ValidationManager()
        params = vm._build_params(orch)
        assert params["batch_data_keys"] == []

    def test_scoring_criteria_serialized(self):
        from dataclasses import dataclass

        @dataclass
        class FakeCriteria:
            criteria_name: str
            source_prompt: str = "p1"
            scale_max: int = 10
            weight: float = 1.0
            normalized: bool = True

        rubric = MagicMock()
        rubric.criteria = [FakeCriteria("skills")]
        orch = _make_minimal_orchestrator(has_scoring=True, scoring_rubric=rubric)

        vm = ValidationManager()
        params = vm._build_params(orch)

        assert len(params["scoring_criteria"]) == 1
        assert params["scoring_criteria"][0]["criteria_name"] == "skills"


class TestValidatePrePlanning:
    def test_validate_pre_planning_passes(self):
        orch = _make_minimal_orchestrator(
            prompts=[{"sequence": 10, "prompt": "test", "prompt_name": "p1", "client": "default"}],
            planning_prompts=[],
        )
        vm = ValidationManager()
        vm.validate_pre_planning(orch)


class TestValidatePostPlanning:
    def test_validate_post_planning_passes(self):
        orch = _make_minimal_orchestrator(
            prompts=[{"sequence": 10, "prompt": "test", "prompt_name": "p1", "client": "default"}],
        )
        vm = ValidationManager()
        vm.validate_post_planning(orch)
