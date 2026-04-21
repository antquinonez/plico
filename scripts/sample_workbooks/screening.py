# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Shared screening evaluation definitions.

Reusable prompt specs, scoring criteria, and synthesis prompts for
screening workbooks and manifests. Both create_screening_workbook.py
and create_screening_manifest.py import from this module.

Each prompt function accepts an optional ``template_path`` argument. When
provided, prompts are loaded from the specified YAML file (or a named
template in ``config/prompts/``). When omitted, the hardcoded defaults
are used, preserving backward compatibility.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .base import PromptSpec

logger = logging.getLogger(__name__)


def get_static_screening_prompts(
    template_path: str | None = None,
) -> list[PromptSpec]:
    """Return evaluation prompts for static scoring mode.

    Args:
        template_path: Optional path to a YAML template file (name in
            ``config/prompts/`` or explicit file path). If None, returns
            the hardcoded defaults.

    Returns:
        List of PromptSpec instances.

    """
    if template_path is not None:
        loaded = _load_from_template(template_path)
        if loaded is not None:
            return loaded
        logger.info(
            "Template not found (%s), falling back to hardcoded static prompts",
            template_path,
        )

    prompts = []

    prompts.append(
        PromptSpec(
            10,
            "extract_profile",
            "Extract from {{candidate_name}}'s resume and return as structured JSON: "
            "full name, contact info, education history (institution, degree, year), "
            "employment history (company, title, dates, responsibilities), and "
            "technical skills list.",
            references='["job_description"]',
        )
    )
    prompts.append(
        PromptSpec(
            15,
            "gate_evaluation",
            "Based on the profile extracted from {{candidate_name}}'s resume, "
            "perform a quick screening check against the job description. "
            "Determine whether this candidate meets the MINIMUM qualifications. "
            "Consider: required years of experience, required education, "
            "core domain relevance, and fundamental deal-breakers (e.g., "
            "entry-level candidate for a senior role, unrelated industry). "
            "Be GENEROUS in borderline cases — only reject candidates who "
            "clearly do not meet the minimum bar. When in doubt, proceed=true. "
            'Return ONLY JSON: {"proceed": true/false, "reason": "..."}',
            history='["extract_profile"]',
            references='["job_description"]',
            abort_condition='json_get({{gate_evaluation.response}}, "proceed") == False',
            notes="Gate: quickly screens out clearly unqualified candidates before detailed evaluation",
        )
    )
    prompts.append(
        PromptSpec(
            20,
            "evaluate_skills",
            "Evaluate {{candidate_name}}'s technical skills against the job description. "
            "For each required skill, rate proficiency (1-10). Return JSON: "
            '{"skills_match": <1-10>, "reasoning": "..."}',
            history='["extract_profile"]',
            references='["job_description"]',
        )
    )
    prompts.append(
        PromptSpec(
            30,
            "evaluate_education",
            "Evaluate {{candidate_name}}'s education quality and relevance. "
            "Consider institution reputation, degree relevance. Return JSON: "
            '{"education": <1-10>, "reasoning": "..."}',
            history='["extract_profile"]',
            references='["job_description"]',
        )
    )
    prompts.append(
        PromptSpec(
            40,
            "evaluate_experience",
            "Evaluate {{candidate_name}}'s work experience depth and relevance. "
            "Consider years, progression, scope, relevance. "
            'Return JSON: {"experience_depth": <1-10>, "reasoning": "..."}',
            history='["extract_profile"]',
            references='["job_description"]',
        )
    )
    prompts.append(
        PromptSpec(
            50,
            "evaluate_growth",
            "Assess {{candidate_name}}'s growth trajectory. Look for increasing responsibility, "
            "career progression, skill development, learning agility. "
            'Return JSON: {"growth_trajectory": <1-10>, "evidence": ["..."], "reasoning": "..."}',
            history='["extract_profile"]',
        )
    )
    prompts.append(
        PromptSpec(
            60,
            "evaluate_employers",
            "Evaluate the quality and relevance of {{candidate_name}}'s past employers. "
            "Consider company reputation, industry alignment, scale, competitiveness. "
            'Return JSON: {"employer_prestige": <1-10>, "reasoning": "..."}',
            history='["extract_profile"]',
        )
    )
    prompts.append(
        PromptSpec(
            70,
            "overall_assessment",
            "Write a 2-3 paragraph narrative assessment of {{candidate_name}} for the role. "
            "Cover strengths, concerns, and overall fit. Be specific and evidence-based, "
            "referencing the evaluation scores above.",
            history='["evaluate_skills", "evaluate_education", "evaluate_experience", '
            '"evaluate_growth", "evaluate_employers"]',
        )
    )

    return prompts


