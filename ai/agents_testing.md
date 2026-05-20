# Testing Principles

Extracted from [AGENTS.md](../AGENTS.md). Read this before writing or reviewing tests.

Tests must verify **correct behavior**, not exercise code paths for coverage. A test that passes without asserting anything meaningful is worse than no test — it gives false confidence and makes real bugs harder to spot during review.

## Organization

- Use pytest with class-based test organization
- Place shared fixtures in `conftest.py`
- Name test files as `test_<module>.py`, classes as `Test<Feature>`, methods as `test_<description>`
- Import modules inside test methods when mocking is needed
- Extract duplicated fixtures to `conftest.py` — do not copy-paste fixtures across test classes

```python
class TestFFAIGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(self, mock_ffmistralsmall):
        """Test basic response generation."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        response = ffai.generate_response("Hello!")

        assert response == "This is a test response."
```

## Principles

### TP-1: Assert specific values, not just types

Every test must assert at least one specific, predictable value. `isinstance(result, float)`, `isinstance(result, list)`, and `result is not None` are not sufficient assertions on their own — they would pass even if the code returned garbage.

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

Acceptable uses of type-only assertions: verifying that a factory method returns the correct subclass, or that an error path returns `None` instead of raising.

### TP-2: Assert the semantics, not the implementation

Tests should verify *what* the code computes, not *how* it computes it. If the test would need to change after a correct refactoring (renaming a private method, reordering internal steps), the test is coupled to the wrong thing.

- For scoring/extraction: assert specific score values for a known input, not that the extraction regex matched.
- For orchestrator execution: assert prompt execution order, result column values, or condition outcomes — not that a specific private method was called.
- For result dataclasses: assert specific field values, not just that the object exists.

### TP-3: Do not enshrine bugs as expected behavior

If a function returns a wrong or nonsensical result, write the test to assert the **correct** behavior and let it fail. Then fix the source code. Never write a passing test that asserts incorrect output just to gain coverage on a code path.

Example: if `extract_score('{"score": "NaN"}')` silently returns `0.0`, do not write `assert result == 0.0`. Instead, either fix the source to reject NaN and assert `ValueError`, or skip the test with a comment explaining the known bug.

### TP-4: Every edge-case test needs a justification

When testing an edge case (empty input, missing document, zero-length collection, malformed JSON), the test must document *why* this edge case matters and what the correct behavior should be. Do not construct pathological inputs just because a code path exists.

Good:
```python
def test_search_empty_index():
    """Searching an empty index returns no results, not an error."""
    results = rag_client.search("anything", n_results=5)
    assert results == []
```

Bad:
```python
def test_search_empty():
    results = rag_client.search("anything")
    assert isinstance(results, list)
```

### TP-5: Test error paths by asserting the error

When testing that invalid input raises an exception, assert the specific exception type and, where practical, the error message content. Do not catch the exception and assert `True`.

Good:
```python
with pytest.raises(ValueError, match="API key not found"):
    client.generate_response("Hello!")
```

Bad:
```python
try:
    client.generate_response("Hello!")
    assert False, "should have raised"
except ValueError:
    pass
```

### TP-6: Coverage is a finding tool, not a target

Use coverage reports to identify untested code paths, then write tests that verify correct behavior on those paths. Do not write tests whose only purpose is to move the coverage number upward. If a code path cannot be tested with a meaningful assertion, it is acceptable to leave it uncovered rather than add a vacuous test.

### TP-7: Avoid compound weak assertions

Prefer one strong assertion over several weak ones. A test that asserts `len(results) == 5` is stronger than a test that asserts `isinstance(results, list)`. A test that asserts `results[0].score == pytest.approx(0.95)` (when the input deterministically produces that score) is strongest.

Use `>=` when the exact count depends on non-deterministic internal ordering. Use `==` when the input deterministically produces a known result.

### TP-8: Test observable behavior over internal state

Prefer testing through the public API. Directly accessing private attributes (`_embeddings`, `_llm_generate_fn`, `_vector_store`) is acceptable for coverage of internal logic that cannot be observed through public methods, but the test must still assert specific values on those internals, not just their existence or type.

Orchestrator lifecycle tests that call private methods (`_init_workbook`, `_load_config`, `_build_execution_graph`) are acceptable because these methods represent distinct state transitions with no public API equivalent — but the test must assert the resulting state, not just that no exception was raised.

### TP-9: Use exact assertions on deterministic outputs

When the test input fully determines the output (a specific workbook with 3 prompts, a fixed scoring rubric, a known document), use `==` not `<=` or `>=`. Range assertions on deterministic values are weaker than necessary — they would pass even if the implementation returned 0 or an arbitrary large number.

Use `>=` or `<=` only when the output is genuinely non-deterministic (LLM response content, embedding similarity ordering) or when testing a structural property (e.g., "all scores are in [1, 10]").

Bad:
```python
count = rag_client.add_document("Some text content")
assert count >= 1  # passes for 0 chunks, which would be a bug
```

Good:
```python
count = rag_client.add_document("Some text content")
assert count == 3  # "Some text content" with chunk_size=10 produces exactly 3 chunks
```

### TP-10: Verify expected values empirically

Before writing an exact assertion, run the code in isolation to confirm the expected value. Guessing at counts, lengths, or numeric results leads to test failures that waste review time. This is especially important for chunking strategies, scoring rubrics, and condition evaluation where the output depends on parsing logic, token boundaries, or weight calculations.

### TP-11: Correctness over coverage

Every test must verify that the code produces the *right* result, not just *any* result. When writing tests:

- **Invariants**: Test bounds, identities, and conservation laws. If composite_score is a weighted average of scores in [1, 10], assert it is in [1, 10]. If token counts must be non-negative, assert it.
- **Consistency**: Two APIs computing the same thing must agree. If scoring extracts `"skills_match": 8` from a response, the composite_score must reflect that value with the correct weight.
- **Independent verification**: When asserting exact values, verify against independent calculation — not by running the code under test and copying its output. A test that asserts `result == run_code_and_print(result)` is a tautology.
- **Property tests over single-value tests**: Prefer testing structural properties (ordering, containment, monotonicity, idempotency) over single-value assertions when the output has natural invariants.

### TP-12: Mock at the boundary, not the internals

Prefer mocking at the `generate_response` boundary over setting private attributes directly. If you must set internals (e.g., for testing a code path unreachable through the constructor), use constructor arguments or public setter methods when available.

Mocking at the wrong level couples tests to implementation details and produces false confidence — the test passes because the mock returns what you expect, not because the integration is correct.

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

When public API is not available for configuration needed in tests, prefer adding a constructor parameter or setter method to the production code rather than bypassing it with private attribute assignment.

### TP-13: Assert DataFrame content, not just structure

Plico uses Polars DataFrames extensively in results. Tests that verify DataFrames must check actual cell values, not just that the frame is non-empty or has expected column names. A DataFrame with the right columns but wrong data is a silent bug.

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

When exact values depend on LLM output (integration tests), assert structural properties instead: column types, non-negative counts, monotonic ordering, or that specific expected columns contain non-null values.
