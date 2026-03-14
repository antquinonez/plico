# Excel Orchestrator Refactoring Plan

## Executive Summary

The `ExcelOrchestrator` class (1177 lines, 75% coverage) is the core orchestration engine for AI prompt workflows. This document analyzes test gaps, identifies refactoring opportunities using design patterns, and provides a phased implementation plan.

---

## Current State Analysis

### Coverage Report

```
src/orchestrator/excel_orchestrator.py     596    148    75%
```

### Uncovered Lines by Category

| Category | Lines | Description |
|----------|-------|-------------|
| Multi-client registry | 204-212 | `_init_client_registry()` |
| Document/RAG integration | 218-262, 287-306, 313-325 | `_init_documents()`, `_inject_references()` |
| Boolean parsing | 337-347 | `_parse_bool_override()` |
| Condition dependencies | 432-433 | Graph building with conditions |
| Skipped prompt handling | 501-504, 562-565, 705-710 | Condition evaluates to false |
| Batch error stop mode | 912-913, 916-919, 1025-1029 | `on_batch_error: stop` |
| Parallel execution edge cases | 825-826, 831, 847, 852-860 | Deadlock, exceptions in threads |
| Separate batch sheets | 1119, 1129-1144 | `batch_output: separate_sheets` |
| Summary with conditions | 1162, 1172-1175 | Condition counts, batch failures |

### Code Smells Identified

1. **God Class**: 1177 lines, 30+ methods, 15+ instance variables
2. **Duplicate Result Building**: Result dicts created inline in 4 places (lines 676-696, 860-879, 956-976)
3. **Long Methods**: `execute_parallel()` (93 lines), `execute_batch_parallel()` (148 lines)
4. **Mixed Abstraction Levels**: High-level orchestration mixed with low-level thread management
5. **Feature Envy**: Methods like `_inject_references()` access many external objects

---

## Test Gaps and Required Tests

### 1. Multi-Client Registry Tests

```python
class TestExcelOrchestratorMultiClient:
    def test_init_client_registry_loads_clients(self):
        """Test that client registry is initialized from workbook."""

    def test_execute_with_named_client(self):
        """Test executing prompt with specific client from registry."""

    def test_fallback_to_default_client(self):
        """Test fallback when named client not found."""
```

### 2. Document/Reference Injection Tests

```python
class TestExcelOrchestratorDocuments:
    def test_init_documents_creates_registry(self):
        """Test document registry initialization."""

    def test_inject_references_basic(self):
        """Test basic document reference injection."""

    def test_inject_references_missing_document_raises(self):
        """Test error when referenced document not found."""

    def test_inject_semantic_query_with_rag(self):
        """Test semantic search query injection."""

    def test_inject_semantic_query_fallback_on_error(self):
        """Test fallback to references when semantic search fails."""
```

### 3. Boolean Override Tests

```python
class TestExcelOrchestratorBoolParsing:
    def test_parse_bool_from_string_true(self):
        """Test parsing 'true', 'yes', '1' as True."""

    def test_parse_bool_from_string_false(self):
        """Test parsing 'false', 'no', '0' as False."""

    def test_parse_bool_from_bool(self):
        """Test passthrough of boolean values."""

    def test_parse_bool_invalid_returns_none(self):
        """Test invalid values return None."""
```

### 4. Condition Evaluation Tests

```python
class TestExcelOrchestratorConditions:
    def test_execute_skips_when_condition_false(self):
        """Test that prompts are skipped when condition is false."""

    def test_condition_dependencies_in_graph(self):
        """Test that condition references are added to dependency graph."""

    def test_condition_error_captured(self):
        """Test that condition evaluation errors are captured."""

    def test_summary_includes_condition_count(self):
        """Test that summary includes prompts_with_conditions."""
```

### 5. Batch Execution Edge Cases

```python
class TestExcelOrchestratorBatchEdgeCases:
    def test_batch_error_stop_mode(self):
        """Test that on_batch_error: stop halts execution."""

    def test_batch_output_separate_sheets(self):
        """Test batch_output: separate_sheets creates multiple sheets."""

    def test_batch_summary_with_failures(self):
        """Test that summary includes batches_with_failures."""
```

### 6. Parallel Execution Edge Cases

