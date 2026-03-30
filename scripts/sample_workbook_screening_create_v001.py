#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Generate sample workbook for document evaluation and screening testing.

Creates a workbook with all sheets: config, prompts, data, documents, scoring, synthesis.
Demonstrates the full evaluation pipeline:
    - Per-row document binding via _documents column
    - Structured score extraction from LLM JSON responses
    - Weighted composite scoring with strategy-based overrides
    - Cross-row synthesis for ranking and comparison

Uses FFLiteLLMClient with LiteLLM routing for Mistral Small.

Paired with: sample_workbook_screening_validate_v001.py

Usage:
    python scripts/sample_workbook_screening_create_v001.py [output_path] [--client CLIENT]

Examples:
    python scripts/sample_workbook_screening_create_v001.py
    python scripts/sample_workbook_screening_create_v001.py ./test.xlsx
    python scripts/sample_workbook_screening_create_v001.py ./test.xlsx --client anthropic
    python scripts/sample_workbook_screening_create_v001.py -c gemini

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import (
    PromptSpec,
    WorkbookBuilder,
    parse_client_args,
)

from src.config import get_config

CANDIDATES = [
    {
        "id": 1,
        "batch_name": "alice_chen",
        "candidate_name": "Alice Chen",
        "_documents": '["resume_alice"]',
    },
    {
        "id": 2,
        "batch_name": "bob_martinez",
        "candidate_name": "Bob Martinez",
        "_documents": '["resume_bob"]',
    },
    {
        "id": 3,
        "batch_name": "carol_okafor",
        "candidate_name": "Carol Okafor",
        "_documents": '["resume_carol"]',
    },
    {
        "id": 4,
        "batch_name": "david_kim",
        "candidate_name": "David Kim",
        "_documents": '["resume_david"]',
    },
    {
        "id": 5,
        "batch_name": "eva_santos",
        "candidate_name": "Eva Santos",
        "_documents": '["resume_eva"]',
    },
]


def get_documents() -> list[dict]:
    """Return document references for the documents sheet."""
    config = get_config()
    library = config.paths.library

    return [
        {
            "reference_name": "job_desc",
            "common_name": "Job Description",
            "file_path": f"{library}/jd_engineer.md",
            "tags": "jd, engineering",
            "notes": "Shared job description for all candidates",
        },
        {
            "reference_name": "resume_alice",
            "common_name": "Alice Chen CV",
            "file_path": f"{library}/resumes/alice_chen.pdf",
            "tags": "resume",
            "notes": "Alice Chen resume",
        },
        {
            "reference_name": "resume_bob",
            "common_name": "Bob Martinez CV",
            "file_path": f"{library}/resumes/bob_martinez.pdf",
            "tags": "resume",
            "notes": "Bob Martinez resume",
        },
        {
            "reference_name": "resume_carol",
            "common_name": "Carol Okafor CV",
            "file_path": f"{library}/resumes/carol_okafor.pdf",
            "tags": "resume",
            "notes": "Carol Okafor resume",
        },
        {
            "reference_name": "resume_david",
            "common_name": "David Kim CV",
            "file_path": f"{library}/resumes/david_kim.pdf",
            "tags": "resume",
            "notes": "David Kim resume",
        },
        {
            "reference_name": "resume_eva",
            "common_name": "Eva Santos CV",
            "file_path": f"{library}/resumes/eva_santos.pdf",
            "tags": "resume",
            "notes": "Eva Santos resume",
        },
    ]


