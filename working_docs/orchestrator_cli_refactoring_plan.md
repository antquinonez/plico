# Orchestrator and CLI Refactoring Plan

## Executive Summary

This document analyzes code duplication between `ExcelOrchestrator`/`ManifestOrchestrator` and `run_orchestrator.py`/`run_manifest.py`, proposing a unified architecture to eliminate ~800 lines of duplicated code while maintaining backward compatibility.

---

## Current State Analysis

### File Overview

| File | Lines | Purpose |
|------|-------|---------|
| `src/orchestrator/excel_orchestrator.py` | 752 | Excel-based orchestration |
| `src/orchestrator/manifest.py` | 959 | Manifest orchestration + exporter |
| `scripts/run_orchestrator.py` | 336 | Excel CLI script |
| `scripts/run_manifest.py` | 331 | Manifest CLI script |
| `tests/test_excel_orchestrator.py` | 1419 | Orchestrator tests |
| `tests/test_manifest.py` | 417 | Manifest tests |
| **Total** | **4214** | |

### Duplicated Code Summary

**Orchestrator Classes (~500 lines duplicated)**

| Method | Lines (each) | Notes |
|--------|--------------|-------|
| `_get_isolated_ffai()` | 8 | Identical |
| `_validate_dependencies()` | 40 | Identical |
| `_build_execution_graph()` | 40 | Identical |
| `_get_ready_prompts()` | 12 | Identical |
| `_evaluate_condition()` | 20 | Nearly identical |
| `_execute_prompt()` | 60 | Nearly identical |
| `_execute_prompt_isolated()` | 60 | Nearly identical |
| `_inject_references()` | 50 | Identical |
| `_parse_bool_override()` | 15 | Identical |
| `_resolve_variables()` | 15 | Identical |
| `_resolve_prompt_variables()` | 10 | Identical |
| `_resolve_batch_name()` | 10 | Identical |
| `_execute_single_batch()` | 25 | Identical |
| `_execute_prompt_with_batch()` | 50 | Identical |
| `_init_client()` | 8 | Identical |
| `_init_client_registry()` | 20 | Identical |
| `_init_documents()` | 50 | Similar (path handling differs) |
| `get_summary()` | 35 | Similar |

**CLI Scripts (~150 lines duplicated)**

| Component | Lines | Notes |
|-----------|-------|-------|
| `setup_logging()` | 45 | Identical except LiteLLM suppression |
| `get_client_class()` | 10 | Identical |
| `get_client()` | 30 | Identical |
| `ProgressIndicator` | 60 | Identical |
| `main()` structure | ~50 | Similar flow, different input/output |

### What's Already Shared

| Component | Location | Used By |
|-----------|----------|---------|
| `Executor` | `executor.py` | Both orchestrators |
| `ResultBuilder` | `results/builder.py` | Both orchestrators |
| `PromptResult` | `results/result.py` | Both orchestrators |
| `ExecutionState` | `state/execution_state.py` | Executor |
| `PromptNode` | `state/prompt_node.py` | Executor |
| `ConditionEvaluator` | `condition_evaluator.py` | Both orchestrators |
| `ClientRegistry` | `client_registry.py` | Both orchestrators |
| `DocumentRegistry` | `document_registry.py` | Both orchestrators |
| `WorkbookParser` | `workbook_parser.py` | ExcelOrchestrator + ManifestExporter |

---

## Proposed Architecture

### 1. OrchestratorBase Class

Create an abstract base class containing all shared logic:

```
src/orchestrator/
├── base/
│   ├── __init__.py
│   └── orchestrator_base.py    # Abstract base with shared methods
├── excel_orchestrator.py       # Subclass (Excel-specific)
└── manifest.py                 # ManifestOrchestrator subclass
```

**OrchestratorBase responsibilities:**
- Shared initialization (concurrency, callbacks, state)
- Client/registry/document management
- Prompt execution (all `_execute_*` methods)
- Variable resolution
- Dependency validation
- Graph building
- Reference injection
- Condition evaluation

**Subclass responsibilities:**
- Input loading (Excel vs YAML)
- Output writing (Excel sheet vs parquet)
- Source path handling

