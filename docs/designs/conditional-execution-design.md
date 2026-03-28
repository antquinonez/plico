# Conditional Execution Design

## Overview

Add conditional execution capability to the Excel Orchestrator, enabling prompts to execute or skip based on the results of previous prompts. This allows analysts to build intelligent workflows with branching logic, error recovery, and response-dependent processing—all without writing code.

## Goals

1. **Workflow Control** - Enable skip/execute decisions based on previous prompt results
2. **Error Recovery** - Allow fallback branches when upstream prompts fail
3. **Cost Optimization** - Skip expensive prompts when conditions aren't met
4. **Safety** - Sandbox condition evaluation to prevent code injection
5. **Transparency** - Log all condition evaluations in results

## Non-Goals

- Loop/iteration constructs (future enhancement)
- External data lookups in conditions (e.g., database, HTTP)
- Custom Python functions in conditions
- Time-based or scheduled conditions

## Current Architecture

```
ExcelOrchestrator.run()
    └── execute() / execute_parallel()
        └── for each prompt:
            └── _execute_prompt()
                └── ffai.generate_response()
                └── Record result (always)
```

**Limitation:** Every prompt executes (or retries until failure). No way to skip prompts based on runtime conditions.

## Proposed Architecture

```
ExcelOrchestrator.run()
    └── execute() / execute_parallel()
        └── for each prompt:
            └── _should_execute(prompt, state)  # NEW
                ├── Resolve {{name.property}} references
                ├── Evaluate condition expression
                └── Return True/False
            └── if should_execute:
                └── _execute_prompt()
                └── Record result: success/failed
            └── else:
                └── Record result: skipped
```

---

## Key Components

### 1. Condition Column

Add optional `condition` column to prompts sheet:

| sequence | prompt_name | prompt | history | condition |
|----------|-------------|--------|---------|-----------|
| 1 | fetch | Retrieve data | | |
| 2 | parse | Extract metrics | `["fetch"]` | `{{fetch.status}} == "success"` |
| 3 | fallback | Use defaults | | `{{fetch.status}} == "failed"` |
| 4 | report | Generate summary | `["parse"]` | `{{parse.status}} == "success"` |

### 2. Condition Syntax

#### Reference Syntax

Reference previous prompt results using double-brace notation:

```
{{prompt_name.property}}
```

#### Available Properties

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `status` | string | Execution result | `"success"`, `"failed"`, `"skipped"` |
| `response` | string | AI response text | Full response content |
| `attempts` | int | Number of retry attempts | `1`, `2`, `3` |
| `error` | string | Error message (if failed) | Empty string if no error |
| `has_response` | bool | Response exists and non-empty | `true`, `false` |

#### Supported Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equal | `{{step1.status}} == "success"` |
| `!=` | Not equal | `{{step1.status}} != "failed"` |
| `>` | Greater than | `{{step1.attempts}} > 1` |
| `<` | Less than | `{{step1.attempts}} < 3` |
| `>=` | Greater or equal | `{{len(step1.response)}} >= 100` |
| `<=` | Less or equal | `{{len(step1.response)}} <= 500` |
| `contains` | Substring check | `{{step1.response}} contains "error"` |
| `not contains` | Substring absence | `{{step1.response}} not contains "error"` |
| `matches` | Regex match | `{{step1.response}} matches "^\\d+"` |
| `and` | Boolean AND | `{{a.status}} == "success" and {{b.status}} == "success"` |
| `or` | Boolean OR | `{{a.status}} == "success" or {{b.status}} == "success"` |
| `not` | Boolean NOT | `not {{step1.has_response}}` |

#### Helper Functions