```python
class TestExcelOrchestratorParallelEdgeCases:
    def test_parallel_deadlock_detection(self, caplog):
        """Test that deadlock is detected and logged."""

    def test_parallel_exception_handling(self):
        """Test that exceptions in threads are captured properly."""

    def test_parallel_skipped_count(self):
        """Test that skipped prompts are counted correctly."""
```

---

## Design Pattern Recommendations

### 1. Strategy Pattern for Execution Modes

**Problem**: Four execution methods (`execute`, `execute_parallel`, `execute_batch`, `execute_batch_parallel`) with overlapping logic.

**Solution**: Extract execution strategy interface.

```python
from abc import ABC, abstractmethod

class ExecutionStrategy(ABC):
    @abstractmethod
    def execute(self, orchestrator: ExcelOrchestrator) -> list[dict[str, Any]]:
        ...

class SequentialStrategy(ExecutionStrategy):
    def execute(self, orchestrator) -> list[dict[str, Any]]:
        ...

class ParallelStrategy(ExecutionStrategy):
    def execute(self, orchestrator) -> list[dict[str, Any]]:
        ...

class BatchSequentialStrategy(ExecutionStrategy):
    def execute(self, orchestrator) -> list[dict[str, Any]]:
        ...

class BatchParallelStrategy(ExecutionStrategy):
    def execute(self, orchestrator) -> list[dict[str, Any]]:
        ...

# In ExcelOrchestrator
def _get_execution_strategy(self) -> ExecutionStrategy:
    if self.is_batch_mode:
        return BatchParallelStrategy() if self.concurrency > 1 else BatchSequentialStrategy()
    return ParallelStrategy() if self.concurrency > 1 else SequentialStrategy()
```

**Benefits**:
- Each strategy in its own file (Single Responsibility)
- Easy to add new execution modes
- Testable in isolation

### 2. Builder Pattern for Result Objects

**Problem**: Result dictionaries built inline in 4+ places with inconsistent fields.

**Solution**: Create a `ResultBuilder` class.

```python
@dataclass
class PromptResult:
    sequence: int
    prompt_name: str | None
    prompt: str
    response: str | None
    status: str  # pending, success, failed, skipped
    attempts: int
    error: str | None
    # ... other fields

class ResultBuilder:
    def __init__(self, prompt: dict[str, Any], batch_id: int | None = None, batch_name: str | None = None):
        self._prompt = prompt
        self._batch_id = batch_id
        self._batch_name = batch_name
        self._result = self._initialize()

    def _initialize(self) -> PromptResult:
        ...

    def with_response(self, response: str) -> ResultBuilder:
        self._result.response = response
        self._result.status = "success"
        return self

    def with_error(self, error: str, attempts: int) -> ResultBuilder:
        self._result.error = error
        self._result.attempts = attempts
        self._result.status = "failed"
        return self

    def as_skipped(self, condition_result: Any, condition_error: str | None) -> ResultBuilder:
        self._result.status = "skipped"
        self._result.condition_result = condition_result
        self._result.condition_error = condition_error
        return self

    def build(self) -> PromptResult:
        return self._result
```

**Benefits**:
- Consistent result structure
- Fluent API for building results
- Single place to add new fields

### 3. Template Method Pattern for Initialization

**Problem**: `run()` method has complex initialization sequence that's hard to test.

**Solution**: Extract initialization into template method.

```python
class OrchestratorInitializer:
    def __init__(self, orchestrator: ExcelOrchestrator):
        self.orchestrator = orchestrator

    def initialize(self) -> None:
        self._init_workbook()
        self._load_config()
        self._load_prompts()
        self._validate_dependencies()
        self._init_client()
        self._init_client_registry()
        self._init_documents()
        self._load_batch_data()

    def _init_workbook(self) -> None:
        ...

    # ... other methods
```

### 4. State Pattern for Execution State

**Problem**: `ExecutionState` dataclass is used but state transitions are implicit.

**Solution**: Make state transitions explicit.

