#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Generate sample workbook for planning-phase screening testing.

Creates a workbook that uses the planning phase to auto-derive scoring criteria
and evaluation prompts from a job description via LLM calls. Demonstrates:
    - Planning prompts with generator=true for artifact generation
    - Refinement pattern (second generator prompt improves first)
    - Static prompts coexisting with LLM-generated prompts
    - Auto-derived scoring rubric (no manual scoring sheet)
    - Per-row document binding via _documents column
    - Cross-row synthesis for ranking and comparison

Unlike v001 which has a hand-written scoring sheet and evaluation prompts,
v002 lets the LLM derive everything from the job description.

Uses FFLiteLLMClient with LiteLLM routing for Mistral Small.

Paired with: sample_workbook_screening_validate_v002.py

Usage:
    python scripts/sample_workbook_screening_create_v002.py [output_path] [--client CLIENT]

Examples:
    python scripts/sample_workbook_screening_create_v002.py
    python scripts/sample_workbook_screening_create_v002.py ./test_planning.xlsx
    python scripts/sample_workbook_screening_create_v002.py ./test.xlsx --client anthropic

Version: 002
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
            "file_path": f"{library}/resumes/alice_chen.md",
            "tags": "resume",
            "notes": "Alice Chen resume",
        },
        {
            "reference_name": "resume_bob",
            "common_name": "Bob Martinez CV",
            "file_path": f"{library}/resumes/bob_martinez.md",
            "tags": "resume",
            "notes": "Bob Martinez resume",
        },
        {
            "reference_name": "resume_carol",
            "common_name": "Carol Okafor CV",
            "file_path": f"{library}/resumes/carol_okafor.md",
            "tags": "resume",
            "notes": "Carol Okafor resume",
        },
        {
            "reference_name": "resume_david",
            "common_name": "David Kim CV",
            "file_path": f"{library}/resumes/david_kim.md",
            "tags": "resume",
            "notes": "David Kim resume",
        },
        {
            "reference_name": "resume_eva",
            "common_name": "Eva Santos CV",
            "file_path": f"{library}/resumes/eva_santos.md",
            "tags": "resume",
            "notes": "Eva Santos resume",
        },
    ]


def get_prompts() -> list[PromptSpec]:
    """Return all prompts for the planning-phase screening workbook.

    Planning prompts (phase=planning):
      - analyze_jd: Master generator that reads the JD and produces
        scoring criteria and evaluation prompt templates.
      - refine_criteria: Refinement generator that takes analyze_jd's
        output and improves it for clarity and scoring reliability.

    Execution prompts (phase=execution, default):
      - extract_profile: Static prompt that extracts candidate info.
      - overall_assessment: Static prompt for narrative assessment.

    The generator prompts produce additional execution prompts dynamically.
    """
    prompts = []

    # ── Planning Phase: Master generator ──────────────────────────
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
            '   - Reference the job description via references: ["job_desc"]\n'
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
            references='["job_desc"]',
            notes="Master generator: derives criteria and evaluation prompts from JD",
            phase="planning",
            generator="true",
        )
    )

    # ── Planning Phase: Refinement pass ───────────────────────────
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
            "Maintain the source_prompt ↔ prompt_name mapping.",
            history='["analyze_jd"]',
            notes="Refinement pass: improves criteria/prompts from analyze_jd",
            phase="planning",
            generator="true",
        )
    )

    # ── Execution Phase: Static prompts ───────────────────────────
    prompts.append(
        PromptSpec(
            100,
            "extract_profile",
            "Extract from {{candidate_name}}'s resume and return as structured JSON: "
            "full name, contact info, education history (institution, degree, year), "
            "employment history (company, title, dates, responsibilities), and "
            "technical skills list.",
            references='["job_desc"]',
            notes="Static prompt: extracts structured profile for downstream evaluation",
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


def create_sample_workbook(output_path: str, config_overrides: dict | None = None):
    """Create the planning-phase screening sample workbook.

    Key differences from v001:
    - No scoring sheet (criteria auto-derived from planning phase)
    - Planning prompts with generator=true and phase=planning
    - Refinement pattern: refine_criteria improves analyze_jd output
    - Only 2 static execution prompts (rest are LLM-generated)

    Args:
        output_path: Path where the workbook will be saved.
        config_overrides: Optional overrides for the config sheet (client_type, model).

    """
    prompts = get_prompts()
    data_rows = CANDIDATES
    documents = get_documents()
    synthesis = get_synthesis_prompts()
    config = get_config()
    batch_config = config.workbook.batch

    builder = WorkbookBuilder(output_path)
    builder.add_config_sheet(
        overrides={
            "system_instructions": (
                "You are an expert technical recruiter and evaluation system designer. "
                "Be objective, evidence-based, and thorough. When asked to return JSON, "
                "return ONLY the requested JSON object with no additional text."
            ),
            "max_tokens": 4096,
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
    # NOTE: No scoring sheet — criteria are auto-derived from planning phase
    builder.add_prompts_sheet(prompts)
    builder.add_synthesis_sheet(synthesis)
    builder.save()

    planning_count = sum(1 for p in prompts if p.phase == "planning")
    execution_count = len(prompts) - planning_count

    builder.print_summary(
        "screening (v002 - planning phase)",
        {
            "Candidates": len(data_rows),
            "Planning prompts": f"{planning_count} (generators that derive criteria + eval prompts)",
            "Static execution prompts": execution_count,
            "Scoring sheet": "NONE (auto-derived from planning phase)",
            "Synthesis prompts": len(synthesis),
            "Client": config_overrides.get("client_type", "default")
            if config_overrides
            else "default",
            "Pipeline": [
                "1. PLANNING: analyze_jd reads JD → generates criteria + eval prompts",
                "2. PLANNING: refine_criteria improves the generated artifacts",
                "3. EXECUTION: extract_profile extracts candidate info (static)",
                "4. EXECUTION: LLM-generated eval prompts score each criterion",
                "5. EXECUTION: overall_assessment writes narrative (static)",
                "6. SCORING: auto-derived rubric aggregates scores",
                "7. SYNTHESIS: rank, compare, recommend across candidates",
            ],
        },
        run_command=f"python scripts/run_orchestrator.py {output_path} -c 1",
    )


if __name__ == "__main__":
    config = get_config()

    default_output = config.sample.workbooks.screening.replace(".xlsx", "_v002.xlsx")

    args, config_overrides, _ = parse_client_args(
        script_description=(
            "Generate sample workbook for planning-phase screening testing (v002)."
        ),
        default_output=default_output,
    )

    create_sample_workbook(args.output, config_overrides)
