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
from src.orchestrator.manifest import ManifestOrchestrator

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
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console logging (logs to file only)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

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
        print(f"\nManifest validated: {manifest_dir}")
        print(f"Source workbook: {manifest_data.get('source_workbook')}")
        print(f"Config: {workbook_config}")
        print(f"Prompts loaded: {len(prompts)}")
        for p in prompts[:10]:
            print(f"  - Seq {p.get('sequence')}: {p.get('prompt_name', '(unnamed)')}")
        if len(prompts) > 10:
            print(f"  ... and {len(prompts) - 10} more")
        return 0

    client_type = workbook_config.get("client") or args.client
    client = get_client(client_type, workbook_config)

    progress = ProgressIndicator(len(prompts), show_names=True)

    orchestrator = ManifestOrchestrator(
        manifest_dir=manifest_dir,
        client=client,
        concurrency=args.concurrency,
        progress_callback=progress.update,
    )

    print(f"\nStarting orchestration with concurrency={args.concurrency}")
    print(f"Client type: {client_type}")
    print(f"Total prompts: {len(prompts)}")
    print(f"Output directory: {output_dir}")
    print()

    parquet_path = orchestrator.run()
    progress.finish()

    summary = orchestrator.get_summary()

    print("\n" + "=" * 60)
    print("ORCHESTRATION COMPLETE")
    print("=" * 60)
    print(f"Manifest:      {manifest_dir}")
    print(f"Parquet:       {parquet_path}")
    print(f"Concurrency:   {args.concurrency}")
    print(f"Total prompts: {summary['total_prompts']}")
    print(f"Successful:    {summary['successful']}")
    print(f"Failed:        {summary['failed']}")
    print("=" * 60 + "\n")

    print(f"Extract results: python scripts/manifest_extract.py {parquet_path} --save\n")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