```python
class ExecutionState:
    def __init__(self, nodes: dict[int, PromptNode]):
        self._nodes = nodes
        self._completed: set[int] = set()
        self._in_progress: set[int] = set()
        self._results: list[dict] = []
        self._lock = threading.Lock()

    def start_prompt(self, seq: int) -> bool:
        """Mark prompt as in-progress. Returns False if already running."""
        with self._lock:
            if seq in self._in_progress or seq in self._completed:
                return False
            self._in_progress.add(seq)
            return True

    def complete_prompt(self, seq: int, result: dict) -> None:
        """Mark prompt as completed with result."""
        with self._lock:
            self._in_progress.discard(seq)
            self._completed.add(seq)
            self._results.append(result)

    def get_ready_prompts(self) -> list[PromptNode]:
        """Get prompts whose dependencies are all completed."""
        with self._lock:
            return [n for n in self._nodes.values()
                    if n.sequence not in self._completed
                    and n.sequence not in self._in_progress
                    and n.dependencies.issubset(self._completed)]
```

### 5. Factory Pattern for FFAI Instances

**Problem**: `_get_isolated_ffai()` couples orchestrator to FFAI creation.

**Solution**: Extract factory.

```python
class FFAIFactory:
    def __init__(self, default_client: FFAIClientBase, registry: ClientRegistry | None = None):
        self._default_client = default_client
        self._registry = registry

    def create_isolated(self, client_name: str | None = None,
                        shared_history: list, lock: threading.Lock) -> FFAI:
        client = self._get_client(client_name)
        return FFAI(client, shared_prompt_attr_history=shared_history, history_lock=lock)

    def _get_client(self, client_name: str | None) -> FFAIClientBase:
        if client_name and self._registry:
            return self._registry.clone(client_name)
        return self._default_client.clone()
```

### 6. Facade Pattern for Document Operations

**Problem**: `_inject_references()` handles both semantic search and reference injection.

**Solution**: Create facade that simplifies the interface.

```python
class DocumentFacade:
    def __init__(self, registry: DocumentRegistry | None, has_documents: bool):
        self._registry = registry
        self._has_documents = has_documents

    def inject(self, prompt: dict[str, Any]) -> str:
        """Inject references or semantic search results into prompt."""
        prompt_text = prompt.get("prompt", "")

        if not self._has_documents:
            return prompt_text

        # Try semantic query first
        if semantic_result := self._try_semantic_query(prompt):
            return semantic_result

        # Fall back to references
        return self._inject_references(prompt_text, prompt.get("references", []))
```

---

## Proposed File Structure

```
src/orchestrator/
├── __init__.py
├── excel_orchestrator.py      # Main class (reduced to ~400 lines)
├── workbook_parser.py         # Existing
├── client_registry.py         # Existing
├── condition_evaluator.py     # Existing
├── document_registry.py       # Existing
├── document_processor.py      # Existing
│
├── execution/                  # NEW: Execution strategies
│   ├── __init__.py
│   ├── base.py                 # ExecutionStrategy ABC
│   ├── sequential.py           # SequentialStrategy
│   ├── parallel.py             # ParallelStrategy
│   ├── batch_sequential.py     # BatchSequentialStrategy
│   └── batch_parallel.py       # BatchParallelStrategy
│
├── results/                    # NEW: Result handling
│   ├── __init__.py
│   ├── result.py               # PromptResult dataclass
│   └── builder.py              # ResultBuilder
│
├── state/                      # NEW: Execution state
│   ├── __init__.py
│   ├── execution_state.py      # Enhanced ExecutionState
│   └── prompt_node.py          # PromptNode dataclass
│
└── initialization/             # NEW: Initialization logic
    ├── __init__.py
    └── initializer.py          # OrchestratorInitializer
```

---

## Phased Implementation Plan

### Phase 1: Test Coverage (Priority: High)
**Goal**: Increase coverage from 75% to 90%

1. Add multi-client registry tests
2. Add document/reference injection tests
3. Add boolean parsing tests
4. Add condition evaluation edge case tests
5. Add batch execution edge case tests
6. Add parallel execution edge case tests

**Estimated Effort**: 2-3 days
**Files Modified**: `tests/test_excel_orchestrator.py` (add ~30 new tests)

### Phase 2: Extract Result Builder (Priority: High)
**Goal**: Eliminate duplicate result building code

1. Create `PromptResult` dataclass
2. Create `ResultBuilder` class
3. Refactor all 4 result creation sites to use builder
4. Update tests

**Estimated Effort**: 1-2 days
**Files Created**: `src/orchestrator/results/result.py`, `src/orchestrator/results/builder.py`
**Files Modified**: `src/orchestrator/excel_orchestrator.py`

