# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for PlanningArtifactParser — parsing, merging, validation, sequencing."""

from __future__ import annotations

import json

import pytest

from src.orchestrator.planning import GeneratedArtifact, PlanningArtifactParser


@pytest.fixture
def parser():
    return PlanningArtifactParser()


class TestParse:
    """Tests for PlanningArtifactParser.parse()."""

    def test_parse_valid_json(self, parser):
        """Test parsing valid generator JSON with both keys."""
        response = json.dumps(
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
                        "prompt": "Evaluate {{candidate_name}}'s skills.",
                    }
                ],
            }
        )

        artifact = parser.parse(response, "analyze_jd")
        assert len(artifact.scoring_criteria) == 1
        assert len(artifact.generated_prompts) == 1
        assert artifact.source == "analyze_jd"
        assert artifact.scoring_criteria[0]["criteria_name"] == "skills"
        assert artifact.generated_prompts[0]["prompt_name"] == "eval_skills"

    def test_parse_missing_arrays(self, parser):
        """Test parsing JSON with missing scoring_criteria and prompts keys."""
        response = json.dumps({"scoring_criteria": []})
        artifact = parser.parse(response, "gen")
        assert artifact.scoring_criteria == []
        assert artifact.generated_prompts == []

    def test_parse_empty_object(self, parser):
        """Test parsing empty JSON object."""
        response = "{}"
        artifact = parser.parse(response, "gen")
        assert artifact.scoring_criteria == []
        assert artifact.generated_prompts == []

    def test_parse_extra_keys_logged(self, parser, caplog):
        """Test that unexpected keys are logged as warnings."""
        response = json.dumps(
            {
                "scoring_criteria": [],
                "prompts": [],
                "unexpected_key": "value",
            }
        )
        artifact = parser.parse(response, "gen")
        assert artifact is not None
        assert "unexpected keys" in caplog.text.lower()

    def test_parse_empty_response_raises(self, parser):
        """Test that empty response raises ValueError."""
        with pytest.raises(ValueError, match="empty response"):
            parser.parse("", "gen")

    def test_parse_non_json_raises(self, parser):
        """Test that non-JSON text raises ValueError."""
        with pytest.raises(ValueError):
            parser.parse("This is not JSON at all", "gen")

    def test_parse_non_dict_raises(self, parser):
        """Test that JSON array (not object) raises ValueError."""
        with pytest.raises(ValueError, match="not a JSON object"):
            parser.parse("[1, 2, 3]", "gen")

    def test_parse_malformed_json_repair(self, parser):
        """Test json_repair can handle slightly malformed JSON."""
        # Missing closing brace — json_repair should handle this
        response = '{"scoring_criteria": [], "prompts": []'
        artifact = parser.parse(response, "gen")
        assert artifact.scoring_criteria == []
        assert artifact.generated_prompts == []

    def test_parse_non_list_scoring_criteria_ignored(self, parser, caplog):
        """Test that non-list scoring_criteria is ignored."""
        response = json.dumps(
            {
                "scoring_criteria": "not a list",
                "prompts": [],
            }
        )
        artifact = parser.parse(response, "gen")
        assert artifact.scoring_criteria == []
        assert "not a list" in caplog.text

    def test_parse_non_list_prompts_ignored(self, parser, caplog):
        """Test that non-list prompts is ignored."""
        response = json.dumps(
            {
                "scoring_criteria": [],
                "prompts": "not a list",
            }
        )
        artifact = parser.parse(response, "gen")
        assert artifact.generated_prompts == []

    def test_parse_string_entries_in_prompts_filtered(self, parser, caplog):
        """Test that non-dict entries in prompts array are dropped."""
        response = json.dumps(
            {
                "scoring_criteria": [],
                "prompts": [
                    "just a string",
                    {"prompt_name": "valid", "prompt": "test"},
                    42,
                ],
            }
        )
        artifact = parser.parse(response, "gen")
        assert len(artifact.generated_prompts) == 1
        assert artifact.generated_prompts[0]["prompt_name"] == "valid"
        assert "non-dict prompts" in caplog.text

    def test_parse_string_entries_in_criteria_filtered(self, parser, caplog):
        """Test that non-dict entries in scoring_criteria array are dropped."""
        response = json.dumps(
            {
                "scoring_criteria": [
                    "bad",
                    {"criteria_name": "good", "description": "valid"},
                ],
                "prompts": [],
            }
        )
        artifact = parser.parse(response, "gen")
        assert len(artifact.scoring_criteria) == 1
        assert artifact.scoring_criteria[0]["criteria_name"] == "good"
        assert "non-dict scoring_criteria" in caplog.text