| Function | Description | Example |
|----------|-------------|---------|
| `len()` | String/list length | `len({{step1.response}}) > 50` |
| `lower()` | Convert to lowercase | `lower({{step1.response}}) == "yes"` |
| `upper()` | Convert to uppercase | `upper({{step1.response}}) == "YES"` |
| `trim()` / `strip()` | Remove whitespace | `trim({{step1.response}}) != ""` |
| `replace(s, old, new)` | Replace substring | `replace({{step1.response}}, "old", "new")` |
| `split(s, sep)` | Split into list | `len(split({{step1.response}}, ",")) > 3` |
| `int()` | Convert to integer | `int({{step1.response}}) > 0` |
| `float()` | Convert to float | `float({{step1.response}}) >= 0.5` |
| `abs()` | Absolute value | `abs({{delta.response}}) < 10` |
| `min()` / `max()` | Min/max values | `min({{a}}, {{b}}) > 0` |
| `round()` | Round to precision | `round({{x}}, 2) == 1.5` |
| `is_null()` | Check for null | `is_null({{optional.response}})` |
| `is_empty()` | Check for empty/null | `is_empty({{text.response}})` |
| `json_parse()` | Parse JSON string | `json_parse({{api.response}})` |
| `json_get(s, path)` | Get value at path | `json_get({{api.response}}, "status")` |
| `json_get_default(s, path, d)` | Get with default | `json_get_default({{api.response}}, "x", 0)` |
| `json_has(s, path)` | Check path exists | `json_has({{api.response}}, "data")` |
| `json_keys()` / `json_values()` | Get keys/values | `len(json_keys({{api.response}})) > 0` |
| `json_type(s, path)` | Get type at path | `json_type({{api.response}}, "x") == "number"` |

#### String Methods

Methods can be called directly on variable references:

```
{{step1.response}}.startswith("prefix")
{{step1.response}}.endswith(".json")
{{step1.response}}.strip().lower() == "yes"
```

**Available methods:** `startswith`, `endswith`, `strip`, `lower`, `upper`, `replace`, `split`, `count`, `find`, `isalpha`, `isdigit`, `isalnum`, and more.

#### Subscript Access

Access list elements or dictionary values:

```
{{step1.response}}.split(",")[0]
{{step1.response}}["key"]
```

### 3. Condition Examples

#### Error Recovery Pattern

```
| seq | name | prompt | history | condition |
|-----|------|--------|---------|-----------|
| 1 | fetch | Get user profile | | |
| 2 | analyze | Analyze profile | `["fetch"]` | `{{fetch.status}} == "success"` |
| 3 | fallback | Generic analysis | | `{{fetch.status}} == "failed"` |
| 4 | report | Create report | `["analyze", "fallback"]` | `{{analyze.status}} == "success" or {{fallback.status}} == "success"` |
```

#### Content-Based Branching

```
| seq | name | prompt | history | condition |
|-----|------|--------|---------|-----------|
| 1 | classify | Classify sentiment: positive, negative, or neutral | | |
| 2 | positive_response | Write a celebratory response | `["classify"]` | `{{classify.response}} contains "positive"` |
| 3 | negative_response | Write an empathetic response | `["classify"]` | `{{classify.response}} contains "negative"` |
| 4 | neutral_response | Write a balanced response | `["classify"]` | `{{classify.response}} contains "neutral"` |
```

#### Retry Logic

```
| seq | name | prompt | history | condition |
|-----|------|--------|---------|-----------|
| 1 | attempt1 | Generate data | | |
| 2 | attempt2 | Try again with different approach | | `{{attempt1.status}} == "failed"` |
| 3 | attempt3 | Final attempt with simplified prompt | | `{{attempt2.status}} == "failed"` |
| 4 | process | Process the generated data | `["attempt1", "attempt2", "attempt3"]` | `{{attempt1.status}} == "success" or {{attempt2.status}} == "success" or {{attempt3.status}} == "success"` |
```

#### Response Length Check

```
| seq | name | prompt | history | condition |
|-----|------|--------|---------|-----------|
| 1 | summarize | Summarize in 100 words | | |
| 2 | expand | Response too short, expand with more detail | `["summarize"]` | `len({{summarize.response}}) < 200` |
| 3 | trim | Response too long, condense further | `["summarize"]` | `len({{summarize.response}}) > 500` |
```

---

## Data Structures

### Prompt Data (Extended)

```python
@dataclass
class PromptData:
    sequence: int
    prompt_name: Optional[str]
    prompt: str
    history: Optional[List[str]]
    client: Optional[str]
    condition: Optional[str]  # NEW
```

### Condition Evaluation Result

```python
@dataclass
class ConditionResult:
    condition: str                    # Original condition expression
    resolved: str                     # After variable substitution
    evaluated: bool                   # Final boolean result
    error: Optional[str] = None       # If evaluation failed
```