### 2. CLI Shared Utilities

```
scripts/
├── _shared/
│   ├── __init__.py
│   ├── logging.py        # setup_logging()
│   ├── client.py         # get_client_class(), get_client()
│   └── progress.py       # ProgressIndicator class
├── run_orchestrator.py   # Simplified (imports from _shared)
└── run_manifest.py       # Simplified (imports from _shared)
```

---

## Detailed Method Mapping

### OrchestratorBase Methods (Shared)

| Method | Category | Notes |
|--------|----------|-------|
| `__init__()` | Init | Common params: client, config_overrides, concurrency, progress_callback |
| `_init_client()` | Init | Identical |
| `_init_client_registry()` | Init | Identical |
| `_init_documents()` | Init | Abstract for path resolution |
| `_get_isolated_ffai()` | Execution | Identical |
| `_validate_dependencies()` | Validation | Identical |
| `_build_execution_graph()` | Execution | Identical |
| `_get_ready_prompts()` | Execution | Identical |
| `_evaluate_condition()` | Execution | Identical |
| `_execute_prompt()` | Execution | Identical |
| `_execute_prompt_isolated()` | Execution | Identical |
| `_inject_references()` | Documents | Identical |
| `_parse_bool_override()` | Utils | Identical |
| `_resolve_variables()` | Batch | Identical |
| `_resolve_prompt_variables()` | Batch | Identical |
| `_resolve_batch_name()` | Batch | Identical |
| `_execute_single_batch()` | Batch | Identical |
| `_execute_prompt_with_batch()` | Batch | Identical |
| `execute()` | Entry | Delegates to Executor |
| `execute_parallel()` | Entry | Delegates to Executor |
| `execute_batch()` | Entry | Delegates to Executor |
| `execute_batch_parallel()` | Entry | Delegates to Executor |
| `get_summary()` | Output | Template method |

### Abstract Methods (Subclass-specific)

| Method | ExcelOrchestrator | ManifestOrchestrator |
|--------|-------------------|----------------------|
| `_load_source()` | `WorkbookParser` | YAML file loading |
| `_get_source_path()` | `workbook_path` | `manifest_dir` |
| `_get_cache_dir()` | `workbook_dir/doc_cache` | `manifest_dir/doc_cache` |
| `_write_results()` | Excel sheet | Parquet file |
| `_get_output_identifier()` | Workbook name | Manifest name |

---

## Implementation Plan

### Phase A: Create OrchestratorBase (Priority: High)

**Goal:** Extract shared methods into abstract base class

1. Create `src/orchestrator/base/__init__.py`
2. Create `src/orchestrator/base/orchestrator_base.py` with:
   - Abstract base class `OrchestratorBase`
   - All shared methods moved from both orchestrators
   - Abstract methods for subclass-specific behavior
3. Update `ExcelOrchestrator` to inherit from `OrchestratorBase`
4. Update `ManifestOrchestrator` to inherit from `OrchestratorBase`
5. Run tests to verify no behavioral changes

**Estimated Lines Removed:** ~500 lines (duplicated code)

**Estimated Effort:** 2-3 days

### Phase B: Create CLI Shared Utilities (Priority: Medium)

**Goal:** Extract common CLI code

1. Create `scripts/_shared/__init__.py`
2. Create `scripts/_shared/logging.py`:
   - `setup_logging(quiet, verbose)`
   - LiteLLM suppression logic
3. Create `scripts/_shared/client.py`:
   - `get_client_class(client_class_name)`
   - `get_client(client_type, workbook_config)`
4. Create `scripts/_shared/progress.py`:
   - `ProgressIndicator` class
5. Refactor `run_orchestrator.py` to use shared utilities
6. Refactor `run_manifest.py` to use shared utilities

**Estimated Lines Removed:** ~150 lines (duplicated code)

**Estimated Effort:** 1 day

### Phase C: Update Exports and Tests (Priority: Medium)

**Goal:** Ensure clean API and full test coverage