def get_planning_screening_prompts(
    template_path: str | None = None,
) -> list[PromptSpec]:
    """Return prompts for planning phase mode (auto-derived scoring).

    Args:
        template_path: Optional path to a YAML template file (name in
            ``config/prompts/`` or explicit file path). If None, returns
            the hardcoded defaults.

    Returns:
        List of PromptSpec instances.

    """
    if template_path is not None:
        loaded = _load_from_template(template_path)
        if loaded is not None:
            return loaded
        logger.info(
            "Template not found (%s), falling back to hardcoded planning prompts",
            template_path,
        )

    prompts = []

    prompts.append(
        PromptSpec(
            10,
            "analyze_jd",
            "Analyze the job description provided below. Your task is to:\n"
            "\n"
            "1. Identify 4-6 key evaluation criteria for screening candidates. "
            "For each criterion, provide: criteria_name (snake_case), description, "
            "scale_min (always 1), scale_max (always 10), weight (0.5-2.0 based on "
            "importance), and source_prompt (the prompt_name that will extract this score).\n"
            "\n"
            "2. Create an evaluation prompt template for each criterion. Each prompt must:\n"
            "   - Include the template variable candidate_name wrapped in double curly "
            "braces (the orchestrator will substitute the actual candidate name at runtime)\n"
            '   - Reference the job description via references: ["job_description"]\n'
            '   - Depend on an extract_profile prompt via history: ["extract_profile"]\n'
            "   - Instruct the LLM to return ONLY a JSON object where the top-level key "
            "is the criteria_name (matching exactly) with an integer score 1-10, plus a "
            "'reasoning' key. Example for a criterion named 'skills_match': "
            '{"skills_match": 8, "reasoning": "..."}\n'
            "\n"
            "Return your response as JSON with exactly two keys:\n"
            '- "scoring_criteria": array of criteria objects\n'
            '- "prompts": array of prompt objects, each with prompt_name, prompt, '
            "references, and history\n"
            "\n"
            "Critical rules:\n"
            "- Each criterion's source_prompt must exactly match a prompt_name "
            "in the prompts array.\n"
            "- Each evaluation prompt must instruct the LLM to return a JSON object "
            "with the criteria_name as a top-level key containing the numeric score.",
            references='["job_description"]',
            notes="Master generator: derives criteria and evaluation prompts from JD",
            phase="planning",
            generator="true",
        )
    )

    prompts.append(
        PromptSpec(
            20,
            "refine_criteria",
            "Review the scoring criteria and evaluation prompts below. "
            "Refine them for:\n"
            "- Clarity: each prompt should be unambiguous about what to evaluate\n"
            "- Consistency: all prompts should use the same scoring scale and JSON format\n"
            "- Reliability: prompts should elicit scores that are reproducible\n"
            "- Completeness: ensure all important aspects of the JD are covered\n"
            "- Weight balance: weights should reflect the JD's priorities\n"
            "\n"
            "Return the updated JSON with the same schema (scoring_criteria + prompts). "
            "You may add, remove, or modify criteria and prompts. "
            "Maintain the source_prompt <-> prompt_name mapping.",
            history='["analyze_jd"]',
            notes="Refinement pass: improves criteria/prompts from analyze_jd",
            phase="planning",
            generator="true",
        )
    )

    prompts.append(
        PromptSpec(
            100,
            "extract_profile",
            "Extract from {{candidate_name}}'s resume and return as structured JSON: "
            "full name, contact info, education history (institution, degree, year), "
            "employment history (company, title, dates, responsibilities), and "
            "technical skills list.",
            references='["job_description"]',
            notes="Static prompt: extracts structured profile for downstream evaluation",
        )
    )

    prompts.append(
        PromptSpec(
            150,
            "gate_evaluation",
            "Based on the profile extracted from {{candidate_name}}'s resume, "
            "perform a quick screening check against the job description. "
            "Determine whether this candidate meets the MINIMUM qualifications. "
            "Consider: required years of experience, required education, "
            "core domain relevance, and fundamental deal-breakers (e.g., "
            "entry-level candidate for a senior role, unrelated industry). "
            "Be GENEROUS in borderline cases — only reject candidates who "
            "clearly do not meet the minimum bar. When in doubt, proceed=true. "
            'Return ONLY JSON: {"proceed": true/false, "reason": "..."}',
            history='["extract_profile"]',
            references='["job_description"]',
            abort_condition='json_get({{gate_evaluation.response}}, "proceed") == False',
            notes="Gate: quickly screens out clearly unqualified candidates before detailed evaluation",
        )
    )

    prompts.append(
        PromptSpec(
            200,
            "overall_assessment",
            "Write a 2-3 paragraph narrative assessment of {{candidate_name}} for "
            "the role described in the job description. Cover strengths, concerns, "
            "and overall fit. Be specific and evidence-based, referencing the "
            "evaluation scores from earlier prompts.",
            history='["extract_profile"]',
            notes="Static prompt: narrative assessment using all prior evaluations",
        )
    )

    return prompts


