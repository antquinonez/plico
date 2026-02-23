# Parallel Execution Implementation Plan

## Phase 1: Core Parallel Execution

### Task 1.1: Add Dependency Graph Analysis
**File:** `src/orchestrator/excel_orchestrator.py`

Add methods to:
- Build dependency graph from prompts
- Calculate execution levels (prompts at same level can run in parallel)
- Identify ready prompts (all dependencies satisfied)

```python
def _build_execution_graph(self) -> Dict[int, PromptNode]:
    """Build dependency graph and assign execution levels."""
    
def _get_ready_prompts(self, completed: Set[int], nodes: Dict[int, PromptNode]) -> List[PromptNode]:
    """Get prompts ready to execute (all deps met)."""
```

### Task 1.2: Implement Parallel Execute Method
**File:** `src/orchestrator/excel_orchestrator.py`

Add `execute_parallel()` method:
- Use `concurrent.futures.ThreadPoolExecutor`
- Thread-safe result collection
- Maintain execution order in results

### Task 1.3: Thread-Safe FFAI Instances
**File:** `src/orchestrator/excel_orchestrator.py`

Each parallel execution needs isolated state:
- Clone client for each thread, OR
- Use thread-local storage, OR
- Create new FFAI per execution (chosen approach)

---

## Phase 2: Progress Indicator

### Task 2.1: Create Progress Bar Module
**File:** `src/orchestrator/progress.py` (NEW)

Simple progress bar with:
- Percentage complete
- Success/Failed counts
- Currently running count
- Single-line update using `\r`

### Task 2.2: Thread-Safe Progress Updates
**File:** `src/orchestrator/progress.py`

Use threading.Lock for:
- Updating counts
- Rendering progress bar

---

## Phase 3: CLI Updates

### Task 3.1: Add Concurrency Argument
**File:** `scripts/run_orchestrator.py`

Add argument:
```python
parser.add_argument(
    "--concurrency", "-c",
    type=int,
    default=2,
    help="Maximum concurrent API calls (default: 2, max: 10)"
)
```

### Task 3.2: Wire Concurrency to Orchestrator
**File:** `scripts/run_orchestrator.py`

Pass concurrency to orchestrator:
```python
orchestrator = ExcelOrchestrator(
    workbook_path=workbook_path,
    client=client,
    concurrency=args.concurrency
)
```

### Task 3.3: Add Progress Callback
**File:** `scripts/run_orchestrator.py`

Pass progress callback to orchestrator for real-time updates.

---

## Phase 4: Test Workbook

### Task 4.1: Create 30-Prompt Test Workbook
**File:** `test_parallel_orchestration.xlsx` (NEW)

Create workbook with:
- 10 prompts at level 0 (no dependencies, fully parallel)
- 10 prompts at level 1 (each depends on one level-0 prompt)
- 10 prompts at level 2 (each depends on one level-1 prompt)

This tests:
- True parallelism (level 0)
- Mixed parallel/sequential (levels 1, 2)
- Dependency chain correctness

---

## Phase 5: Testing & Validation

### Task 5.1: Unit Tests
**File:** `tests/test_parallel_execution.py` (NEW)

Test:
- Dependency graph building
- Level calculation
- Ready prompt identification

### Task 5.2: Integration Test
Run full orchestration with test workbook:
- Verify all 30 prompts complete
- Verify correct results
- Verify order is maintained in output

---

## Implementation Order

1. ✅ Design document
2. ✅ Plan document  
3. ⬜ Task 1.1: Dependency graph analysis
4. ⬜ Task 1.2: Parallel execute method
5. ⬜ Task 2.1: Progress bar module
6. ⬜ Task 3.1 & 3.2: CLI updates
7. ⬜ Task 4.1: Test workbook
8. ⬜ Task 5.2: Integration test

---

## Risk Mitigation

### Risk: Thread Safety Issues
**Mitigation:** Create fresh FFAI instance per prompt execution

### Risk: API Rate Limiting
**Mitigation:** Default concurrency of 2, max of 10

### Risk: Complex Dependencies
**Mitigation:** Validate dependency graph before execution, fail fast on cycles

---

## Success Criteria

1. ✅ 30-prompt workbook completes successfully
2. ✅ Parallel execution faster than sequential (with concurrency > 1)
3. ✅ Results identical between sequential and parallel modes
4. ✅ Progress indicator shows real-time updates
5. ✅ CLI accepts --concurrency argument
