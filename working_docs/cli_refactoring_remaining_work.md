# CLI Script Refactoring - Remaining Work

## Overview

This document outlines the remaining work to refactor `run_orchestrator.py` and `run_manifest.py` to use the shared utilities created in Phase B.

## Current State

### Files to Refactor

| File | Current Lines | Target Lines | Reduction |
|------|---------------|--------------|-----------|
| `scripts/run_orchestrator.py` | 336 | ~150 | -186 |
| `scripts/run_manifest.py` | 331 | ~150 | -181 |

### Shared Utilities Available

Location: `scripts/_shared/`

```
scripts/_shared/
├── __init__.py           # Exports all utilities
├── logging.py            # setup_logging(quiet, verbose, suppress_litellm)
├── client.py             # get_client_class(name), get_client(type, config)
└── progress.py           # ProgressIndicator class
```

## Current Code Duplication

### run_orchestrator.py (336 lines)

| Section | Lines | Will Use |
|---------|-------|----------|
| `setup_logging()` | 45 | `_shared.logging.setup_logging` |
| `get_client_class()` | 10 | `_shared.client.get_client_class` |
| `get_client()` | 30 | `_shared.client.get_client` |
| `ProgressIndicator` | 60 | `_shared.progress.ProgressIndicator` |
| `main()` | 100 | Simplified (keep only Excel-specific logic) |

### run_manifest.py (331 lines)

| Section | Lines | Will Use |
|---------|-------|----------|
| `setup_logging()` | 45 | `_shared.logging.setup_logging` |
| `get_client_class()` | 10 | `_shared.client.get_client_class` |
| `get_client()` | 30 | `_shared.client.get_client` |
| `ProgressIndicator` | 60 | `_shared.progress.ProgressIndicator` |
| `main()` | 100 | Simplified (keep only manifest-specific logic) |

## Proposed Refactored Structure

### run_orchestrator.py (Target: ~150 lines)

```python
#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""Excel Orchestrator CLI - Refactored version using shared utilities."""

import argparse
import logging
import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _shared import get_client, ProgressIndicator, setup_logging
from src.config import get_config
from src.orchestrator import ExcelOrchestrator

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
    )
    parser.add_argument("workbook", help="Path to Excel workbook")
    parser.add_argument(
        "--client",
        choices=available_clients,
        default=default_client,
        help=f"AI client to use (default: {default_client})",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=default_concurrency,
        help=f"Maximum concurrent API calls (default: {default_concurrency})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate without executing")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress console output")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    global logger
    logger = setup_logging(quiet=args.quiet, verbose=args.verbose)

    # Create workbook if not exists
    from src.orchestrator.workbook_parser import WorkbookParser
    builder = WorkbookParser(args.workbook)

    if not os.path.exists(args.workbook):
        builder.create_template_workbook()
        print(f"\nCreated template workbook: {args.workbook}")
        print("Edit the 'prompts' sheet and run again.\n")
        return 0

    # Load config and validate
    builder.validate_workbook()
    workbook_config = builder.load_config()

    if args.dry_run:
        prompts = builder.load_prompts()
        print(f"\nWorkbook validated: {args.workbook}")
        print(f"Prompts: {len(prompts)}")
        for p in prompts[:10]:
            print(f"  - Seq {p['sequence']}: {p.get('prompt_name', '(unnamed)')}")
        return 0

    # Get client and run
    client_type = workbook_config.get("client_type") or args.client
    client = get_client(client_type, workbook_config)

    prompts = builder.load_prompts()
    progress = ProgressIndicator(len(prompts))

    orchestrator = ExcelOrchestrator(
        workbook_path=args.workbook,
        client=client,
        concurrency=args.concurrency,
        progress_callback=progress.update,
    )

    print(f"\nStarting orchestration (concurrency={args.concurrency})")
    print(f"Client: {client_type}, Prompts: {len(prompts)}\n")

    results_sheet = orchestrator.run()
    progress.finish()

    summary = orchestrator.get_summary()

    print("\n" + "=" * 60)
    print("ORCHESTRATION COMPLETE")
    print("=" * 60)
    print(f"Workbook:      {args.workbook}")
    print(f"Results sheet: {results_sheet}")
    print(f"Total:         {summary['total_prompts']}")
    print(f"Successful:    {summary['successful']}")
    print(f"Failed:        {summary['failed']}")
    print("=" * 60 + "\n")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

### run_manifest.py (Target: ~150 lines)

```python
#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""Manifest Orchestrator CLI - Refactored version using shared utilities."""

