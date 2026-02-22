#!/usr/bin/env python
"""
Excel Orchestrator CLI

Usage:
    python scripts/run_orchestrator.py <workbook_path> [--client <client_type>]

Examples:
    # Create new workbook and run
    python scripts/run_orchestrator.py my_prompts.xlsx

    # Run existing workbook
    python scripts/run_orchestrator.py my_prompts.xlsx --client mistral-small
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import ExcelOrchestrator
from src.Clients.FFMistralSmall import FFMistralSmall
from src.Clients.FFMistral import FFMistral

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

CLIENT_MAP = {
    "mistral-small": FFMistralSmall,
    "mistral": FFMistral,
}


def get_client(client_type: str, config: dict) -> object:
    """Instantiate the appropriate client."""
    client_class = CLIENT_MAP.get(client_type)

    if not client_class:
        raise ValueError(
            f"Unknown client type: {client_type}. Available: {list(CLIENT_MAP.keys())}"
        )

    api_key_env = config.get("api_key_env", "MISTRALSMALL_KEY")
    api_key = os.getenv(api_key_env)

    if not api_key:
        raise ValueError(f"API key not found in environment variable: {api_key_env}")

    return client_class(
        api_key=api_key,
        model=config.get("model"),
        temperature=config.get("temperature"),
        max_tokens=config.get("max_tokens"),
        system_instructions=config.get("system_instructions"),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run Excel-based prompt orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "workbook", help="Path to Excel workbook (will be created if not exists)"
    )
    parser.add_argument(
        "--client",
        choices=list(CLIENT_MAP.keys()),
        default="mistral-small",
        help="AI client to use (default: mistral-small)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate workbook without executing"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    workbook_path = args.workbook

    if not os.path.exists(workbook_path):
        logger.info(f"Workbook not found, will create: {workbook_path}")

    from src.orchestrator.workbook_builder import WorkbookBuilder

    builder = WorkbookBuilder(workbook_path)

    if not os.path.exists(workbook_path):
        builder.create_template_workbook()
        print(f"\nCreated template workbook: {workbook_path}")
        print(
            "Please edit the 'prompts' sheet to define your prompts, then run again.\n"
        )
        return 0

    builder.validate_workbook()
    config = builder.load_config()

    if args.dry_run:
        prompts = builder.load_prompts()
        print(f"\nWorkbook validated: {workbook_path}")
        print(f"Config: {config}")
        print(f"Prompts loaded: {len(prompts)}")
        for p in prompts:
            print(f"  - Seq {p['sequence']}: {p.get('prompt_name', '(unnamed)')}")
        return 0

    client = get_client(args.client, config)

    orchestrator = ExcelOrchestrator(
        workbook_path=workbook_path,
        client=client,
    )

    results_sheet = orchestrator.run()
    summary = orchestrator.get_summary()

    print("\n" + "=" * 60)
    print("ORCHESTRATION COMPLETE")
    print("=" * 60)
    print(f"Workbook:     {summary['workbook']}")
    print(f"Results sheet: {results_sheet}")
    print(f"Total prompts: {summary['total_prompts']}")
    print(f"Successful:    {summary['successful']}")
    print(f"Failed:        {summary['failed']}")
    print("=" * 60 + "\n")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
