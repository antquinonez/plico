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
        assert len(result) == 7
        assert result[0].name == "extract_profile"

    def test_load_planning_template(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_planning")
        assert result is not None
        assert len(result) == 4
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


class TestScreeningFallbackIntegration:
    """Tests that screening.py functions fall back correctly."""

    @pytest.fixture(autouse=True)
    def _add_scripts_to_path(self):
        scripts_dir = str(Path(__file__).parent.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

    def test_static_prompts_default(self):
        from sample_workbooks.screening import get_static_screening_prompts

        prompts = get_static_screening_prompts()
        assert len(prompts) == 7
        assert prompts[0].name == "extract_profile"

    def test_planning_prompts_default(self):
        from sample_workbooks.screening import get_planning_screening_prompts

        prompts = get_planning_screening_prompts()
        assert len(prompts) == 4
        assert prompts[0].name == "analyze_jd"

    def test_static_prompts_with_valid_template(self):
        from sample_workbooks.screening import get_static_screening_prompts

        prompts = get_static_screening_prompts(template_path="screening_static")
        assert len(prompts) == 7
        assert prompts[0].name == "extract_profile"

    def test_planning_prompts_with_valid_template(self):
        from sample_workbooks.screening import get_planning_screening_prompts

        prompts = get_planning_screening_prompts(template_path="screening_planning")
        assert len(prompts) == 4
        assert prompts[0].name == "analyze_jd"

    def test_static_prompts_fallback_on_missing_template(self):
        from sample_workbooks.screening import get_static_screening_prompts

        prompts = get_static_screening_prompts(template_path="nonexistent_xyz")
        assert len(prompts) == 7

    def test_planning_prompts_fallback_on_missing_template(self):
        from sample_workbooks.screening import get_planning_screening_prompts

        prompts = get_planning_screening_prompts(template_path="nonexistent_xyz")
        assert len(prompts) == 4

    def test_synthesis_prompts_default(self):
        from sample_workbooks.screening import get_screening_synthesis_prompts

        synthesis = get_screening_synthesis_prompts(top_n=10)
        assert len(synthesis) == 3
        assert synthesis[0]["source_scope"] == "top:10"

    def test_synthesis_prompts_with_template(self):
        from sample_workbooks.screening import get_screening_synthesis_prompts

        synthesis = get_screening_synthesis_prompts(top_n=8, template_path="screening_synthesis")
        assert len(synthesis) == 3
        assert synthesis[0]["source_scope"] == "top:8"

    def test_synthesis_prompts_fallback_on_missing_template(self):
        from sample_workbooks.screening import get_screening_synthesis_prompts

        synthesis = get_screening_synthesis_prompts(top_n=5, template_path="nonexistent_xyz")
        assert len(synthesis) == 3

    def test_static_prompts_custom_file(self, tmp_path):
        from sample_workbooks.screening import get_static_screening_prompts

        template_data = {
            "name": "custom",
            "prompts": [
                {
                    "sequence": 1,
                    "prompt_name": "custom_eval",
                    "prompt": "Evaluate {{candidate_name}}",
                },
            ],
        }
        template_file = tmp_path / "custom.yaml"
        with open(template_file, "w") as f:
            yaml.dump(template_data, f)

        prompts = get_static_screening_prompts(template_path=str(template_file))
        assert len(prompts) == 1
        assert prompts[0].name == "custom_eval"


class TestScreeningSkillsPlanningTemplate:
    """Tests for the screening_skills_planning template."""

    @pytest.fixture(autouse=True)
    def _add_scripts_to_path(self):
        scripts_dir = str(Path(__file__).parent.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

    def test_load_skills_planning_template(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        assert result is not None
        assert len(result) == 4

    def test_skills_planning_has_correct_prompt_names(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        names = [p.name for p in result]
        assert "analyze_jd" in names
        assert "refine_criteria" in names
        assert "extract_profile" in names
        assert "overall_assessment" in names

    def test_skills_planning_analyze_jd_is_generator(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        analyze = next(p for p in result if p.name == "analyze_jd")
        assert analyze.phase == "planning"
        assert analyze.generator == "true"

    def test_skills_planning_refine_is_generator(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        refine = next(p for p in result if p.name == "refine_criteria")
        assert refine.phase == "planning"
        assert refine.generator == "true"
        assert refine.history == '["analyze_jd"]'

    def test_skills_planning_extract_profile_is_execution(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        profile = next(p for p in result if p.name == "extract_profile")
        assert profile.phase is None or profile.phase != "planning"
        assert profile.references == '["job_description"]'

    def test_skills_planning_overall_assessment_references_profile(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        overall = next(p for p in result if p.name == "overall_assessment")
        assert overall.history == '["extract_profile"]'

    def test_skills_planning_analyze_jd_mentions_exhaustive(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        analyze = next(p for p in result if p.name == "analyze_jd")
        assert "exhaustively" in analyze.prompt.lower()
        assert "one skill per criterion" in analyze.prompt.lower()

    def test_skills_planning_refine_mentions_deduplication(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        refine = next(p for p in result if p.name == "refine_criteria")
        assert "dedup" in refine.prompt.lower()

    def test_skills_planning_via_screening_function(self):
        from sample_workbooks.screening import get_planning_screening_prompts

        prompts = get_planning_screening_prompts(template_path="screening_skills_planning")
        assert len(prompts) == 4
        names = [p.name for p in prompts]
        assert "analyze_jd" in names
        assert "refine_criteria" in names

    def test_skills_planning_analyze_jd_references_jd(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        analyze = next(p for p in result if p.name == "analyze_jd")
        assert analyze.references == '["job_description"]'
