#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Run Orchestration from Manifest Folder

Usage:
    python scripts/manifest_run.py <manifest_dir> [--client <client_type>] [--concurrency N]

Examples:
    # Run with default settings
    python scripts/manifest_run.py ./manifests/manifest_my_prompts

    # Run with specific client and concurrency
    python scripts/manifest_run.py ./manifests/manifest_my_prompts --client mistral-small -c 4

    # Dry run to validate manifest
    python scripts/manifest_run.py ./manifests/manifest_my_prompts --dry-run

    # Run with auto-discovered documents and a shared document
    python scripts/manifest_run.py ./manifests/manifest_screening \
        --documents-path ./resumes/ --shared-document ./job_description.md -c 1

Output:
    Results are written to a parquet file:
    ./outputs/<manifest_name>/<timestamp>.parquet
"""

import argparse
import logging
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from _shared import ProgressIndicator, get_client, setup_logging

from src.config import get_config
from src.orchestrator.explain import build_explain_plan, format_explain, format_prompt_preview
from src.orchestrator.manifest import ManifestOrchestrator
from src.orchestrator.validation import OrchestratorValidator

load_dotenv()

logger = logging.getLogger(__name__)


def main():
    app_config = get_config()
    default_concurrency = app_config.orchestrator.default_concurrency
    max_concurrency = app_config.orchestrator.max_concurrency
    default_client = app_config.get_default_client_type()
    available_clients = app_config.get_available_client_types()
    output_dir = app_config.paths.output_dir

    parser = argparse.ArgumentParser(
        description="Run orchestration from manifest folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("manifest", help="Path to manifest folder")
    parser.add_argument(
        "--client",
        choices=available_clients,
        default=default_client,
        help=f"AI client to use (default: {default_client})",
    )
    parser.add_argument(
        "--concurrency",
        "-c",
        type=int,
        default=default_concurrency,
        help=f"Maximum concurrent API calls (default: {default_concurrency}, max: {max_concurrency})",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate manifest without executing"
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Show execution plan (DAG, dependencies, cost estimate) without executing",
    )
    parser.add_argument(
        "--prompt",
        help="Show resolved prompt preview for a specific prompt_name (requires --explain)",
    )
    parser.add_argument(
        "--batch-row",
        type=int,
        default=None,
        help="Batch row index (0-based) for variable substitution in prompt preview",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console logging (logs to file only)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--documents-path",
        help="Folder path to auto-discover documents. "
        "Populates documents and batch data at runtime without modifying the manifest.",
    )
    parser.add_argument(
        "--shared-document",
        help="Path to a shared document file (e.g., job description, rubric). "
        "Added to the documents registry under a reference name derived from the filename.",
    )
    parser.add_argument(
        "--shared-document-name",
        help="Explicit reference name for the shared document (e.g., 'job_description'). "
        "Required when the filename doesn't match the reference name used in prompts.",
    )

    args = parser.parse_args()

    if args.prompt and not args.explain:
        parser.error("--prompt requires --explain")

    global logger
    logger = setup_logging(quiet=args.quiet, verbose=args.verbose)

    manifest_dir = args.manifest

    if not os.path.isdir(manifest_dir):
        logger.error(f"Manifest directory not found: {manifest_dir}")
        return 1

    manifest_yaml = os.path.join(manifest_dir, "manifest.yaml")
    if not os.path.exists(manifest_yaml):
        logger.error(f"manifest.yaml not found in: {manifest_dir}")
        return 1

    with open(manifest_yaml, encoding="utf-8") as f:
        manifest_data = yaml.safe_load(f)

    config_yaml = os.path.join(manifest_dir, "config.yaml")
    with open(config_yaml, encoding="utf-8") as f:
        workbook_config = yaml.safe_load(f) or {}

    prompts_yaml = os.path.join(manifest_dir, "prompts.yaml")
    with open(prompts_yaml, encoding="utf-8") as f:
        prompts_data = yaml.safe_load(f) or {}

    prompts = prompts_data.get("prompts", [])

    if args.dry_run:
        print(f"\nValidating manifest: {manifest_dir}")

        clients_yaml = os.path.join(manifest_dir, "clients.yaml")
        client_names: list[str] = []
        if os.path.exists(clients_yaml):
            with open(clients_yaml, encoding="utf-8") as f:
                clients_data = yaml.safe_load(f) or {}
            client_names = [
                c.get("name", "") for c in clients_data.get("clients", []) if c.get("name")
            ]

        doc_names: list[str] = []
        if manifest_data.get("has_documents"):
            documents_yaml = os.path.join(manifest_dir, "documents.yaml")
            if os.path.exists(documents_yaml):
                with open(documents_yaml, encoding="utf-8") as f:
                    docs_data = yaml.safe_load(f) or {}
                doc_names = [
                    d.get("reference_name", "")
                    for d in docs_data.get("documents", [])
                    if d.get("reference_name")
                ]

        batch_keys: list[str] = []
        if manifest_data.get("has_data"):
            data_yaml = os.path.join(manifest_dir, "data.yaml")
            if os.path.exists(data_yaml):
                with open(data_yaml, encoding="utf-8") as f:
                    batch_data = yaml.safe_load(f) or {}
                batch_keys = OrchestratorValidator.extract_batch_keys(batch_data.get("batches", []))

        validator = OrchestratorValidator(
            prompts=prompts,
            config=workbook_config,
            manifest_meta=manifest_data,
            client_names=client_names,
            batch_data_keys=batch_keys,
            doc_ref_names=doc_names,
            available_client_types=available_clients,
        )
        result = validator.validate()

        print(f"Source workbook: {manifest_data.get('source_workbook')}")
        print(f"Prompts loaded:  {len(prompts)}")
        if client_names:
            print(f"Clients:        {', '.join(client_names)}")

        print()
        print(result.format_report())

        for p in prompts[:10]:
            print(f"  Seq {p.get('sequence')}: {p.get('prompt_name', '(unnamed)')}")
        if len(prompts) > 10:
            print(f"  ... and {len(prompts) - 10} more")

        return 1 if result.has_errors else 0

    if args.explain:
        if args.prompt:
            target = None
            for p in prompts:
                if p.get("prompt_name") == args.prompt:
                    target = p
                    break
            if not target:
                print(f"Error: prompt '{args.prompt}' not found.")
                print(
                    f"Available: {', '.join(p.get('prompt_name', '') for p in prompts if p.get('prompt_name'))}"
                )
                return 1
            batch_row = None
            if manifest_data.get("has_data") and args.batch_row is not None:
                data_yaml = os.path.join(manifest_dir, "data.yaml")
                if os.path.exists(data_yaml):
                    with open(data_yaml, encoding="utf-8") as f:
                        batch_data = yaml.safe_load(f) or {}
                    batches = batch_data.get("batches", [])
                    idx = args.batch_row
                    if 0 <= idx < len(batches):
                        batch_row = batches[idx]
                    else:
                        print(f"Warning: --batch-row {idx} out of range (0-{len(batches) - 1})")
            print(format_prompt_preview(target, batch_row=batch_row))
            return 0

        plan = build_explain_plan(prompts)

        batch_keys: list[str] = []
        if manifest_data.get("has_data"):
            data_yaml = os.path.join(manifest_dir, "data.yaml")
            if os.path.exists(data_yaml):
                with open(data_yaml, encoding="utf-8") as f:
                    batch_data = yaml.safe_load(f) or {}
                batch_keys = batch_data.get("batches", [])

        if batch_keys:
            plan.has_batch = True
            plan.batch_count = len(batch_keys)

        print(
            format_explain(
                plan,
                title=os.path.basename(manifest_dir),
                concurrency=args.concurrency,
            )
        )
        return 0

    client_type = workbook_config.get("client") or args.client
    client = get_client(client_type, workbook_config)

    progress = ProgressIndicator(len(prompts), show_names=True)

    orchestrator = ManifestOrchestrator(
        manifest_dir=manifest_dir,
        client=client,
        concurrency=args.concurrency,
        progress_callback=progress.update,
        documents_path=args.documents_path,
        shared_document_path=args.shared_document,
        shared_document_name=args.shared_document_name,
    )

    print(f"\nStarting orchestration with concurrency={args.concurrency}")
    print(f"Client type: {client_type}")
    print(f"Total prompts: {len(prompts)}")
    print(f"Output directory: {output_dir}")
    if args.documents_path:
        print(f"Documents path: {args.documents_path} (auto-discovered)")
    if args.shared_document:
        print(f"Shared document: {args.shared_document}")
    print()

    parquet_path = orchestrator.run()
    progress.finish()

    summary = orchestrator.get_summary()

    pre_screen_report = None
    pre_screen_yaml = os.path.join(manifest_dir, "pre_screening_report.yaml")
    if os.path.exists(pre_screen_yaml):
        with open(pre_screen_yaml, encoding="utf-8") as f:
            pre_screen_report = yaml.safe_load(f)

    print("\n" + "=" * 60)
    print("ORCHESTRATION COMPLETE")
    print("=" * 60)
    print(f"Manifest:      {manifest_dir}")
    print(f"Parquet:       {parquet_path}")
    print(f"Concurrency:   {args.concurrency}")

    if pre_screen_report:
        total_discovered = pre_screen_report.get("total_discovered", 0)
        bm25_excluded = pre_screen_report.get("bm25_excluded", 0)
        after_bm25 = pre_screen_report.get("after_bm25", 0)
        top_k_excluded = pre_screen_report.get("top_k_excluded", 0)
        evaluated_by_llm = pre_screen_report.get("evaluated_by_llm", 0)
        print()
        print("Screening Pipeline:")
        print(f"  Discovered:         {total_discovered}")
        print(f"  BM25 excluded:      {bm25_excluded}")
        print(f"  After BM25:         {after_bm25}")
        print(f"  Top-K excluded:     {top_k_excluded}")
        print(f"  Evaluated by LLM:   {evaluated_by_llm}")

    if summary.get("total_batches"):
        candidates_with_aborted_prompts = 0
        if hasattr(orchestrator, "results") and orchestrator.results:
            batch_names_with_abort = set()
            for r in orchestrator.results:
                if r.get("status") == "aborted" and r.get("batch_name"):
                    batch_names_with_abort.add(r["batch_name"])
            candidates_with_aborted_prompts = len(batch_names_with_abort)
        if candidates_with_aborted_prompts > 0:
            print(
                f"  LLM suspended:    {candidates_with_aborted_prompts} candidates had aborted prompts"
            )

    print()
    print(f"Total prompts: {summary['total_prompts']}")
    print(f"Successful:    {summary['successful']}")
    print(f"Aborted:       {summary['aborted']}")
    print(f"Failed:        {summary['failed']}")
    if summary.get("tokens"):
        print(f"Tokens:        {summary['tokens']['total']:,}")
    if summary.get("cost_usd") is not None:
        print(f"Cost:          ${summary['cost_usd']:.6f}")
    print("=" * 60 + "\n")

    print(f"Extract results: python scripts/manifest_extract.py {parquet_path} --save\n")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