### Execution Result (Extended)

```python
@dataclass
class ExecutionResult:
    sequence: int
    prompt_name: Optional[str]
    prompt: str
    history: Optional[List[str]]
    client: Optional[str]
    response: Optional[str]
    status: str  # "success", "failed", "skipped"
    attempts: int
    error: Optional[str]
    condition: Optional[str]           # NEW: Original condition
    condition_result: Optional[bool]   # NEW: Evaluated result
    condition_error: Optional[str]     # NEW: If condition failed to evaluate
```

---

## Condition Evaluation Engine

### Security Model

**Never use `eval()` or `exec()` on user input.** Conditions must be parsed and evaluated using a restricted AST-based evaluator.

### Implementation

```python
import ast
import re
import operator
from typing import Any, Dict, Optional


class ConditionEvaluator:
    """Safely evaluates condition expressions."""

    ALLOWED_OPERATORS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
        ast.Not: operator.not_,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
    }

    ALLOWED_FUNCTIONS = {
        'len': len,
        'lower': lambda s: str(s).lower(),
        'upper': lambda s: str(s).upper(),
        'trim': lambda s: str(s).strip(),
    }

    def __init__(self, results_by_name: Dict[str, Dict[str, Any]]):
        self.results_by_name = results_by_name

    def evaluate(self, condition: str) -> tuple[bool, Optional[str]]:
        """
        Evaluate a condition expression.

        Returns:
            Tuple of (result, error_message)
        """
        try:
            # Resolve {{name.property}} references
            resolved = self._resolve_variables(condition)

            # Parse and evaluate
            tree = ast.parse(resolved, mode='eval')
            result = self._eval_node(tree.body)

            return bool(result), None

        except Exception as e:
            return False, str(e)

    def _resolve_variables(self, text: str) -> str:
        """Replace {{name.property}} with actual values."""
        pattern = r'\{\{(\w+)\.(\w+)\}\}'

        def replacer(match):
            name = match.group(1)
            prop = match.group(2)

            if name not in self.results_by_name:
                raise ValueError(f"Unknown prompt name: {name}")

            result = self.results_by_name[name]
            value = result.get(prop)

            if value is None:
                return '""' if prop in ('response', 'error', 'status') else '0'

            if isinstance(value, str):
                # Escape quotes and wrap in quotes
                escaped = value.replace('\\', '\\\\').replace('"', '\\"')
                return f'"{escaped}"'
            elif isinstance(value, bool):
                return 'True' if value else 'False'
            else:
                return str(value)

        return re.sub(pattern, replacer, text)

    def _eval_node(self, node: ast.AST) -> Any:
        """Recursively evaluate AST node."""

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Str):  # Python < 3.8 compatibility
            return node.s

        if isinstance(node, ast.Num):  # Python < 3.8 compatibility
            return node.n

        if isinstance(node, ast.NameConstant):  # Python < 3.8
            return node.value

        if isinstance(node, ast.Name):
            name = node.id
            if name in ('True', 'true'):
                return True
            if name in ('False', 'false'):
                return False
            raise ValueError(f"Unknown name: {name}")

        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)

            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator)

                # Handle 'contains' as custom operator
                if isinstance(op, ast.In):
                    if not isinstance(left, str) or not isinstance(right, str):
                        raise ValueError("'contains' requires strings")
                    left = left in right
                elif isinstance(op, ast.NotIn):
                    if not isinstance(left, str) or not isinstance(right, str):
                        raise ValueError("'not contains' requires strings")
                    left = left not in right
                elif type(op) in self.ALLOWED_OPERATORS:
                    left = self.ALLOWED_OPERATORS[type(op)](left, right)
                else:
                    raise ValueError(f"Unsupported operator: {type(op).__name__}")

            return left

        if isinstance(node, ast.BoolOp):
            values = [self._eval_node(v) for v in node.values]

            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)

            raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)

            if isinstance(node.op, ast.Not):
                return not operand

            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only named functions allowed")

            func_name = node.func.id
            if func_name not in self.ALLOWED_FUNCTIONS:
                raise ValueError(f"Unknown function: {func_name}")

            args = [self._eval_node(arg) for arg in node.args]
            return self.ALLOWED_FUNCTIONS[func_name](*args)

        # Handle 'matches' via method call syntax: {{x}} matches "pattern"
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Mod):  # Using % as 'matches'
                left = self._eval_node(node.left)
                right = self._eval_node(node.right)
                if isinstance(left, str) and isinstance(right, str):
                    return bool(re.search(right, left))
                raise ValueError("'matches' requires strings")

        raise ValueError(f"Unsupported expression: {type(node).__name__}")
```

