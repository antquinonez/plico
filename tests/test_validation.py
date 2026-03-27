from __future__ import annotations

from src.orchestrator.validation import (
    OrchestratorValidator,
    ValidationResult,
)


def _make_prompt(
    sequence: int = 1,
    prompt_name: str = "step1",
    prompt: str = "Do something",
    history: list[str] | None = None,
    client: str | None = None,
    condition: str | None = None,
    references: list[str] | None = None,
) -> dict:
    return {
        "sequence": sequence,
        "prompt_name": prompt_name,
        "prompt": prompt,
        "history": history or [],
        "client": client,
        "condition": condition,
        "references": references or [],
        "semantic_query": None,
        "semantic_filter": None,
        "query_expansion": None,
        "rerank": None,
    }


class TestValidationResult:
    def test_has_errors_false_when_empty(self):
        result = ValidationResult()
        assert not result.has_errors
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_has_errors_true_with_error(self):
        result = ValidationResult()
        result.add_error("TEST", "something failed")
        assert result.has_errors
        assert result.error_count == 1

    def test_has_errors_false_with_only_warning(self):
        result = ValidationResult()
        result.add_warning("TEST", "something suspicious")
        assert not result.has_errors
        assert result.warning_count == 1

    def test_raise_on_error_noop_when_clean(self):
        result = ValidationResult()
        result.raise_on_error()

    def test_raise_on_error_raises_with_errors(self):
        result = ValidationResult()
        result.add_error("CODE", "message")
        raised = False
        try:
            result.raise_on_error()
        except ValueError:
            raised = True
        assert raised

    def test_format_report_all_passed(self):
        result = ValidationResult()
        report = result.format_report()
        assert "All checks passed" in report

    def test_format_report_with_errors_and_warnings(self):
        result = ValidationResult()
        result.add_error("E1", "error one")
        result.add_warning("W1", "warning one")
        report = result.format_report()
        assert "1 error" in report
        assert "1 warning" in report


class TestValidatePromptFields:
    def test_valid_prompts(self):
        prompts = [_make_prompt(1, "a"), _make_prompt(2, "b")]
        result = OrchestratorValidator(prompts, {}).validate()
        assert not result.has_errors

    def test_missing_prompt_name(self):
        prompts = [{"sequence": 1, "prompt_name": None, "prompt": "hi", "history": []}]
        result = OrchestratorValidator(prompts, {}).validate()
        codes = [e.code for e in result.errors]
        assert "MISSING_FIELD" in codes

    def test_missing_prompt(self):
        prompts = [{"sequence": 1, "prompt_name": "a", "prompt": None, "history": []}]
        result = OrchestratorValidator(prompts, {}).validate()
        codes = [e.code for e in result.errors]
        assert "MISSING_FIELD" in codes

    def test_missing_sequence(self):
        prompts = [{"sequence": None, "prompt_name": "a", "prompt": "hi", "history": []}]
        result = OrchestratorValidator(prompts, {}).validate()
        codes = [e.code for e in result.errors]
        assert "MISSING_FIELD" in codes


class TestValidateUniquePromptNames:
    def test_unique_names(self):
        prompts = [_make_prompt(1, "a"), _make_prompt(2, "b")]
        result = OrchestratorValidator(prompts, {}).validate()
        dupes = [e for e in result.errors if e.code == "DUPLICATE_PROMPT_NAME"]
        assert len(dupes) == 0

    def test_duplicate_names(self):
        prompts = [_make_prompt(1, "a"), _make_prompt(2, "a")]
        result = OrchestratorValidator(prompts, {}).validate()
        dupes = [e for e in result.errors if e.code == "DUPLICATE_PROMPT_NAME"]
        assert len(dupes) == 1
        assert dupes[0].prompt_name == "a"


class TestValidateSequences:
    def test_valid_sequences(self):
        prompts = [_make_prompt(1, "a"), _make_prompt(2, "b")]
        result = OrchestratorValidator(prompts, {}).validate()
        invalids = [e for e in result.errors if e.code == "INVALID_SEQUENCE"]
        assert len(invalids) == 0

    def test_zero_sequence(self):
        prompts = [_make_prompt(0, "a")]
        result = OrchestratorValidator(prompts, {}).validate()
        codes = [e.code for e in result.errors]
        assert "INVALID_SEQUENCE" in codes


