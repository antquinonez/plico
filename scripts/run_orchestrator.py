#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Excel Orchestrator CLI

Usage:
    python scripts/run_orchestrator.py <workbook_path> [--client <client_type>]

Examples:
    # Create new workbook and run
    python scripts/run_orchestrator.py my_prompts.xlsx

    # Run existing workbook
    python scripts/run_orchestrator.py my_prompts.xlsx --client mistral-small

    # Run with parallel execution (4 concurrent calls)
    python scripts/run_orchestrator.py my_prompts.xlsx --concurrency 4

    # Run with logging to file only (quiet mode)
    python scripts/run_orchestrator.py my_prompts.xlsx --quiet

    # Run with auto-discovered documents and a shared document
    python scripts/run_orchestrator.py screening.xlsx \
        --documents-path ./resumes/ --shared-document ./job_description.md -c 1
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
from src.orchestrator import ExcelOrchestrator
from src.orchestrator.explain import build_explain_plan, format_explain, format_prompt_preview
from src.orchestrator.validation import OrchestratorValidator

load_dotenv()

logger = logging.getLogger(__name__)


def main():
    app_config = get_config()
    default_concurrency = app_config.orchestrator.default_concurrency
    max_concurrency = app_config.orchestrator.max_concurrency
    default_client = app_config.get_default_client_type()
    available_clients = app_config.get_available_client_types()

    parser = argparse.ArgumentParser(
        description="Run Excel-based prompt orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("workbook", help="Path to Excel workbook (will be created if not exists)")
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
        "--dry-run", action="store_true", help="Validate workbook without executing"
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
        "Populates documents and batch data at runtime without modifying the workbook.",
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

    workbook_path = args.workbook

    if not os.path.exists(workbook_path):
        logger.info(f"Workbook not found, will create: {workbook_path}")

    from src.orchestrator.workbook_parser import WorkbookParser

    builder = WorkbookParser(workbook_path)

    if not os.path.exists(workbook_path):
        builder.create_template_workbook()
        print(f"\nCreated template workbook: {workbook_path}")
        print("Please edit the 'prompts' sheet to define your prompts, then run again.\n")
        return 0

    builder.validate_workbook()
    workbook_config = builder.load_config()

    if args.dry_run:
        prompts = builder.load_prompts()

        client_names: list[str] = []
        clients_data = builder.load_clients()
        if clients_data:
            client_names = [c.get("name", "") for c in clients_data if c.get("name")]

        doc_names: list[str] = []
        documents_data = builder.load_documents()
        if documents_data:
            doc_names = [
                d.get("reference_name", "") for d in documents_data if d.get("reference_name")
            ]

        batch_data = builder.load_data()
        batch_keys = OrchestratorValidator.extract_batch_keys(batch_data) if batch_data else []

        validator = OrchestratorValidator(
            prompts=prompts,
            config=workbook_config,
            client_names=client_names,
            batch_data_keys=batch_keys,
            doc_ref_names=doc_names,
            available_client_types=available_clients,
        )
        result = validator.validate()

        print(f"\nWorkbook validated: {workbook_path}")
        print(f"Prompts loaded:  {len(prompts)}")

        print()
        print(result.format_report())

        for p in prompts:
            print(f"  Seq {p['sequence']}: {p.get('prompt_name', '(unnamed)')}")

        return 1 if result.has_errors else 0

    if args.explain:
        prompts = builder.load_prompts()
        batch_data = builder.load_data()

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
            if batch_data and args.batch_row is not None:
                idx = args.batch_row
                if 0 <= idx < len(batch_data):
                    batch_row = batch_data[idx]
                else:
                    print(f"Warning: --batch-row {idx} out of range (0-{len(batch_data) - 1})")
            print(format_prompt_preview(target, batch_row=batch_row))
            return 0

        plan = build_explain_plan(
            prompts,
            batch_data=batch_data,
        )
        print(
            format_explain(
                plan,
                title=os.path.basename(workbook_path),
                concurrency=args.concurrency,
            )
        )
        return 0

    client_type = workbook_config.get("client_type") or args.client
    client = get_client(client_type, workbook_config)

    prompts = builder.load_prompts()
    progress = ProgressIndicator(len(prompts), show_names=True)

    orchestrator = ExcelOrchestrator(
        workbook_path=workbook_path,
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
    if args.documents_path:
        print(f"Documents path: {args.documents_path} (auto-discovered)")
    if args.shared_document:
        print(f"Shared document: {args.shared_document}")
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), app_config.logging.directory
    )
    print(f"Log file: {os.path.join(log_dir, app_config.logging.filename)}\n")

    results_sheet = orchestrator.run()
    progress.finish()

    summary = orchestrator.get_summary()

    pre_screen_report = None
    report_path = os.path.splitext(workbook_path)[0] + ".pre_screening_report.yaml"
    if os.path.exists(report_path):
        with open(report_path, encoding="utf-8") as f:
            pre_screen_report = yaml.safe_load(f)

    print("\n" + "=" * 60)
    print("ORCHESTRATION COMPLETE")
    print("=" * 60)
    print(f"Workbook:      {summary['workbook']}")
    print(f"Results sheet: {results_sheet}")
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

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
