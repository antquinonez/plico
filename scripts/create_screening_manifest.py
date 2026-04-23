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
from src.orchestrator.pre_screener import ResumePreScreener

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
    has_clients: bool = False,
    has_data: bool = False,
) -> dict[str, Any]:
    """Build manifest.yaml metadata.

    Args:
        name: Manifest name.
        planning: Whether planning phase is enabled.
        prompt_count: Number of prompts.
        has_documents: Whether documents.yaml was written.
        has_clients: Whether clients.yaml was written.
        has_data: Whether data.yaml was written (pre-screening).

    Returns:
        Manifest metadata dict.

    """
    return {
        "name": name,
        "description": f"Screening evaluation ({'planning' if planning else 'static scoring'})",
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "has_data": has_data,
        "has_clients": has_clients,
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
    planning: bool = False,
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

    PLANNING_MAX_TOKENS = 16000
    default_max_tokens = sample.default_max_tokens
    if planning:
        default_max_tokens = PLANNING_MAX_TOKENS

    return {
        "name": "screening",
        "client_type": client_type,
        "model": sample.default_model,
        "max_retries": sample.default_retries,
        "temperature": sample.default_temperature,
        "max_tokens": default_max_tokens,
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
        "--planning-client",
        default=None,
        metavar="CLIENT_TYPE",
        help="Client type from config/clients.yaml for planning-phase prompts. "
        "Only used with --planning. Execution prompts use --client. "
        "Example: litellm-mistral-large",
    )
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
    parser.add_argument(
        "--pre-screen",
        nargs="?",
        const=-1,
        type=int,
        default=None,
        metavar="N",
        help="Enable embedding-based pre-screening to rank and filter resumes "
        "before creating the manifest. Reduces LLM costs by only evaluating "
        "top-K candidates. Optionally specify N to override config default.",
    )

    args = parser.parse_args()

    if args.planning_prompts and not args.planning:
        print("Warning: --planning-prompts has no effect without --planning.\n")
    if args.planning_client and not args.planning:
        print("Warning: --planning-client has no effect without --planning.\n")
    if args.static_prompts and args.planning:
        print("Warning: --static-prompts has no effect with --planning (use --planning-prompts).\n")
    if args.pre_screen is not None and not args.jd:
        print("Error: --pre-screen requires --jd (need JD text for embedding comparison).\n")
        return 1
    if args.pre_screen is not None and not args.resumes_path:
        print("Error: --pre-screen requires --resumes-path.\n")
        return 1

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
    pre_screen_report = None
    filtered_doc_specs = None
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

        if args.pre_screen is not None and resume_count > 0:
            top_k = args.pre_screen if args.pre_screen > 0 else config.pre_screening.top_k
            print(f"\n  Pre-screening enabled (top-{top_k} of {resume_count})")
            print(f"  Embedding model: {config.pre_screening.embedding_model}")
            print(
                f"  Weights: BM25={config.pre_screening.bm25_weight}, "
                f"embedding={config.pre_screening.embedding_weight}"
            )

            jd_text = Path(args.jd).read_text(encoding="utf-8")

            pre_screener = ResumePreScreener(
                embedding_model=config.pre_screening.embedding_model,
                bm25_weight=config.pre_screening.bm25_weight,
                embedding_weight=config.pre_screening.embedding_weight,
                bm25_min_score=config.pre_screening.bm25_min_score,
                bm25_min_overlap_ratio=config.pre_screening.bm25_min_overlap_ratio,
                embedding_cache_size=config.pre_screening.embedding_cache_size,
            )
            ranked = pre_screener.rank_resumes(jd_text, args.resumes_path, extensions=extensions)
            filtered = pre_screener.filter_to_top_k(ranked, top_k)
            filtered_doc_specs = pre_screener.build_document_specs(filtered)
            pre_screen_report = pre_screener.build_report(ranked, top_k)

            resume_count = len(filtered)
            print("\n  Pre-screening results:")
            print(f"    Total candidates:   {pre_screen_report['total_candidates']}")
            print(f"    BM25 filtered out:  {pre_screen_report['bm25_filtered']}")
            print(f"    Selected (top-{top_k}):    {len(filtered)}")
            if filtered:
                print(
                    f"    Best match:         {filtered[0].common_name} "
                    f"(score={filtered[0].combined_score:.4f})"
                )
                if len(filtered) > 1:
                    print(
                        f"    Worst selected:     {filtered[-1].common_name} "
                        f"(score={filtered[-1].combined_score:.4f})"
                    )

    synthesis_top_n = (
        max(resume_count, DEFAULT_SYNTHESIS_TOP_N) if resume_count > 0 else DEFAULT_SYNTHESIS_TOP_N
    )

    prompts = (
        get_planning_screening_prompts(template_path=args.planning_prompts)
        if args.planning
        else get_static_screening_prompts(template_path=args.static_prompts)
    )

    planning_client_type = args.planning_client if args.planning else None

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
    has_data = filtered_doc_specs is not None

    write_yaml(
        manifest_path / "manifest.yaml",
        build_manifest_yaml(
            manifest_name,
            args.planning,
            len(prompts),
            has_documents=has_documents,
            has_clients=planning_client_type is not None,
            has_data=has_data,
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
            planning=args.planning,
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

    if planning_client_type:
        planning_client_config = config.get_client_type_config(planning_client_type)
        if planning_client_config is None:
            available = config.get_available_client_types()
            print(f"\nError: Unknown planning client type '{planning_client_type}'.")
            print(f"  Available: {', '.join(available)}")
            return 1
        for p in prompts:
            if p.phase == "planning":
                p.client = "planner"
        write_yaml(
            manifest_path / "clients.yaml",
            {
                "clients": [
                    {
                        "name": "planner",
                        "client_type": planning_client_type,
                        "api_key_env": planning_client_config.api_key_env,
                        "model": planning_client_config.default_model,
                    }
                ]
            },
        )

    if args.jd:
        jd_doc = create_jd_document(args.jd)
        docs_list = [jd_doc]
        if filtered_doc_specs is not None:
            docs_list.extend(filtered_doc_specs)
            write_yaml(
                manifest_path / "data.yaml",
                {
                    "batches": [
                        {
                            "id": i,
                            "batch_name": r["reference_name"],
                            "candidate_name": r["common_name"],
                            "_documents": f'["{r["reference_name"]}"]',
                        }
                        for i, r in enumerate(filtered_doc_specs, start=1)
                    ]
                },
            )
        write_yaml(
            manifest_path / "documents.yaml",
            build_documents_yaml(docs_list),
        )
        if pre_screen_report is not None:
            write_yaml(
                manifest_path / "pre_screening_report.yaml",
                pre_screen_report,
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
        if args.pre_screen is not None and pre_screen_report:
            print(
                f"Resumes:         {pre_screen_report['total_candidates']} discovered, "
                f"{resume_count} after pre-screening (baked in)"
            )
        else:
            print(f"Resumes:         {resume_count} discovered (injected at runtime)")
    else:
        print("Resumes:         inject at runtime (--documents-path)")
    print(f"Prompts:         {prompt_summary}")
    print(
        f"Scoring:         {'Auto-derived from planning phase' if args.planning else 'Static (5 criteria)'}"
    )
    print(f"Synthesis:       {len(synthesis)} prompts")
    print(f"Client:          {client_type}")
    if planning_client_type:
        print(f"Planning client: {planning_client_type} (via named client 'planner')")
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
        if filtered_doc_specs is not None:
            print("\nRun with:")
            print(f"  python scripts/manifest_run.py {manifest_path} -c 5")
        else:
            print("\nRun with:")
            print(
                f"  python scripts/manifest_run.py {manifest_path} --documents-path ./resumes/ -c 1"
            )
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
