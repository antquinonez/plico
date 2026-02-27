#!/usr/bin/env python3
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
FFClients Invoke Tasks

A Python-based task runner replacing the Makefile. Uses the config system
directly for workbook paths and supports parallel execution.

Usage:
    inv --list                  # Show all available tasks
    inv create                  # Create all test workbooks
    inv run                     # Run orchestrator on all workbooks
    inv run -c 4                # Run with concurrency=4
    inv validate                # Validate all workbook results
    inv all                     # Full pipeline: clean, create, run, validate
    inv basic                   # Create and run basic workbook only

Parallel execution:
    inv create --parallel       # Create workbooks in parallel
    inv run --parallel          # Run workbooks in parallel
"""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from invoke import Context, task

sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config

VENV_ACTIVATION = "source .venv/bin/activate && POLARS_SKIP_CPU_CHECK=1"


def _run_cmd(ctx: Context, cmd: str, capture: bool = False) -> subprocess.CompletedProcess | None:
    """Run a command with virtual environment activated."""
    full_cmd = f"{VENV_ACTIVATION} && {cmd}"
    if capture:
        return subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    ctx.run(full_cmd, echo=False, pty=True)
    return None


def _get_workbook_configs() -> dict[str, tuple[str, str]]:
    """Get workbook configurations from config system.

    Returns:
        Dict mapping workbook name to (path, default_concurrency)
    """
    config = get_config()
    return {
        "basic": (config.sample.workbooks.basic, "3"),
        "multiclient": (config.sample.workbooks.multiclient, "2"),
        "conditional": (config.sample.workbooks.conditional, "3"),
        "documents": (config.sample.workbooks.documents, "1"),
        "batch": (config.sample.workbooks.batch, "3"),
        "max": (config.sample.workbooks.max, "3"),
    }


def _create_single_workbook(name: str) -> tuple[str, bool, str]:
    """Create a single workbook. Used for parallel execution.

    Returns:
        Tuple of (name, success, output/error message)
    """
    script_map = {
        "basic": "scripts/create_sample_workbook.py",
        "multiclient": "scripts/create_sample_workbook_multiclient.py",
        "conditional": "scripts/create_sample_workbook_conditional.py",
        "documents": "scripts/create_sample_workbook_documents.py",
        "batch": "scripts/create_sample_workbook_batch.py",
        "max": "scripts/create_sample_workbook_max.py",
    }

    script = script_map[name]
    cmd = f"{VENV_ACTIVATION} && python {script}"

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        return (name, True, result.stdout)
    else:
        return (name, False, result.stderr or result.stdout)


def _run_single_workbook(name: str, concurrency: str) -> tuple[str, bool, str]:
    """Run orchestrator on a single workbook. Used for parallel execution.

    Returns:
        Tuple of (name, success, output/error message)
    """
    configs = _get_workbook_configs()
    path, default_conc = configs[name]
    conc = concurrency or default_conc

    cmd = f"{VENV_ACTIVATION} && python scripts/run_orchestrator.py {path} -c {conc}"

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        return (name, True, result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    else:
        return (name, False, result.stderr or result.stdout)


# ============================================================================
# MAIN TASKS
# ============================================================================


@task
def help(c: Context) -> None:
    """Show detailed help information."""
    print("""
FFClients Invoke Tasks
======================

A Python-based task runner for managing test workbooks and orchestration.

USAGE:
    inv <task> [options]
    inv --list              # Show all available tasks
    inv --help <task>       # Show help for specific task

MAIN TASKS:
    inv create              # Create all test workbooks
    inv clean               # Remove all test workbooks
    inv run                 # Run orchestrator on all workbooks
    inv validate            # Validate all workbook results
    inv spot-check          # Spot check responses
    inv all                 # Full pipeline: clean, create, run, validate

INDIVIDUAL WORKBOOKS:
    inv basic               # Create and run basic workbook
    inv multiclient         # Create and run multiclient workbook
    inv conditional         # Create and run conditional workbook
    inv documents           # Create and run documents workbook
    inv batch               # Create and run batch workbook
    inv max                 # Create and run max workbook