import argparse
import logging
import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _shared import get_client, ProgressIndicator, setup_logging
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
    )
    parser.add_argument("manifest", help="Path to manifest folder")
    parser.add_argument(
        "--client",
        choices=available_clients,
        default=default_client,
        help=f"AI client to use (default: {default_client})",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=default_concurrency,
        help=f"Maximum concurrent API calls (default: {default_concurrency})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate without executing")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress console output")
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

    # Load manifest for dry-run validation
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
        print(f"Source: {manifest_data.get('source_workbook')}")
        print(f"Prompts: {len(prompts)}")
        for p in prompts[:10]:
            print(f"  - Seq {p.get('sequence')}: {p.get('prompt_name', '(unnamed)')}")
        return 0

    # Get client and run
    client_type = workbook_config.get("client") or args.client
    client = get_client(client_type, workbook_config)

    progress = ProgressIndicator(len(prompts))

    orchestrator = ManifestOrchestrator(
        manifest_dir=manifest_dir,
        client=client,
        concurrency=args.concurrency,
        progress_callback=progress.update,
    )

    print(f"\nStarting orchestration (concurrency={args.concurrency})")
    print(f"Client: {client_type}, Prompts: {len(prompts)}")
    print(f"Output: {output_dir}\n")

    parquet_path = orchestrator.run()
    progress.finish()

    summary = orchestrator.get_summary()

    print("\n" + "=" * 60)
    print("ORCHESTRATION COMPLETE")
    print("=" * 60)
    print(f"Manifest:      {manifest_dir}")
    print(f"Parquet:       {parquet_path}")
    print(f"Total:         {summary['total_prompts']}")
    print(f"Successful:    {summary['successful']}")
    print(f"Failed:        {summary['failed']}")
    print("=" * 60 + "\n")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

## Implementation Checklist

### Step 1: Backup Original Files
```bash
cp scripts/run_orchestrator.py scripts/run_orchestrator.py.backup
cp scripts/run_manifest.py scripts/run_manifest.py.backup
```

### Step 2: Refactor run_orchestrator.py
- [ ] Replace `setup_logging()` with import from `_shared`
- [ ] Replace `get_client_class()` with import from `_shared`
- [ ] Replace `get_client()` with import from `_shared`
- [ ] Replace `ProgressIndicator` with import from `_shared`
- [ ] Simplify imports
- [ ] Run tests: `python scripts/run_orchestrator.py --help`

### Step 3: Refactor run_manifest.py
- [ ] Replace `setup_logging()` with import from `_shared`
- [ ] Replace `get_client_class()` with import from `_shared`
- [ ] Replace `get_client()` with import from `_shared`
- [ ] Replace `ProgressIndicator` with import from `_shared`
- [ ] Simplify imports
- [ ] Run tests: `python scripts/run_manifest.py --help`

### Step 4: Verification
- [ ] Run: `python scripts/run_orchestrator.py <workbook.xlsx> --dry-run`
- [ ] Run: `python scripts/run_manifest.py <manifest_dir> --dry-run`
- [ ] Run: `pytest tests/ -q`
- [ ] Run: `ruff check scripts/ && ruff format scripts/ --check`

### Step 5: Cleanup
- [ ] Remove backup files if all tests pass
- [ ] Update `AGENTS.md` with new CLI script references

## Expected Results

### Line Count Comparison

| File | Before | After | Change |
|------|--------|-------|--------|
| `run_orchestrator.py` | 336 | ~150 | -186 |
| `run_manifest.py` | 331 | ~150 | -181 |
| `_shared/*.py` | 286 | 286 | 0 |
| **Net Total** | 953 | ~586 | **-367 (-38%)** |

### Benefits

1. **Single source of truth** for logging, client creation, progress display
2. **Easier maintenance** - bug fixes in `_shared` apply to both scripts
3. **Consistent behavior** - both CLIs behave identically for shared functionality
4. **Reduced testing surface** - test shared utilities once, not twice

## Potential Issues

### Import Path

The `_shared` directory needs to be importable from the scripts directory. The current approach uses:

```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _shared import ...
```

This assumes scripts are run from the project root or the scripts directory.

Alternative: Use relative imports with `-m` execution:
```bash
python -m scripts.run_orchestrator workbook.xlsx
```

### LiteLLM Suppression

The original `run_orchestrator.py` had extra LiteLLM suppression logic:
```python
if quiet:
    litellm_logger = logging.getLogger("LiteLLM")
    litellm_logger.setLevel(logging.WARNING)
    litellm_logger.propagate = False
```

This is now handled by `setup_logging(suppress_litellm=True)` which is the default.

## Testing Commands

After refactoring, verify with:

```bash
# Help output
python scripts/run_orchestrator.py --help
python scripts/run_manifest.py --help

# Dry run
python scripts/run_orchestrator.py workbooks/test.xlsx --dry-run
python scripts/run_manifest.py manifests/test_manifest --dry-run

# Full test suite
pytest tests/ -q

# Linting
ruff check scripts/ --fix
ruff format scripts/
```

## Notes

- The refactored scripts maintain 100% backward compatibility with CLI arguments
- All existing functionality is preserved
- The shared utilities are already tested indirectly through the orchestrator tests
