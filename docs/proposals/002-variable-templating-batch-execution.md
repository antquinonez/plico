# Proposal: Variable Templating & Batch Execution

## Status
Draft

## Summary
Enable a single workbook to execute multiple variations of prompts by injecting variables from a data source. This transforms the orchestrator from a single-run tool into a batch processing engine.

## Motivation
Currently, to run the same prompt workflow with different inputs, users must:
1. Duplicate the entire prompts sheet with different values
2. Create multiple workbooks and run them separately
3. Write external scripts to modify and re-run workbooks

This is tedious for common use cases:
- Analyze 50 different customer segments
- Generate reports for 12 months of data
- Test prompts against multiple test cases
- Run comparisons across different configurations

## Proposed Design

### New Sheet: `data`

A dedicated sheet for variable definitions:

```
| id | region | product | quarter |
|----|--------|---------|---------|
| 1 | north | widget_a | Q1 |
| 2 | north | widget_a | Q2 |
| 3 | north | widget_b | Q1 |
| 4 | south | widget_a | Q1 |
| ... | | | |
```

### Template Syntax in Prompts

Prompts use `{{variable}}` syntax to reference data columns:

```
=== prompts sheet ===
| seq | name | prompt | history |
|-----|------|--------|---------|
| 1 | analyze | Analyze sales performance for {{region}} region, {{product}} product, in {{quarter}}. | |
| 2 | recommendations | Based on the analysis, suggest 3 improvements for {{product}} in {{region}}. | ["analyze"] |
```

### Execution Modes

#### Mode 1: Single Row (Default)
If no data sheet or single row, behaves as currently—executes once.

#### Mode 2: Batch All Rows
```bash
python scripts/run_orchestrator.py workbook.xlsx --batch
```

Executes the prompt chain once for each row in the data sheet.

#### Mode 3: Filtered Batch
```bash
python scripts/run_orchestrator.py workbook.xlsx --batch --where "region=north"
```

Executes only for matching rows.

### Results Sheet Structure

Each execution gets `batch_id` and `batch_name` columns referencing the data row:

**Combined output (default):**

```
| batch_id | batch_name | sequence | prompt_name | prompt | response | status |
|----------|------------|----------|-------------|--------|----------|--------|
| 1 | north_widget_a_Q1 | 1 | analyze | Analyze sales... (north, widget_a, Q1) | ... | success |
| 1 | north_widget_a_Q1 | 2 | recommendations | Based on... | ... | success |
| 2 | north_widget_a_Q2 | 1 | analyze | Analyze sales... (north, widget_a, Q2) | ... | success |
| 2 | north_widget_a_Q2 | 2 | recommendations | Based on... | ... | success |
```

**Separate sheets output (`batch_output: separate_sheets`):**

```
results_north_widget_a_Q1
results_north_widget_a_Q2
...
```

### Config Sheet Extensions

```
| field | value | description |
|-------|-------|-------------|
| batch_mode | per_row | Execution mode (per_row or none) |
| batch_output | combined | Output format: "combined" or "separate_sheets" |
| on_batch_error | continue | "continue" or "stop" on batch failure |
```

Batch naming is handled via an optional `batch_name` column in the data sheet. If present, values can use `{{variable}}` syntax for dynamic naming.

## Usage Examples

### Example 1: Multi-Region Analysis

```
=== data sheet ===
| region |
|--------|
| north |
| south |
| east |
| west |

=== prompts sheet ===
| seq | name | prompt |
|-----|------|--------|
| 1 | summarize | Summarize quarterly performance for the {{region}} region. |
```

Result: 4 executions, one per region.

### Example 2: Test Case Validation

```
=== data sheet ===
| id | input | expected_output |
|----|-------|-----------------|
| 1 | Hello | Greeting |
| 2 | Error | Error message |
| 3 | Buy now | Sales pitch |

=== prompts sheet ===
| seq | name | prompt | history |
|-----|------|--------|---------|
| 1 | classify | Classify this text: "{{input}}" | |
| 2 | validate | The classification was "{{classify.response}}". Expected: {{expected_output}}. Is this correct? | ["classify"] |
```

Result: Automated test suite with 3 test cases.

### Example 3: Configuration Matrix

