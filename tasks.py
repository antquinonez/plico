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
    inv wb.create               # Create all test workbooks
    inv wb.run                  # Run orchestrator on all workbooks
    inv wb.run -c 4             # Run with concurrency=4
    inv wb.validate             # Validate all workbook results
    inv wb.all                  # Full pipeline: clean, create, run, validate
    inv wb.basic                # Create, run, and validate basic workbook

Parallel execution:
    inv wb.create --parallel    # Create workbooks in parallel
    inv wb.run --parallel       # Run workbooks in parallel

RAG operations:
    inv rag.status              # Show RAG indexing status
    inv rag.clear               # Clear all RAG indexes
    inv rag.rebuild             # Rebuild indexes from workbook
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from invoke import Collection, Context, task

sys.path.insert(0, str(Path(__file__).parent))

from src.config import get_config

IS_WINDOWS = platform.system() == "Windows"
PTY = not IS_WINDOWS

PYTHON_EXE = sys.executable


def _run_cmd(ctx: Context, cmd: str, capture: bool = False) -> subprocess.CompletedProcess | None:
    """Run a command with virtual environment activated."""
    env = os.environ.copy()
    env["POLARS_SKIP_CPU_CHECK"] = "1"

    cmd = cmd.replace("python ", f'"{PYTHON_EXE}" ')

    if capture:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
    ctx.run(cmd, echo=False, pty=PTY, env=env)
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


def _get_create_script(name: str) -> str:
    """Get the create script path for a workbook type."""
    script_map = {
        "basic": "scripts/sample_workbook_basic_create_v001.py",
        "multiclient": "scripts/sample_workbook_multiclient_create_v001.py",
        "conditional": "scripts/sample_workbook_conditional_create_v001.py",
        "documents": "scripts/sample_workbook_documents_create_v001.py",
        "batch": "scripts/sample_workbook_batch_create_v001.py",
        "max": "scripts/sample_workbook_max_create_v001.py",
    }
    return script_map[name]


def _get_validate_script(name: str) -> str:
    """Get the validate script path for a workbook type."""
    script_map = {
        "basic": "scripts/sample_workbook_basic_validate_v001.py",
        "multiclient": "scripts/sample_workbook_multiclient_validate_v001.py",
        "conditional": "scripts/sample_workbook_conditional_validate_v001.py",
        "documents": "scripts/sample_workbook_documents_validate_v001.py",
        "batch": "scripts/sample_workbook_batch_validate_v001.py",
        "max": "scripts/sample_workbook_max_validate_v001.py",
    }
    return script_map[name]


