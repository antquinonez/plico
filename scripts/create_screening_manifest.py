#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Create a screening evaluation manifest.

Generates a manifest folder (YAML files) for resume screening evaluation.
The JD can optionally be baked into documents.yaml; resumes are always
injected at runtime via manifest_run.py --documents-path.

Supports two scoring modes:
    - Static scoring (default): Includes scoring.yaml with predefined
      criteria. Prompts extract scores from LLM JSON responses.
    - Planning phase (--planning): Uses generator prompts to auto-derive
      scoring criteria and evaluation prompts from the JD. No scoring.yaml.

Two creation modes:
    - Template (JD baked): JD baked into documents.yaml. Resumes injected
      at runtime via --documents-path.
    - Template (generic): Nothing baked in. Both JD and resumes injected
      at runtime.

Usage:
    # Template with JD baked in
    python scripts/create_screening_manifest.py --jd <file>

    # Generic template (nothing baked in)
    python scripts/create_screening_manifest.py

    # With resume count for synthesis top_n sizing
    python scripts/create_screening_manifest.py --jd ./jd.md --resumes-path ./resumes/

Examples:
    python scripts/create_screening_manifest.py ./manifests/manifest_screening \
        --jd ./job_description.md

    python scripts/create_screening_manifest.py --planning \
        --jd ./jd.md

Runtime execution:
    # With JD baked in
    python scripts/manifest_run.py <manifest_dir> \
        --documents-path ./resumes/ -c 1

    # With JD injected at runtime
    python scripts/manifest_run.py <manifest_dir> \
        --shared-document ./jd.md --shared-document-name job_description \
        --documents-path ./resumes/ -c 1
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from dotenv import load_dotenv
from sample_workbooks.screening import (
    _parse_json_field,
    create_jd_document,
    get_planning_screening_prompts,
    get_screening_scoring_criteria,
    get_screening_synthesis_prompts,
    get_static_screening_prompts,
    prompt_spec_to_dict,
)

from src.config import get_config
from src.orchestrator.discovery import discover_documents

load_dotenv()

DEFAULT_SYNTHESIS_TOP_N = 10


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write data to a YAML file.

    Args:
        path: Output file path.
        data: Data to serialize.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def build_manifest_yaml(
    name: str,
    planning: bool,
    prompt_count: int,
    has_documents: bool = False,
) -> dict[str, Any]:
    """Build manifest.yaml metadata.

    Args:
        name: Manifest name.
        planning: Whether planning phase is enabled.
        prompt_count: Number of prompts.
        has_documents: Whether documents.yaml was written.

    Returns:
        Manifest metadata dict.

    """
    return {
        "name": name,
        "description": f"Screening evaluation ({'planning' if planning else 'static scoring'})",
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "has_data": False,
        "has_clients": False,
        "has_documents": has_documents,
        "has_tools": False,
        "has_scoring": not planning,
        "has_synthesis": True,
        "has_planning": planning,
        "prompt_count": prompt_count,
    }


def build_config_yaml(
    client_type: str,
    system_instructions: str,
    evaluation_strategy: str,
    batch_mode: str,
    batch_output: str,
    on_batch_error: str,
) -> dict[str, Any]:
    """Build config.yaml data.

    Args:
        client_type: Client type identifier.
        system_instructions: System prompt for the AI.
        evaluation_strategy: Evaluation strategy name.
        batch_mode: Batch execution mode.
        batch_output: Batch output format.
        on_batch_error: Error handling mode.

    Returns:
        Config dict.

    """
    config = get_config()
    sample = config.sample

    return {
        "name": "screening",
        "client_type": client_type,
        "model": sample.default_model,
        "max_retries": sample.default_retries,
        "temperature": sample.default_temperature,
        "max_tokens": sample.default_max_tokens,
        "system_instructions": system_instructions,
        "evaluation_strategy": evaluation_strategy,
        "batch_mode": batch_mode,
        "batch_output": batch_output,
        "on_batch_error": on_batch_error,
    }


def build_prompts_yaml(prompts: list[Any]) -> dict[str, Any]:
    """Build prompts.yaml data from PromptSpec list.

    Args:
        prompts: List of PromptSpec objects.

    Returns:
        Prompts dict with 'prompts' key.

    """
    return {"prompts": [prompt_spec_to_dict(p) for p in prompts]}