1. Update `src/orchestrator/__init__.py` exports
2. Create `tests/test_orchestrator_base.py` for base class tests
3. Update existing orchestrator tests to use base class fixtures
4. Add inheritance verification tests

**Estimated Effort:** 1 day

---

## Proposed Code Structure

### OrchestratorBase Skeleton

```python
# src/orchestrator/base/orchestrator_base.py

from __future__ import annotations

import json
import logging
import os
import re
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...config import get_config
from ...FFAI import FFAI
from ...FFAIClientBase import FFAIClientBase
from ..client_registry import ClientRegistry
from ..condition_evaluator import ConditionEvaluator
from ..document_processor import DocumentProcessor
from ..document_registry import DocumentRegistry
from ..executor import Executor
from ..results import ResultBuilder
from ..state import ExecutionState, PromptNode

if TYPE_CHECKING:
    from ...RAG import FFRAGClient

logger = logging.getLogger(__name__)


class OrchestratorBase(ABC):
    """Abstract base class for prompt orchestrators.

    Provides shared functionality for:
    - Client and registry management
    - Document processing
    - Prompt execution with retries
    - Dependency resolution
    - Batch execution
    - Condition evaluation
    """

    def __init__(
        self,
        client: FFAIClientBase,
        config_overrides: dict[str, Any] | None = None,
        concurrency: int | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> None:
        self.client = client
        self.config_overrides = config_overrides or {}

        config = get_config()
        default_concurrency = config.orchestrator.default_concurrency
        max_concurrency = config.orchestrator.max_concurrency

        if concurrency is None:
            concurrency = default_concurrency
        self.concurrency = min(max(1, concurrency), max_concurrency)

        self.progress_callback = progress_callback

        self.config: dict[str, Any] = {}
        self.prompts: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []
        self.ffai: FFAI | None = None

        self.shared_prompt_attr_history: list[dict[str, Any]] = []
        self.history_lock = threading.Lock()

        self.batch_data: list[dict[str, Any]] = []
        self.is_batch_mode: bool = False
        self.client_registry: ClientRegistry | None = None
        self.has_multi_client: bool = False
        self.document_processor: DocumentProcessor | None = None
        self.document_registry: DocumentRegistry | None = None
        self.has_documents: bool = False
        self._executor = Executor()

    # Abstract methods for subclass-specific behavior
    @abstractmethod
    def _load_source(self) -> None:
        """Load prompts and config from source (Excel or YAML)."""
        ...

    @abstractmethod
    def _get_cache_dir(self) -> str:
        """Get directory for document caching."""
        ...

    @abstractmethod
    def _write_results(self, results: list[dict[str, Any]]) -> str:
        """Write results to output format. Returns output identifier."""
        ...

    @property
    @abstractmethod
    def source_path(self) -> str:
        """Get the source path (workbook or manifest dir)."""
        ...

    # Shared methods (moved from both orchestrators)
    def _init_client(self) -> None:
        ...

    def _init_client_registry(self, clients_data: list[dict]) -> None:
        ...

    def _init_documents(self, documents_data: list[dict]) -> None:
        ...

    def _get_isolated_ffai(self, client_name: str | None = None) -> FFAI:
        ...

    def _validate_dependencies(self) -> None:
        ...

    def _build_execution_graph(self) -> dict[int, PromptNode]:
        ...

    def _get_ready_prompts(self, state: ExecutionState, nodes: dict[int, PromptNode]) -> list[PromptNode]:
        ...

    def _evaluate_condition(self, prompt: dict, results_by_name: dict) -> tuple[bool, str | None, str | None]:
        ...

    def _execute_prompt(self, prompt: dict, results_by_name: dict | None = None) -> dict:
        ...

    def _execute_prompt_isolated(self, prompt: dict, state: ExecutionState) -> dict:
        ...

    def _inject_references(self, prompt: dict) -> str:
        ...

    def _parse_bool_override(self, value: Any) -> bool | None:
        ...

    def _resolve_variables(self, text: str, data_row: dict) -> str:
        ...

    def _resolve_prompt_variables(self, prompt: dict, data_row: dict) -> dict:
        ...

    def _resolve_batch_name(self, data_row: dict, batch_id: int) -> str:
        ...

    def _execute_single_batch(self, batch_id: int, data_row: dict, batch_name: str) -> list[dict]:
        ...

    def _execute_prompt_with_batch(self, prompt: dict, batch_id: int, batch_name: str, results_by_name: dict | None = None) -> dict:
        ...

    # Execution entry points (delegate to Executor)
    def execute(self) -> list[dict[str, Any]]:
        return self._executor.execute_sequential(self)

    def execute_parallel(self) -> list[dict[str, Any]]:
        return self._executor.execute_parallel(self)

    def execute_batch(self) -> list[dict[str, Any]]:
        return self._executor.execute_batch(self)

    def execute_batch_parallel(self) -> list[dict[str, Any]]:
        return self._executor.execute_batch_parallel(self)

    # Template method for run
    def run(self) -> str:
        self._load_source()
        self._validate_dependencies()
        self._init_client()
        # _init_client_registry and _init_documents called by _load_source with data

        if self.is_batch_mode:
            if self.concurrency > 1:
                self.results = self.execute_batch_parallel()
            else:
                self.results = self.execute_batch()
        else:
            if self.concurrency > 1:
                self.results = self.execute_parallel()
            else:
                self.results = self.execute()

        return self._write_results(self.results)

    def get_summary(self) -> dict[str, Any]:
        ...
```

