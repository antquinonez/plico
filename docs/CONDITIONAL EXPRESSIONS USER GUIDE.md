# Conditional Expressions User Guide

## Overview

Conditional execution allows prompts to run or skip based on the results of previous prompts. This enables:

- **Branching logic** - Execute different prompts based on response content
- **Error recovery** - Run fallback prompts when previous steps fail
- **Cost optimization** - Skip expensive operations when conditions aren't met
- **Response-dependent processing** - Adapt workflow based on AI outputs

Conditional expressions are written in the optional `condition` column of the `prompts` sheet. The system uses a secure AST-based evaluator—**never** `eval()` or `exec()`—so expressions are safe to use with untrusted input.

---

## Quick Start

Add a `condition` column to your prompts sheet:

| sequence | prompt_name | prompt | history | condition |
|----------|-------------|--------|---------|-----------|
| 1 | fetch | Retrieve data from the API | | |
| 2 | parse | Parse the retrieved data | `["fetch"]` | `{{fetch.status}} == "success"` |
| 3 | fallback | The API call failed. Generate sample data. | | `{{fetch.status}} == "failed"` |

**Result:**
- If `fetch` succeeds → `parse` runs, `fallback` skips
- If `fetch` fails → `parse` skips, `fallback` runs

---

## Workbook Integration

### Prompts Sheet with Condition Column

The `condition` column is optional and can be added to any prompts sheet:

| Column | Required | Description |
|--------|----------|-------------|
| `sequence` | Yes | Execution order (1, 2, 3...) |
| `prompt_name` | Recommended | Name for referencing in history and conditions |
| `prompt` | Yes | The prompt text (supports `{{variable}}` templating) |
| `history` | No | JSON array of prompt_name dependencies |
| `client` | No | Named client from `clients` sheet |
| `condition` | No | Expression determining if prompt should execute |

### Execution Flow

1. **Dependency Resolution** - All `history` references and condition variable references are added to the dependency graph
2. **Condition Evaluation** - Before executing a prompt, its condition (if any) is evaluated
3. **Execute or Skip** - If condition is `true`, prompt executes; if `false`, prompt is skipped with status `"skipped"`
4. **Results Recording** - Both executed and skipped prompts are recorded in the results sheet

### Implicit Dependencies

Condition references automatically become dependencies. If your condition is:

```
{{analyze.status}} == "success"
```

The system ensures `analyze` completes before evaluating this condition—you don't need to add it to the `history` column.

### Results Sheet Columns

When conditions are used, the results sheet includes:

| Column | Description |
|--------|-------------|
| `condition` | The original condition expression |
| `condition_result` | Boolean result of evaluation (`true`/`false`) |
| `condition_error` | Error message if condition failed to evaluate |

---

## Syntax Reference

### Variable References

Access previous prompt results using double-brace syntax:

```
{{prompt_name.property}}
```

- `prompt_name` - The name assigned in the `prompt_name` column
- `property` - A property of the result (see table below)

**Example:**
```
{{fetch.status}} == "success"
```

### Available Properties

| Property | Type | Values | Description |
|----------|------|--------|-------------|
| `status` | string | `"success"`, `"failed"`, `"skipped"` | Execution status of the prompt |
| `response` | string | Any text | The AI's response text (empty string if none) |
| `attempts` | int | 0, 1, 2, ... | Number of retry attempts made |
| `error` | string | Error message or empty string | Error message if the prompt failed |
| `has_response` | bool | `true`, `false` | True if response exists and is non-empty |

### Comparison Operators

| Operator | Syntax | Returns | Example |
|----------|--------|---------|---------|
| Equality | `==` | true if equal | `{{fetch.status}} == "success"` |
| Inequality | `!=` | true if not equal | `{{fetch.status}} != "failed"` |
| Less Than | `<` | true if left < right | `{{retry.attempts}} < 3` |
| Less or Equal | `<=` | true if left ≤ right | `{{retry.attempts}} <= 2` |
| Greater Than | `>` | true if left > right | `len({{fetch.response}}) > 100` |
| Greater or Equal | `>=` | true if left ≥ right | `{{fetch.attempts}} >= 1` |
| Contains | `in` | true if left is substring of right | `"error" in {{analyze.response}}` |
| Not Contains | `not in` | true if left is not substring | `"success" not in {{analyze.response}}` |

**Note:** For `in` and `not in`, the left operand is the substring to search for, and the right operand is the text to search in.

### Boolean Operators

| Operator | Syntax | Returns | Example |
|----------|--------|---------|---------|
| And | `and` | true if both operands are true | `{{a.status}} == "success" and {{b.status}} == "success"` |
| Or | `or` | true if either operand is true | `{{a.status}} == "failed" or {{b.status}} == "failed"` |
| Not | `not` | true if operand is false | `not {{fetch.has_response}}` |

