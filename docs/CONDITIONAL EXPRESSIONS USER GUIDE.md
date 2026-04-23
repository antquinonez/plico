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
| `abort_condition` | No | Post-execution condition; if true, aborts remaining prompts in scope |

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
| `status` | string | `"success"`, `"failed"`, `"skipped"`, `"aborted"` | Execution status of the prompt |
| `response` | string | Any text | The AI's response text (empty string if none) |
| `attempts` | int | 0, 1, 2, ... | Number of retry attempts made |
| `error` | string | Error message or empty string | Error message if the prompt failed |
| `has_response` | bool | `true`, `false` | True if response exists and is non-empty |
| `agent_mode` | bool | `true`, `false` | True if prompt used agentic tool-call loop |
| `tool_calls_count` | int | 0, 1, 2, ... | Number of tool calls made |
| `last_tool_name` | string | Tool name or empty string | Name of last tool called |
| `total_rounds` | int | 0, 1, 2, ... | Number of rounds in agentic loop |
| `total_llm_calls` | int | 0, 1, 2, ... | Total LLM API calls within agent loop |
| `validation_passed` | bool or null | `true`, `false`, `null` | Whether response passed validation |
| `validation_attempts` | int | 0, 1, 2, ... | Number of validation attempts |

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
| `len` | `len(value)` | Returns length of string/list | `len({{fetch.response}}) > 500` |
| `lower` | `lower(value)` | Converts to lowercase | `lower({{classify.response}}) == "positive"` |
| `upper` | `upper(value)` | Converts to uppercase | `upper({{status.response}}) == "ERROR"` |
| `trim` / `strip` | `trim(value)` | Removes leading/trailing whitespace | `trim({{input.response}}) != ""` |
| `lstrip` | `lstrip(value)` | Removes leading whitespace | `lstrip({{input.response}}) != ""` |
| `rstrip` | `rstrip(value)` | Removes trailing whitespace | `rstrip({{input.response}}) != ""` |
| `int` | `int(value)` | Converts to integer | `int({{count.response}}) > 10` |
| `float` | `float(value)` | Converts to float | `float({{score.response}}) >= 0.5` |
| `str` | `str(value)` | Converts to string | `str({{num.attempts}}) == "1"` |
| `bool` | `bool(value)` | Converts to boolean | `bool({{flag.response}})` |
| `replace` | `replace(value, old, new)` | Replace substring | `replace({{text.response}}, "old", "new")` |
| `split` | `split(value, sep)` | Split into list | `len(split({{csv.response}}, ",")) > 3` |
| `count` | `count(value, sub)` | Count occurrences | `count({{text.response}}, "error") > 0` |
| `find` | `find(value, sub)` | Find substring position | `find({{text.response}}, "key") >= 0` |
| `abs` | `abs(value)` | Absolute value | `abs({{delta.response}}) < 10` |
| `min` | `min(a, b, ...)` | Minimum value | `min({{a.response}}, {{b.response}}) > 0` |
| `max` | `max(a, b, ...)` | Maximum value | `max({{a.response}}, {{b.response}}) < 100` |
| `round` | `round(value, digits)` | Round to precision | `round({{score.response}}, 2) == 0.75` |
| `rfind` | `rfind(value, sub)` | Find substring position from right | `rfind({{text.response}}, "key") >= 0` |
| `rsplit` | `rsplit(value, sep)` | Split from right | `len(rsplit({{csv.response}}, ",")) > 3` |
| `slice` | `slice(value, start, end)` | Slice string/list | `slice({{text.response}}, 0, 10) == "prefix" |
| `is_null` | `is_null(value)` | Check if null/None | `is_null({{optional.response}})` |
| `is_empty` | `is_empty(value)` | Check if empty/null/whitespace | `is_empty({{text.response}})` |
| `json_parse` | `json_parse(string)` | Parse JSON string | `json_parse({{api.response}})` |
| `json_get` | `json_get(string, path)` | Get value at path | `json_get({{api.response}}, "data.status")` |
| `json_get_default` | `json_get_default(string, path, default)` | Get with fallback | `json_get_default({{api.response}}, "count", 0)` |
| `json_has` | `json_has(string, path)` | Check path exists | `json_has({{api.response}}, "data.items")` |
| `json_keys` | `json_keys(string)` | Get object keys | `len(json_keys({{api.response}})) > 0` |
| `json_values` | `json_values(string)` | Get object values | `len(json_values({{api.response}})) > 0` |
| `json_type` | `json_type(string, path)` | Get type at path | `json_type({{api.response}}, "data") == "object"` |
| `json_values` | `json_values(string)` | Get object values | `len(json_values({{api.response}})) > 0` |

All functions handle `null` values gracefully:
- `lower(null)` returns `""`
- `int(null)` returns `0`
- `float(null)` returns `0.0`
- `split(null)` returns `[]`
- `json_parse(null)` returns `{}`

### String Methods

Call methods directly on variable references using dot notation:

```
{{prompt_name.response}}.startswith("prefix")
{{prompt_name.response}}.endswith(".json")
{{prompt_name.response}}.lower() == "yes"
{{prompt_name.response}}.strip() != ""
```

**Available String Methods:**

| Method | Returns | Example |
|--------|---------|---------|
| `startswith(prefix)` | bool | `{{text.response}}.startswith("SUCCESS")` |
| `endswith(suffix)` | bool | `{{file.response}}.endswith(".json")` |
| `lower()` | string | `{{status.response}}.lower() == "ok"` |
| `upper()` | string | `{{status.response}}.upper() == "OK"` |
| `strip()` | string | `{{input.response}}.strip() != ""` |
| `lstrip()` | string | `{{input.response}}.lstrip() != ""` |
| `rstrip()` | string | `{{input.response}}.rstrip() != ""` |
| `replace(old, new)` | string | `{{text.response}}.replace("old", "new")` |
| `split(sep)` | list | `{{csv.response}}.split(",")[0]` |
| `count(sub)` | int | `{{text.response}}.count("error") > 0` |
| `find(sub)` | int | `{{text.response}}.find("key") >= 0` |
| `isalpha()` | bool | `{{text.response}}.isalpha()` |
| `isdigit()` | bool | `{{text.response}}.isdigit()` |
| `isalnum()` | bool | `{{text.response}}.isalnum()` |
| `isspace()` | bool | `{{text.response}}.isspace()` |
| `islower()` | bool | `{{text.response}}.islower()` |
| `isupper()` | bool | `{{text.response}}.isupper()` |
| `title()` | string | `{{name.response}}.title()` |
| `capitalize()` | string | `{{sentence.response}}.capitalize()` |

**Method Chaining:**

Chain multiple methods together:

```
{{text.response}}.strip().lower() == "yes"
{{file.response}}.lower().endswith(".json")
```

### JSON Functions

Parse and navigate JSON responses from AI outputs:

```
json_get({{api.response}}, "data.status") == "success"
json_has({{api.response}}, "data.items[0]")
json_type({{api.response}}, "data.count") == "number"
```

**Path Syntax:**

- Simple key: `"status"`
- Nested: `"data.items"`
- Array index: `"items[0]"`
- Combined: `"data.users[0].name"`

**JSON Function Examples:**

```
# Check nested value
json_get({{api.response}}, "result.status") == "ok"

