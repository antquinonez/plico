#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Create a screening evaluation workbook from a folder of resumes.

Auto-discovers documents from --resumes-path, adds a job description from
--jd, and creates a complete .xlsx workbook ready for the orchestrator.

Supports two modes:
    - Static scoring (default): Includes a scoring sheet with predefined
      criteria. Prompts extract scores from LLM JSON responses.
    - Planning phase (--planning): Uses generator prompts to auto-derive
      scoring criteria and evaluation prompts from the JD. No scoring sheet.

Usage:
    python scripts/create_screening_workbook.py <output_path> \
        --resumes-path <folder> --jd <file>

Examples:
    # Static scoring mode
    python scripts/create_screening_workbook.py ./screening.xlsx \
        --resumes-path ./resumes/ --jd ./job_description.md

    # Planning phase mode (auto-derive scoring)
    python scripts/create_screening_workbook.py ./screening.xlsx \
        --resumes-path ./resumes/ --jd ./jd.md --planning

    # With custom file extensions
    python scripts/create_screening_workbook.py ./screening.xlsx \
        --resumes-path ./resumes/ --jd ./jd.md --extensions .pdf .docx .txt .md
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sample_workbooks import (
    PromptSpec,
    WorkbookBuilder,
)

from src.config import get_config
from src.orchestrator.discovery import (
    create_data_rows_from_documents,
    discover_documents,
)

load_dotenv()


def get_static_prompts() -> list[PromptSpec]:
    """Return evaluation prompts for static scoring mode."""
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


def get_planning_prompts() -> list[PromptSpec]:
    """Return prompts for planning phase mode (auto-derived scoring)."""
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
            "Maintain the source_prompt ↔ prompt_name mapping.",
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


def get_scoring_criteria() -> list[dict]:
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


def get_synthesis_prompts(top_n: int = 5) -> list[dict]:
    """Return synthesis prompts.

    Args:
        top_n: Number of candidates for the top scope. Clamped to min(top_n, actual).

    """
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
        print(f"Error: Job description file not found: {jd_path}")
        sys.exit(1)

    return {
        "reference_name": "job_description",
        "common_name": "Job Description",
        "file_path": str(path),
        "tags": "jd",
        "notes": f"Shared job description: {path.name}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a screening evaluation workbook from a folder of resumes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "output",
        help="Output path for the .xlsx workbook",
    )
    parser.add_argument(
        "--resumes-path",
        required=True,
        help="Folder path containing resume documents to auto-discover",
    )
    parser.add_argument(
        "--jd",
        required=True,
        help="Path to the job description file",
    )
    parser.add_argument(
        "--planning",
        action="store_true",
        help="Use planning phase mode (auto-derive scoring from JD via LLM). "
        "Default uses static scoring sheet.",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".pdf", ".docx", ".doc", ".txt", ".md"],
        help="File extensions to include (default: .pdf .docx .doc .txt .md)",
    )
    parser.add_argument(
        "--client",
        help="Client type from config/clients.yaml",
    )
    parser.add_argument(
        "--system-instructions",
        default=(
            "You are an expert technical recruiter. Be objective, evidence-based, "
            "and thorough. When scoring, return ONLY the requested JSON object."
        ),
        help="System instructions for the AI",
    )
    parser.add_argument(
        "--evaluation-strategy",
        default="balanced",
        help="Evaluation strategy (default: balanced)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    config = get_config()
    app_config = config
    default_client = app_config.get_default_client_type()
    client_type = args.client or default_client

    extensions = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions}

    print(f"\nCreating screening workbook: {args.output}")
    print(f"  Resumes path: {args.resumes_path}")
    print(f"  Job description: {args.jd}")
    print(f"  Mode: {'planning' if args.planning else 'static scoring'}")

    jd_doc = create_jd_document(args.jd)

    resume_docs = discover_documents(
        args.resumes_path,
        extensions=extensions,
        absolute_paths=True,
        tags=["resume"],
    )

    if not resume_docs:
        print(f"\nError: No documents found in {args.resumes_path}")
        print(f"  Extensions: {', '.join(sorted(extensions))}")
        return 1

    print(f"  Discovered {len(resume_docs)} documents")

    all_documents = [jd_doc, *resume_docs]
    data_rows = create_data_rows_from_documents(resume_docs)

    prompts = get_planning_prompts() if args.planning else get_static_prompts()
    synthesis = get_synthesis_prompts(top_n=len(resume_docs))

    batch_config = config.workbook.batch

    builder = WorkbookBuilder(args.output)
    builder.add_config_sheet(
        overrides={
            "client_type": client_type,
            "system_instructions": args.system_instructions,
        },
        extra_fields=[
            (
                "evaluation_strategy",
                args.evaluation_strategy,
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
    builder.add_documents_sheet(all_documents)
    builder.add_data_sheet(data_rows)

    if not args.planning:
        builder.add_scoring_sheet(get_scoring_criteria())

    builder.add_prompts_sheet(prompts)
    builder.add_synthesis_sheet(synthesis)
    builder.save()

    total_prompts = len(prompts)
    if args.planning:
        planning_count = sum(1 for p in prompts if p.phase == "planning")
        execution_count = total_prompts - planning_count
        prompt_summary = (
            f"{planning_count} planning + {execution_count} static execution "
            f"(+ LLM-generated eval prompts)"
        )
    else:
        prompt_summary = f"{total_prompts} evaluation prompts"

    builder.print_summary(
        f"screening ({'planning' if args.planning else 'static'})",
        {
            "Resumes discovered": len(resume_docs),
            "Job description": jd_doc["file_path"],
            "Documents total": len(all_documents),
            "Candidates (batch rows)": len(data_rows),
            "Prompts": prompt_summary,
            "Scoring": "Auto-derived from planning phase"
            if args.planning
            else "Static (5 criteria)",
            "Synthesis prompts": len(synthesis),
            "Client": client_type,
            "Total batch executions": f"{total_prompts} prompts x {len(data_rows)} candidates = "
            f"{total_prompts * len(data_rows)}",
        },
        run_command=f"python scripts/run_orchestrator.py {args.output} -c 1",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