class TestValidateHistoryDependencies:
    def test_valid_history(self):
        prompts = [_make_prompt(1, "a"), _make_prompt(2, "b", history=["a"])]
        result = OrchestratorValidator(prompts, {}).validate()
        deps = [e for e in result.errors if "DEPENDENCY" in e.code]
        assert len(deps) == 0

    def test_unknown_dependency(self):
        prompts = [_make_prompt(1, "a", history=["nonexistent"])]
        result = OrchestratorValidator(prompts, {}).validate()
        codes = [e.code for e in result.errors]
        assert "UNKNOWN_DEPENDENCY" in codes

    def test_forward_dependency(self):
        prompts = [_make_prompt(1, "a", history=["b"]), _make_prompt(2, "b")]
        result = OrchestratorValidator(prompts, {}).validate()
        codes = [e.code for e in result.errors]
        assert "FORWARD_DEPENDENCY" in codes


class TestValidateTemplateReferences:
    def test_valid_template_ref(self):
        prompts = [
            _make_prompt(1, "a"),
            _make_prompt(2, "b", prompt="{{a.response}} do this", history=["a"]),
        ]
        result = OrchestratorValidator(prompts, {}).validate()
        refs = [e for e in result.errors if "TEMPLATE_REF" in e.code or "UNDECLARED" in e.code]
        assert len(refs) == 0

    def test_unknown_template_ref(self):
        prompts = [_make_prompt(1, "a", prompt="{{nonexistent.response}} do this")]
        result = OrchestratorValidator(prompts, {}).validate()
        codes = [e.code for e in result.errors]
        assert "UNKNOWN_TEMPLATE_REF" in codes

    def test_undeclared_history_ref_warning(self):
        prompts = [_make_prompt(1, "a"), _make_prompt(2, "b", prompt="{{a.response}} do this")]
        result = OrchestratorValidator(prompts, {}).validate()
        warnings = [e for e in result.errors if e.code == "UNDECLARED_HISTORY_REF"]
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"


class TestValidateConditionSyntax:
    def test_valid_condition(self):
        prompts = [
            _make_prompt(1, "a"),
            _make_prompt(2, "b", condition='{{a.status}} == "success"'),
        ]
        result = OrchestratorValidator(prompts, {}).validate()
        conds = [e for e in result.errors if e.code == "INVALID_CONDITION"]
        assert len(conds) == 0

    def test_invalid_condition_syntax(self):
        prompts = [_make_prompt(1, "a", condition="broken (( syntax")]
        result = OrchestratorValidator(prompts, {}).validate()
        codes = [e.code for e in result.errors]
        assert "INVALID_CONDITION" in codes

    def test_null_condition_skipped(self):
        prompts = [_make_prompt(1, "a", condition=None)]
        result = OrchestratorValidator(prompts, {}).validate()
        conds = [e for e in result.errors if e.code == "INVALID_CONDITION"]
        assert len(conds) == 0


class TestValidateClientAssignments:
    def test_valid_client(self):
        prompts = [_make_prompt(1, "a", client="writer")]
        result = OrchestratorValidator(prompts, {}, client_names=["writer"]).validate()
        assert not result.has_errors

    def test_unknown_client(self):
        prompts = [_make_prompt(1, "a", client="nonexistent")]
        result = OrchestratorValidator(prompts, {}, client_names=["writer"]).validate()
        codes = [e.code for e in result.errors]
        assert "UNKNOWN_CLIENT" in codes

    def test_null_client_skipped(self):
        prompts = [_make_prompt(1, "a", client=None)]
        result = OrchestratorValidator(prompts, {}, client_names=["writer"]).validate()
        assert not result.has_errors


class TestValidateConfigValues:
    def test_valid_config(self):
        result = OrchestratorValidator([], {"temperature": 0.7, "max_retries": 3}).validate()
        assert not result.has_errors

    def test_temperature_out_of_range(self):
        result = OrchestratorValidator([], {"temperature": 5.0}).validate()
        codes = [e.code for e in result.errors]
        assert "INVALID_CONFIG" in codes

    def test_max_retries_out_of_range(self):
        result = OrchestratorValidator([], {"max_retries": 20}).validate()
        codes = [e.code for e in result.errors]
        assert "INVALID_CONFIG" in codes

    def test_unknown_client_type(self):
        result = OrchestratorValidator(
            [], {"client_type": "fake-client"}, available_client_types=["mistral-small"]
        ).validate()
        codes = [e.code for e in result.errors]
        assert "UNKNOWN_CLIENT_TYPE" in codes