class TestMergeArtifacts:
    """Tests for PlanningArtifactParser.merge_artifacts()."""

    def test_merge_single_artifact(self, parser):
        """Test merging a single artifact returns its contents."""
        artifact = GeneratedArtifact(
            scoring_criteria=[{"criteria_name": "a", "description": "A"}],
            generated_prompts=[{"prompt_name": "p1", "prompt": "test"}],
            source="gen1",
        )
        criteria, prompts = parser.merge_artifacts([artifact])
        assert len(criteria) == 1
        assert len(prompts) == 1

    def test_merge_refinement_overwrite(self, parser, caplog):
        """Test that later artifacts overwrite earlier ones on key collisions."""
        a1 = GeneratedArtifact(
            scoring_criteria=[{"criteria_name": "skills", "description": "v1"}],
            generated_prompts=[{"prompt_name": "eval", "prompt": "v1"}],
            source="gen1",
        )
        a2 = GeneratedArtifact(
            scoring_criteria=[{"criteria_name": "skills", "description": "v2"}],
            generated_prompts=[{"prompt_name": "eval", "prompt": "v2"}],
            source="gen2",
        )
        criteria, prompts = parser.merge_artifacts([a1, a2])
        assert len(criteria) == 1
        assert criteria[0]["description"] == "v2"
        assert len(prompts) == 1
        assert prompts[0]["prompt"] == "v2"
        assert "overwrites" in caplog.text.lower()

    def test_merge_collision_warnings(self, parser, caplog):
        """Test collision warnings are logged for both criteria and prompts."""
        a1 = GeneratedArtifact(
            scoring_criteria=[{"criteria_name": "x", "description": "d"}],
            generated_prompts=[{"prompt_name": "y", "prompt": "t"}],
            source="g1",
        )
        a2 = GeneratedArtifact(
            scoring_criteria=[{"criteria_name": "x", "description": "d2"}],
            generated_prompts=[{"prompt_name": "y", "prompt": "t2"}],
            source="g2",
        )
        parser.merge_artifacts([a1, a2])
        assert caplog.text.count("overwrites") >= 2

    def test_merge_empty_list(self, parser):
        """Test merging empty list returns empty results."""
        criteria, prompts = parser.merge_artifacts([])
        assert criteria == []
        assert prompts == []

    def test_merge_multiple_distinct(self, parser):
        """Test merging artifacts with distinct names preserves all."""
        a1 = GeneratedArtifact(
            scoring_criteria=[{"criteria_name": "a", "description": "A"}],
            generated_prompts=[{"prompt_name": "p1", "prompt": "t1"}],
            source="g1",
        )
        a2 = GeneratedArtifact(
            scoring_criteria=[{"criteria_name": "b", "description": "B"}],
            generated_prompts=[{"prompt_name": "p2", "prompt": "t2"}],
            source="g2",
        )
        criteria, prompts = parser.merge_artifacts([a1, a2])
        assert len(criteria) == 2
        assert len(prompts) == 2