def build_scoring_yaml(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    """Build scoring.yaml data.

    Args:
        criteria: List of scoring criteria dicts.

    Returns:
        Scoring dict with 'scoring' key.

    """
    return {"scoring": criteria}


def build_synthesis_yaml(synthesis: list[dict[str, Any]]) -> dict[str, Any]:
    """Build synthesis.yaml data.

    Args:
        synthesis: List of synthesis prompt dicts.

    Returns:
        Synthesis dict with 'synthesis' key.

    """
    parsed = []
    for item in synthesis:
        entry = dict(item)
        if isinstance(entry.get("source_prompts"), str):
            entry["source_prompts"] = _parse_json_field(entry["source_prompts"])
        if isinstance(entry.get("history"), str):
            entry["history"] = _parse_json_field(entry["history"])
        parsed.append(entry)
    return {"synthesis": parsed}


def build_documents_yaml(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Build documents.yaml data.

    Args:
        documents: List of document definition dicts.

    Returns:
        Documents dict with 'documents' key.

    """
    return {"documents": documents}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a screening evaluation manifest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="",
        help="Output directory for the manifest folder "
        "(default: <manifest_dir>/manifest_screening)",
    )
    parser.add_argument(
        "--resumes-path",
        default=None,
        help="Folder path containing resume documents. Used to count "
        "candidates for synthesis top_n sizing. Resumes are always "
        "injected at runtime via --documents-path on manifest_run.py.",
    )
    parser.add_argument(
        "--jd",
        default=None,
        help="Path to the job description file. If provided, baked into "
        "documents.yaml with reference_name='job_description'.",
    )
    parser.add_argument(
        "--planning",
        action="store_true",
        help="Use planning phase mode (auto-derive scoring from JD via LLM). "
        "Default uses static scoring.",
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
    default_client = config.get_default_client_type()
    client_type = args.client or default_client

    extensions = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions}

    output_dir = args.output or str(Path(config.paths.manifest_dir) / "manifest_screening")
    manifest_path = Path(output_dir)

    mode_label = "planning" if args.planning else "static scoring"
    creation_mode = "template (JD baked)" if args.jd else "template (generic)"

    print(f"\nCreating screening manifest: {manifest_path}")
    print(f"  Mode: {mode_label}")
    print(f"  Creation: {creation_mode}")
    if args.jd:
        print(f"  Job description: {args.jd}")
    if args.resumes_path:
        print(f"  Resumes path: {args.resumes_path}")

    if args.jd and not Path(args.jd).is_file():
        print(f"\nError: Job description file not found: {args.jd}")
        return 1

    resume_count = 0
    if args.resumes_path:
        resume_docs = discover_documents(
            args.resumes_path,
            extensions=extensions,
            absolute_paths=True,
            tags=["resume"],
        )
        resume_count = len(resume_docs)
        if resume_count > 0:
            print(f"  Discovered {resume_count} documents")
        else:
            print(f"  Warning: No documents found in {args.resumes_path}")

    synthesis_top_n = (
        max(resume_count, DEFAULT_SYNTHESIS_TOP_N) if resume_count > 0 else DEFAULT_SYNTHESIS_TOP_N
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

    manifest_name = (
        manifest_path.name.replace("manifest_", "")
        if manifest_path.name.startswith("manifest_")
        else manifest_path.name
    )

    has_documents = args.jd is not None

    write_yaml(
        manifest_path / "manifest.yaml",
        build_manifest_yaml(
            manifest_name, args.planning, len(prompts), has_documents=has_documents
        ),
    )
    write_yaml(
        manifest_path / "config.yaml",
        build_config_yaml(
            client_type=client_type,
            system_instructions=args.system_instructions,
            evaluation_strategy=args.evaluation_strategy,
            batch_mode=batch_config.mode,
            batch_output=batch_config.output,
            on_batch_error=batch_config.on_error,
        ),
    )
    write_yaml(
        manifest_path / "prompts.yaml",
        build_prompts_yaml(prompts),
    )

    if not args.planning:
        write_yaml(
            manifest_path / "scoring.yaml",
            build_scoring_yaml(get_screening_scoring_criteria()),
        )

    write_yaml(
        manifest_path / "synthesis.yaml",
        build_synthesis_yaml(synthesis),
    )

    if args.jd:
        jd_doc = create_jd_document(args.jd)
        write_yaml(
            manifest_path / "documents.yaml",
            build_documents_yaml([jd_doc]),
        )

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

    print(f"\n{'=' * 60}")
    print(f"Created screening ({mode_label}) manifest")
    print(f"{'=' * 60}")
    print(f"Manifest path:   {manifest_path}")
    print(f"Creation mode:   {creation_mode}")
    if args.jd:
        print(f"Job description: baked in ({args.jd})")
    else:
        print("Job description: inject at runtime (--shared-document)")
    if resume_count > 0:
        print(f"Resumes:         {resume_count} discovered (injected at runtime)")
    else:
        print("Resumes:         inject at runtime (--documents-path)")
    print(f"Prompts:         {prompt_summary}")
    print(
        f"Scoring:         {'Auto-derived from planning phase' if args.planning else 'Static (5 criteria)'}"
    )
    print(f"Synthesis:       {len(synthesis)} prompts")
    print(f"Client:          {client_type}")
    if args.planning_prompts or args.static_prompts or args.synthesis_prompts:
        sources = []
        if args.planning and args.planning_prompts:
            sources.append(f"planning={args.planning_prompts}")
        if not args.planning and args.static_prompts:
            sources.append(f"static={args.static_prompts}")
        if args.synthesis_prompts:
            sources.append(f"synthesis={args.synthesis_prompts}")
        print(f"Templates:       {', '.join(sources)}")

    if args.jd:
        print("\nRun with:")
        print(f"  python scripts/manifest_run.py {manifest_path} --documents-path ./resumes/ -c 1")
    else:
        print("\nRun with:")
        print(
            f"  python scripts/manifest_run.py {manifest_path} "
            f"--shared-document ./jd.md --shared-document-name job_description "
            f"--documents-path ./resumes/ -c 1"
        )

    print(f"{'=' * 60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