def _load_from_template(template_path: str) -> list[PromptSpec] | None:
    """Load prompt specs from a YAML template file.

    Args:
        template_path: Template name or file path.

    Returns:
        List of PromptSpec instances, or None if file not found.

    """
    from src.prompt_templates import load_prompt_template

    return load_prompt_template(template_path)


def get_screening_scoring_criteria() -> list[dict[str, Any]]:
    """Return scoring criteria for static mode."""
    return [
        {
            "criteria_name": "skills_match",
            "description": "Technical skills alignment with JD requirements",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 1.0,
            "source_prompt": "evaluate_skills",
            "score_type": "normalized_score",
        },
        {
            "criteria_name": "education",
            "description": "Quality and relevance of educational background",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 0.8,
            "source_prompt": "evaluate_education",
            "score_type": "normalized_score",
        },
        {
            "criteria_name": "experience_depth",
            "description": "Years and depth of relevant work experience",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 1.0,
            "source_prompt": "evaluate_experience",
            "score_type": "normalized_score",
        },
        {
            "criteria_name": "employer_prestige",
            "description": "Quality and relevance of past employers",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 0.7,
            "source_prompt": "evaluate_employers",
            "score_type": "normalized_score",
        },
        {
            "criteria_name": "growth_trajectory",
            "description": "Evidence of career growth and learning agility",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 0.5,
            "source_prompt": "evaluate_growth",
            "score_type": "normalized_score",
        },
    ]