class TestValidateCriteria:
    """Tests for PlanningArtifactParser.validate_criteria()."""

    def test_valid_criteria(self, parser):
        """Test valid criteria produce no errors."""
        criteria = [
            {
                "criteria_name": "skills",
                "description": "Skills match",
                "source_prompt": "eval_skills",
                "weight": 1.0,
                "scale_min": 1,
                "scale_max": 10,
            }
        ]
        errors = parser.validate_criteria(criteria, {"eval_skills"})
        assert errors == []

    def test_missing_source_prompt(self, parser):
        """Test criteria with invalid source_prompt produces error."""
        criteria = [
            {
                "criteria_name": "skills",
                "description": "Skills match",
                "source_prompt": "nonexistent",
                "weight": 1.0,
            }
        ]
        errors = parser.validate_criteria(criteria, {"eval_skills"})
        assert any("nonexistent" in e for e in errors)

    def test_zero_weight(self, parser):
        """Test zero weight produces error."""
        criteria = [
            {
                "criteria_name": "skills",
                "description": "Skills match",
                "weight": 0,
            }
        ]
        errors = parser.validate_criteria(criteria, set())
        assert any("weight" in e.lower() for e in errors)

    def test_inconsistent_scales(self, parser):
        """Test inconsistent scales produce error."""
        criteria = [
            {
                "criteria_name": "a",
                "description": "A",
                "scale_min": 1,
                "scale_max": 10,
            },
            {
                "criteria_name": "b",
                "description": "B",
                "scale_min": 0,
                "scale_max": 5,
            },
        ]
        errors = parser.validate_criteria(criteria, set())
        assert any("inconsistent" in e.lower() for e in errors)

    def test_missing_criteria_name(self, parser):
        """Test missing criteria_name produces error."""
        criteria = [{"description": "No name"}]
        errors = parser.validate_criteria(criteria, set())
        assert any("criteria_name" in e for e in errors)

    def test_missing_description(self, parser):
        """Test missing description produces error."""
        criteria = [{"criteria_name": "x"}]
        errors = parser.validate_criteria(criteria, set())
        assert any("description" in e for e in errors)


class TestValidatePrompts:
    """Tests for PlanningArtifactParser.validate_prompts()."""

    def test_valid_prompts(self, parser):
        """Test valid prompts produce no errors."""
        prompts = [
            {
                "prompt_name": "eval_skills",
                "prompt": "Evaluate {{candidate_name}}'s skills.",
            }
        ]
        errors = parser.validate_prompts(
            prompts,
            existing_names=set(),
            doc_refs=set(),
            batch_keys={"candidate_name"},
        )
        assert errors == []

    def test_missing_prompt_name(self, parser):
        """Test missing prompt_name produces error."""
        prompts = [{"prompt": "test"}]
        errors = parser.validate_prompts(prompts, set(), set(), set())
        assert any("prompt_name" in e for e in errors)

    def test_missing_prompt(self, parser):
        """Test missing prompt text produces error."""
        prompts = [{"prompt_name": "x"}]
        errors = parser.validate_prompts(prompts, set(), set(), set())
        assert any("'prompt'" in e for e in errors)

    def test_name_collision(self, parser):
        """Test collision with existing prompt produces error."""
        prompts = [{"prompt_name": "existing", "prompt": "test"}]
        errors = parser.validate_prompts(
            prompts,
            existing_names={"existing"},
            doc_refs=set(),
            batch_keys=set(),
        )
        assert any("collides" in e for e in errors)

    def test_invalid_doc_ref(self, parser):
        """Test invalid document reference produces error."""
        prompts = [
            {
                "prompt_name": "p1",
                "prompt": "test",
                "references": ["bad_doc"],
            }
        ]
        errors = parser.validate_prompts(
            prompts,
            existing_names=set(),
            doc_refs={"good_doc"},
            batch_keys=set(),
        )
        assert any("bad_doc" in e for e in errors)

    def test_invalid_history_dep(self, parser):
        """Test invalid history dependency produces error."""
        prompts = [
            {
                "prompt_name": "p1",
                "prompt": "test",
                "history": ["nonexistent"],
            }
        ]
        errors = parser.validate_prompts(
            prompts,
            existing_names=set(),
            doc_refs=set(),
            batch_keys=set(),
        )
        assert any("nonexistent" in e for e in errors)

    def test_invalid_variable(self, parser):
        """Test unknown batch variable produces error."""
        prompts = [
            {
                "prompt_name": "p1",
                "prompt": "Evaluate {{unknown_var}} now.",
            }
        ]
        errors = parser.validate_prompts(
            prompts,
            existing_names=set(),
            doc_refs=set(),
            batch_keys={"candidate_name"},
        )
        assert any("unknown_var" in e for e in errors)

    def test_duplicate_generated_names(self, parser):
        """Test duplicate names within generated prompts produces error."""
        prompts = [
            {"prompt_name": "dup", "prompt": "test1"},
            {"prompt_name": "dup", "prompt": "test2"},
        ]
        errors = parser.validate_prompts(prompts, set(), set(), set())
        assert any("duplicate" in e.lower() for e in errors)


