# Proposal: Conditional Execution & Branching Logic

## Status
Draft

## Summary
Enable prompts to conditionally execute based on the results of previous prompts, allowing sophisticated workflow control without writing code.

## Motivation
Currently, every prompt in the `prompts` sheet executes sequentially (or in parallel where dependencies allow). There's no way to:
- Skip a prompt if a previous step failed
- Take different paths based on previous responses
- Implement error recovery branches

Users who need conditional logic must either:
1. Split into multiple workbooks and orchestrate externally
2. Accept that all prompts run regardless of prior outcomes
3. Write custom Python code

## Proposed Design

### New Column: `condition`

Add an optional `condition` column to the `prompts` sheet that defines when a prompt should execute.

```
| sequence | prompt_name | prompt | history | condition |
|----------|-------------|--------|---------|-----------|
| 1 | fetch | Get the latest data | | |
| 2 | parse | Extract key metrics | ["fetch"] | {{fetch.status}} == "success" |
| 3 | retry | The fetch failed. Try again. | | {{fetch.status}} != "success" |
| 4 | summarize | Summarize the metrics | ["parse"] | {{parse.status}} == "success" |
```

### Condition Syntax

Conditions reference previous prompt results using `{{prompt_name.property}}` syntax:

| Property | Description | Example |
|----------|-------------|---------|
| `status` | Execution status ("success" or "failed") | `{{step1.status}} == "success"` |
| `response` | The response text | `"error" in {{step2.response}}` |
| `attempts` | Number of retry attempts | `{{step1.attempts}} < 3` |
| `error` | Error message (if failed) | `{{step1.error}} != ""` |

### Supported Operators

```
== !=                    Equality (string/number)
> < >= <=               Comparison (numbers)
in not in               Substring containment
and or not              Boolean logic
```

### Condition Evaluation

Conditions are evaluated at runtime, just before prompt execution:

```python
def _should_execute(self, prompt: Dict, completed_results: Dict) -> bool:
    if "condition" not in prompt or not prompt["condition"]:
        return True  # No condition = always execute
    
    condition = prompt["condition"]
    
    # Resolve {{name.property}} references
    resolved = self._resolve_condition_variables(condition, completed_results)
    
    # Safely evaluate the expression
    return self._evaluate_condition(resolved)
```

### Workbook Example: Error Handling Branch

```
=== config sheet ===
model: mistral-small-2503
max_retries: 2

=== prompts sheet ===
| seq | name | prompt | history | condition |
|-----|------|--------|---------|-----------|
| 1 | fetch | Retrieve the user profile for ID 123 | | |
| 2 | analyze | Analyze this profile for risk factors | ["fetch"] | {{fetch.status}} == "success" |
| 3 | fallback | Profile fetch failed. Provide generic advice. | | {{fetch.status}} == "failed" |
| 4 | report | Create a summary report | ["analyze", "fallback"] | {{analyze.status}} == "success" or {{fallback.status}} == "success" |
```

In this example:
- If `fetch` succeeds → `analyze` runs, `fallback` skips
- If `fetch` fails → `analyze` skips, `fallback` runs
- `report` runs if either branch succeeded

### Results Sheet Output

Skipped prompts are recorded with status `skipped`:

| sequence | prompt_name | prompt | response | status | condition_eval |
|----------|-------------|--------|----------|--------|----------------|
| 1 | fetch | Retrieve... | {...} | success | |
| 2 | analyze | Analyze... | Risk factors: ... | success | True |
| 3 | fallback | Profile... | | skipped | False |

## Implementation Details

### Phase 1: Basic Conditions

1. Add `condition` column to prompts schema (optional)
2. Implement condition parser and evaluator
3. Add `_should_execute()` check in execution loop
4. Record condition evaluation result in output

### Phase 2: Advanced Features

1. Support for `contains` / `matches` operators on response text
2. Numeric comparisons on response length or extracted values
3. Custom functions (e.g., `{{len(analyze.response)}} > 100`)

### Security Consideration

Condition evaluation must be sandboxed. Never use `eval()` directly on user input.

```python
import ast
import operator

ALLOWED_OPERATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.Gt: operator.gt,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
}

def _evaluate_condition(self, expr: str) -> bool:
    """Safely evaluate a condition expression."""
    tree = ast.parse(expr, mode='eval')
    return self._eval_node(tree.body)
```

## Alternatives Considered

### 1. Excel IF Formulas
Let users write Excel formulas in a condition column.

**Pros:** No new syntax to learn
**Cons:** Can't reference runtime results (status, response); Excel formulas evaluate at edit time, not execution time

### 2. Separate "flows" Sheet
Define branching logic in a separate sheet with source/target edges.

**Pros:** Visual graph representation
**Cons:** More complex, harder to read for simple cases

### 3. Python Callbacks
Allow inline Python in conditions.

**Pros:** Maximum flexibility
**Cons:** Security risk, breaks the "no-code" goal

## Open Questions

1. Should conditions support regex matching on responses? (e.g., `{{fetch.response}} matches /error:\w+/`)
2. Should there be a `max_executions` limit to prevent infinite loops if we add loop constructs later?
3. How should conditions interact with parallel execution? (Blocked dependencies still block, but skipped dependencies shouldn't)

## Success Metrics

- Users can implement error recovery patterns without code
- Condition syntax is intuitive for Excel users (close to Excel formula syntax)
- No security vulnerabilities from condition evaluation