def get_prompts() -> list[PromptSpec]:
    """Return all prompts for the screening workbook."""
    prompts = []

    prompts.append(
        PromptSpec(
            10,
            "extract_profile",
            "Extract from {{candidate_name}}'s resume and return as structured JSON: "
            "full name, contact info, education history (institution, degree, year), "
            "employment history (company, title, dates, responsibilities), and technical skills list.",
            references='["job_desc"]',
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
            references='["job_desc"]',
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
            references='["job_desc"]',
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
            references='["job_desc"]',
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


def get_scoring_criteria() -> list[dict]:
    """Return scoring criteria for the scoring sheet."""
    return [
        {
            "criteria_name": "skills_match",
            "description": "Technical skills alignment with JD requirements",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 1.0,
            "source_prompt": "evaluate_skills",
        },
        {
            "criteria_name": "education",
            "description": "Quality and relevance of educational background",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 0.8,
            "source_prompt": "evaluate_education",
        },
        {
            "criteria_name": "experience_depth",
            "description": "Years and depth of relevant work experience",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 1.0,
            "source_prompt": "evaluate_experience",
        },
        {
            "criteria_name": "employer_prestige",
            "description": "Quality and relevance of past employers",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 0.7,
            "source_prompt": "evaluate_employers",
        },
        {
            "criteria_name": "growth_trajectory",
            "description": "Evidence of career growth and learning agility",
            "scale_min": 1,
            "scale_max": 10,
            "weight": 0.5,
            "source_prompt": "evaluate_growth",
        },
    ]


def get_synthesis_prompts() -> list[dict]:
    """Return synthesis prompts for the synthesis sheet."""
    return [
        {
            "sequence": 100,
            "prompt_name": "rank_summary",
            "source_scope": "top:5",
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
            "source_scope": "top:3",
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
            "source_prompts": '["extract_profile", "rank_summary", "overall_assessment"]',
            "include_scores": True,
            "history": '["rank_summary"]',
            "condition": "",
            "prompt": "Write a final hiring recommendation for the top candidate. Include: "
            "recommended decision (hire/pass/hold), key qualifications, potential concerns, "
            "suggested follow-up questions for the interview, and overall confidence level "
            "(high/medium/low).",
        },
    ]


def create_sample_workbook(output_path: str, config_overrides: dict | None = None):
    """Create the screening sample workbook.

    Args:
        output_path: Path where the workbook will be saved.
        config_overrides: Optional overrides for the config sheet (client_type, model).

    """
    prompts = get_prompts()
    data_rows = CANDIDATES
    documents = get_documents()
    scoring = get_scoring_criteria()
    synthesis = get_synthesis_prompts()
    config = get_config()
    batch_config = config.workbook.batch

    builder = WorkbookBuilder(output_path)
    builder.add_config_sheet(
        overrides={
            "system_instructions": (
                "You are an expert technical recruiter. Be objective, evidence-based, "
                "and thorough. When scoring, return ONLY the requested JSON object."
            ),
            **(config_overrides or {}),
        },
        extra_fields=[
            (
                "evaluation_strategy",
                "balanced",
                "Evaluation strategy from config/main.yaml (potential, experience, balanced)",
            ),
            (
                "batch_mode",
                batch_config.mode,
                "Batch execution mode: 'per_row' (execute for each data row)",
            ),
            (
                "batch_output",
                batch_config.output,
                "Output format: 'combined' (single sheet) or 'separate_sheets'",
            ),
            (
                "on_batch_error",
                batch_config.on_error,
                "Error handling: 'continue' (skip failed) or 'stop' (halt on error)",
            ),
        ],
    )
    builder.add_documents_sheet(documents)
    builder.add_data_sheet(data_rows)
    builder.add_scoring_sheet(scoring)
    builder.add_prompts_sheet(prompts, include_extra_columns=False)
    builder.add_synthesis_sheet(synthesis)
    builder.save()

    builder.print_summary(
        "screening",
        {
            "Candidates": len(data_rows),
            "Prompts": len(prompts),
            "Scoring criteria": len(scoring),
            "Synthesis prompts": len(synthesis),
            "Client": config_overrides.get("client_type", "default")
            if config_overrides
            else "default",
            "Pipeline": [
                "1. Per-row document binding (_documents column)",
                "2. Extract profile + 5 evaluation criteria (scores 1-10)",
                "3. Overall narrative assessment",
                "4. Scoring aggregation with strategy-based weights",
                "5. Cross-row synthesis: rank, compare, recommend",
            ],
            "Total batch executions": (
                f"{len(prompts)} prompts x {len(data_rows)} candidates = "
                f"{len(prompts) * len(data_rows)}"
            ),
        },
        run_command=f"python scripts/run_orchestrator.py {output_path} -c 1",
    )


if __name__ == "__main__":
    config = get_config()

    args, config_overrides, _ = parse_client_args(
        script_description="Generate sample workbook for document evaluation and screening testing.",
        default_output=config.sample.workbooks.screening,
    )

    create_sample_workbook(args.output, config_overrides)
