#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Create a screening evaluation workbook.

Creates a .xlsx workbook with prompts, scoring, and synthesis sheets for
resume screening. Documents and batch data can be baked in or injected
at runtime via the orchestrator.

Supports two scoring modes:
    - Static scoring (default): Includes a scoring sheet with predefined
      criteria. Prompts extract scores from LLM JSON responses.
    - Planning phase (--planning): Uses generator prompts to auto-derive
      scoring criteria and evaluation prompts from the JD. No scoring sheet.

Three creation modes:
    - Self-contained: JD and resumes baked in. Run with no flags.
    - Template (JD baked): JD baked in, resumes injected at runtime.
    - Template (generic): Nothing baked in. All injected at runtime.

Usage:
    # Self-contained (JD + resumes baked in)
    python scripts/create_screening_workbook.py <output_path> \
        --resumes-path <folder> --jd <file>

    # Template with JD baked in
    python scripts/create_screening_workbook.py <output_path> --jd <file>

    # Generic template (nothing baked in)
    python scripts/create_screening_workbook.py <output_path>

Examples:
    python scripts/create_screening_workbook.py ./screening.xlsx \
        --resumes-path ./resumes/ --jd ./job_description.md

    python scripts/create_screening_workbook.py ./template.xlsx \
        --jd ./jd.md --planning

    python scripts/create_screening_workbook.py ./template.xlsx
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

DEFAULT_SYNTHESIS_TOP_N = 10


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a screening evaluation workbook.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "output",
        help="Output path for the .xlsx workbook",
    )
    parser.add_argument(
        "--resumes-path",
        default=None,
        help="Folder path containing resume documents to bake in. "
        "If omitted, resumes must be injected at runtime via "
        "--documents-path on run_orchestrator.py.",
    )
    parser.add_argument(
        "--jd",
        default=None,
        help="Path to the job description file to bake in. "
        "If omitted, a JD must be injected at runtime via "
        "--shared-document on run_orchestrator.py.",
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
    parser.add_argument(
        "--planning-prompts",
        default=None,
        metavar="TEMPLATE",
        help="Custom planning prompt template (name in config/prompts/ or file path). "
        "Only used with --planning. Default: config/prompts/screening_planning.yaml",
    )
    parser.add_argument(
        "--static-prompts",
        default=None,
        metavar="TEMPLATE",
        help="Custom static prompt template (name in config/prompts/ or file path). "
        "Default: config/prompts/screening_static.yaml",
    )
    parser.add_argument(
        "--synthesis-prompts",
        default=None,
        metavar="TEMPLATE",
        help="Custom synthesis prompt template (name in config/prompts/ or file path). "
        "Default: config/prompts/screening_synthesis.yaml",
    )

    args = parser.parse_args()

    if args.planning_prompts and not args.planning:
        print("Warning: --planning-prompts has no effect without --planning.\n")
    if args.static_prompts and args.planning:
        print("Warning: --static-prompts has no effect with --planning (use --planning-prompts).\n")

    if not args.resumes_path and not args.jd:
        print("Note: Neither --resumes-path nor --jd provided.")
        print("      Creating a generic template. All data must be injected at runtime.\n")

    config = get_config()
    app_config = config
    default_client = app_config.get_default_client_type()
    client_type = args.client or default_client

    extensions = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions}

    mode_label = "planning" if args.planning else "static scoring"
    if args.resumes_path and args.jd:
        creation_mode = "self-contained"
    elif args.jd:
        creation_mode = "template (JD baked)"
    elif args.resumes_path:
        creation_mode = "template (resumes baked)"
    else:
        creation_mode = "template (generic)"

    print(f"\nCreating screening workbook: {args.output}")
    print(f"  Mode: {mode_label}")
    print(f"  Creation: {creation_mode}")
    if args.jd:
        print(f"  Job description: {args.jd}")
    if args.resumes_path:
        print(f"  Resumes path: {args.resumes_path}")

    all_documents: list[dict[str, str | list[str]]] = []
    data_rows: list[dict[str, str | int]] = []
    resume_docs: list[dict[str, str | list[str]]] = []

    if args.jd:
        jd_doc = create_jd_document(args.jd)
        all_documents.append(jd_doc)

    if args.resumes_path:
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
        all_documents.extend(resume_docs)
        data_rows = create_data_rows_from_documents(resume_docs)

    candidate_count = len(data_rows)
    synthesis_top_n = (
        max(candidate_count, DEFAULT_SYNTHESIS_TOP_N)
        if candidate_count > 0
        else DEFAULT_SYNTHESIS_TOP_N
    )

    prompts = (
        get_planning_screening_prompts(template_path=args.planning_prompts)
        if args.planning
        else get_static_screening_prompts(template_path=args.static_prompts)
    )
    synthesis = get_screening_synthesis_prompts(
        top_n=synthesis_top_n, template_path=args.synthesis_prompts
    )

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

    if all_documents:
        builder.add_documents_sheet(all_documents)
    if data_rows:
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

    summary_extra: dict[str, str] = {
        "Creation mode": creation_mode,
        "Prompts": prompt_summary,
        "Scoring": "Auto-derived from planning phase" if args.planning else "Static (5 criteria)",
        "Synthesis prompts": str(len(synthesis)),
        "Client": client_type,
    }
    if args.planning_prompts or args.static_prompts or args.synthesis_prompts:
        sources = []
        if args.planning and args.planning_prompts:
            sources.append(f"planning={args.planning_prompts}")
        if not args.planning and args.static_prompts:
            sources.append(f"static={args.static_prompts}")
        if args.synthesis_prompts:
            sources.append(f"synthesis={args.synthesis_prompts}")
        summary_extra["Prompt templates"] = ", ".join(sources)
    if args.jd:
        summary_extra["Job description"] = jd_doc["file_path"]
    if candidate_count > 0:
        summary_extra["Resumes discovered"] = str(candidate_count)
        summary_extra["Candidates (batch rows)"] = str(candidate_count)
        summary_extra["Total batch executions"] = (
            f"{total_prompts} prompts x {candidate_count} candidates = "
            f"{total_prompts * candidate_count}"
        )

    run_flags: list[str] = []
    if args.jd and not args.resumes_path:
        run_flags.append("--documents-path ./resumes/")
    elif not args.jd:
        run_flags.append("--shared-document ./jd.md --shared-document-name job_description")
        run_flags.append("--documents-path ./resumes/")
    run_command = f"python scripts/run_orchestrator.py {args.output} -c 1"
    if run_flags:
        run_command += " \\\n    " + " \\\n    ".join(run_flags)

    builder.print_summary(
        f"screening ({mode_label})",
        summary_extra,
        run_command=run_command,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