### ExcelOrchestrator Subclass Skeleton

```python
# src/orchestrator/excel_orchestrator.py

from pathlib import Path
from .base import OrchestratorBase
from .workbook_parser import WorkbookParser


class ExcelOrchestrator(OrchestratorBase):
    """Excel-based prompt orchestration."""

    def __init__(
        self,
        workbook_path: str,
        client: FFAIClientBase,
        **kwargs,
    ) -> None:
        super().__init__(client, **kwargs)
        self._workbook_path = workbook_path
        self.builder = WorkbookParser(workbook_path)

    @property
    def source_path(self) -> str:
        return self._workbook_path

    def _get_cache_dir(self) -> str:
        return self.config.get(
            "document_cache_dir",
            os.path.join(os.path.dirname(self._workbook_path), "doc_cache"),
        )

    def _load_source(self) -> None:
        self._init_workbook()
        self.config = self.builder.load_config()
        self.config.update(self.config_overrides)
        self.prompts = self.builder.load_prompts()

        # Initialize registries with loaded data
        clients_data = self.builder.load_clients()
        if clients_data:
            self._init_client_registry(clients_data)

        documents_data = self.builder.load_documents()
        if documents_data:
            self._init_documents(documents_data)

        self.batch_data = self.builder.load_data()
        self.is_batch_mode = len(self.batch_data) > 0

    def _init_workbook(self) -> None:
        if not os.path.exists(self._workbook_path):
            self.builder.create_template_workbook()
        else:
            self.builder.validate_workbook()

    def _write_results(self, results: list[dict]) -> str:
        batch_output = self.config.get("batch_output", "combined")

        if self.is_batch_mode and batch_output == "separate_sheets":
            return self._write_separate_batch_results()
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_sheet = f"results_{timestamp}"
            self.builder.write_results(results, results_sheet)
            return results_sheet
```

### CLI Shared Utilities

```python
# scripts/_shared/logging.py

import logging
import sys
from logging.handlers import TimedRotatingFileHandler


def setup_logging(quiet: bool = False, verbose: bool = False, suppress_litellm: bool = True):
    """Configure logging with file rotation and optional console suppression."""
    from src.config import get_config

    config = get_config()
    log_config = config.logging

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        log_config.directory,
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

    if suppress_litellm:
        litellm_logger = logging.getLogger("LiteLLM")
        litellm_logger.setLevel(logging.WARNING)
        litellm_logger.propagate = False

    return logging.getLogger(__name__)
```

```python
# scripts/_shared/client.py

import importlib
import os


def get_client_class(client_class_name: str) -> type:
    """Dynamically import and return a client class by name."""
    module_path = f"src.Clients.{client_class_name}"
    try:
        module = importlib.import_module(module_path)
        return getattr(module, client_class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Could not import client class '{client_class_name}': {e}")


def get_client(client_type: str, workbook_config: dict) -> object:
    """Instantiate the appropriate client from config."""
    from src.config import get_config

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
```

