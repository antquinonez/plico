# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for scripts/sample_workbooks/screening.py and screening templates."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml


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
        assert len(prompts) == 8
        assert prompts[0].name == "extract_profile"

    def test_planning_prompts_default(self):
        from sample_workbooks.screening import get_planning_screening_prompts

        prompts = get_planning_screening_prompts()
        assert len(prompts) == 5
        assert prompts[0].name == "analyze_jd"

    def test_static_prompts_with_valid_template(self):
        from sample_workbooks.screening import get_static_screening_prompts

        prompts = get_static_screening_prompts(template_path="screening_static")
        assert len(prompts) == 8
        assert prompts[0].name == "extract_profile"

    def test_planning_prompts_with_valid_template(self):
        from sample_workbooks.screening import get_planning_screening_prompts

        prompts = get_planning_screening_prompts(template_path="screening_planning")
        assert len(prompts) == 5
        assert prompts[0].name == "analyze_jd"

    def test_static_prompts_fallback_on_missing_template(self):
        from sample_workbooks.screening import get_static_screening_prompts

        prompts = get_static_screening_prompts(template_path="nonexistent_xyz")
        assert len(prompts) == 8

    def test_planning_prompts_fallback_on_missing_template(self):
        from sample_workbooks.screening import get_planning_screening_prompts

        prompts = get_planning_screening_prompts(template_path="nonexistent_xyz")
        assert len(prompts) == 5

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
        assert len(result) == 5

    def test_skills_planning_has_correct_prompt_names(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        names = [p.name for p in result]
        assert "analyze_jd" in names
        assert "refine_criteria" in names
        assert "extract_profile" in names
        assert "gate_evaluation" in names
        assert "overall_assessment" in names

    def test_skills_planning_gate_has_abort_condition(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        gate = next(p for p in result if p.name == "gate_evaluation")
        assert gate.abort_condition is not None
        assert "json_get" in gate.abort_condition
        assert "proceed" in gate.abort_condition

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
        assert profile.references is None

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
        assert len(prompts) == 5
        names = [p.name for p in prompts]
        assert "analyze_jd" in names
        assert "refine_criteria" in names

    def test_skills_planning_analyze_jd_references_jd(self):
        from src.prompt_templates import load_prompt_template

        result = load_prompt_template("screening_skills_planning")
        analyze = next(p for p in result if p.name == "analyze_jd")
        assert analyze.references == '["job_description"]'