# Get array element
json_get({{api.response}}, "items[0]") == "first item"

# Check if path exists
json_has({{api.response}}, "error.message")

# Get with default value
json_get_default({{api.response}}, "count", 0) > 10

# Check type at path
json_type({{api.response}}, "data") == "object"

# Count object keys
len(json_keys({{api.response}})) > 0
```

**JSON Robustness:**

The JSON functions handle common LLM output issues:
- Markdown code blocks (` ```json...``` `)
- Trailing commas
- Unquoted keys
- Single quotes instead of double quotes
- Comments in JSON

### Arithmetic Operators

Standard arithmetic is supported on numeric values:

| Operator | Syntax | Example |
|----------|--------|---------|
| Addition | `+` | `{{a.response}} + {{b.response}}` |
| Subtraction | `-` | `{{a.response}} - 10` |
| Multiplication | `*` | `{{a.response}} * 2` |
| Division | `/` | `{{a.response}} / 3` |

String concatenation also uses `+`:

```
{{first.response}} + " " + {{last.response}} == "Alice Chen"
```

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

### Level 10: String Methods

Use string methods directly on variable references.

**Use Case:** Check response prefix/suffix or test character classes.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | status | Report status: SUCCESS or FAILURE | |
| 2 | celebrate | Generate celebration message | `{{status.response}}.startswith("SUCCESS")` |
| 3 | filename | Provide a filename for the output | |
| 4 | validate | Check file type | `{{filename.response}}.strip().lower().endswith(".json")` |

**What happens:**
- `celebrate` runs only if status starts with "SUCCESS"
- `validate` chains methods: strip whitespace, lowercase, then check suffix

---

### Level 11: JSON Functions

Parse and navigate JSON responses from AI.

**Use Case:** Process structured AI outputs.

| sequence | prompt_name | prompt | condition |
|----------|-------------|--------|-----------|
| 1 | api | Return JSON with status and count fields | |
| 2 | process | Process the data | `json_get({{api.response}}, "status") == "ok"` |
| 3 | check_count | Verify count threshold | `json_get_default({{api.response}}, "count", 0) > 5` |
| 4 | has_items | Check for items array | `json_has({{api.response}}, "items")` |
| 5 | validate_type | Ensure data is object | `json_type({{api.response}}, "data") == "object"` |

**What happens:**
- `process` extracts the "status" field from JSON
- `check_count` gets count with a default of 0 if missing
- `has_items` checks if "items" path exists
- `validate_type` verifies the data type at a path

**JSON Path Examples:**

| Path | Description |
|------|-------------|
| `"status"` | Top-level key |
| `"data.status"` | Nested key |
| `"items[0]"` | First array element |
| `"users[0].name"` | Nested with array |
| `"data.items[2].id"` | Deep nesting |

---

## Technical Reference: Security Model

### Why AST-Based Evaluation?

Traditional `eval()` and `exec()` are dangerous because they can execute arbitrary Python code:

```python
# DANGEROUS - Never do this
eval("os.system('rm -rf /')")  # Could delete files
```

Plico uses Python's `ast` (Abstract Syntax Tree) module to parse expressions without executing them. The expression is converted to a tree structure, and only whitelisted operations are evaluated.

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
| Attribute | `ast.Attribute` | Method access (whitelisted methods only) |
| Subscript | `ast.Subscript` | List/dict indexing |
| IfExp | `ast.IfExp` | Ternary expressions (`x if cond else y`) |

### Blocked Operations

| Category | Blocked | Why |
|----------|---------|-----|
| Code Execution | `eval`, `exec`, `compile` | Arbitrary code execution |
| Imports | `import`, `__import__` | Module access |
| Private Methods | Methods starting with `_` | Accessing internal objects |
| Dunder Methods | `__class__`, `__dict__`, etc. | Type introspection |
| Comprehensions | `[x for x in y]` | Complex expressions |
| Lambdas | `lambda x: x` | Anonymous functions |
| Assignments | `x = 1` | Modifying state |

### Allowed vs Blocked Examples

| Expression | Allowed? | Reason |
|------------|----------|--------|
| `{{a.status}} == "success"` | ✅ | Simple comparison |
| `len({{a.response}}) > 100` | ✅ | Whitelisted function |
| `{{a.response}} % "^\d+$"` | ✅ | Regex via % operator |
| `{{a.response}}.upper()` | ✅ | Whitelisted string method |
| `{{a.response}}.startswith("OK")` | ✅ | Whitelisted string method |
| `json_get({{a.response}}, "key")` | ✅ | Whitelisted JSON function |
| `{{a.response}}.strip().lower()` | ✅ | Method chaining |
| `{{a.response}}[0]` | ✅ | Subscript access |
| `__import__("os").system("ls")` | ❌ | Module import blocked |
| `eval("print('hi')")` | ❌ | `eval` not in whitelist |
| `{{a.response}}.__class__` | ❌ | Private method blocked |
| `{{a.response}}._private()` | ❌ | Private method blocked |
| `[x for x in {{a.response}}]` | ❌ | Comprehension blocked |

### Security Guarantees

1. **No Arbitrary Code Execution** - Only whitelisted operations can run
2. **No Module Access** - Cannot import or access Python modules
3. **No State Modification** - Cannot assign variables or modify data
4. **Sandboxed Functions** - 27+ safe functions available (string, math, JSON, type checking)
5. **Sandboxed Methods** - Only 30+ whitelisted string/list/dict methods allowed
6. **No Private Access** - Methods starting with `_` are blocked
7. **Controlled Property Access** - Can only access the 10 defined properties (`status`, `response`, `attempts`, `error`, `has_response`, `agent_mode`, `tool_calls_count`, `last_tool_name`, `total_rounds`, `total_llm_calls`)

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
| `Unknown function: 'xyz'` | Function not in whitelist | Use only the whitelisted functions |
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
| `len(x)` | String/List | Integer | `len(null)` → 0 |
| `lower(x)` | String | String | `lower(null)` → "" |
| `upper(x)` | String | String | `upper(null)` → "" |
| `trim(x)` / `strip(x)` | String | String | `trim(null)` → "" |
| `lstrip(x)` | String | String | `lstrip(null)` → "" |
| `rstrip(x)` | String | String | `rstrip(null)` → "" |
| `int(x)` | Any | Integer | `int(null)` → 0 |
| `float(x)` | Any | Float | `float(null)` → 0.0 |
| `str(x)` | Any | String | `str(null)` → "" |
| `bool(x)` | Any | Boolean | `bool(null)` → False |
| `replace(x, old, new)` | String | String | `replace(null, ...)` → "" |
| `split(x, sep)` | String | List | `split(null, ...)` → [] |
| `count(x, sub)` | String | Integer | `count(null, ...)` → 0 |
| `find(x, sub)` | String | Integer | `find(null, ...)` → -1 |
| `abs(x)` | Number | Number | - |
| `min(a, b, ...)` | Numbers | Number | - |
| `max(a, b, ...)` | Numbers | Number | - |
| `round(x, digits)` | Number | Number | - |
| `is_null(x)` | Any | Boolean | - |
| `is_empty(x)` | Any | Boolean | - |
| `json_parse(x)` | String | Dict/List | `json_parse(null)` → {} |
| `json_get(x, path)` | String | Any | `json_get(null, ...)` → None |
| `json_get_default(x, path, d)` | String | Any | Returns `d` if not found |
| `json_has(x, path)` | String | Boolean | `json_has(null, ...)` → False |
| `json_keys(x)` | String | List | `json_keys(null)` → [] |
| `json_values(x)` | String | List | `json_values(null)` → [] |
| `json_type(x, path)` | String | String | Returns "null", "object", etc. |

### String Method Quick Reference

| Method | Example | Result |
|--------|---------|--------|
| `startswith(p)` | `{{x}}.startswith("OK")` | Boolean |
| `endswith(s)` | `{{x}}.endswith(".json")` | Boolean |
| `lower()` | `{{x}}.lower()` | Lowercase string |
| `upper()` | `{{x}}.upper()` | Uppercase string |
| `strip()` | `{{x}}.strip()` | Trimmed string |
| `replace(old, new)` | `{{x}}.replace("a", "b")` | String with replacements |
| `split(sep)` | `{{x}}.split(",")` | List of strings |
| `count(sub)` | `{{x}}.count("e")` | Integer count |
| `find(sub)` | `{{x}}.find("key")` | Index or -1 |
| `isalpha()` | `{{x}}.isalpha()` | Boolean |
| `isdigit()` | `{{x}}.isdigit()` | Boolean |
| `isalnum()` | `{{x}}.isalnum()` | Boolean |
| `islower()` | `{{x}}.islower()` | Boolean |
| `isupper()` | `{{x}}.isupper()` | Boolean |

---

## Support

For issues or questions, contact: antquinonez@farfiner.com