### Alternative: Simple Parser for Non-AST Approach

For environments where AST parsing is too complex, a simpler regex-based approach:

```python
class SimpleConditionEvaluator:
    """Simplified condition evaluator using regex."""

    def __init__(self, results_by_name: Dict[str, Dict[str, Any]]):
        self.results_by_name = results_by_name

    def evaluate(self, condition: str) -> tuple[bool, Optional[str]]:
        try:
            resolved = self._resolve_variables(condition)

            # Handle boolean operators
            if ' or ' in resolved.lower():
                parts = re.split(r'\s+or\s+', resolved, flags=re.IGNORECASE)
                return any(self._evaluate_simple(p.strip())[0] for p in parts), None

            if ' and ' in resolved.lower():
                parts = re.split(r'\s+and\s+', resolved, flags=re.IGNORECASE)
                return all(self._evaluate_simple(p.strip())[0] for p in parts), None

            return self._evaluate_simple(resolved)

        except Exception as e:
            return False, str(e)

    def _evaluate_simple(self, expr: str) -> tuple[bool, Optional[str]]:
        """Evaluate a simple comparison expression."""

        # Pattern: "value" == "other"
        # Pattern: "value" contains "substring"
        # Pattern: number > number

        patterns = [
            (r'^"([^"]*)"\s*==\s*"([^"]*)"$', lambda a, b: a == b),
            (r'^"([^"]*)"\s*!=\s*"([^"]*)"$', lambda a, b: a != b),
            (r'^"([^"]*)"\s+contains\s+"([^"]*)"$', lambda a, b: b in a),
            (r'^"([^"]*)"\s+not\s+contains\s+"([^"]*)"$', lambda a, b: b not in a),
            (r'^(\d+)\s*(>=|>|<=|<|==|!=)\s*(\d+)$', self._numeric_compare),
        ]

        for pattern, comparator in patterns:
            match = re.match(pattern, expr, re.IGNORECASE)
            if match:
                return comparator(*match.groups()), None

        return False, f"Cannot parse: {expr}"
```

---

## Integration with Execution Flow

### Sequential Execution

```python
def execute(self) -> List[Dict[str, Any]]:
    self.results = []
    results_by_name: Dict[str, Dict] = {}

    for prompt in self.prompts:
        # Check condition
        should_execute = True
        condition_result = None
        condition_error = None

        condition = prompt.get("condition")
        if condition:
            evaluator = ConditionEvaluator(results_by_name)
            should_execute, condition_error = evaluator.evaluate(condition)
            condition_result = should_execute

        result = {
            "sequence": prompt["sequence"],
            "prompt_name": prompt.get("prompt_name"),
            "prompt": prompt["prompt"],
            "history": prompt.get("history"),
            "client": prompt.get("client"),
            "condition": condition,
            "condition_result": condition_result,
            "condition_error": condition_error,
            "response": None,
            "status": "pending",
            "attempts": 0,
            "error": None,
        }

        if should_execute:
            # Execute the prompt
            exec_result = self._execute_prompt(prompt)
            result.update(exec_result)
        else:
            # Skip the prompt
            result["status"] = "skipped"
            logger.info(f"Skipped sequence {prompt['sequence']}: condition evaluated to False")

        self.results.append(result)

        if result.get("prompt_name"):
            results_by_name[result["prompt_name"]] = result

    return self.results
```

### Parallel Execution

Condition evaluation adds complexity to parallel execution:

**Rules:**
1. A prompt with a condition on `prompt_a` must wait for `prompt_a` to complete
2. Dependency graph must include condition references as implicit dependencies
3. Skipped prompts don't block downstream prompts that don't depend on them

