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

    # Run with parallel execution (4 concurrent calls)
    python scripts/run_orchestrator.py my_prompts.xlsx --concurrency 4

    # Run with logging to file only (quiet mode)
    python scripts/run_orchestrator.py my_prompts.xlsx --quiet
"""

import argparse
import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_config
from src.Clients.FFAnthropic import FFAnthropic
from src.Clients.FFAnthropicCached import FFAnthropicCached
from src.Clients.FFAzureCodestral import FFAzureCodestral
from src.Clients.FFAzureDeepSeek import FFAzureDeepSeek
from src.Clients.FFAzureDeepSeekV3 import FFAzureDeepSeekV3
from src.Clients.FFAzureMistral import FFAzureMistral
from src.Clients.FFAzureMistralSmall import FFAzureMistralSmall
from src.Clients.FFAzurePhi import FFAzurePhi
from src.Clients.FFGemini import FFGemini
from src.Clients.FFLiteLLMClient import FFLiteLLMClient
from src.Clients.FFMistral import FFMistral
from src.Clients.FFMistralSmall import FFMistralSmall
from src.Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek
from src.Clients.FFPerplexity import FFPerplexity
from src.orchestrator import ExcelOrchestrator

load_dotenv()


def setup_logging(quiet: bool = False, verbose: bool = False):
    """Configure logging with file rotation and optional console suppression."""
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

CLIENT_MAP = {
    "mistral-small": FFMistralSmall,
    "mistral": FFMistral,
    "anthropic": FFAnthropic,
    "anthropic-cached": FFAnthropicCached,
    "gemini": FFGemini,
    "perplexity": FFPerplexity,
    "nvidia-deepseek": FFNvidiaDeepSeek,
    "azure-mistral": FFAzureMistral,
    "azure-mistral-small": FFAzureMistralSmall,
    "azure-codestral": FFAzureCodestral,
    "azure-deepseek": FFAzureDeepSeek,
    "azure-deepseek-v3": FFAzureDeepSeekV3,
    "azure-phi": FFAzurePhi,
    "litellm": FFLiteLLMClient,
    "litellm-mistral": FFLiteLLMClient,
    "litellm-anthropic": FFLiteLLMClient,
    "litellm-openai": FFLiteLLMClient,
    "litellm-azure": FFLiteLLMClient,
    "litellm-gemini": FFLiteLLMClient,
    "litellm-perplexity": FFLiteLLMClient,
}


def _get_litellm_prefix(client_type: str) -> str:
    """Get LiteLLM provider prefix for a client type from config."""
    config = get_config()
    return config.get_litellm_prefix(client_type)


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


def get_client(client_type: str, config: dict) -> object:
    """Instantiate the appropriate client."""
    client_class = CLIENT_MAP.get(client_type)

    if not client_class:
        raise ValueError(
            f"Unknown client type: {client_type}. Available: {list(CLIENT_MAP.keys())}"
        )

    if client_type.startswith("litellm"):
        provider_prefix = _get_litellm_prefix(client_type)
        model = config.get("model", "gpt-4")
        model_string = f"{provider_prefix}{model}" if provider_prefix else model

        api_key_env = config.get("api_key_env", "MISTRAL_API_KEY")
        api_key = os.getenv(api_key_env)

        if not api_key:
            raise ValueError(f"API key not found in environment variable: {api_key_env}")

        return client_class(
            model_string=model_string,
            api_key=api_key,
            temperature=config.get("temperature"),
            max_tokens=config.get("max_tokens"),
            system_instructions=config.get("system_instructions"),
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
    app_config = get_config()
    default_concurrency = app_config.orchestrator.default_concurrency
    max_concurrency = app_config.orchestrator.max_concurrency

    parser = argparse.ArgumentParser(
        description="Run Excel-based prompt orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("workbook", help="Path to Excel workbook (will be created if not exists)")
    parser.add_argument(
        "--client",
        choices=list(CLIENT_MAP.keys()),
        default="litellm-mistral",
        help="AI client to use (default: litellm-mistral)",
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
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console logging (logs to file only)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    global logger
    logger = setup_logging(quiet=args.quiet, verbose=args.verbose)

    workbook_path = args.workbook

    if not os.path.exists(workbook_path):
        logger.info(f"Workbook not found, will create: {workbook_path}")

    from src.orchestrator.workbook_builder import WorkbookBuilder

    builder = WorkbookBuilder(workbook_path)

    if not os.path.exists(workbook_path):
        builder.create_template_workbook()
        print(f"\nCreated template workbook: {workbook_path}")
        print("Please edit the 'prompts' sheet to define your prompts, then run again.\n")
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

    prompts = builder.load_prompts()
    progress = ProgressIndicator(len(prompts), show_names=True)

    orchestrator = ExcelOrchestrator(
        workbook_path=workbook_path,
        client=client,
        concurrency=args.concurrency,
        progress_callback=progress.update,
    )

    print(f"\nStarting orchestration with concurrency={args.concurrency}")
    print(f"Total prompts: {len(prompts)}")
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), app_config.logging.directory
    )
    print(f"Log file: {os.path.join(log_dir, app_config.logging.filename)}\n")

    results_sheet = orchestrator.run()
    progress.finish()

    summary = orchestrator.get_summary()

    print("\n" + "=" * 60)
    print("ORCHESTRATION COMPLETE")
    print("=" * 60)
    print(f"Workbook:      {summary['workbook']}")
    print(f"Results sheet: {results_sheet}")
    print(f"Concurrency:   {args.concurrency}")
    print(f"Total prompts: {summary['total_prompts']}")
    print(f"Successful:    {summary['successful']}")
    print(f"Failed:        {summary['failed']}")
    print("=" * 60 + "\n")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