def _create_single_workbook(name: str) -> tuple[str, bool, str]:
    """Create a single workbook. Used for parallel execution.

    Returns:
        Tuple of (name, success, output/error message)
    """
    script = _get_create_script(name)
    cmd = f'"{PYTHON_EXE}" {script}'

    env = os.environ.copy()
    env["POLARS_SKIP_CPU_CHECK"] = "1"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)

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

    cmd = f'"{PYTHON_EXE}" scripts/run_orchestrator.py {path} -c {conc}'

    env = os.environ.copy()
    env["POLARS_SKIP_CPU_CHECK"] = "1"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)

    if result.returncode == 0:
        return (name, True, result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    else:
        return (name, False, result.stderr or result.stdout)


def _validate_single_workbook(name: str) -> tuple[str, bool, str]:
    """Validate a single workbook. Used for parallel execution.

    Returns:
        Tuple of (name, success, output/error message)
    """
    configs = _get_workbook_configs()
    path, _ = configs[name]
    script = _get_validate_script(name)

    cmd = f'"{PYTHON_EXE}" {script} {path}'

    env = os.environ.copy()
    env["POLARS_SKIP_CPU_CHECK"] = "1"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)

    if result.returncode == 0:
        return (name, True, result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    else:
        return (name, False, result.stderr or result.stdout)


# ============================================================================
# MAIN TASKS (root level)
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

WORKBOOK TASKS (inv wb.<task>):
    inv wb.create           # Create all test workbooks
    inv wb.clean            # Remove all test workbooks
    inv wb.run              # Run orchestrator on all workbooks
    inv wb.validate         # Validate all workbook results
    inv wb.spot-check       # Spot check responses
    inv wb.all              # Full pipeline: clean, create, run, validate

INDIVIDUAL WORKBOOKS (create + run + validate):
    inv wb.basic            # Create, run, and validate basic workbook
    inv wb.multiclient      # Create, run, and validate multiclient workbook
    inv wb.conditional      # Create, run, and validate conditional workbook
    inv wb.documents        # Create, run, and validate documents workbook
    inv wb.batch            # Create, run, and validate batch workbook
    inv wb.max              # Create, run, and validate max workbook

RAG TASKS (inv rag.<task>):
    inv rag.status          # Show RAG indexing status
    inv rag.clear           # Clear all RAG indexes
    inv rag.clear-strategy  # Clear specific chunking strategy
    inv rag.rebuild         # Rebuild indexes from workbook
    inv rag.stats           # Show detailed RAG statistics

OTHER TASKS:
    inv lint                # Run linting (ruff)
    inv format              # Run code formatting (ruff format)
    inv test                # Run tests (excludes integration)
    inv test-all            # Run all tests including integration
    inv config-check        # Display current configuration

OPTIONS:
    -c, --concurrency N     # Set parallel execution concurrency (default: varies by workbook)
    --parallel              # Enable parallel execution for create/run tasks
    -q, --quiet             # Suppress detailed output

EXAMPLES:
    inv wb.create --parallel        # Create all workbooks in parallel
    inv wb.run -c 4                 # Run with concurrency=4
    inv wb.run --parallel           # Run all workbooks in parallel
    inv wb.all --parallel           # Full pipeline with parallel execution
    inv wb.basic -c 2               # Run basic workbook with concurrency=2

CONFIGURATION:
    Workbook paths and client configurations are loaded from config/test.yaml
    Access via: config.sample.workbooks.basic, config.sample.sample_clients, etc.
""")


@task
def config_check(c: Context) -> None:
    """Display current configuration values."""
    config = get_config()

    print("\n" + "=" * 60)
    print("CONFIGURATION")
    print("=" * 60)

    print("\nTest Workbook Paths:")
    print(f"  basic:       {config.sample.workbooks.basic}")
    print(f"  multiclient: {config.sample.workbooks.multiclient}")
    print(f"  conditional: {config.sample.workbooks.conditional}")
    print(f"  documents:   {config.sample.workbooks.documents}")
    print(f"  batch:       {config.sample.workbooks.batch}")
    print(f"  max:         {config.sample.workbooks.max}")

    print("\nTest Defaults:")
    print(f"  model:       {config.sample.default_model}")
    print(f"  temperature: {config.sample.default_temperature}")
    print(f"  max_tokens:  {config.sample.default_max_tokens}")
    print(f"  retries:     {config.sample.default_retries}")

    print("\nTest Clients:")
    for name, client_cfg in config.sample.sample_clients.items():
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
    c.run("ruff check src tests", pty=PTY)


@task
def format(c: Context):
    """Run code formatting (ruff format)."""
    c.run("ruff format src tests", pty=PTY)


@task
def test(c: Context, path: str = "tests", verbose: bool = False):
    """Run tests.

    Args:
        path: Test path (default: tests)
        verbose: Enable verbose output
    """
    v_flag = "-v" if verbose else ""
    c.run(f"python -m pytest {path} {v_flag} --ignore=tests/integration", pty=PTY)


@task
def test_all(c: Context):
    """Run all tests including integration tests."""
    c.run("python -m pytest tests -v -m ''", pty=PTY)


# ============================================================================
# WORKBOOK TASKS (wb namespace)
# ============================================================================


@task
def wb_create(c: Context, parallel: bool = False, quiet: bool = False):
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
            _, success, output = _create_single_workbook(name)
            if not quiet:
                if success:
                    print(f"  ✓ {name}")
                else:
                    print(f"  ✗ {name}: {output}")

    print("All workbooks created.")


@task
def wb_clean(c: Context):
    """Remove all test workbooks."""
    config = get_config()

    paths = [
        config.sample.workbooks.basic,
        config.sample.workbooks.multiclient,
        config.sample.workbooks.conditional,
        config.sample.workbooks.documents,
        config.sample.workbooks.batch,
        config.sample.workbooks.max,
    ]

    print("Removing test workbooks...")
    for path in paths:
        if Path(path).exists():
            Path(path).unlink()
            print(f"  ✓ Removed {path}")
        else:
            print(f"  - Not found: {path}")
    print("All workbooks removed.")


@task
def wb_run(c: Context, concurrency: str | None = None, parallel: bool = False, quiet: bool = False):
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
def wb_validate(c: Context, parallel: bool = False, quiet: bool = False):
    """Validate all workbook results using individual validation scripts.

    Args:
        parallel: Validate workbooks in parallel (faster)
        quiet: Suppress detailed output
    """
    print("Validating all workbooks...")

    workbook_names = ["basic", "multiclient", "conditional", "documents", "batch", "max"]

    if parallel:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(_validate_single_workbook, name): name for name in workbook_names
            }

            for future in as_completed(futures):
                name, success, output = future.result()
                if success:
                    if not quiet:
                        print(f"  ✓ {name}")
                else:
                    print(f"  ✗ {name}: {output}")
    else:
        configs = _get_workbook_configs()
        for name in workbook_names:
            path, _ = configs[name]
            script = _get_validate_script(name)

            if not quiet:
                print(f"  Validating {name}...")

            _run_cmd(c, f"python {script} {path}")

            if not quiet:
                print(f"  ✓ {name}")

    print("All workbooks validated.")


@task
def wb_spot_check(c: Context):
    """Spot check responses from key prompts."""
    print("Spot checking responses...")
    _run_cmd(c, "python scripts/validation/spot_check.py")


@task
def wb_all(c: Context, parallel: bool = False, concurrency: str | None = None):
    """Full pipeline: clean, create, run, and validate.

    Args:
        parallel: Enable parallel execution for create/run
        concurrency: Override default concurrency
    """
    wb_clean(c)
    wb_create(c, parallel=parallel)
    wb_run(c, concurrency=concurrency, parallel=parallel)
    wb_validate(c, parallel=parallel)

    print("\n" + "=" * 60)
    print("FULL PIPELINE COMPLETE")
    print("=" * 60)


@task
def wb_basic(c: Context, concurrency: str = "3"):
    """Create, run, and validate basic workbook."""
    config = get_config()
    print("Processing basic workbook...")
    _run_cmd(c, f"python {_get_create_script('basic')}")
    _run_cmd(
        c, f"python scripts/run_orchestrator.py {config.sample.workbooks.basic} -c {concurrency}"
    )
    _run_cmd(c, f"python {_get_validate_script('basic')} {config.sample.workbooks.basic}")
    print("Basic workbook complete!")


@task
def wb_multiclient(c: Context, concurrency: str = "2"):
    """Create, run, and validate multiclient workbook."""
    config = get_config()
    print("Processing multiclient workbook...")
    _run_cmd(c, f"python {_get_create_script('multiclient')}")
    _run_cmd(
        c,
        f"python scripts/run_orchestrator.py {config.sample.workbooks.multiclient} -c {concurrency}",
    )
    _run_cmd(
        c, f"python {_get_validate_script('multiclient')} {config.sample.workbooks.multiclient}"
    )
    print("Multiclient workbook complete!")


@task
def wb_conditional(c: Context, concurrency: str = "3"):
    """Create, run, and validate conditional workbook."""
    config = get_config()
    print("Processing conditional workbook...")
    _run_cmd(c, f"python {_get_create_script('conditional')}")
    _run_cmd(
        c,
        f"python scripts/run_orchestrator.py {config.sample.workbooks.conditional} -c {concurrency}",
    )
    _run_cmd(
        c, f"python {_get_validate_script('conditional')} {config.sample.workbooks.conditional}"
    )
    print("Conditional workbook complete!")


@task
def wb_documents(c: Context):
    """Create, run, and validate documents workbook."""
    config = get_config()
    print("Processing documents workbook...")
    _run_cmd(c, f"python {_get_create_script('documents')}")
    _run_cmd(c, f"python scripts/run_orchestrator.py {config.sample.workbooks.documents}")
    _run_cmd(c, f"python {_get_validate_script('documents')} {config.sample.workbooks.documents}")
    print("Documents workbook complete!")


@task
def wb_batch(c: Context, concurrency: str = "3"):
    """Create, run, and validate batch workbook."""
    config = get_config()
    print("Processing batch workbook...")
    _run_cmd(c, f"python {_get_create_script('batch')}")
    _run_cmd(
        c, f"python scripts/run_orchestrator.py {config.sample.workbooks.batch} -c {concurrency}"
    )
    _run_cmd(c, f"python {_get_validate_script('batch')} {config.sample.workbooks.batch}")
    print("Batch workbook complete!")


@task
def wb_max(c: Context, concurrency: str = "3"):
    """Create, run, and validate max workbook."""
    config = get_config()
    print("Processing max workbook...")
    _run_cmd(c, f"python {_get_create_script('max')}")
    _run_cmd(
        c, f"python scripts/run_orchestrator.py {config.sample.workbooks.max} -c {concurrency}"
    )
    _run_cmd(c, f"python {_get_validate_script('max')} {config.sample.workbooks.max}")
    print("Max workbook complete!")


# ============================================================================
# RAG TASKS (rag namespace)
# ============================================================================


@task
def rag_status(c: Context):
    """Show current RAG indexing status.

    Displays all indexed documents grouped by chunking strategy,
    along with their checksums and last indexed time.
    """
    from src.RAG import FFRAGClient

    print("\n" + "=" * 60)
    print("RAG INDEX STATUS")
    print("=" * 60)

    try:
        rag = FFRAGClient()
        indexed_docs = rag.get_indexed_documents()

        if not indexed_docs:
            print("\nNo documents indexed.")
            return

        by_strategy: dict[str, list[dict]] = {}
        for doc in indexed_docs:
            strategy = doc.get("chunking_strategy", "unknown")
            if strategy not in by_strategy:
                by_strategy[strategy] = []
            by_strategy[strategy].append(doc)

        total_chunks = rag.count()
        print(f"\nTotal chunks: {total_chunks}")
        print(f"Chunking strategies: {len(by_strategy)}")

        for strategy, docs in sorted(by_strategy.items()):
            print(f"\n--- Chunking Strategy: {strategy} ({len(docs)} documents) ---")
            for doc in docs:
                ref = doc.get("reference_name", "unknown")
                checksum = doc.get("document_checksum", "")[:8]
                indexed_at = doc.get("indexed_at", "unknown")
                tags = doc.get("tags", "")
                tags_display = f" tags=[{tags}]" if tags else ""
                print(f"  {ref}: checksum={checksum}... indexed={indexed_at}{tags_display}")

    except ImportError:
        print("\nRAG not available. Ensure chromadb is installed.")
    except Exception as e:
        print(f"\nError accessing RAG index: {e}")


@task
def rag_clear(c: Context, chunking_strategy: str = ""):
    """Clear RAG indexes.

    Args:
        chunking_strategy: Specific chunking strategy to clear (e.g., 'recursive', 'markdown').
                    If empty, clears ALL indexes.

    Examples:
        inv rag.clear                          # Clear all indexes
        inv rag.clear -c recursive             # Clear only 'recursive' indexes
        inv rag.clear -c markdown              # Clear only 'markdown' indexes
    """
    from src.RAG import FFRAGClient

    print("\n" + "=" * 60)
    print("CLEARING RAG INDEXES")
    print("=" * 60)

    try:
        rag = FFRAGClient()

        if chunking_strategy:
            print(f"\nClearing chunking strategy: {chunking_strategy}")
            count = rag.clear_chunking_strategy(chunking_strategy)
            print(f"Cleared {count} documents from chunking strategy '{chunking_strategy}'")
        else:
            print("\nClearing ALL indexes...")
            rag.clear()
            print("All indexes cleared.")

    except ImportError:
        print("\nRAG not available. Ensure chromadb is installed.")
    except Exception as e:
        print(f"\nError clearing indexes: {e}")


@task
def rag_clear_strategy(c: Context, chunking_strategy: str):
    """Clear RAG indexes for a specific chunking strategy only.

    Args:
        chunking_strategy: The chunking strategy to clear (e.g., 'recursive', 'markdown', 'code').

    Examples:
        inv rag.clear-strategy recursive
        inv rag.clear-strategy markdown

    """
    from src.RAG import FFRAGClient

    print("\n" + "=" * 60)
    print("CLEAR RAG INDEXING STRATEGY")
    print("=" * 60)

    if not chunking_strategy:
        print("\nError: chunking_strategy is required")
        print("Usage: inv rag.clear-strategy <chunking_strategy>")
        return

    try:
        rag = FFRAGClient()
        print(f"\nClearing all indexes with strategy: {chunking_strategy}")

        cleared = rag.clear_chunking_strategy(chunking_strategy)
        print(f"Cleared {cleared} documents with chunking_strategy={chunking_strategy}")

    except ImportError:
        print("\nRAG not available. Ensure chromadb is installed.")
    except Exception as e:
        print(f"\nError clearing chunking strategy: {e}")


@task
def rag_rebuild(c: Context, workbook: str = ""):
    """Rebuild RAG indexes from a workbook's documents.

    This re-indexes all documents defined in a workbook's 'documents' sheet.

    Args:
        workbook: Path to workbook. If empty, uses default documents workbook.

    Examples:
        inv rag.rebuild                           # Use default documents workbook
        inv rag.rebuild -w ./my_workbook.xlsx     # Use specific workbook

    """
    from dotenv import load_dotenv

    from src.orchestrator.document_processor import DocumentProcessor
    from src.orchestrator.document_registry import DocumentRegistry
    from src.orchestrator.workbook_parser import WorkbookParser
    from src.RAG import FFRAGClient

    load_dotenv()

    config = get_config()
    workbook_path = workbook or config.sample.workbooks.documents

    print("\n" + "=" * 60)
    print("REBUILDING RAG INDEXES")
    print("=" * 60)
    print(f"\nWorkbook: {workbook_path}")

    if not os.path.exists(workbook_path):
        print(f"\nError: Workbook not found: {workbook_path}")
        return

    try:
        builder = WorkbookParser(workbook_path)
        documents_data = builder.load_documents()

        if not documents_data:
            print("\nNo documents found in workbook.")
            return

        print(f"Found {len(documents_data)} documents to index")

        rag = FFRAGClient()
        processor = DocumentProcessor(
            cache_dir=config.paths.doc_cache,
            rag_client=rag,
        )

        registry = DocumentRegistry(
            documents=documents_data,
            processor=processor,
            workbook_dir=os.path.dirname(workbook_path),
            rag_client=rag,
        )

        registry.validate_documents()

        print("\nIndexing documents...")
        results = registry.index_all_documents(force=True)

        print("\n" + "-" * 40)
        print("RESULTS")
        print("-" * 40)

        total_chunks = 0
        for ref_name, chunks in results.items():
            status = "✓" if chunks > 0 else "✗"
            print(f"  {status} {ref_name}: {chunks} chunks")
            total_chunks += chunks

        print(f"\nTotal: {total_chunks} chunks indexed")
        print(f"Index type: {rag.chunking_strategy}")

    except ImportError as e:
        print(f"\nRAG not available: {e}")
    except Exception as e:
        print(f"\nError rebuilding indexes: {e}")


@task
def rag_stats(c: Context):
    """Show detailed RAG statistics."""
    from src.RAG import FFRAGClient

    print("\n" + "=" * 60)
    print("RAG STATISTICS")
    print("=" * 60)

    try:
        rag = FFRAGClient()
        stats = rag.get_stats()

        print(f"\nCollection: {stats.get('collection_name', 'unknown')}")
        print(f"Persist dir: {stats.get('persist_dir', 'unknown')}")
        print(f"Total chunks: {stats.get('count', 0)}")
        print(f"Embedding model: {stats.get('embedding_model', 'unknown')}")
        print(f"\nChunking strategy: {stats.get('chunking_strategy', 'unknown')}")
        print(f"Chunk size: {stats.get('chunk_size', 0)}")
        print(f"Chunk overlap: {stats.get('chunk_overlap', 0)}")
        print(f"\nSearch mode: {stats.get('search_mode', 'unknown')}")
        print(f"Hierarchical: {stats.get('hierarchical_enabled', False)}")

        indexed_docs = rag.get_indexed_documents()
        strategies = {d.get("chunking_strategy", "unknown") for d in indexed_docs}
        print(
            f"\nChunking strategies in use: {', '.join(sorted(strategies)) if strategies else 'none'}"
        )
        print(f"Documents indexed: {len(indexed_docs)}")

    except ImportError:
        print("\nRAG not available. Ensure chromadb is installed.")
    except Exception as e:
        print(f"\nError getting RAG stats: {e}")


# ============================================================================
# NAMESPACES
# ============================================================================

# Workbook namespace
wb = Collection()
wb.add_task(wb_create, name="create")
wb.add_task(wb_clean, name="clean")
wb.add_task(wb_run, name="run")
wb.add_task(wb_validate, name="validate")
wb.add_task(wb_spot_check, name="spot-check")
wb.add_task(wb_all, name="all")
wb.add_task(wb_basic, name="basic")
wb.add_task(wb_multiclient, name="multiclient")
wb.add_task(wb_conditional, name="conditional")
wb.add_task(wb_documents, name="documents")
wb.add_task(wb_batch, name="batch")
wb.add_task(wb_max, name="max")

# RAG namespace
rag = Collection()
rag.add_task(rag_status, name="status")
rag.add_task(rag_clear, name="clear")
rag.add_task(rag_clear_strategy, name="clear-strategy")
rag.add_task(rag_rebuild, name="rebuild")
rag.add_task(rag_stats, name="stats")

# Root namespace
ns = Collection()
ns.add_task(help)
ns.add_task(config_check, name="config-check")
ns.add_task(lint)
ns.add_task(format)
ns.add_task(test)
ns.add_task(test_all, name="test-all")
ns.add_collection(wb, name="wb")
ns.add_collection(rag, name="rag")
