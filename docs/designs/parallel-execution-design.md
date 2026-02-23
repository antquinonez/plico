# Parallel Execution Design

## Overview

Add parallel execution capability to the Excel Orchestrator to significantly reduce execution time for large workbooks with independent prompts.

## Goals

1. **Performance** - Reduce total execution time by running independent prompts concurrently
2. **Configurability** - Allow users to control concurrency level via CLI
3. **Visibility** - Show real-time progress during execution
4. **Safety** - Maintain correctness with dependency-aware scheduling

## Non-Goals

- Async/await implementation (using threads for simplicity)
- Distributed execution across multiple machines
- Dynamic scaling of concurrency based on response times

## Current Architecture

```
ExcelOrchestrator.run()
    └── execute()
        └── for each prompt (sequential):
            └── _execute_prompt()
                └── ffai.generate_response()
```

## Proposed Architecture

```
ExcelOrchestrator.run()
    └── execute_parallel(concurrency=2)
        └── _build_execution_graph()     # NEW: Analyze dependencies
        └── ThreadPoolExecutor
            └── _execute_prompt() for each ready prompt
        └── Progress indicator updates
```

## Key Components

### 1. Dependency Graph Analysis

Build a directed acyclic graph (DAG) of prompt dependencies:

```
Sequence 1 (context)     → no deps → can run immediately
Sequence 2 (problem)     → no deps → can run immediately  
Sequence 3 (solution)    → deps: [context, problem] → wait for 1,2
Sequence 4 (prioritize)  → deps: [solution] → wait for 3
```

**Levels:**
- Level 0: Prompts with no dependencies
- Level 1: Prompts depending only on Level 0
- Level N: Prompts depending only on levels < N

### 2. Thread-Safe Execution

Each thread gets its own FFAI instance to avoid shared state issues:

```python
class ExcelOrchestrator:
    def execute_parallel(self, max_workers: int = 2) -> List[Dict]:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit ready prompts, collect results
```

### 3. Progress Indicator

Real-time progress bar in CLI:

```
Executing prompts: [████████░░░░░░░░░░░░] 12/30 (40%) | ETA: 45s
```

## Data Structures

### Execution Graph

```python
@dataclass
class PromptNode:
    sequence: int
    prompt: Dict[str, Any]
    dependencies: Set[int]  # sequence numbers of dependencies
    level: int              # execution level (0 = no deps)
```

### Execution State

```python
@dataclass 
class ExecutionState:
    completed: Set[int]           # completed sequence numbers
    in_progress: Set[int]         # currently running
    pending: List[PromptNode]     # not yet started
    results: Dict[int, Dict]      # sequence -> result
```

## Concurrency Control

### Default: 2 workers

Conservative default that:
- Provides meaningful speedup
- Avoids overwhelming most API rate limits
- Works well on typical machines

### User Configuration

```bash
python scripts/run_orchestrator.py workbook.xlsx --concurrency 4
```

### Max Concurrency

- Minimum: 1 (sequential, current behavior)
- Maximum: 10 (hard limit for safety)
- Default: 2

## Progress Indicator

### Format

```
Executing: [████████░░░░░░░░░░░░] 12/30 (40%) | Success: 11 | Failed: 0 | Running: 2
```

### Update Frequency

- Update after each prompt completion
- Clear and rewrite on same line (using `\r`)

### Colors (optional, using colorama)

- Green: Success count
- Red: Failed count  
- Yellow: Running count

## Error Handling

### Failed Prompts

- Failed prompts don't block dependents if dependency allows
- If dependency was required, dependent prompts fail fast
- All errors captured in results

### Thread Safety

- Each prompt execution uses isolated state
- Results collected thread-safely
- Progress updates use lock

## CLI Changes

### New Argument

```
--concurrency, -c INTEGER  Maximum concurrent API calls (default: 2, max: 10)
```

### Help Text Update

```
Usage: run_orchestrator.py [OPTIONS] WORKBOOK

Options:
  --client TEXT              AI client to use  [default: mistral-small]
  --concurrency, -c INTEGER  Max concurrent calls  [default: 2]
  --dry-run                  Validate without executing
  --verbose                  Enable debug logging
  --help                     Show this message and exit.
```

## Backward Compatibility

- Sequential execution remains default when `concurrency=1`
- All existing functionality preserved
- Results format unchanged

## Testing Strategy

### Unit Tests

1. Test dependency graph building
2. Test level calculation
3. Test thread-safe result collection

### Integration Tests

1. Test with 30 independent prompts
2. Test with dependency chains
3. Test with mixed independent/dependent prompts

### Performance Tests

1. Compare execution time: sequential vs parallel (2 workers)
2. Verify correct results in both modes