### Phase 3: Extract Execution Strategies (Priority: Medium)
**Goal**: Decompose execution methods

1. Create `ExecutionStrategy` ABC
2. Extract `SequentialStrategy`
3. Extract `ParallelStrategy`
4. Extract `BatchSequentialStrategy`
5. Extract `BatchParallelStrategy`
6. Update `run()` to use strategy pattern
7. Add strategy-specific tests

**Estimated Effort**: 3-4 days
**Files Created**: `src/orchestrator/execution/*.py`
**Files Modified**: `src/orchestrator/excel_orchestrator.py`

### Phase 4: Extract State Management (Priority: Medium)
**Goal**: Improve thread safety and testability

1. Move `PromptNode` to separate file
2. Enhance `ExecutionState` with explicit state transitions
3. Add state transition logging
4. Add state-specific tests

**Estimated Effort**: 1-2 days
**Files Created**: `src/orchestrator/state/*.py`
**Files Modified**: `src/orchestrator/excel_orchestrator.py`, execution strategies

### Phase 5: Extract Facade Patterns (Priority: Low)
**Goal**: Simplify complex interfaces

1. Create `DocumentFacade`
2. Create `FFAIFactory`
3. Update orchestrator to use facades

**Estimated Effort**: 1-2 days
**Files Created**: `src/orchestrator/facades/*.py`
**Files Modified**: `src/orchestrator/excel_orchestrator.py`

---

## Expected Outcomes

| Metric | Before | After Phase 3 |
|--------|--------|---------------|
| excel_orchestrator.py lines | 1177 | ~400 |
| Test coverage | 75% | 90%+ |
| Execution methods | 4 in one class | 4 separate classes |
| Result building sites | 4 inline | 1 builder |
| Max method length | 148 lines | ~50 lines |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing behavior | Comprehensive test suite before refactoring |
| Performance regression | Benchmark execution times before/after |
| Thread safety issues | Add thread-safety tests, use static analysis |
| Circular imports | Careful dependency management, use TYPE_CHECKING |

---

## Next Steps

1. **Complete**: ~~Implement Phase 1 test coverage improvements~~ ✅
2. **Review**: Get stakeholder sign-off on proposed structure
3. **Iterate**: Implement phases 2-5 incrementally with tests at each step

---

## Phase 1 Completion Report

### Tests Added (26 new tests)

| Test Class | Tests | Purpose |
|------------|-------|---------|
| `TestExcelOrchestratorBoolParsing` | 5 | Boolean string parsing |
| `TestExcelOrchestratorConditions` | 4 | Conditional execution, dependencies, errors |
| `TestExcelOrchestratorBatchEdgeCases` | 3 | Batch error modes, output sheets |
| `TestExcelOrchestratorParallelEdgeCases` | 2 | Skipped counts, thread exceptions |
| `TestExcelOrchestratorMultiClient` | 3 | Client registry initialization |
| `TestExcelOrchestratorDocuments` | 4 | Document/reference injection |
| `TestExcelOrchestratorIsolatedFFAI` | 3 | FFAI isolation with/without registry |
| `TestExcelOrchestratorSummaryEdgeCases` | 2 | Summary with skipped/conditions |

### Coverage Improvement

| Metric | Before | After Phase 1 |
|--------|--------|---------------|
| Test count | 38 | **64** |
| Coverage | 75% | **86%** |
| Uncovered lines | 148 | **83** |

### Remaining Uncovered Lines (83 lines)

These require integration tests or specialized mocking:

1. **Document/RAG integration** (lines 218-262, 287-325): Requires real document processing
2. **Multi-client actual switching** (line 170): Requires real client cloning
3. **Parallel execution edge cases** (lines 437, 610, 705-710, 767, 786, 809, 825-826, 831, 852-860): Deadlock detection, thread exceptions
4. **Batch parallel internal paths** (lines 916-919, 986-991, 1027-1029, 1056-1057, 1070-1072): Error handling in parallel batches
5. **Separate batch output** (lines 1109, 1114): Multiple result sheets

### Recommendation

Proceed to **Phase 2: Extract Result Builder** - this will:
- Centralize result dict creation
- Reduce code duplication
- Make future phases easier to implement