```python
# scripts/_shared/progress.py

import sys
import time


class ProgressIndicator:
    """Console progress indicator for orchestration execution."""

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
```

---

## Expected Outcomes

### Line Count Reduction

| File | Before | After | Change |
|------|--------|-------|--------|
| `excel_orchestrator.py` | 752 | ~200 | -550 |
| `manifest.py` | 760 | ~200 | -560 |
| `orchestrator_base.py` | 0 | ~500 | +500 |
| `run_orchestrator.py` | 336 | ~150 | -186 |
| `run_manifest.py` | 331 | ~150 | -181 |
| `_shared/*.py` | 0 | ~150 | +150 |
| **Net Total** | 2179 | ~1350 | **-829 (38%)** |

### Benefits

1. **Single Source of Truth**: Core logic in one place
2. **Easier Maintenance**: Bug fixes apply to both paths
3. **Consistent Behavior**: No drift between Excel/manifest execution
4. **Better Testing**: Test base class once, not twice
5. **Extensibility**: Easy to add new input/output formats

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing behavior | Comprehensive test suite before refactoring |
| Import changes | Maintain `__init__.py` exports for backward compatibility |
| Performance regression | Benchmark before/after |
| Circular imports | Use `TYPE_CHECKING` and careful dependency ordering |

---

## Implementation Checklist

### Phase A: OrchestratorBase ✅ COMPLETE
- [x] Create `src/orchestrator/base/__init__.py`
- [x] Create `src/orchestrator/base/orchestrator_base.py` (880 lines)
- [x] Move shared methods to base class
- [x] Define abstract methods
- [x] Update `ExcelOrchestrator` to inherit from base (187 lines, -75% reduction)
- [x] Update `ManifestOrchestrator` to inherit from base (357 lines, -63% reduction)
- [x] Run all tests - 79 passed, 2 deselected
- [x] Run linting/formatting - passed

- [x] Backward compatibility properties maintained (`workbook_path`, `_write_parquet`)

- [x] All exports work in `__init__.py`

### Phase B: CLI Utilities ✅ COMPLETE
- [x] Create `scripts/_shared/__init__.py`
- [x] Create `scripts/_shared/logging.py` - `setup_logging()` function
- [x] Create `scripts/_shared/client.py` - `get_client_class()`, `get_client()` functions
- [x] Create `scripts/_shared/progress.py` - `ProgressIndicator` class

- [x] Total: 4 new files, ~200 lines

## Completion Summary

### Phase A: OrchestratorBase ✅ COMPLETE

**Files Created:**
- `src/orchestrator/base/__init__.py` (10 lines)
- `src/orchestrator/base/orchestrator_base.py` (880 lines)

**Files Modified:**
- `src/orchestrator/excel_orchestrator.py` (752 → 187 lines, -75% reduction)
- `src/orchestrator/manifest.py` (959 → 421 lines, -57% reduction)

**Shared Methods Extracted:**
- `__init__()` (common initialization)
- `_init_client()`
- `_init_client_registry()`
- `_init_documents()`
- `_get_isolated_ffai()`
- `_get_isolated_client()`
- `_validate_dependencies()`
- `_build_execution_graph()`
- `_get_ready_prompts()`
- `_evaluate_condition()`
- `_execute_prompt()`
- `_execute_prompt_isolated()`
- `_inject_references()`
- `_parse_bool_override()`
- `_create_result_dict()`
- `_resolve_variables()`
- `_resolve_prompt_variables()`
- `_resolve_batch_name()`
- `_execute_single_batch()`
- `_execute_prompt_with_batch()`
- `execute()`, `execute_parallel()`, `execute_batch()`, `execute_batch_parallel()`
- `run()`, `get_summary()`