```
=== data sheet ===
| temperature | style |
|-------------|-------|
| 0.3 | formal |
| 0.3 | casual |
| 0.7 | formal |
| 0.7 | casual |

=== config sheet ===
| field | value |
|-------|-------|
| temperature | {{temperature}} |

=== prompts sheet ===
| seq | name | prompt |
|-----|------|--------|
| 1 | write | Write a {{style}} email introducing our product. |
```

Result: 4 variations with different temperature/style combinations.

## Implementation Details

### Variable Resolution

```python
def _resolve_variables(self, text: str, data_row: Dict) -> str:
    """Replace {{variable}} placeholders with values from data row."""
    import re
    pattern = r'\{\{(\w+)\}\}'

    def replacer(match):
        var_name = match.group(1)
        if var_name in data_row:
            return str(data_row[var_name])
        raise ValueError(f"Variable '{var_name}' not found in data row")

    return re.sub(pattern, replacer, text)
```

### Batch Execution Flow

```python
def execute_batch(self) -> List[Dict]:
    """Execute prompts for each row in data sheet."""
    data_rows = self.workbook_builder.load_data()
    all_results = []

    for batch_id, row in enumerate(data_rows, start=1):
        # Resolve variables in prompts
        resolved_prompts = self._resolve_prompt_variables(self.prompts, row)

        # Execute the chain
        results = self._execute_chain(resolved_prompts, batch_id=batch_id)
        all_results.extend(results)

    return all_results
```

### Parallel Batch Execution

With `--concurrency 4`, up to 4 batch rows execute in parallel:

```python
def execute_batch_parallel(self, concurrency: int) -> List[Dict]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    data_rows = self.workbook_builder.load_data()
    all_results = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                self._execute_chain_with_data,
                prompts=self.prompts,
                data_row=row,
                batch_id=batch_id
            ): batch_id
            for batch_id, row in enumerate(data_rows, start=1)
        }

        for future in as_completed(futures):
            results = future.result()
            all_results.extend(results)

    return all_results
```

### Interaction with History

Variables are resolved before history assembly. A prompt's resolved text (with variables substituted) is stored in history, not the template:

```
History for batch_id=1:
  USER: Analyze sales performance for north region, widget_a product, in Q1.
  ASSISTANT: Analysis shows...

History for batch_id=2:
  USER: Analyze sales performance for north region, widget_a product, in Q2.
  ASSISTANT: Analysis shows...
```

Each batch has isolated history.

## Data Source Options (Future)

Phase 1: `data` sheet in the workbook

Phase 2: External data sources
```bash
--data-file customers.csv
--data-file config.json
--data-query "SELECT * FROM analysis_targets" --db sqlite://batch.db
```

## Alternatives Considered

### 1. Excel Formulas in Prompts
Let users write `=A2` references.

**Pros:** Native Excel familiarity
**Cons:** Doesn't work with openpyxl read mode; confusing when prompts sheet is separate from data

### 2. Multiple Prompts Sheets
`prompts_north`, `prompts_south`, etc.

**Pros:** Simple
**Cons:** Duplication, maintenance nightmare, doesn't scale

### 3. External Templating (Jinja2 Files)
Use Jinja2 templates outside Excel.

**Pros:** Powerful templating
**Cons:** Breaks the "everything in Excel" goal

## Resolved Design Decisions

1. **Batch naming**: Users CAN name batches dynamically via `batch_name` column in data sheet (e.g., `{{region}}_{{quarter}}`). Falls back to `batch_1`, `batch_2`, etc. if not provided.

2. **Error handling**: Configurable via `on_batch_error` config option:
   - `continue` (default): Continue to next batch, record failure
   - `stop`: Stop all processing on first batch failure

3. **Memory**: For large batches, results are written incrementally (per-batch flush to sheet). Streaming not needed for initial implementation.

4. **Cross-batch aggregation**: Not in scope for initial implementation. Users can add a summary sheet manually or process results externally.

## Success Metrics

- Single workbook can process N data rows without duplication
- Template syntax is intuitive (`{{variable}}` is familiar from many tools)
- Parallel batch execution maintains same throughput as parallel single execution
- Users can implement test suites and batch analysis without writing code