```python
def _build_execution_graph(self) -> Dict[int, PromptNode]:
    """Build dependency graph, including condition-based dependencies."""

    # Extract explicit history dependencies
    name_to_sequence = {
        p["prompt_name"]: p["sequence"]
        for p in self.prompts
        if p.get("prompt_name")
    }

    nodes = {}
    for prompt in self.prompts:
        seq = prompt["sequence"]
        deps = set()

        # Explicit history dependencies
        if prompt.get("history"):
            for dep_name in prompt["history"]:
                if dep_name in name_to_sequence:
                    deps.add(name_to_sequence[dep_name])

        # Condition-based dependencies (implicit)
        condition = prompt.get("condition")
        if condition:
            # Extract all {{name.property}} references
            refs = re.findall(r'\{\{(\w+)\.\w+\}\}', condition)
            for ref_name in refs:
                if ref_name in name_to_sequence:
                    deps.add(name_to_sequence[ref_name])

        nodes[seq] = PromptNode(
            sequence=seq,
            prompt=prompt,
            dependencies=deps,
            level=0,
        )

    # Calculate levels
    for seq, node in sorted(nodes.items()):
        if node.dependencies:
            max_dep_level = max(nodes[d].level for d in node.dependencies)
            node.level = max_dep_level + 1

    return nodes
```

---

## WorkbookBuilder Changes

### Prompts Sheet Schema

```python
PROMPTS_HEADERS = [
    "sequence",
    "prompt_name",
    "prompt",
    "history",
    "client",
    "condition",  # NEW
]

REQUIRED_PROMPTS_HEADERS = [
    "sequence",
    "prompt_name",
    "prompt",
    "history",
]
```

### Results Sheet Schema

```python
RESULTS_HEADERS = [
    "batch_id",
    "batch_name",
    "sequence",
    "prompt_name",
    "prompt",
    "history",
    "client",
    "response",
    "status",
    "attempts",
    "error",
    "condition",          # NEW
    "condition_result",   # NEW
    "condition_error",    # NEW
]
```

---

## Validation

### Pre-Execution Validation

Before executing, validate conditions:

```python
def _validate_conditions(self) -> List[str]:
    """Validate condition syntax and references."""
    errors = []
    prompt_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}

    for prompt in self.prompts:
        condition = prompt.get("condition")
        if not condition:
            continue

        # Extract referenced prompt names
        refs = re.findall(r'\{\{(\w+)\.\w+\}\}', condition)
        for ref_name in refs:
            if ref_name not in prompt_names:
                errors.append(
                    f"Sequence {prompt['sequence']}: condition references "
                    f"unknown prompt '{ref_name}'"
                )

            # Check that referenced prompt comes before this one
            ref_seq = next(
                (p["sequence"] for p in self.prompts if p.get("prompt_name") == ref_name),
                None
            )
            if ref_seq and ref_seq >= prompt["sequence"]:
                errors.append(
                    f"Sequence {prompt['sequence']}: condition references "
                    f"'{ref_name}' (seq {ref_seq}) which must be defined first"
                )

        # Validate condition syntax (dry-run evaluation)
        try:
            ConditionEvaluator({})._resolve_variables(condition)
        except Exception as e:
            errors.append(
                f"Sequence {prompt['sequence']}: invalid condition syntax: {e}"
            )

    return errors
```

---

## CLI Changes

### Dry-Run Enhancement

```bash
python scripts/run_orchestrator.py workbook.xlsx --dry-run

# Output includes condition validation:
Validating workbook...
✓ Config sheet found
✓ Prompts sheet found
✓ 15 prompts loaded
✓ Dependencies validated
✓ Conditions validated (3 prompts with conditions)

Condition summary:
  - Sequence 2: {{fetch.status}} == "success"
  - Sequence 3: {{fetch.status}} == "failed"
  - Sequence 7: len({{analyze.response}}) > 100

Would execute 15 prompts (some may be skipped based on conditions)
Estimated cost: ~$0.45
```

### New Verbosity Option