def get_screening_synthesis_prompts(
    top_n: int = 5,
    template_path: str | None = None,
) -> list[dict[str, Any]]:
    """Return synthesis prompts.

    Args:
        top_n: Number of candidates for the top scope. Clamped to min(top_n, actual).
        template_path: Optional path to a YAML template file (name in
            ``config/prompts/`` or explicit file path). If None, returns
            the hardcoded defaults.

    """
    if template_path is not None:
        from src.prompt_templates import load_synthesis_template

        loaded = load_synthesis_template(template_path, top_n=top_n)
        if loaded is not None:
            return loaded
        logger.info(
            "Template not found (%s), falling back to hardcoded synthesis prompts",
            template_path,
        )

    return [
        {
            "sequence": 100,
            "prompt_name": "rank_summary",
            "source_scope": f"top:{top_n}",
            "source_prompts": '["extract_profile", "overall_assessment"]',
            "include_scores": True,
            "history": "",
            "condition": "",
            "prompt": "Based on the evaluations below, rank all candidates from strongest "
            "to weakest overall fit for this role. For each candidate, provide a one-sentence "
            "justification. End with a summary table showing rank, name, composite score, "
            "and key strength.",
        },
        {
            "sequence": 110,
            "prompt_name": "comparison",
            "source_scope": f"top:{min(3, top_n)}",
            "source_prompts": '["extract_profile", "overall_assessment"]',
            "include_scores": True,
            "history": "",
            "condition": "",
            "prompt": "Compare the top 3 candidates side by side across all evaluation "
            "criteria. Highlight where each candidate excels and where they have gaps "
            "relative to each other. Identify which candidate is the strongest hire and why.",
        },
        {
            "sequence": 120,
            "prompt_name": "recommendation",
            "source_scope": "top:1",
            "source_prompts": '["extract_profile", "overall_assessment"]',
            "include_scores": True,
            "history": '["rank_summary"]',
            "condition": "",
            "prompt": "Write a final hiring recommendation for the top candidate. Include: "
            "recommended decision (hire/pass/hold), key qualifications, potential concerns, "
            "suggested follow-up questions for the interview, and overall confidence level "
            "(high/medium/low).",
        },
    ]


def create_jd_document(jd_path: str) -> dict[str, Any]:
    """Create a document definition for the job description.

    Args:
        jd_path: Path to the JD file.

    Returns:
        Document definition dict.

    """
    path = Path(jd_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Job description file not found: {jd_path}")

    return {
        "reference_name": "job_description",
        "common_name": "Job Description",
        "file_path": str(path),
        "tags": "shared",
        "chunking_strategy": "",
        "notes": f"Shared job description: {path.name}",
    }


def _parse_json_field(value: str | None) -> Any:
    """Parse a JSON string field into its native type.

    PromptSpec stores references, history, tools etc. as JSON strings
    (e.g., '["job_description"]'). YAML manifests need native lists.

    Args:
        value: Raw string value or None.

    Returns:
        Parsed value (list, dict, or the original string if not valid JSON).

    """
    if not value:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else value
        except (json.JSONDecodeError, ValueError):
            return value
    return value


def prompt_spec_to_dict(spec: PromptSpec) -> dict[str, Any]:
    """Convert a PromptSpec to a manifest-compatible dict.

    Args:
        spec: PromptSpec instance.

    Returns:
        Dictionary matching the prompts.yaml schema.

    """
    d: dict[str, Any] = {
        "sequence": spec.sequence,
        "prompt_name": spec.name,
        "prompt": spec.prompt,
        "history": _parse_json_field(spec.history),
        "notes": spec.notes,
        "client": spec.client,
        "condition": spec.condition,
        "abort_condition": spec.abort_condition,
        "references": _parse_json_field(spec.references),
        "semantic_query": spec.semantic_query,
        "semantic_filter": _parse_json_field(spec.semantic_filter),
        "query_expansion": spec.query_expansion,
        "rerank": spec.rerank,
    }

    if spec.agent_mode:
        d["agent_mode"] = True
        d["tools"] = _parse_json_field(spec.tools)
        if spec.max_tool_rounds:
            d["max_tool_rounds"] = spec.max_tool_rounds
        if spec.validation_prompt:
            d["validation_prompt"] = spec.validation_prompt
        if spec.max_validation_retries:
            d["max_validation_retries"] = spec.max_validation_retries

    d["phase"] = spec.phase or "execution"
    if spec.generator:
        d["generator"] = True

    return d