OPTIONS:
    -c, --concurrency N     # Set parallel execution concurrency (default: varies by workbook)
    --parallel              # Enable parallel execution for create/run tasks
    -q, --quiet             # Suppress detailed output

EXAMPLES:
    inv create --parallel           # Create all workbooks in parallel
    inv run -c 4                    # Run with concurrency=4
    inv run --parallel              # Run all workbooks in parallel
    inv all --parallel              # Full pipeline with parallel execution
    inv basic -c 2                  # Run basic workbook with concurrency=2

CONFIGURATION:
    Workbook paths and client configurations are loaded from config/test.yaml
    Access via: config.test.workbooks.basic, config.test.test_clients, etc.
""")


@task
def create(c: Context, parallel: bool = False, quiet: bool = False) -> None:
    """Create all test workbooks.

    Args:
        parallel: Create workbooks in parallel (faster)
        quiet: Suppress detailed output
    """
    print("Creating test workbooks...")

    workbook_names = ["basic", "multiclient", "max", "documents", "conditional", "batch"]

    if parallel:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(_create_single_workbook, name): name for name in workbook_names
            }

            for future in as_completed(futures):
                name, success, output = future.result()
                if success:
                    if not quiet:
                        print(f"  ✓ {name}")
                else:
                    print(f"  ✗ {name}: {output}")
    else:
        for name in workbook_names:
            _create_single_workbook(name)
            if not quiet:
                print(f"  ✓ {name}")

    print("All workbooks created.")


@task
def clean(c: Context) -> None:
    """Remove all test workbooks."""
    config = get_config()

    paths = [
        config.test.workbooks.basic,
        config.test.workbooks.multiclient,
        config.test.workbooks.conditional,
        config.test.workbooks.documents,
        config.test.workbooks.batch,
        config.test.workbooks.max,
    ]

    print("Removing test workbooks...")
    for path in paths:
        if Path(path).exists():
            Path(path).unlink()
            print(f"  ✓ Removed {path}")
        else:
            print(f"  - Not found: {path}")
    print("All workbooks removed.")


@task(create)
def run(
    c: Context, concurrency: str | None = None, parallel: bool = False, quiet: bool = False
) -> None:
    """Run orchestrator on all workbooks.

    Args:
        concurrency: Override default concurrency for all workbooks
        parallel: Run workbooks in parallel (experimental)
        quiet: Suppress detailed output
    """
    print("Running orchestrator on all workbooks...")

    configs = _get_workbook_configs()
    workbook_names = ["basic", "multiclient", "conditional", "documents", "batch", "max"]

    if parallel:
        with ThreadPoolExecutor(max_workers=min(6, len(workbook_names))) as executor:
            futures = {
                executor.submit(_run_single_workbook, name, concurrency or configs[name][1]): name
                for name in workbook_names
            }

            for future in as_completed(futures):
                name, success, output = future.result()
                if success:
                    if not quiet:
                        print(f"  ✓ {name}")
                else:
                    print(f"  ✗ {name}: {output}")
    else:
        for name in workbook_names:
            path, default_conc = configs[name]
            conc = concurrency or default_conc

            if not quiet:
                print(f"  Running {name}...")

            _run_cmd(c, f"python scripts/run_orchestrator.py {path} -c {conc}")

            if not quiet:
                print(f"  ✓ {name}")

    print("All workbooks processed.")


@task
def validate(c: Context) -> None:
    """Validate all workbook results."""
    print("Validating all workbooks...")
    _run_cmd(c, "python scripts/validation/validate_all.py")


@task
def spot_check(c: Context) -> None:
    """Spot check responses from key prompts."""
    print("Spot checking responses...")
    _run_cmd(c, "python scripts/validation/spot_check.py")


@task(clean, create, run, validate)
def all(c: Context, parallel: bool = False, concurrency: str | None = None) -> None:
    """Full pipeline: clean, create, run, and validate.

    Args:
        parallel: Enable parallel execution for create/run
        concurrency: Override default concurrency
    """
    print("\n" + "=" * 60)
    print("FULL PIPELINE COMPLETE")
    print("=" * 60)


# ============================================================================
# INDIVIDUAL WORKBOOK TASKS
# ============================================================================


@task(create)
def basic(c: Context, concurrency: str = "3") -> None:
    """Create and run basic workbook."""
    config = get_config()
    _run_cmd(
        c, f"python scripts/run_orchestrator.py {config.test.workbooks.basic} -c {concurrency}"
    )


@task(create)
def multiclient(c: Context, concurrency: str = "2") -> None:
    """Create and run multiclient workbook."""
    config = get_config()
    _run_cmd(
        c,
        f"python scripts/run_orchestrator.py {config.test.workbooks.multiclient} -c {concurrency}",
    )


@task(create)
def conditional(c: Context, concurrency: str = "3") -> None:
    """Create and run conditional workbook."""
    config = get_config()
    _run_cmd(
        c,
        f"python scripts/run_orchestrator.py {config.test.workbooks.conditional} -c {concurrency}",
    )


@task(create)
def documents(c: Context) -> None:
    """Create and run documents workbook."""
    config = get_config()
    _run_cmd(c, f"python scripts/run_orchestrator.py {config.test.workbooks.documents}")


@task(create)
def batch(c: Context, concurrency: str = "3") -> None:
    """Create and run batch workbook."""
    config = get_config()
    _run_cmd(
        c, f"python scripts/run_orchestrator.py {config.test.workbooks.batch} -c {concurrency}"
    )


@task(create)
def max(c: Context, concurrency: str = "3") -> None:
    """Create and run max workbook."""
    config = get_config()
    _run_cmd(c, f"python scripts/run_orchestrator.py {config.test.workbooks.max} -c {concurrency}")


# ============================================================================
# UTILITY TASKS
# ============================================================================


@task
def config_check(c: Context) -> None:
    """Display current configuration values."""
    config = get_config()

    print("\n" + "=" * 60)
    print("CONFIGURATION")
    print("=" * 60)

    print("\nTest Workbook Paths:")
    print(f"  basic:       {config.test.workbooks.basic}")
    print(f"  multiclient: {config.test.workbooks.multiclient}")
    print(f"  conditional: {config.test.workbooks.conditional}")
    print(f"  documents:   {config.test.workbooks.documents}")
    print(f"  batch:       {config.test.workbooks.batch}")
    print(f"  max:         {config.test.workbooks.max}")

    print("\nTest Defaults:")
    print(f"  model:       {config.test.default_model}")
    print(f"  temperature: {config.test.default_temperature}")
    print(f"  max_tokens:  {config.test.default_max_tokens}")
    print(f"  retries:     {config.test.default_retries}")

    print("\nTest Clients:")
    for name, client_cfg in config.test.test_clients.items():
        print(f"  {name}:")
        print(f"    client_type:  {client_cfg['client_type']}")
        print(f"    temperature:  {client_cfg['temperature']}")
        print(f"    max_tokens:   {client_cfg['max_tokens']}")

    print("\nOrchestrator:")
    print(f"  default_concurrency: {config.orchestrator.default_concurrency}")
    print(f"  max_concurrency:     {config.orchestrator.max_concurrency}")


@task
def lint(c: Context) -> None:
    """Run linting (ruff)."""
    c.run("ruff check src tests", pty=True)


@task
def format(c: Context) -> None:
    """Run code formatting (ruff format)."""
    c.run("ruff format src tests", pty=True)


@task
def test(c: Context, path: str = "tests", verbose: bool = False) -> None:
    """Run tests.

    Args:
        path: Test path (default: tests)
        verbose: Enable verbose output
    """
    v_flag = "-v" if verbose else ""
    c.run(f"python -m pytest {path} {v_flag} --ignore=tests/integration", pty=True)


@task
def test_all(c: Context) -> None:
    """Run all tests including integration tests."""
    c.run("python -m pytest tests -v", pty=True)


# Namespace for better help organization
ns = {
    "help": help,
    "create": create,
    "clean": clean,
    "run": run,
    "validate": validate,
    "spot-check": spot_check,
    "all": all,
    "basic": basic,
    "multiclient": multiclient,
    "conditional": conditional,
    "documents": documents,
    "batch": batch,
    "max": max,
    "config-check": config_check,
    "lint": lint,
    "format": format,
    "test": test,
    "test-all": test_all,
}