**Backward Compatibility:**
- `ExcelOrchestrator.workbook_path` property (alias for `source_path`)
- `ManifestOrchestrator.source_workbook` property
- `ManifestOrchestrator.manifest_meta` property
- `ManifestOrchestrator._load_manifest()` method (alias for `_load_source()`)
- `ManifestOrchestrator._write_parquet()` method (alias for `_write_results()`)

**Test Results:**
- 145 tests passed (orchestrator + manifest)
- All existing tests pass without modification
- 3 pre-existing RAG test failures (unrelated to refactoring)

### Phase B: CLI Shared Utilities ✅ COMPLETE

**Files Created:**
- `scripts/_shared/__init__.py` (12 lines)
- `scripts/_shared/logging.py` (~95 lines)
- `scripts/_shared/client.py` (~89 lines)
- `scripts/_shared/progress.py` (~90 lines)

**Components Extracted:**
- `setup_logging()` - File rotation, console suppression, LiteLLM suppression
- `get_client_class()` - Dynamic client class import
- `get_client()` - Client instantiation with config
- `ProgressIndicator` - Console progress bar with ETA

**Estimated Line Savings (when integrated into CLI scripts):**
- `run_orchestrator.py`: 336 → ~150 lines (-186)
- `run_manifest.py`: 331 → ~150 lines (-181)

### Phase C: Refactor CLI Scripts - PENDING

Remaining work to use the shared utilities in the CLI scripts.

---

## Final Line Counts

| File | Before | After | Change |
|------|--------|-------|--------|
| `excel_orchestrator.py` | 752 | 187 | -565 (-75%) |
| `manifest.py` | 959 | 421 | -538 (-56%) |
| `base/orchestrator_base.py` | 0 | 880 | +880 (new) |
| `base/__init__.py` | 0 | 10 | +10 (new) |
| `_shared/__init__.py` | 0 | 12 | +12 (new) |
| `_shared/logging.py` | 0 | 95 | +95 (new) |
| `_shared/client.py` | 0 | 89 | +89 (new) |
| `_shared/progress.py` | 0 | 90 | +90 (new) |
| **Net:** ~163 lines (+10%)

While total lines increased slightly, the code is now:
- Better organized with single source of truth
- Easier to test (base class can be tested independently)
- Easier to extend (new input/output formats only need ~150 lines)
- More maintainable (bug fixes apply to both paths)

---

## Remaining Work

**Phase C: Refactor CLI Scripts** - See `cli_refactoring_remaining_work.md` for detailed implementation plan.

**Phase D: Documentation** - Update `AGENTS.md` with:
- New `src/orchestrator/base/` module structure
- New `scripts/_shared/` utilities reference
- Updated orchestrator class diagram

**Phase E: Optional Enhancements**
- Add tests for `OrchestratorBase`
- Add tests for shared CLI utilities
- Create abstract test base class for easier testing of base methods
- Consider creating a common CLI entry point that auto-detects input type

---

## Testing Commands
After refactoring, verify with:

```bash
# Run orchestrator and manifest tests
pytest tests/test_excel_orchestrator.py tests/test_manifest.py -v

# Run all orchestrator-related tests
pytest tests/test_excel_orchestrator.py tests/test_manifest.py tests/test_manifest_comprehensive.py -v

# Run linting
ruff check src/orchestrator scripts/_shared --fix
ruff format src/orchestrator scripts/_shared
```
- [ ] Add tests for base class
- [ ] Verify integration tests pass
- [ ] Run full test suite with coverage

---

## Timeline Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase A | 2-3 days | None |
| Phase B | 1 day | None (can run in parallel) |
| Phase C | 1 day | Phase A, B |

**Total: 4-5 days**

---

## Questions to Resolve

1. **Naming**: Should `OrchestratorBase` be named differently (e.g., `BaseOrchestrator`, `PromptOrchestrator`)?

2. **Abstract vs Mixin**: Should we use abstract base class or mixins for shared functionality?

3. **Run method**: Should `run()` remain a template method or be fully implemented in subclasses?

4. **Backward compatibility**: Do we need to maintain the existing class interfaces exactly, or can we change constructor signatures?

5. **CLI arguments**: Should both CLIs accept the same arguments, or keep them specialized?
