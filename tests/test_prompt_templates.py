# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for src.prompt_templates module."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestResolveTemplatePath:
    """Tests for resolve_template_path."""

    def test_resolve_explicit_file_path(self, tmp_path):
        from src.prompt_templates import resolve_template_path

        template = tmp_path / "my_template.yaml"
        template.write_text("name: test\n")
        result = resolve_template_path(str(template))
        assert result is not None
        assert result == template.resolve()

    def test_resolve_explicit_file_path_without_extension(self, tmp_path):
        from src.prompt_templates import resolve_template_path

        template = tmp_path / "my_template.yaml"
        template.write_text("name: test\n")
        result = resolve_template_path(str(tmp_path / "my_template"))
        assert result is not None
        assert result == template.resolve()

    def test_resolve_nonexistent_path_returns_none(self):
        from src.prompt_templates import resolve_template_path

        result = resolve_template_path("/nonexistent/path/to/template.yaml")
        assert result is None

    def test_resolve_named_template_from_config_prompts(self):
        from src.prompt_templates import resolve_template_path

        result = resolve_template_path("screening_planning")
        assert result is not None
        assert result.name == "screening_planning.yaml"

    def test_resolve_named_template_nonexistent_returns_none(self):
        from src.prompt_templates import resolve_template_path

        result = resolve_template_path("nonexistent_template_xyz")
        assert result is None


