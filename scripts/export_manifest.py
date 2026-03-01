#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Export Excel Workbook to Manifest Folder

Usage:
    python scripts/export_manifest.py <workbook_path> [--output <manifest_dir>]

Examples:
    # Export to default manifest directory
    python scripts/export_manifest.py ./workbooks/my_prompts.xlsx

    # Export to custom directory
    python scripts/export_manifest.py ./workbook.xlsx --output ./custom_manifest/

The manifest folder will contain:
    - manifest.yaml   (metadata)
    - config.yaml     (configuration)
    - prompts.yaml    (all prompts)
    - data.yaml       (batch data, if present)
    - clients.yaml    (client configs, if present)
    - documents.yaml  (document refs, if present)
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_config
from src.orchestrator.manifest import WorkbookManifestExporter

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    config = get_config()
    default_manifest_dir = config.paths.manifest_dir

    parser = argparse.ArgumentParser(
        description="Export Excel workbook to YAML manifest folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("workbook", help="Path to Excel workbook")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help=f"Output directory for manifest (default: {default_manifest_dir})",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    workbook_path = args.workbook

    if not os.path.exists(workbook_path):
        logger.error(f"Workbook not found: {workbook_path}")
        return 1

    print(f"\nExporting workbook: {workbook_path}")

    exporter = WorkbookManifestExporter(workbook_path)

    try:
        manifest_path = exporter.export(manifest_dir=args.output)

        manifest_yaml = os.path.join(manifest_path, "manifest.yaml")
        import yaml

        with open(manifest_yaml, encoding="utf-8") as f:
            manifest_data = yaml.safe_load(f)

        print(f"\n{'=' * 60}")
        print("MANIFEST EXPORTED SUCCESSFULLY")
        print(f"{'=' * 60}")
        print(f"Manifest path: {manifest_path}")
        print(f"Source workbook: {manifest_data.get('source_workbook')}")
        print(f"Exported at: {manifest_data.get('exported_at')}")
        print(f"Prompt count: {manifest_data.get('prompt_count')}")
        print("\nContents:")
        print("  - manifest.yaml (metadata)")
        print("  - config.yaml (configuration)")
        print(f"  - prompts.yaml ({manifest_data.get('prompt_count')} prompts)")
        if manifest_data.get("has_data"):
            print("  - data.yaml (batch data)")
        if manifest_data.get("has_clients"):
            print("  - clients.yaml (client configurations)")
        if manifest_data.get("has_documents"):
            print("  - documents.yaml (document references)")
        print(f"\n{'=' * 60}")
        print(f"Run with: python scripts/run_manifest.py {manifest_path} -c 3")
        print(f"{'=' * 60}\n")

        return 0

    except Exception as e:
        logger.error(f"Export failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
