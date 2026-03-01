# Shared History Architecture Design

> **Status: ✅ IMPLEMENTED**
>
> This design has been fully implemented in `src/FFAI.py` and `src/orchestrator/excel_orchestrator.py`.
> The implementation supports `shared_prompt_attr_history` and `history_lock` parameters for
> thread-safe cross-client history sharing during parallel execution.

## Problem Statement

When using multiple AI clients within a single workbook execution, prompts need to reference results from previously executed prompts regardless of which client executed them. The current implementation isolates FFAI history per-client, breaking cross-client history references.

### Example Scenario

```
Prompt 1 (client="fast"):      "What is 2+2?" → Response: "4" (stored as step1)
Prompt 2 (client="detailed"):  "What is 3+3?" → Response: "6" (stored as step2)
Prompt 3 (client=default):     "Add step1 and step2" with history=["step1", "step2"]
                               → MUST find BOTH step1 AND step2
```

### Current Behavior (Broken)

Each FFAI instance has its own `OrderedPromptHistory`, so:
- step1 is stored in FFAI_fast.history
- step2 is stored in FFAI_detailed.history
- FFAI_default can't find either → WARNING: No matching entries

### Desired Behavior

All FFAI instances share a single `OrderedPromptHistory`:
- step1 stored in shared_history
- step2 stored in shared_history
- FFAI_default finds both in shared_history ✓

---

## Architecture Analysis

### Component Responsibilities

| Component | Responsibility | Current State | Proposed State |
|-----------|---------------|---------------|----------------|
| **Client** | API communication, per-request state | Cloned per prompt (isolated) | Unchanged |
| **FFAI** | Prompt assembly, response handling | New instance per prompt | New instance with shared history |
| **OrderedPromptHistory** | Stores named prompt interactions | Owned by FFAI | Shared reference |
| **ExcelOrchestrator** | Orchestrates execution | Owns default FFAI | Owns shared history |

### State Separation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STATE SEPARATION MODEL                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  EXECUTION STATE (Per-Prompt, Isolated)                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Client instance                                                      │   │
│  │   - api_key, model, temperature, max_tokens                          │   │
│  │   - conversation_history (always empty - no accumulation)            │   │
│  │   - HTTP connection                                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  CONVERSATION STATE (Shared Across All Prompts)                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ OrderedPromptHistory (shared reference)                              │   │
│  │   - prompt_attr_history: List of {prompt_name, prompt, response}     │   │
│  │   - Used for declarative context assembly                            │   │
│  │   - Thread-safe via lock                                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Thread Safety Considerations

| Operation | Thread Safety | Mitigation |
|-----------|--------------|------------|
| Read history (context assembly) | Safe under GIL | No lock needed for read |
| Write history (add_interaction) | Needs protection | Lock on write |
| Parallel prompt execution | Safe | DAG ensures dependencies complete first |

**Key insight:** In parallel execution, a prompt's `history` references only prompt_names that have already completed (DAG dependency). So read/write race conditions are minimal. Lock is defense-in-depth.

---

## Implementation Plan

### Phase 1: FFAI Changes

**File: `src/FFAI.py`**

1. Add `shared_history` parameter to `__init__`
2. Add `_history_lock` attribute for thread-safe writes
3. Modify `add_interaction()` to use lock when writing

```python
def __init__(self, client, shared_history=None, history_lock=None):
    self.client = client
    self.ordered_history = shared_history if shared_history else OrderedPromptHistory()
    self._history_lock = history_lock
    # ... rest of init

def add_interaction(self, prompt, response, ...):
    # ... build interaction dict ...

    if self._history_lock:
        with self._history_lock:
            self.ordered_history.add_interaction(...)
    else:
        self.ordered_history.add_interaction(...)
```

### Phase 2: ExcelOrchestrator Changes

**File: `src/orchestrator/excel_orchestrator.py`**

1. Add `self.shared_history` and `self.history_lock` in `__init__`
2. Modify `_get_isolated_ffai()` helper to pass shared history
3. Update all execution paths to use the helper

```python
def __init__(self, ...):
    # ... existing init ...
    self.shared_history = OrderedPromptHistory()
    self.history_lock = threading.Lock()

def _get_isolated_ffai(self, client_name=None):
    """Get FFAI with isolated client but shared history."""
    isolated_client = self._get_isolated_client(client_name)
    ffai = FFAI(
        isolated_client,
        shared_history=self.shared_history,
        history_lock=self.history_lock
    )
    return ffai
```

### Phase 3: Test Updates

**Unit Tests:**
- Update tests that mock FFAI to handle new parameters
- Add tests for shared history behavior

**Integration Tests:**
- Update `spy_client` fixture if needed
- Add cross-client history test

### Phase 4: Validation

1. Run unit tests
2. Run integration tests
3. Run orchestrator on all workbook types:
   - sample_workbook.xlsx (basic)
   - sample_workbook_batch.xlsx (batch)
   - sample_workbook_multiclient.xlsx (multi-client)
   - sample_workbook_conditional.xlsx (conditional)

---

## API Changes

### FFAI Constructor

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `client` | FFAIClientBase | Required | AI client instance |
| `shared_history` | OrderedPromptHistory | None | Shared history instance (new) |
| `history_lock` | threading.Lock | None | Lock for thread-safe writes (new) |

### Backward Compatibility

- **Existing FFAI usage:** No changes required - creates own history if not provided
- **Existing workbooks:** No changes required - behavior identical
- **Existing orchestrators:** No changes required - orchestrator manages sharing

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Thread deadlock | Low | High | Lock only on write, short critical section |
| Performance impact | Low | Low | Lock overhead is minimal |
| Breaking existing FFAI usage | Very Low | Medium | Backward compatible API |
| Memory growth in long workflows | Low | Low | History already accumulates, no change |

---

## Success Criteria

1. ✅ Cross-client history references work (step1 from "fast" visible to default)
2. ✅ All existing unit tests pass
3. ✅ All integration tests pass
4. ✅ All workbook types execute successfully
5. ✅ No performance regression in parallel execution
