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

    def test_valid_max_tokens(self):
        result = OrchestratorValidator([], {"max_tokens": 4096}).validate()
        assert not result.has_errors

    def test_max_tokens_zero(self):
        result = OrchestratorValidator([], {"max_tokens": 0}).validate()
        codes = [e.code for e in result.errors]
        assert "INVALID_CONFIG" in codes

    def test_max_tokens_negative(self):
        result = OrchestratorValidator([], {"max_tokens": -100}).validate()
        codes = [e.code for e in result.errors]
        assert "INVALID_CONFIG" in codes

    def test_max_tokens_non_numeric(self):
        result = OrchestratorValidator([], {"max_tokens": "huge"}).validate()
        codes = [e.code for e in result.errors]
        assert "INVALID_CONFIG" in codes


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


class TestExtractBatchKeys:
    def test_extracts_unique_keys(self):
        from src.orchestrator.validation import OrchestratorValidator

        rows = [
            {"id": 1, "batch_name": "a", "region": "US", "topic": "AI"},
            {"id": 2, "batch_name": "b", "region": "EU", "tone": "formal"},
        ]
        keys = OrchestratorValidator.extract_batch_keys(rows)
        assert keys == ["region", "topic", "tone"]

    def test_empty_rows(self):
        from src.orchestrator.validation import OrchestratorValidator

        assert OrchestratorValidator.extract_batch_keys([]) == []

    def test_skips_id_and_batch_name(self):
        from src.orchestrator.validation import OrchestratorValidator

        rows = [{"id": 1, "batch_name": "x", "value": "y"}]
        keys = OrchestratorValidator.extract_batch_keys(rows)
        assert keys == ["value"]

    def test_skips_documents_column(self):
        from src.orchestrator.validation import OrchestratorValidator

        rows = [
            {"id": 1, "batch_name": "x", "_documents": '["resume_a"]', "region": "US"},
        ]
        keys = OrchestratorValidator.extract_batch_keys(rows)
        assert "_documents" not in keys
        assert "region" in keys


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


class TestValidatorIntegration:
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


class TestRowDocumentValidation:
    def test_valid_row_documents(self):
        prompts = [_make_prompt(1, "eval")]
        result = OrchestratorValidator(
            prompts,
            {},
            doc_ref_names=["jd", "resume_alice", "resume_bob"],
            row_doc_refs={0: ["resume_alice"], 1: ["resume_bob"]},
        ).validate()
        doc_errors = [e for e in result.errors if e.code == "UNKNOWN_ROW_DOCUMENT"]
        assert len(doc_errors) == 0

    def test_invalid_row_document_reference(self):
        prompts = [_make_prompt(1, "eval")]
        result = OrchestratorValidator(
            prompts,
            {},
            doc_ref_names=["jd", "resume_alice"],
            row_doc_refs={0: ["resume_alice"], 1: ["nonexistent_resume"]},
        ).validate()
        doc_errors = [e for e in result.errors if e.code == "UNKNOWN_ROW_DOCUMENT"]
        assert len(doc_errors) == 1
        assert "nonexistent_resume" in doc_errors[0].message
        assert "row 1" in doc_errors[0].message

    def test_row_documents_no_doc_sheet_warning(self):
        prompts = [_make_prompt(1, "eval")]
        result = OrchestratorValidator(
            prompts,
            {},
            doc_ref_names=[],
            row_doc_refs={0: ["resume_alice"]},
        ).validate()
        warnings = [e for e in result.errors if e.code == "ROW_DOCS_NO_SHEET"]
        assert len(warnings) == 1

    def test_row_documents_empty_refs_skipped(self):
        prompts = [_make_prompt(1, "eval")]
        result = OrchestratorValidator(
            prompts,
            {},
            doc_ref_names=["jd"],
            row_doc_refs={},
        ).validate()
        assert not result.has_errors

    def test_row_documents_multiple_invalid(self):
        prompts = [_make_prompt(1, "eval")]
        result = OrchestratorValidator(
            prompts,
            {},
            doc_ref_names=["jd"],
            row_doc_refs={0: ["bad_ref_1", "bad_ref_2"], 2: ["bad_ref_3"]},
        ).validate()
        doc_errors = [e for e in result.errors if e.code == "UNKNOWN_ROW_DOCUMENT"]
        assert len(doc_errors) == 3