class TestLoadPromptTemplate:
    """Tests for load_prompt_template."""

    def test_load_from_explicit_path(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test_template",
            "prompts": [
                {
                    "sequence": 10,
                    "prompt_name": "test_prompt",
                    "prompt": "Hello {{candidate_name}}",
                    "references": '["job_description"]',
                },
            ],
        }
        template_file = tmp_path / "test.yaml"
        with open(template_file, "w") as f:
            yaml.dump(template_data, f)

        result = load_prompt_template(str(template_file))
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "test_prompt"
        assert result[0].sequence == 10

    def test_load_named_template(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_static")
        assert result is not None
        assert len(result) == 8
        assert result[0].name == "extract_profile"

    def test_load_planning_template(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_planning")
        assert result is not None
        assert len(result) == 5
        names = [p.name for p in result]
        assert "analyze_jd" in names
        assert "refine_criteria" in names

    def test_load_nonexistent_returns_none(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("nonexistent_template")
        assert result is None

    def test_load_empty_prompts_returns_none(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_file = tmp_path / "empty.yaml"
        with open(template_file, "w") as f:
            yaml.dump({"name": "empty", "prompts": []}, f)

        result = load_prompt_template(str(template_file))
        assert result is None

    def test_list_references_converted_to_json_string(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test",
            "prompts": [
                {
                    "sequence": 1,
                    "prompt_name": "p1",
                    "prompt": "Test",
                    "references": ["doc1", "doc2"],
                },
            ],
        }
        template_file = tmp_path / "test.yaml"
        with open(template_file, "w") as f:
            yaml.dump(template_data, f)

        result = load_prompt_template(str(template_file))
        assert result is not None
        assert result[0].references == '["doc1", "doc2"]'

    def test_list_history_converted_to_json_string(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test",
            "prompts": [
                {
                    "sequence": 1,
                    "prompt_name": "p1",
                    "prompt": "Test",
                    "history": ["p0"],
                },
            ],
        }
        template_file = tmp_path / "test.yaml"
        with open(template_file, "w") as f:
            yaml.dump(template_data, f)

        result = load_prompt_template(str(template_file))
        assert result is not None
        assert result[0].history == '["p0"]'

    def test_phase_and_generator_fields(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test",
            "prompts": [
                {
                    "sequence": 1,
                    "prompt_name": "gen",
                    "prompt": "Generate",
                    "phase": "planning",
                    "generator": "true",
                },
            ],
        }
        template_file = tmp_path / "test.yaml"
        with open(template_file, "w") as f:
            yaml.dump(template_data, f)

        result = load_prompt_template(str(template_file))
        assert result is not None
        assert result[0].phase == "planning"
        assert result[0].generator == "true"


class TestLoadSynthesisTemplate:
    """Tests for load_synthesis_template."""

    def test_load_synthesis_template(self):
        from src.prompt_templates import load_synthesis_template

        result = load_synthesis_template("screening_synthesis", top_n=5)
        assert result is not None
        assert len(result) == 3
        assert result[0]["prompt_name"] == "rank_summary"
        assert result[0]["source_scope"] == "top:5"

    def test_synthesis_top_n_substitution(self):
        from src.prompt_templates import load_synthesis_template

        result = load_synthesis_template("screening_synthesis", top_n=15)
        assert result is not None
        assert result[0]["source_scope"] == "top:15"

    def test_synthesis_comparison_n_substitution(self):
        from src.prompt_templates import load_synthesis_template

        result = load_synthesis_template("screening_synthesis", top_n=10)
        assert result is not None
        assert result[1]["source_scope"] == "top:3"

    def test_synthesis_comparison_n_clamped(self):
        from src.prompt_templates import load_synthesis_template

        result = load_synthesis_template("screening_synthesis", top_n=2)
        assert result is not None
        assert result[1]["source_scope"] == "top:2"

    def test_synthesis_source_prompts_serialized(self):
        from src.prompt_templates import load_synthesis_template

        result = load_synthesis_template("screening_synthesis", top_n=5)
        assert result is not None
        sp = result[0]["source_prompts"]
        assert isinstance(sp, str)
        parsed = json.loads(sp)
        assert "extract_profile" in parsed

    def test_load_nonexistent_synthesis_returns_none(self):
        from src.prompt_templates import load_synthesis_template

        result = load_synthesis_template("nonexistent", top_n=5)
        assert result is None


class TestDictToPromptSpecFieldFiltering:
    """Tests for _dict_to_prompt_spec stripping unknown fields."""

    @pytest.fixture(autouse=True)
    def _add_scripts_to_path(self):
        scripts_dir = str(Path(__file__).parent.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

    def test_unknown_fields_stripped(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test",
            "prompts": [
                {
                    "sequence": 1,
                    "prompt_name": "p1",
                    "prompt": "Test",
                    "unknown_field": "should_be_removed",
                    "also_unknown": 42,
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(template_data))
        result = load_prompt_template(str(f))
        assert result is not None
        assert not hasattr(result[0], "unknown_field")
        assert result[0].name == "p1"

    def test_sequence_as_string_converted_to_int(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test",
            "prompts": [
                {
                    "sequence": "7",
                    "prompt_name": "p1",
                    "prompt": "Test",
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(template_data))
        result = load_prompt_template(str(f))
        assert result is not None
        assert result[0].sequence == 7
        assert isinstance(result[0].sequence, int)

    def test_tools_list_converted_to_json(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test",
            "prompts": [
                {
                    "sequence": 1,
                    "prompt_name": "p1",
                    "prompt": "Test",
                    "tools": ["rag_search", "calculate"],
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(template_data))
        result = load_prompt_template(str(f))
        assert result is not None
        assert result[0].tools == '["rag_search", "calculate"]'
        parsed = json.loads(result[0].tools)
        assert parsed == ["rag_search", "calculate"]

    def test_semantic_filter_dict_converted_to_json(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test",
            "prompts": [
                {
                    "sequence": 1,
                    "prompt_name": "p1",
                    "prompt": "Test",
                    "semantic_filter": {"category": "tech"},
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(template_data))
        result = load_prompt_template(str(f))
        assert result is not None
        parsed = json.loads(result[0].semantic_filter)
        assert parsed == {"category": "tech"}

    def test_prompt_name_mapped_to_name(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test",
            "prompts": [
                {
                    "sequence": 1,
                    "prompt_name": "my_prompt",
                    "prompt": "Test",
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(template_data))
        result = load_prompt_template(str(f))
        assert result[0].name == "my_prompt"

    def test_history_none_left_as_none(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_data = {
            "name": "test",
            "prompts": [
                {
                    "sequence": 1,
                    "prompt_name": "p1",
                    "prompt": "Test",
                    "history": None,
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(template_data))
        result = load_prompt_template(str(f))
        assert result[0].history is None


class TestResolveTemplatePathEdgeCases:
    def test_resolve_path_with_yaml_suffix_already_present(self, tmp_path):
        from src.prompt_templates import resolve_template_path

        template = tmp_path / "already.yaml"
        template.write_text("name: test\n")
        result = resolve_template_path(str(template))
        assert result is not None
        assert result == template.resolve()

    def test_resolve_directory_returns_none(self, tmp_path):
        from src.prompt_templates import resolve_template_path

        subdir = tmp_path / "subdir.yaml"
        subdir.mkdir()
        result = resolve_template_path(str(subdir))
        assert result is None


class TestLoadPromptTemplateEdgeCases:
    def test_load_yaml_with_no_prompts_key(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_file = tmp_path / "no_prompts_key.yaml"
        template_file.write_text(yaml.dump({"name": "no_prompts"}))
        result = load_prompt_template(str(template_file))
        assert result is None

    def test_load_yaml_with_null_prompts(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_file = tmp_path / "null_prompts.yaml"
        template_file.write_text(yaml.dump({"name": "null", "prompts": None}))
        result = load_prompt_template(str(template_file))
        assert result is None

    def test_load_yaml_with_string_prompts(self, tmp_path):
        from src.prompt_templates import load_prompt_template

        template_file = tmp_path / "string_prompts.yaml"
        template_file.write_text(yaml.dump({"name": "str", "prompts": "not a list"}))
        result = load_prompt_template(str(template_file))
        assert result is None


class TestLoadSynthesisTemplateEdgeCases:
    def test_explicit_comparison_n(self, tmp_path):
        from src.prompt_templates import load_synthesis_template

        data = {
            "name": "test",
            "prompts": [
                {
                    "prompt_name": "p1",
                    "source_scope": "top:{{comparison_n}}",
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))
        result = load_synthesis_template(str(f), top_n=5, comparison_n=7)
        assert result is not None
        assert result[0]["source_scope"] == "top:7"

    def test_history_none_becomes_empty_string(self, tmp_path):
        from src.prompt_templates import load_synthesis_template

        data = {
            "name": "test",
            "prompts": [
                {
                    "prompt_name": "p1",
                    "source_scope": "top:{{top_n}}",
                    "history": None,
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))
        result = load_synthesis_template(str(f), top_n=5)
        assert result[0]["history"] == ""

    def test_condition_none_becomes_empty_string(self, tmp_path):
        from src.prompt_templates import load_synthesis_template

        data = {
            "name": "test",
            "prompts": [
                {
                    "prompt_name": "p1",
                    "source_scope": "top:{{top_n}}",
                    "condition": None,
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))
        result = load_synthesis_template(str(f), top_n=5)
        assert result[0]["condition"] == ""

    def test_history_list_serialized_to_json(self, tmp_path):
        from src.prompt_templates import load_synthesis_template

        data = {
            "name": "test",
            "prompts": [
                {
                    "prompt_name": "p1",
                    "source_scope": "top:{{top_n}}",
                    "history": ["prev_prompt"],
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))
        result = load_synthesis_template(str(f), top_n=5)
        parsed = json.loads(result[0]["history"])
        assert parsed == ["prev_prompt"]

    def test_source_prompts_list_serialized_to_json(self, tmp_path):
        from src.prompt_templates import load_synthesis_template

        data = {
            "name": "test",
            "prompts": [
                {
                    "prompt_name": "p1",
                    "source_scope": "top:{{top_n}}",
                    "source_prompts": ["extract_profile", "overall_assessment"],
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))
        result = load_synthesis_template(str(f), top_n=5)
        parsed = json.loads(result[0]["source_prompts"])
        assert parsed == ["extract_profile", "overall_assessment"]

    def test_no_prompts_key_returns_none(self, tmp_path):
        from src.prompt_templates import load_synthesis_template

        f = tmp_path / "empty.yaml"
        f.write_text(yaml.dump({"name": "empty"}))
        result = load_synthesis_template(str(f), top_n=5)
        assert result is None

    def test_comparison_n_defaults_to_min_of_3_and_top_n(self, tmp_path):
        from src.prompt_templates import load_synthesis_template

        data = {
            "name": "test",
            "prompts": [
                {
                    "prompt_name": "p1",
                    "source_scope": "top:{{top_n}}",
                },
                {
                    "prompt_name": "p2",
                    "source_scope": "top:{{comparison_n}}",
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))

        result_top10 = load_synthesis_template(str(f), top_n=10)
        assert result_top10[1]["source_scope"] == "top:3"

        result_top2 = load_synthesis_template(str(f), top_n=2)
        assert result_top2[1]["source_scope"] == "top:2"

    def test_string_source_scope_not_substituted_when_no_placeholders(self, tmp_path):
        from src.prompt_templates import load_synthesis_template

        data = {
            "name": "test",
            "prompts": [
                {
                    "prompt_name": "p1",
                    "source_scope": "all",
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))
        result = load_synthesis_template(str(f), top_n=5)
        assert result[0]["source_scope"] == "all"

    def test_non_string_source_scope_not_modified(self, tmp_path):
        from src.prompt_templates import load_synthesis_template

        data = {
            "name": "test",
            "prompts": [
                {
                    "prompt_name": "p1",
                    "source_scope": None,
                },
            ],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data))
        result = load_synthesis_template(str(f), top_n=5)
        assert result[0]["source_scope"] is None