### Regex Matching Operator

Use the `%` operator for regular expression matching:

| Operator | Syntax | Returns | Example |
|----------|--------|---------|---------|
| Matches | `%` | true if pattern matches | `{{extract.response}} % "^\d{4}-\d{2}-\d{2}$"` |

The pattern (right operand) is a Python regular expression matched against the text (left operand).

### Functions

| Function | Signature | Purpose | Example |
|----------|-----------|---------|---------|
| `len` | `len(value)` | Returns length of string | `len({{fetch.response}}) > 500` |
| `lower` | `lower(value)` | Converts to lowercase | `lower({{classify.response}}) == "positive"` |
| `upper` | `upper(value)` | Converts to uppercase | `upper({{status.response}}) contains "ERROR"` |
| `trim` | `trim(value)` | Removes leading/trailing whitespace | `trim({{input.response}}) != ""` |
| `int` | `int(value)` | Converts to integer | `int({{count.response}}) > 10` |
| `float` | `float(value)` | Converts to float | `float({{score.response}}) >= 0.5` |
| `str` | `str(value)` | Converts to string | `str({{num.attempts}}) contains "1"` |

All functions handle `null` values gracefully:
- `lower(null)` returns `""`
- `int(null)` returns `0`
- `float(null)` returns `0.0`

### Ternary Expressions

Use `if`/`else` for conditional values:

```
{{a.status}} == "success" if {{a.has_response}} else False
```

### Chained Comparisons

Chain multiple comparisons:

```
{{retry.attempts}} > 0 and {{retry.attempts}} < 5
```

---

## Tutorial

### Level 1: Status-Based Branching

Skip a prompt if a previous prompt failed.

**Use Case:** Only process data if the fetch succeeded.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | fetch | Retrieve data from the API | |
| 2 | process | Process the retrieved data | `{{fetch.status}} == "success"` |

**What happens:**
- `fetch` runs unconditionally
- `process` only runs if `fetch` succeeded

---

### Level 2: Content-Based Branching

Execute based on response content.

**Use Case:** Only escalate if the response contains an error indicator.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | analyze | Analyze the log file for errors | |
| 2 | escalate | The analysis found errors. Generate incident report. | `"error" in {{analyze.response}}` |

**What happens:**
- If `analyze.response` contains "error", `escalate` runs
- Otherwise, `escalate` is skipped

---

### Level 3: Length Guards

Skip prompts when responses are too short or too long.

**Use Case:** Only summarize if there's enough content.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | fetch | Retrieve the document | |
| 2 | summarize | Summarize the document in 3 bullet points | `len({{fetch.response}}) > 100` |

**What happens:**
- `summarize` only runs if the fetched response is longer than 100 characters

---

### Level 4: Boolean Combinations

Combine multiple conditions with `and` / `or`.

**Use Case:** Only proceed if both data sources succeeded.

| sequence | prompt_name | prompt | history | condition |
|----------|-------------|--------|---------|-----------|
| 1 | fetch_sales | Retrieve sales data | | |
| 2 | fetch_inventory | Retrieve inventory data | | |
| 3 | correlate | Correlate sales with inventory | `["fetch_sales", "fetch_inventory"]` | `{{fetch_sales.status}} == "success" and {{fetch_inventory.status}} == "success"` |

**What happens:**
- `correlate` only runs if both `fetch_sales` and `fetch_inventory` succeeded
- These execute in parallel since they have no dependencies on each other

---

### Level 5: Case-Insensitive Matching

Use `lower()` for case-insensitive string comparisons.

**Use Case:** Match sentiment regardless of capitalization.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | classify | Classify the sentiment as Positive, Negative, or Neutral | |
| 2 | celebrate | Great news! Generate a celebratory message. | `lower({{classify.response}}) == "positive"` |

**What happens:**
- Works whether `classify` returns "Positive", "POSITIVE", or "positive"

---

### Level 6: Error Recovery Patterns

Create fallback chains for resilient workflows.

**Use Case:** Try primary method, fall back to alternative if it fails.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | primary | [Complex analysis that might fail] | |
| 2 | secondary | [Simpler fallback analysis] | `{{primary.status}} == "failed"` |
| 3 | report | Generate final report | `{{primary.status}} == "success" or {{secondary.status}} == "success"` |

**What happens:**
- `primary` runs first
- If `primary` fails, `secondary` runs
- `report` runs if either succeeded

---

### Level 7: Regex Pattern Matching

Use `%` operator for pattern-based decisions.

**Use Case:** Validate response format before processing.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | extract | Extract the date from the document | |
| 2 | validate | The extracted date is valid. Proceed. | `{{extract.response}} % "^\d{4}-\d{2}-\d{2}$"` |