class TestValidationValidatorAgentMode:
    def test_validation_prompt_without_agent_mode_warns(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "test",
                    "prompt": "test prompt",
                    "agent_mode": False,
                    "validation_prompt": "Must be a number",
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        warnings = [
            e
            for e in result.errors
            if e.severity == "warning" and e.code == "VALIDATION_WITHOUT_AGENT"
        ]
        assert len(warnings) == 1

    def test_max_validation_retries_out_of_range(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "test",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": ["calculate"],
                    "validation_prompt": "Must be a number",
                    "max_validation_retries": 20,
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_INVALID_MAX_VALIDATION_RETRIES"]
        assert len(errors) == 1

    def test_max_validation_retries_valid(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "test",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": ["calculate"],
                    "validation_prompt": "Must be a number",
                    "max_validation_retries": 3,
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_INVALID_MAX_VALIDATION_RETRIES"]
        assert len(errors) == 0


class TestFormatReportSingleSeverity:
    """Line 92: continue when no findings for a severity level."""

    def test_errors_only_skips_warning_section(self):
        result = ValidationResult()
        result.add_error("E1", "error one")
        report = result.format_report()
        assert "1 error:" in report
        assert "warning" not in report

    def test_warnings_only_skips_error_section(self):
        result = ValidationResult()
        result.add_warning("W1", "warning one")
        report = result.format_report()
        assert "1 warning:" in report
        assert not any(
            "error" in ln.lower() for ln in report.split("\n") if "warning" not in ln.lower()
        )

    def test_plural_label_for_multiple(self):
        result = ValidationResult()
        result.add_error("E1", "first")
        result.add_error("E2", "second")
        report = result.format_report()
        assert "2 errors:" in report


class TestValidateAbortConditionSyntax:
    """Line 311: invalid abort_condition syntax."""

    def test_invalid_abort_condition(self):
        prompts = [
            {
                "sequence": 1,
                "prompt_name": "a",
                "prompt": "test",
                "history": [],
                "abort_condition": "broken (( syntax",
            }
        ]
        result = OrchestratorValidator(prompts, {}).validate()
        errors = [e for e in result.errors if e.code == "INVALID_ABORT_CONDITION"]
        assert len(errors) == 1
        assert "abort_condition syntax error" in errors[0].message

    def test_valid_abort_condition(self):
        prompts = [
            {
                "sequence": 1,
                "prompt_name": "a",
                "prompt": "test",
                "history": [],
                "abort_condition": '{{a.status}} == "failed"',
            }
        ]
        result = OrchestratorValidator(prompts, {}).validate()
        errors = [e for e in result.errors if e.code == "INVALID_ABORT_CONDITION"]
        assert len(errors) == 0


class TestValidateConfigNonNumeric:
    """Lines 341-342: temperature non-numeric; Lines 354-355: max_retries non-numeric."""

    def test_temperature_non_numeric(self):
        result = OrchestratorValidator([], {"temperature": "hot"}).validate()
        errors = [
            e
            for e in result.errors
            if e.code == "INVALID_CONFIG" and "not a valid number" in e.message
        ]
        assert len(errors) == 1

    def test_max_retries_non_numeric(self):
        result = OrchestratorValidator([], {"max_retries": "many"}).validate()
        errors = [
            e
            for e in result.errors
            if e.code == "INVALID_CONFIG" and "not a valid integer" in e.message
        ]
        assert len(errors) == 1


class TestValidateBatchVariableEdgeCases:
    """Lines 408, 411: batch variable edge cases."""

    def test_empty_prompt_text_skipped(self):
        prompts = [{"sequence": 1, "prompt_name": "a", "prompt": "", "history": []}]
        result = OrchestratorValidator(prompts, {}, batch_data_keys=["region"]).validate()
        warnings = [e for e in result.errors if e.code == "UNKNOWN_BATCH_VARIABLE"]
        assert len(warnings) == 0

    def test_batch_var_matching_prompt_name_not_flagged(self):
        prompts = [
            _make_prompt(1, "region"),
            _make_prompt(2, "b", prompt="Process {{region}} data"),
        ]
        result = OrchestratorValidator(prompts, {}, batch_data_keys=["other_key"]).validate()
        warnings = [e for e in result.errors if e.code == "UNKNOWN_BATCH_VARIABLE"]
        assert len(warnings) == 0


class TestValidateScoringEdgeCases:
    """Lines 441-442, 467-468, 488-489: scoring edge cases."""

    def test_missing_criteria_name(self):
        result = OrchestratorValidator(
            [],
            {},
            scoring_criteria=[{"source_prompt": "a", "weight": 1.0}],
        ).validate()
        errors = [e for e in result.errors if e.code == "MISSING_CRITERIA_NAME"]
        assert len(errors) == 1

    def test_weight_not_a_number(self):
        result = OrchestratorValidator(
            [],
            {},
            scoring_criteria=[{"criteria_name": "quality", "weight": "heavy"}],
        ).validate()
        errors = [e for e in result.errors if e.code == "INVALID_SCORING_WEIGHT"]
        assert len(errors) == 1
        assert "not a number" in errors[0].message
        assert "heavy" in errors[0].message

    def test_scale_non_integer_silently_skipped(self):
        result = OrchestratorValidator(
            [],
            {},
            scoring_criteria=[
                {"criteria_name": "quality", "scale_min": "low", "scale_max": "high"},
            ],
        ).validate()
        errors = [e for e in result.errors if e.code == "INCONSISTENT_SCORING_SCALE"]
        assert len(errors) == 0


class TestValidateSynthesisEdgeCases:
    """Lines 529, 540: synthesis string normalization."""

    def test_source_prompts_as_string(self):
        prompts = [_make_prompt(1, "a")]
        result = OrchestratorValidator(
            prompts,
            {},
            synthesis_prompts=[{"prompt_name": "synth1", "sequence": 1, "source_prompts": "a"}],
        ).validate()
        errors = [e for e in result.errors if e.code == "INVALID_SYNTHESIS_SOURCE_PROMPT"]
        assert len(errors) == 0

    def test_history_as_string(self):
        result = OrchestratorValidator(
            [],
            {},
            synthesis_prompts=[
                {"prompt_name": "synth1", "sequence": 1},
                {"prompt_name": "synth2", "sequence": 2, "history": "synth1"},
            ],
        ).validate()
        errors = [e for e in result.errors if e.code == "INVALID_SYNTHESIS_HISTORY"]
        assert len(errors) == 0


class TestValidateAgentModeEdgeCases:
    """Lines 594-600, 603-609, 614, 626-633, 642, 660-661."""

    def test_agent_no_tools_warning(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "agent1",
                    "prompt": "test",
                    "agent_mode": True,
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        warnings = [e for e in result.errors if e.code == "AGENT_NO_TOOLS"]
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"

    def test_agent_tools_not_list(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "agent1",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": "calculate",
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_INVALID_TOOLS"]
        assert len(errors) == 1
        assert "str" in errors[0].message

    def test_agent_unknown_tools(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "agent1",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": ["known", "mystery"],
                },
            ],
            config={},
            tool_names=["known"],
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_UNKNOWN_TOOLS"]
        assert len(errors) == 1
        assert "mystery" in errors[0].message

    def test_agent_max_tool_rounds_out_of_range(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "agent1",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": ["t1"],
                    "max_tool_rounds": 100,
                },
            ],
            config={},
            tool_names=["t1"],
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_INVALID_MAX_ROUNDS"]
        assert len(errors) == 1
        assert "100" in errors[0].message

    def test_agent_max_tool_rounds_non_integer(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "agent1",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": ["t1"],
                    "max_tool_rounds": "many",
                },
            ],
            config={},
            tool_names=["t1"],
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_INVALID_MAX_ROUNDS"]
        assert len(errors) == 1
        assert "many" in errors[0].message

    def test_agent_validation_prompt_not_string(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "agent1",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": ["t1"],
                    "validation_prompt": 123,
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_INVALID_VALIDATION_PROMPT"]
        assert len(errors) == 1
        assert "int" in errors[0].message

    def test_agent_max_validation_retries_non_integer(self):
        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "agent1",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": ["t1"],
                    "validation_prompt": "check",
                    "max_validation_retries": "lots",
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_INVALID_MAX_VALIDATION_RETRIES"]
        assert len(errors) == 1
        assert "lots" in errors[0].message


class TestValidateManifestMetadataEdgeCases:
    """Lines 682-683, 700, 707, 714: manifest metadata edge cases."""

    def test_prompt_count_non_integer(self):
        prompts = [_make_prompt(1, "a")]
        result = OrchestratorValidator(
            prompts,
            {},
            manifest_meta={"prompt_count": "three"},
        ).validate()
        warnings = [e for e in result.errors if e.code == "PROMPT_COUNT_MISMATCH"]
        assert len(warnings) == 1
        assert "three" in warnings[0].message
        assert warnings[0].severity == "warning"

    def test_has_data_no_batch_keys(self):
        prompts = [_make_prompt(1, "a")]
        result = OrchestratorValidator(
            prompts,
            {},
            manifest_meta={"has_data": True},
        ).validate()
        warnings = [e for e in result.errors if e.code == "HAS_DATA_NO_BATCH"]
        assert len(warnings) == 1

    def test_has_clients_no_client_names(self):
        prompts = [_make_prompt(1, "a")]
        result = OrchestratorValidator(
            prompts,
            {},
            manifest_meta={"has_clients": True},
        ).validate()
        warnings = [e for e in result.errors if e.code == "HAS_CLIENTS_NO_REGISTRY"]
        assert len(warnings) == 1

    def test_has_documents_no_doc_refs(self):
        prompts = [_make_prompt(1, "a")]
        result = OrchestratorValidator(
            prompts,
            {},
            manifest_meta={"has_documents": True},
        ).validate()
        warnings = [e for e in result.errors if e.code == "HAS_DOCS_NO_REGISTRY"]
        assert len(warnings) == 1