class TestAssignSequences:
    """Tests for PlanningArtifactParser.assign_sequences()."""

    def test_auto_base(self, parser):
        """Test auto base assigns sequences after existing max."""
        prompts = [
            {"prompt_name": "a"},
            {"prompt_name": "b"},
        ]
        result = parser.assign_sequences(
            prompts,
            existing_sequences={100, 200},
            base="auto",
            step=10,
        )
        # Max existing is 200, rounds up to 300
        assert result[0]["sequence"] == 300
        assert result[1]["sequence"] == 310

    def test_explicit_base(self, parser):
        """Test explicit base uses the given value."""
        prompts = [{"prompt_name": "a"}]
        result = parser.assign_sequences(
            prompts,
            existing_sequences=set(),
            base=500,
            step=10,
        )
        assert result[0]["sequence"] == 500

    def test_no_existing_sequences(self, parser):
        """Test auto base with no existing sequences defaults to 1000."""
        prompts = [{"prompt_name": "a"}]
        result = parser.assign_sequences(
            prompts,
            existing_sequences=set(),
            base="auto",
            step=10,
        )
        assert result[0]["sequence"] == 1000

    def test_step_correctness(self, parser):
        """Test step increments between generated prompts."""
        prompts = [{"prompt_name": "a"}, {"prompt_name": "b"}, {"prompt_name": "c"}]
        result = parser.assign_sequences(
            prompts,
            existing_sequences={500},
            base="auto",
            step=20,
        )
        assert result[0]["sequence"] == 600
        assert result[1]["sequence"] == 620
        assert result[2]["sequence"] == 640

    def test_collision_avoidance(self, parser):
        """Test that assigned sequences avoid collisions with existing."""
        prompts = [{"prompt_name": "a"}]
        # 300 is already taken, so it should pick 301
        result = parser.assign_sequences(
            prompts,
            existing_sequences={100, 200, 300},
            base="auto",
            step=10,
        )
        assert result[0]["sequence"] not in {100, 200, 300}

    def test_empty_prompts(self, parser):
        """Test empty prompts list returns empty."""
        result = parser.assign_sequences([], set(), "auto", 10)
        assert result == []


class TestBuildScoringCriteria:
    """Tests for PlanningArtifactParser.build_scoring_criteria()."""

    def test_basic_build(self, parser):
        """Test building ScoringCriteria from valid dicts."""
        criteria_dicts = [
            {
                "criteria_name": "skills",
                "description": "Skills match",
                "scale_min": 1,
                "scale_max": 10,
                "weight": 2.0,
                "source_prompt": "eval_skills",
                "score_type": "normalized",
            }
        ]
        result = parser.build_scoring_criteria(criteria_dicts)
        assert len(result) == 1
        assert result[0].criteria_name == "skills"
        assert result[0].weight == 2.0
        assert result[0].source_prompt == "eval_skills"

    def test_defaults(self, parser):
        """Test building with missing optional fields uses defaults."""
        criteria_dicts = [
            {
                "criteria_name": "x",
                "description": "X",
            }
        ]
        result = parser.build_scoring_criteria(criteria_dicts)
        assert result[0].scale_min == 1
        assert result[0].scale_max == 10
        assert result[0].weight == 1.0
        assert result[0].source_prompt == ""
        assert result[0].score_type == "normalized_score"

    def test_explicit_score_type_preserved(self, parser):
        """Test explicit score_type from generator is preserved."""
        criteria_dicts = [
            {
                "criteria_name": "x",
                "description": "X",
                "score_type": "custom_type",
            }
        ]
        result = parser.build_scoring_criteria(criteria_dicts)
        assert result[0].score_type == "custom_type"
