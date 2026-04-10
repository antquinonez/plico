#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Create a screening evaluation manifest from a folder of resumes.

Generates a manifest folder (YAML files) directly, without an Excel
intermediary. Documents and batch data are injected at runtime via
manifest_run.py --resumes-path and --jd flags.

Supports two modes:
    - Static scoring (default): Includes scoring.yaml with predefined
      criteria. Prompts extract scores from LLM JSON responses.
    - Planning phase (--planning): Uses generator prompts to auto-derive
      scoring criteria and evaluation prompts from the JD. No scoring.yaml.

Usage:
    python scripts/create_screening_manifest.py [output_dir] \
        --resumes-path <folder> --jd <file>

Examples:
    # Static scoring mode
    python scripts/create_screening_manifest.py ./manifests/manifest_screening \
        --resumes-path ./resumes/ --jd ./job_description.md

    # Planning phase mode (auto-derive scoring)
    python scripts/create_screening_manifest.py --planning \
        --resumes-path ./resumes/ --jd ./jd.md

    # Create only (no execution)
    python scripts/create_screening_manifest.py --resumes-path ./resumes/ --jd ./jd.md

Runtime execution:
    python scripts/manifest_run.py <manifest_dir> \
        --resumes-path ./resumes/ --jd ./jd.md -c 1
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
    get_planning_screening_prompts,
    get_screening_scoring_criteria,
    get_screening_synthesis_prompts,
    get_static_screening_prompts,
    prompt_spec_to_dict,
)

from src.config import get_config
from src.orchestrator.discovery import discover_documents

load_dotenv()


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write data to a YAML file.

    Args:
        path: Output file path.
        data: Data to serialize.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def build_manifest_yaml(name: str, planning: bool, prompt_count: int) -> dict[str, Any]:
    """Build manifest.yaml metadata.

    Args:
        name: Manifest name.
        planning: Whether planning phase is enabled.
        prompt_count: Number of prompts.

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
        "has_documents": False,
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a screening evaluation manifest from a folder of resumes.",
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
        required=True,
        help="Folder path containing resume documents to validate discovery",
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

    args = parser.parse_args()

    config = get_config()
    default_client = config.get_default_client_type()
    client_type = args.client or default_client

    extensions = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions}

    output_dir = args.output or str(Path(config.paths.manifest_dir) / "manifest_screening")
    manifest_path = Path(output_dir)

    print(f"\nCreating screening manifest: {manifest_path}")
    print(f"  Resumes path: {args.resumes_path}")
    print(f"  Job description: {args.jd}")
    print(f"  Mode: {'planning' if args.planning else 'static scoring'}")

    if not Path(args.jd).is_file():
        print(f"\nError: Job description file not found: {args.jd}")
        return 1

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

    prompts = get_planning_screening_prompts() if args.planning else get_static_screening_prompts()
    synthesis = get_screening_synthesis_prompts(top_n=len(resume_docs))
    batch_config = config.workbook.batch

    manifest_name = (
        manifest_path.name.replace("manifest_", "")
        if manifest_path.name.startswith("manifest_")
        else manifest_path.name
    )

    write_yaml(
        manifest_path / "manifest.yaml",
        build_manifest_yaml(manifest_name, args.planning, len(prompts)),
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
    print(f"Created screening ({'planning' if args.planning else 'static'}) manifest")
    print(f"{'=' * 60}")
    print(f"Manifest path:   {manifest_path}")
    print(f"Resumes:         {len(resume_docs)} discovered")
    print(f"Job description: {args.jd}")
    print(f"Prompts:         {prompt_summary}")
    print(
        f"Scoring:         {'Auto-derived from planning phase' if args.planning else 'Static (5 criteria)'}"
    )
    print(f"Synthesis:       {len(synthesis)} prompts")
    print(f"Client:          {client_type}")
    print("\nNote: Documents and batch data are injected at runtime, not baked in.")
    print(
        f"  Total batch executions: {total_prompts} prompts x {len(resume_docs)} candidates = "
        f"{total_prompts * len(resume_docs)}"
    )
    print("\nRun with:")
    print(
        f"  python scripts/manifest_run.py {manifest_path} "
        f"--resumes-path {args.resumes_path} --jd {args.jd} -c 1"
    )
    print(f"{'=' * 60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