```bash
python scripts/run_orchestrator.py workbook.xlsx --show-conditions

# Shows condition evaluation during execution:
[12:34:56] Executing sequence 1: fetch
[12:34:58] ✓ fetch completed (status: success)
[12:34:58] Evaluating condition for sequence 2: {{fetch.status}} == "success" → True
[12:34:58] Executing sequence 2: analyze
[12:35:01] ✓ analyze completed (status: success)
[12:35:01] Evaluating condition for sequence 3: {{fetch.status}} == "failed" → False
[12:35:01] ⊘ sequence 3 skipped (condition: False)
```

---

## Testing Strategy

### Unit Tests

1. **ConditionEvaluator**
   - Test variable resolution: `{{name.property}}`
   - Test equality operators: `==`, `!=`
   - Test comparison operators: `>`, `<`, `>=`, `<=`
   - Test boolean operators: `and`, `or`, `not`
   - Test `contains` / `not contains`
   - Test `matches` with regex
   - Test helper functions: `len()`, `lower()`, `upper()`, `trim()`
   - Test error handling for invalid syntax
   - Test security: no code execution

2. **Dependency Graph**
   - Test condition-based dependencies added to graph
   - Test level calculation with condition deps

3. **Validation**
   - Test unknown prompt reference detection
   - Test forward reference detection
   - Test syntax error detection

### Integration Tests

1. **Sequential Execution**
   - Test skip when condition false
   - Test execute when condition true
   - Test chained conditions
   - Test error recovery pattern

2. **Parallel Execution**
   - Test condition deps don't deadlock
   - Test skipped prompts release dependents
   - Test mixed skip/execute in same level

3. **Batch Mode**
   - Test conditions with batch variables
   - Test per-batch condition evaluation

### Test Workbook

Create `conditional_execution_test.xlsx`:

```
=== prompts sheet ===
| seq | name | prompt | history | condition |
|-----|------|--------|---------|-----------|
| 1 | step1 | Generate a random number between 1 and 10 | | |
| 2 | step2_high | The number was high. Explain why high numbers are interesting. | `["step1"]` | `{{step1.status}} == "success"` |
| 3 | step2_low | The number was low. Explain why low numbers are interesting. | `["step1"]` | `{{step1.status}} == "success"` |
| 4 | step3 | Summarize what you learned | `["step2_high", "step2_low"]` | `{{step2_high.status}} == "success" or {{step2_low.status}} == "success"` |
| 5 | error_handler | Something went wrong. Provide a fallback. | | `{{step1.status}} == "failed"` |
```

---

## Migration & Backward Compatibility

### Existing Workbooks

- Workbooks without `condition` column continue to work unchanged
- Empty condition cells are treated as "always execute"
- Results sheet gains new columns, but existing columns unchanged

### Version Check

```python
def _detect_workbook_version(self) -> str:
    """Detect workbook schema version."""
    if self.builder.has_clients_sheet():
        return "2.0"  # Multi-client + conditions
    elif self.builder.has_condition_column():
        return "1.5"  # Conditions only
    else:
        return "1.0"  # Original
```

---

## Documentation Updates

### User Guide Additions

1. **Condition Syntax Reference** - Complete syntax guide
2. **Common Patterns** - Error recovery, content branching, retry logic
3. **Troubleshooting** - Common condition errors and fixes

### README Updates

Add to features list:
```
- **Conditional Execution**: Skip or execute prompts based on previous results
```

---

## Implementation Checklist

- [x] Add `condition` column to WorkbookBuilder
- [x] Implement ConditionEvaluator class
- [x] Add `_should_execute()` method to ExcelOrchestrator
- [x] Integrate with sequential execution
- [x] Integrate with parallel execution (dependency graph)
- [x] Add condition validation to `_validate()`
- [x] Update results schema with condition columns
- [ ] Add `--show-conditions` CLI option
- [x] Write unit tests for ConditionEvaluator
- [x] Write integration tests for execution flow
- [x] Create test workbook generator
- [x] Update documentation
- [x] Add string method support (startswith, endswith, strip, lower, upper, etc.)
- [x] Add JSON functions (json_get, json_has, json_keys, json_type, etc.)
- [x] Add math functions (abs, min, max, round)
- [x] Add type checking functions (is_null, is_empty, bool)
- [x] Add method chaining support
- [x] Add subscript access (list/dict indexing)
- [x] Create sample workbook for new condition features (v001)
- [x] Write tests for string methods and JSON functions