class TestValidateDocumentReferences:
    def test_valid_reference(self):
        prompts = [_make_prompt(1, "a", references=["spec"])]
        result = OrchestratorValidator(prompts, {}, doc_ref_names=["spec"]).validate()
        assert not result.has_errors

    def test_unknown_reference(self):
        prompts = [_make_prompt(1, "a", references=["nonexistent"])]
        result = OrchestratorValidator(prompts, {}, doc_ref_names=["spec"]).validate()
        codes = [e.code for e in result.errors]
        assert "UNKNOWN_DOCUMENT_REF" in codes


class TestValidateBatchVariables:
    def test_valid_batch_var(self):
        prompts = [_make_prompt(1, "a", prompt="Process {{region}} data")]
        result = OrchestratorValidator(prompts, {}, batch_data_keys=["region"]).validate()
        warnings = [e for e in result.errors if e.code == "UNKNOWN_BATCH_VARIABLE"]
        assert len(warnings) == 0

    def test_unknown_batch_var(self):
        prompts = [_make_prompt(1, "a", prompt="Process {{unknown_var}} data")]
        result = OrchestratorValidator(prompts, {}, batch_data_keys=["region"]).validate()
        warnings = [e for e in result.errors if e.code == "UNKNOWN_BATCH_VARIABLE"]
        assert len(warnings) == 1

    def test_prompt_name_not_treated_as_batch_var(self):
        prompts = [
            _make_prompt(1, "a"),
            _make_prompt(2, "b", prompt="{{a.response}} result"),
        ]
        result = OrchestratorValidator(prompts, {}, batch_data_keys=["region"]).validate()
        warnings = [e for e in result.errors if e.code == "UNKNOWN_BATCH_VARIABLE"]
        assert len(warnings) == 0


class TestValidateManifestMetadata:
    def test_matching_prompt_count(self):
        prompts = [_make_prompt(1, "a"), _make_prompt(2, "b")]
        result = OrchestratorValidator(prompts, {}, manifest_meta={"prompt_count": 2}).validate()
        warnings = [e for e in result.errors if e.code == "PROMPT_COUNT_MISMATCH"]
        assert len(warnings) == 0

    def test_mismatched_prompt_count(self):
        prompts = [_make_prompt(1, "a")]
        result = OrchestratorValidator(prompts, {}, manifest_meta={"prompt_count": 5}).validate()
        warnings = [e for e in result.errors if e.code == "PROMPT_COUNT_MISMATCH"]
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"

    def test_valid_output_prompts(self):
        prompts = [_make_prompt(1, "a"), _make_prompt(2, "b")]
        result = OrchestratorValidator(
            prompts, {}, manifest_meta={"output_prompts": ["a", "b"]}
        ).validate()
        assert not result.has_errors

    def test_unknown_output_prompts(self):
        prompts = [_make_prompt(1, "a")]
        result = OrchestratorValidator(
            prompts, {}, manifest_meta={"output_prompts": ["a", "nonexistent"]}
        ).validate()
        codes = [e.code for e in result.errors]
        assert "UNKNOWN_OUTPUT_PROMPT" in codes


class TestOrchestratorValidatorIntegration:
    def test_clean_manifest_passes(self):
        prompts = [
            _make_prompt(1, "research", client="researcher"),
            _make_prompt(
                2,
                "draft",
                prompt="Based on {{research.response}}, write this",
                history=["research"],
                client="writer",
            ),
            _make_prompt(
                3,
                "evaluate",
                prompt="Score: {{draft.response}}",
                history=["draft"],
                client="analyst",
            ),
        ]
        result = OrchestratorValidator(
            prompts,
            {"temperature": 0.7},
            client_names=["researcher", "writer", "analyst"],
            available_client_types=["litellm-mistral-small"],
        ).validate()
        assert not result.has_errors

    def test_multi_error_manifest(self):
        prompts = [
            _make_prompt(1, "a", client="nonexistent"),
            _make_prompt(1, "a"),
            _make_prompt(
                3, "c", prompt="{{missing.response}}", history=["future"], condition="bad ((("
            ),
            _make_prompt(5, None, None),
        ]
        result = OrchestratorValidator(
            prompts,
            {"temperature": 5.0, "max_retries": 20},
            client_names=["writer"],
        ).validate()
        assert result.error_count >= 6

    def test_no_manifest_meta_skips_manifest_checks(self):
        prompts = [_make_prompt(1, "a")]
        result = OrchestratorValidator(prompts, {}).validate()
        assert not result.has_errors
