# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for src.orchestrator.templating -- variable resolution and batch templating.

Migrated from:
- test_orchestrator_base.py::TestRowDocumentBinding
- test_excel_orchestrator.py::TestExcelOrchestratorBatchVariableResolution
- test_manifest_comprehensive.py::TestManifestOrchestratorVariables

These are pure function tests -- no orchestrator instance needed.
"""

from src.orchestrator.templating import (
    resolve_batch_name,
    resolve_prompt_variables,
    resolve_variables,
)


class TestResolveVariables:
    """Tests for resolve_variables."""

    def test_basic_replacement(self):
        result = resolve_variables(
            "Analyze {{region}} region, product {{product}}.",
            {"region": "north", "product": "widget_a", "price": 10},
        )
        assert result == "Analyze north region, product widget_a."

    def test_multiple_occurrences(self):
        result = resolve_variables(
            "{{region}} has price {{price}} and tax on {{price}}.",
            {"region": "east", "price": 20},
        )
        assert result == "east has price 20 and tax on 20."

    def test_missing_keeps_placeholder(self):
        result = resolve_variables(
            "Region: {{region}}, Missing: {{unknown}}",
            {"region": "north"},
        )
        assert result == "Region: north, Missing: {{unknown}}"

    def test_empty_text(self):
        assert resolve_variables("", {"region": "North"}) == ""

    def test_none_value_keeps_placeholder(self):
        result = resolve_variables("Value: {{value}}", {"value": None})
        assert result == "Value: {{value}}"

    def test_none_text_returns_none(self):
        assert resolve_variables(None, {}) is None

    def test_integer_value_converted(self):
        result = resolve_variables("Price: {{price}}", {"price": 10})
        assert result == "Price: 10"


class TestResolvePromptVariables:
    """Tests for resolve_prompt_variables."""

    def test_basic_resolution(self):
        prompt = {
            "sequence": 1,
            "prompt_name": "test",
            "prompt": "Price is {{price}}, quantity is {{quantity}}.",
        }
        result = resolve_prompt_variables(prompt, {"price": 10, "quantity": 100})

        assert result["prompt"] == "Price is 10, quantity is 100."
        assert result["sequence"] == 1

    def test_prompt_name_resolved(self):
        prompt = {
            "prompt": "Hello {{name}}",
            "prompt_name": "greeting_{{region}}",
            "sequence": 1,
        }
        result = resolve_prompt_variables(prompt, {"name": "World", "region": "North"})

        assert result["prompt"] == "Hello World"
        assert result["prompt_name"] == "greeting_North"
        assert result["sequence"] == 1

    def test_with_documents(self):
        """Test that _documents from data row are merged into references."""
        prompt = {
            "sequence": 1,
            "prompt_name": "evaluate",
            "prompt": "Evaluate {{candidate}}",
            "references": ["job_description"],
        }
        data_row = {"candidate": "Alice", "_documents": '["resume_alice"]'}

        resolved = resolve_prompt_variables(prompt, data_row)

        assert resolved["prompt"] == "Evaluate Alice"
        assert resolved["references"] == ["job_description", "resume_alice"]

    def test_additive_merge(self):
        """Test additive merge: static references preserved, _documents appended."""
        prompt = {
            "sequence": 1,
            "prompt_name": "eval",
            "prompt": "Go",
            "references": ["shared_doc", "rubric"],
        }
        data_row = {"_documents": '["resume_bob"]'}

        resolved = resolve_prompt_variables(prompt, data_row)

        assert resolved["references"] == ["shared_doc", "rubric", "resume_bob"]

    def test_empty_static_refs(self):
        """Test merge when prompt has no static references."""
        prompt = {
            "sequence": 1,
            "prompt_name": "eval",
            "prompt": "Go",
            "references": None,
        }
        data_row = {"_documents": '["resume_alice", "cover_letter_alice"]'}

        resolved = resolve_prompt_variables(prompt, data_row)

        assert resolved["references"] == ["resume_alice", "cover_letter_alice"]

    def test_no_documents_column(self):
        """Test that prompts without _documents are unchanged."""
        prompt = {
            "sequence": 1,
            "prompt_name": "eval",
            "prompt": "Go",
            "references": ["job_description"],
        }
        data_row = {"candidate": "Bob"}

        resolved = resolve_prompt_variables(prompt, data_row)

        assert resolved["references"] == ["job_description"]

    def test_documents_empty_string(self):
        """Test that empty _documents string is ignored."""
        prompt = {
            "sequence": 1,
            "prompt_name": "eval",
            "prompt": "Go",
            "references": ["jd"],
        }
        data_row = {"_documents": ""}

        resolved = resolve_prompt_variables(prompt, data_row)

        assert resolved["references"] == ["jd"]

    def test_does_not_mutate_original(self):
        """Test that resolve_prompt_variables does not mutate the original prompt dict."""
        prompt = {
            "sequence": 1,
            "prompt_name": "eval",
            "prompt": "Go",
            "references": ["jd"],
        }
        original_refs = list(prompt["references"])
        data_row = {"_documents": '["resume_alice"]'}

        resolved = resolve_prompt_variables(prompt, data_row)

        assert prompt["references"] == original_refs
        assert resolved["references"] == ["jd", "resume_alice"]

    def test_documents_json_list(self):
        """Test _documents as a pre-parsed list (from data loading)."""
        prompt = {
            "sequence": 1,
            "prompt_name": "eval",
            "prompt": "Go",
            "references": ["jd"],
        }
        data_row = {"_documents": ["resume_alice", "cover_letter"]}

        resolved = resolve_prompt_variables(prompt, data_row)

        assert resolved["references"] == ["jd", "resume_alice", "cover_letter"]


class TestResolveBatchName:
    """Tests for resolve_batch_name."""

    def test_custom_template(self):
        data_row = {
            "region": "north",
            "product": "widget_a",
            "batch_name": "{{region}}_{{product}}",
        }
        assert resolve_batch_name(data_row, 1) == "north_widget_a"

    def test_default_name(self):
        data_row = {"region": "north", "product": "widget_a"}
        assert resolve_batch_name(data_row, 5) == "batch_5"

    def test_sanitizes_special_chars(self):
        data_row = {"batch_name": "test @#$ batch!!!", "region": "north"}
        result = resolve_batch_name(data_row, 1)
        assert "@" not in result
        assert "#" not in result
        assert "!" not in result

    def test_truncates_long_names(self):
        data_row = {"batch_name": "a" * 100}
        result = resolve_batch_name(data_row, 1)
        assert len(result) == 50

    def test_empty_batch_name_falls_through(self):
        data_row = {"batch_name": ""}
        result = resolve_batch_name(data_row, 3)
        assert result == "batch_3"

    def test_hyphens_and_underscores_preserved(self):
        data_row = {"batch_name": "my-test_batch"}
        result = resolve_batch_name(data_row, 1)
        assert result == "my-test_batch"
