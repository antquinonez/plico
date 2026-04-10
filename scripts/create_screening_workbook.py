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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sample_workbooks import WorkbookBuilder
from sample_workbooks.screening import (
    create_jd_document,
    get_planning_screening_prompts,
    get_screening_scoring_criteria,
    get_screening_synthesis_prompts,
    get_static_screening_prompts,
)

from src.config import get_config
from src.orchestrator.discovery import (
    create_data_rows_from_documents,
    discover_documents,
)

load_dotenv()


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

    prompts = get_planning_screening_prompts() if args.planning else get_static_screening_prompts()
    synthesis = get_screening_synthesis_prompts(top_n=len(resume_docs))

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
        builder.add_scoring_sheet(get_screening_scoring_criteria())

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
