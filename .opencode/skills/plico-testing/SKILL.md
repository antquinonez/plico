---
name: plico-testing
description: Use when writing, reviewing, or enhancing tests for the Plico project. Triggers on test-related tasks including writing new tests, fixing test failures, improving test quality, or auditing test coverage. Load BEFORE writing or modifying any test file.
---

# Plico Testing Principles

Read this before writing or reviewing tests. Tests must verify **correct behavior**, not exercise code paths for coverage. A test that passes without asserting anything meaningful is worse than no test.

## Organization

- Use pytest with class-based test organization
- Place shared fixtures in `conftest.py` — do not copy-paste fixtures across test classes
- Name test files as `test_<module>.py`, classes as `Test<Feature>`, methods as `test_<description>`
- Import modules inside test methods when mocking is needed

## Principles

### TP-1: Assert specific values, not just types

Every test must assert at least one specific, predictable value. `isinstance(result, float)`, `isinstance(result, list)`, and `result is not None` are not sufficient assertions on their own.

Bad:
```python
results = rag_client.search("What is this about?", n_results=5)
assert isinstance(results, list)
```

Good:
```python
results = rag_client.search("What is this about?", n_results=5)
assert len(results) == 5
assert results[0].score > 0.5
```

### TP-2: Assert the semantics, not the implementation

Tests should verify *what* the code computes, not *how* it computes it. If the test would need to change after a correct refactoring, the test is coupled to the wrong thing.

- For scoring/extraction: assert specific score values for known input, not that the regex matched.
- For orchestrator execution: assert prompt execution order, result column values, or condition outcomes — not that a specific private method was called.
- For result dataclasses: assert specific field values, not just that the object exists.

### TP-3: Do not enshrine bugs as expected behavior

If a function returns a wrong result, write the test to assert the **correct** behavior and let it fail. Then fix the source code. Never write a passing test that asserts incorrect output just to gain coverage.

### TP-4: Every edge-case test needs a justification

When testing an edge case (empty input, missing document, malformed JSON), document *why* this edge case matters and what the correct behavior should be. Do not construct pathological inputs just because a code path exists.

### TP-5: Test error paths by asserting the error

Assert the specific exception type and error message content. Do not catch the exception and assert `True`.

Good:
```python
with pytest.raises(ValueError, match="API key not found"):
    client.generate_response("Hello!")
```

### TP-6: Coverage is a finding tool, not a target

Use coverage reports to identify untested code paths, then write tests that verify correct behavior on those paths. Do not write tests whose only purpose is to move the coverage number upward.

### TP-7: Avoid compound weak assertions

Prefer one strong assertion over several weak ones. Use `==` when the input deterministically produces a known result. Use `>=` only when the exact count depends on non-deterministic ordering.

### TP-8: Test observable behavior over internal state

Prefer testing through the public API. Orchestrator lifecycle tests that call private methods (`_init_workbook`, `_load_config`) are acceptable because these represent distinct state transitions with no public API equivalent — but the test must assert the resulting state, not just that no exception was raised.

### TP-9: Use exact assertions on deterministic outputs

When the test input fully determines the output, use `==` not `<=` or `>=`. Use `>=` or `<=` only when the output is genuinely non-deterministic (LLM response content, embedding similarity ordering) or when testing a structural property.

Bad:
```python
count = rag_client.add_document("Some text content")
assert count >= 1
```

Good:
```python
count = rag_client.add_document("Some text content")
assert count == 3  # chunk_size=10 produces exactly 3 chunks
```

### TP-10: Verify expected values empirically

Before writing an exact assertion, run the code in isolation to confirm the expected value. Guessing at counts or numeric results leads to test failures that waste review time.

### TP-11: Correctness over coverage

- **Invariants**: Test bounds, identities, and conservation laws. If composite_score is a weighted average of scores in [1, 10], assert it is in [1, 10].
- **Consistency**: Two APIs computing the same thing must agree.
- **Independent verification**: Verify against independent calculation — not by running the code under test and copying its output.
- **Property tests over single-value tests**: Prefer testing structural properties (ordering, containment, idempotency) when the output has natural invariants.

### TP-12: Mock at the boundary, not the internals

Prefer mocking at the `generate_response` boundary over setting private attributes directly. When public API is not available for configuration needed in tests, prefer adding a constructor parameter to the production code rather than bypassing it with private attribute assignment.

Bad:
```python
rag_client._embeddings = mock_embeddings
rag_client._llm_generate_fn = mock_llm
rag_client._query_expander = None
rag_client._reranker = None
```

Good:
```python
rag_client = FFRAGClient(
    chunking_strategy="recursive",
    search_mode="hybrid",
    embeddings=mock_embeddings,
)
```

### TP-13: Assert DataFrame content, not just structure

Tests that verify DataFrames must check actual cell values, not just that the frame is non-empty or has expected column names.

Bad:
```python
df = get_model_stats_df(ffai)
assert not df.is_empty()
assert "model" in df.columns
```

Good:
```python
df = get_model_stats_df(ffai)
assert not df.is_empty()
assert "model" in df.columns
assert df["model"][0] == "mistral-small-latest"
assert df["count"][0] == 3
```

## Test Commands

```bash
pytest tests/ -v                           # Run all tests (excluding integration)
pytest tests/test_ffai.py -v               # Run single test file
pytest tests/test_ffai.py::TestFFAIInit -v # Run single test class
pytest tests/ --cov=src --cov-report=term-missing  # Run with coverage
inv test                                   # Run tests via invoke
inv test -p tests/test_ffai.py             # Run specific file via invoke
```

## Known Anti-Patterns in the Current Suite

When enhancing tests, watch for these patterns that already exist:

1. **`test_rag.py`**: Heavy use of `>=` where `==` is appropriate (~15 instances). Many tests set private attributes directly instead of using constructor args.
2. **`test_ffai.py`**: DataFrame tests check `is_empty()` and column names but never cell values (~7 instances).
3. **`test_excel_orchestrator.py`**: Tests call private lifecycle methods without asserting resulting state. Workbook construction boilerplate is duplicated across tests.
4. **Integration tests**: Only assert `is not None` for real API responses — should verify response content or structural properties.
5. **Duplicated fixtures**: RAG test fixtures are copy-pasted across 8 test classes (~150 lines of duplication). Extract to `conftest.py`.
