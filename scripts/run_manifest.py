#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Run Orchestration from Manifest Folder

Usage:
    python scripts/run_manifest.py <manifest_dir> [--client <client_type>] [--concurrency N]

Examples:
    # Run with default settings
    python scripts/run_manifest.py ./manifests/manifest_my_prompts

    # Run with specific client and concurrency
    python scripts/run_manifest.py ./manifests/manifest_my_prompts --client mistral-small -c 4

    # Dry run to validate manifest
    python scripts/run_manifest.py ./manifests/manifest_my_prompts --dry-run

Output:
    Results are written to a parquet file:
    ./outputs/YYYYMMDDHHMMSS_<workbook_basename>.parquet
"""

import argparse
import importlib
import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_config
from src.orchestrator.manifest import ManifestOrchestrator

load_dotenv()


def setup_logging(quiet: bool = False, verbose: bool = False):
    config = get_config()
    log_config = config.logging

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), log_config.directory
    )
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, log_config.filename)

    file_handler = TimedRotatingFileHandler(
        log_file,
        when=log_config.rotation.when,
        interval=log_config.rotation.interval,
        backupCount=log_config.rotation.backup_count,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_config.format))
    root_logger.addHandler(file_handler)

    if not quiet:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_config.format))
        root_logger.addHandler(console_handler)

    return logging.getLogger(__name__)


logger = setup_logging(quiet=False)


def get_client_class(client_class_name: str) -> type:
    module_path = f"src.Clients.{client_class_name}"
    try:
        module = importlib.import_module(module_path)
        return getattr(module, client_class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Could not import client class '{client_class_name}': {e}")


def get_client(client_type: str, workbook_config: dict) -> object:
    app_config = get_config()
    client_type_config = app_config.get_client_type_config(client_type)

    if client_type_config is None:
        available = app_config.get_available_client_types()
        raise ValueError(f"Unknown client type: '{client_type}'. Available types: {available}")

    client_class = get_client_class(client_type_config.client_class)

    api_key_env = workbook_config.get("api_key_env") or client_type_config.api_key_env
    api_key = os.getenv(api_key_env)

    if not api_key:
        raise ValueError(f"API key not found in environment variable: {api_key_env}")

    model = workbook_config.get("model") or client_type_config.default_model
    temperature = workbook_config.get("temperature")
    max_tokens = workbook_config.get("max_tokens")
    system_instructions = workbook_config.get("system_instructions")

    if client_type_config.type == "litellm":
        provider_prefix = client_type_config.provider_prefix
        model_string = f"{provider_prefix}{model}" if provider_prefix else model

        return client_class(
            model_string=model_string,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            system_instructions=system_instructions,
        )
    else:
        return client_class(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_instructions=system_instructions,
        )


class ProgressIndicator:
    def __init__(self, total: int, show_names: bool = True):
        self.total = total
        self.start_time = time.time()
        self.last_update = 0
        self.show_names = show_names
        self.current_names: list = []
        self.completed_names: list = []
        self.running = 0

    def update(
        self,
        completed: int,
        total: int,
        success: int,
        failed: int,
        current_name: str = None,
        running: int = 0,
    ):
        now = time.time()
        if now - self.last_update < 0.1 and completed < total:
            return
        self.last_update = now
        self.running = running

        pct = (completed / total * 100) if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * completed / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        elapsed = now - self.start_time
        if completed > 0 and completed < total:
            eta = (elapsed / completed) * (total - completed)
            if eta > 60:
                eta_str = f"ETA: {int(eta // 60)}m {int(eta % 60)}s"
            else:
                eta_str = f"ETA: {int(eta)}s"
        elif completed == total:
            if elapsed > 60:
                eta_str = f"Done: {int(elapsed // 60)}m {int(elapsed % 60)}s"
            else:
                eta_str = f"Done: {int(elapsed)}s"
        else:
            eta_str = "ETA: --"

        status = f"\r[{bar}] {completed}/{total} ({pct:.0f}%) | ✓{success} ✗{failed}"

        if self.show_names and current_name:
            name_display = current_name[:20] if len(current_name) > 20 else current_name
            status += f" | →{name_display}"

        if running > 0:
            status += f" | ⏳{running}"

        status += f" | {eta_str}"

        sys.stdout.write(status)
        sys.stdout.flush()

    def finish(self):
        sys.stdout.write("\n")
        sys.stdout.flush()


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
        "--dry-run",
        action="store_true",
        help="Validate manifest without executing",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console logging (logs to file only)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

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

    import yaml

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

    print(f"Inspect results: python scripts/inspect_parquet.py {parquet_path}\n")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