**What happens:**
- `validate` only runs if `extract.response` matches the date pattern `YYYY-MM-DD`

**Common Regex Patterns:**

| Pattern | Matches |
|---------|---------|
| `^\d+$` | Numbers only |
| `^[A-Z]{2,3}$` | 2-3 uppercase letters |
| `^\S+@\S+\.\S+$` | Simple email format |
| `^https?://` | URL starting with http/https |
| `\b\d{3}[-.]?\d{3}[-.]?\d{4}\b` | Phone number formats |

---

### Level 8: Complex Multi-Branch Logic

Build decision trees with mutually exclusive conditions.

**Use Case:** Route to different processors based on classification.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | classify | Classify as: URGENT, NORMAL, or LOW | |
| 2 | urgent_handler | Handle urgent item immediately | `lower({{classify.response}}) == "urgent"` |
| 3 | normal_handler | Handle normal priority item | `lower({{classify.response}}) == "normal"` |
| 4 | low_handler | Queue low priority item | `lower({{classify.response}}) == "low"` |

**What happens:**
- Exactly one handler runs based on classification
- Others are skipped

---

### Level 9: Function Chaining

Combine functions for robust conditions.

**Use Case:** Check for non-empty, trimmed, lowercase content.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | input | Get user input | |
| 2 | process | Process the input | `trim(lower({{input.response}})) != ""` |
| 3 | special | Handle special keyword | `trim(lower({{input.response}})) == "help"` |

**What happens:**
- `process` runs if input is non-empty after trimming
- `special` runs only if input (trimmed and lowercased) equals "help"

---

## Technical Reference: Security Model

### Why AST-Based Evaluation?

Traditional `eval()` and `exec()` are dangerous because they can execute arbitrary Python code:

```python
# DANGEROUS - Never do this
eval("os.system('rm -rf /')")  # Could delete files
```

FFClients uses Python's `ast` (Abstract Syntax Tree) module to parse expressions without executing them. The expression is converted to a tree structure, and only whitelisted operations are evaluated.

### Evaluation Flow

```
Condition String
      │
      ▼
┌─────────────────┐
│ Variable        │  {{fetch.status}} → "success"
│ Resolution      │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ AST Parser      │  Parses expression into tree
│ ast.parse()     │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ Tree Walker     │  Validates and evaluates
│ _eval_node()    │  only whitelisted nodes
└─────────────────┘
      │
      ▼
   Boolean Result
```

### Whitelisted AST Nodes

| Node Type | Python Class | Purpose |
|-----------|--------------|---------|
| Constant | `ast.Constant` | Literal values (strings, numbers, booleans) |
| Name | `ast.Name` | Identifiers (`True`, `False`, `None`) |
| Compare | `ast.Compare` | Comparison operations (`==`, `<`, `in`, etc.) |
| BoolOp | `ast.BoolOp` | Boolean operations (`and`, `or`) |
| UnaryOp | `ast.UnaryOp` | Unary operations (`not`) |
| BinOp | `ast.BinOp` | Binary operations (`+`, `-`, `*`, `/`, `%`) |
| Call | `ast.Call` | Function calls (whitelisted functions only) |
| IfExp | `ast.IfExp` | Ternary expressions (`x if cond else y`) |

### Blocked Operations

| Category | Blocked | Why |
|----------|---------|-----|
| Code Execution | `eval`, `exec`, `compile` | Arbitrary code execution |
| Imports | `import`, `__import__` | Module access |
| Attribute Access | `obj.attr` (beyond `{{name.prop}}`) | Accessing internal objects |
| Subscript Access | `obj[key]` | Dictionary/list access |
| Comprehensions | `[x for x in y]` | Complex expressions |
| Lambdas | `lambda x: x` | Anonymous functions |
| Assignments | `x = 1` | Modifying state |

### Allowed vs Blocked Examples

| Expression | Allowed? | Reason |
|------------|----------|--------|
| `{{a.status}} == "success"` | ✅ | Simple comparison |
| `len({{a.response}}) > 100` | ✅ | Whitelisted function |
| `{{a.response}} % "^\d+$"` | ✅ | Regex via % operator |
| `__import__("os").system("ls")` | ❌ | Module import blocked |
| `eval("print('hi')")` | ❌ | `eval` not in whitelist |
| `{{a.response}}.upper()` | ❌ | Attribute access blocked |
| `[x for x in {{a.response}}]` | ❌ | Comprehension blocked |

### Security Guarantees

1. **No Arbitrary Code Execution** - Only whitelisted operations can run
2. **No Module Access** - Cannot import or access Python modules
3. **No State Modification** - Cannot assign variables or modify data
4. **Sandboxed Functions** - Only 7 safe functions available (`len`, `lower`, `upper`, `trim`, `int`, `float`, `str`)
5. **Controlled Property Access** - Can only access the 5 defined properties (`status`, `response`, `attempts`, `error`, `has_response`)

---

## Best Practices

### Use `has_response` Before Content Checks

Before checking response content, verify a response exists:

```
{{fetch.has_response}} and "success" in {{fetch.response}}
```

This prevents false positives from empty responses.

### Name Prompts Meaningfully

Good names make conditions readable:

```
{{customer_data.status}} == "success"  ✅ Clear
{{p1.status}} == "success"             ❌ Cryptic
```

### Avoid Deeply Nested Conditions

Break complex logic into multiple prompts:

```
❌ Complex:
{{a.status}} == "success" and {{b.status}} == "success" and {{c.status}} == "success" and len({{a.response}}) > 100

✅ Simpler with intermediate:
# Add intermediate prompt that summarizes a, b, c
{{intermediate.status}} == "success"
```

### Test Conditions with `--dry-run`

Always validate workbooks before execution:

```bash
python scripts/run_orchestrator.py my_workbook.xlsx --dry-run
```

This catches syntax errors and invalid references early.

### Order Matters for Dependencies

Referenced prompts must have lower sequence numbers:

```
| sequence | prompt_name | condition |
|----------|-------------|-----------|
| 1        | first       |           |        ✅
| 2        | second      | {{first.status}} == "success"  ✅
| 1        | third       | {{second.status}} == "success" ❌ Error: second not yet executed
```

---

## Troubleshooting

### Common Errors

| Error Message | Cause | Fix |
|---------------|-------|-----|
| `Unknown prompt name in condition: 'xyz'` | Referenced prompt doesn't exist | Check spelling and ensure `prompt_name` column has `xyz` |
| `Syntax error in condition` | Invalid expression syntax | Check quotes, parentheses, and operator usage |
| `Unsupported comparison operator` | Used operator not in whitelist | Use only supported operators (see Reference) |
| `Unknown function: 'xyz'` | Function not in whitelist | Use only the 7 allowed functions |
| `Invalid regex pattern` | Malformed regular expression | Test regex at regex101.com first |
| `'contains' operator requires string values` | Used `in` with non-string | Ensure both operands are strings |

### Debugging Tips

1. **Check the results sheet** - The `condition` and `condition_result` columns show what was evaluated
2. **Simplify the expression** - Break complex conditions into smaller parts
3. **Use `--verbose`** - Enable debug logging to see evaluation details
4. **Test in isolation** - Create a minimal workbook with just the problematic condition

### Validation at Startup

The orchestrator validates all conditions before execution:

```bash
$ python scripts/run_orchestrator.py my_workbook.xlsx --dry-run

Validating workbook...
✓ Config validated
✓ Prompts validated (15 prompts)
✓ Dependencies validated
✓ Conditions validated (3 prompts with conditions)
✗ Error: Sequence 5: condition references undefined prompt 'analzye'
         (did you mean 'analyze'?)
```

---

## Appendix: Complete Operator Reference

### Quick Reference Table

| Operator | Type | Example | Result |
|----------|------|---------|--------|
| `==` | Comparison | `{{a.status}} == "success"` | Equality check |
| `!=` | Comparison | `{{a.status}} != "failed"` | Inequality check |
| `<` | Comparison | `{{a.attempts}} < 3` | Less than |
| `<=` | Comparison | `{{a.attempts}} <= 2` | Less or equal |
| `>` | Comparison | `len({{a.response}}) > 100` | Greater than |
| `>=` | Comparison | `{{a.attempts}} >= 1` | Greater or equal |
| `in` | String | `"error" in {{a.response}}` | Contains substring |
| `not in` | String | `"error" not in {{a.response}}` | Does not contain |
| `%` | Regex | `{{a.response}} % "^\d+$"` | Matches pattern |
| `and` | Boolean | `{{a.status}} == "success" and {{b.status}} == "success"` | Both true |
| `or` | Boolean | `{{a.status}} == "failed" or {{b.status}} == "failed"` | Either true |
| `not` | Boolean | `not {{a.has_response}}` | Negation |

### Function Quick Reference

| Function | Input | Output | Null Handling |
|----------|-------|--------|---------------|
| `len(x)` | String | Integer | `len(null)` → 0 |
| `lower(x)` | String | String | `lower(null)` → "" |
| `upper(x)` | String | String | `upper(null)` → "" |
| `trim(x)` | String | String | `trim(null)` → "" |
| `int(x)` | Any | Integer | `int(null)` → 0 |
| `float(x)` | Any | Float | `float(null)` → 0.0 |
| `str(x)` | Any | String | `str(null)` → "" |

---

## Support

For issues or questions, contact: antquinonez@farfiner.com
