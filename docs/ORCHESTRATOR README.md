# Excel Orchestrator

## Overview

The Excel Orchestrator enables non-programmers to define and execute AI prompt workflows using Excel workbooks. Define prompts, dependencies, and configuration in Excel, then run the orchestrator to execute and capture results.

**Key Features:**
- Spreadsheet-based workflow definition
- Declarative context dependencies
- Parallel execution with configurable concurrency
- Real-time progress indicator
- Automatic retry on failure

## Quick Start

```bash
# Create a new workbook template
python scripts/run_orchestrator.py my_prompts.xlsx

# Edit the prompts sheet in Excel, then run
python scripts/run_orchestrator.py my_prompts.xlsx --client mistral-small

# Run with parallel execution (4 concurrent API calls)
python scripts/run_orchestrator.py my_prompts.xlsx -c 4
```

---

## Workbook Structure

The orchestrator expects an Excel workbook with two sheets: `config` and `prompts`.

### config Sheet

Configuration for the orchestration run.

| Field | Description | Default |
|-------|-------------|---------|
| `model` | Model identifier | `mistral-small-2503` |
| `api_key_env` | Environment variable containing API key | `MISTRALSMALL_KEY` |
| `max_retries` | Retry attempts per prompt | `3` |
| `temperature` | Model temperature (0-2) | `0.8` |
| `max_tokens` | Maximum response tokens | `4096` |
| `system_instructions` | System prompt | `You are a helpful assistant...` |
| `created_at` | Timestamp of workbook creation | (auto-generated) |

**Example:**

| field | value |
|-------|-------|
| model | mistral-small-2503 |
| api_key_env | MISTRALSMALL_KEY |
| max_retries | 3 |
| temperature | 0.7 |
| max_tokens | 8000 |
| system_instructions | You are a data analyst. Be concise and accurate. |

### prompts Sheet

Prompt definitions with optional dependencies.

| Column | Description | Required |
|--------|-------------|----------|
| `sequence` | Execution order (1, 2, 3...) | Yes |
| `prompt_name` | Name for referencing in history | No (recommended) |
| `prompt` | The prompt text | Yes |
| `history` | JSON array of prompt_name dependencies | No |

**Example:**

| sequence | prompt_name | prompt | history |
|----------|-------------|--------|---------|
| 1 | intro | My name is Alice and I work in finance. | |
| 2 | question | What is compound interest? | |
| 3 | personalize | Based on my introduction, explain why compound interest matters to me. | `["intro", "question"]` |

---

## History Dependencies

The `history` column lets you include previous prompts as context for the current prompt.

### Syntax

Use a JSON-like array of prompt names:

```
["prompt_name1", "prompt_name2", "prompt_name3"]
```

### Rules

1. Dependencies must be defined **before** they are referenced (lower sequence numbers)
2. Prompt names are case-sensitive
3. Empty or missing history means no additional context

### How It Works

When you specify `history: ["math", "greeting"]`, the orchestrator builds context:

```
<conversation_history>
<interaction prompt_name='math'>
USER: What is 2 + 2?
SYSTEM: The sum of 2 + 2 is 4.
</interaction>
<interaction prompt_name='greeting'>
USER: How are you?
SYSTEM: I'm functioning well, thank you!
</interaction>
</conversation_history>
===
Based on the conversation history above, please answer: [your prompt]
```

### Example Workflow

| sequence | prompt_name | prompt | history |
|----------|-------------|--------|---------|
| 1 | context | I run a coffee shop with 50 daily customers. | |
| 2 | problem | My electricity bill is too high. What are common causes? | |
| 3 | solution | Given my coffee shop context, suggest 3 specific ways to reduce my bill. | `["context", "problem"]` |
| 4 | prioritize | Which of these solutions should I implement first and why? | `["solution"]` |

---

## Execution

### Run Command

```bash
python scripts/run_orchestrator.py <workbook_path> [options]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--client <type>` | | AI client to use: `mistral-small` (default) or `mistral` |
| `--concurrency <n>` | `-c` | Maximum concurrent API calls (default: 2, max: 10) |
| `--dry-run` | | Validate workbook without executing |
| `--quiet` | `-q` | Suppress console output (logs to file only) |
| `--verbose` | | Enable debug logging |

### Examples

```bash
# Create new workbook
python scripts/run_orchestrator.py analysis.xlsx

# Validate before running
python scripts/run_orchestrator.py analysis.xlsx --dry-run

# Run with parallel execution (4 workers)
python scripts/run_orchestrator.py analysis.xlsx -c 4

# Run with quiet mode (clean progress indicator, no console logging)
python scripts/run_orchestrator.py analysis.xlsx -c 4 --quiet

# Run with debug logging to file
python scripts/run_orchestrator.py analysis.xlsx -q --verbose

# Use different client
python scripts/run_orchestrator.py analysis.xlsx --client mistral
```

---

## Logging

### Log File Location

All execution logs are written to `logs/orchestrator.log` with automatic daily rotation.

```
logs/
├── orchestrator.log          # Current log file
├── orchestrator.log.2026-02-22  # Previous day
├── orchestrator.log.2026-02-21
└── ...                       # Last 10 days retained
```

### Log Rotation

- **Frequency**: Daily at midnight
- **Retention**: 10 days
- **Format**: `orchestrator.log.YYYY-MM-DD`

### Quiet Mode

Use `--quiet` (or `-q`) to suppress console logging and see only the progress indicator:

```bash
python scripts/run_orchestrator.py workbook.xlsx --quiet -c 4
```

This is recommended for production runs to keep the output clean.

### Verbose Mode

Use `--verbose` to enable debug-level logging (writes to file, optionally to console):

```bash
# Debug to console
python scripts/run_orchestrator.py workbook.xlsx --verbose

# Debug to file only
python scripts/run_orchestrator.py workbook.xlsx -q --verbose
```

---

## Parallel Execution

### Overview

The orchestrator supports parallel execution of independent prompts, significantly reducing total execution time for large workbooks.

**Performance Example (30 prompts):**

| Concurrency | Time | Speedup |
|-------------|------|---------|
| 1 (sequential) | 36s | baseline |
| 2 | 33s | 9% faster |
| 3 | 24s | 33% faster |
| 4 | 22s | 39% faster |

### How It Works

1. **Dependency Analysis** - Builds a directed acyclic graph (DAG) of prompt dependencies
2. **Level Assignment** - Prompts at the same level have no dependencies on each other
3. **Parallel Scheduling** - Prompts at the same level execute concurrently
4. **Thread Isolation** - Each execution gets its own isolated client clone

### Dependency Levels

```
Level 0: [prompt_1] [prompt_2] [prompt_3]     ← All run in parallel
           │       │       │
Level 1: [prompt_4] [prompt_5]               ← Wait for level 0
           │       │
Level 2: [prompt_6]                          ← Waits for level 1
```

### Progress Indicator

The orchestrator displays a real-time progress indicator during execution:

```
Starting orchestration with concurrency=4
Total prompts: 30
Log file: /path/to/logs/orchestrator.log

[████████░░░░░░░░░░░░] 15/30 (48%) | ✓14 ✗0 | →compare_9 | ⏳2 | ETA: 4s
```

**Progress Indicator Elements:**

| Element | Description |
|---------|-------------|
| `[████░░]` | Visual progress bar |
| `15/30` | Completed / Total prompts |
| `(48%)` | Percentage complete |
| `✓14` | Successful count |
| `✗0` | Failed count |
| `→compare_9` | Current prompt being processed |
| `⏳2` | Number currently running in parallel |
| `ETA: 4s` | Estimated time remaining (shows minutes when >60s) |

**Completed State:**

```
[████████████████████] 30/30 (100%) | ✓30 ✗0 | →final_prompt | Done: 22s
```

### Choosing Concurrency

- **Default (2)**: Safe for most API rate limits
- **3-4**: Optimal for workbooks with many independent prompts
- **5-10**: Only if you have high API rate limits
- **1**: Sequential execution (for debugging)

### Thread Safety

Each parallel execution uses an isolated client instance with:
- Empty conversation history
- Injected dependency context from completed prompts
- No shared state with other executions

---

## Results

After execution, a new sheet is added to the workbook with a timestamped name (e.g., `results_20260221_143052`).

### Results Sheet Columns

| Column | Description |
|--------|-------------|
| `sequence` | Execution order |
| `prompt_name` | Name of the prompt |
| `prompt` | The prompt text |
| `history` | Dependencies (JSON array) |
| `response` | AI response |
| `status` | `success` or `failed` |
| `attempts` | Number of retry attempts |
| `error` | Error message (if failed) |

---

## Error Handling

### Retry Logic

Failed prompts are retried up to `max_retries` times (default: 3). Configure in the `config` sheet.

### Validation Errors

The orchestrator validates before execution:

- **Missing sheet**: `config` or `prompts` sheet not found
- **Missing columns**: Required columns not in prompts sheet
- **Invalid dependencies**: Referenced prompt_name doesn't exist
- **Dependency order**: Dependency defined after its use

### Handling Failures

If a prompt fails after all retries:
- Status is set to `failed`
- Error message is recorded
- Execution continues with next prompt
- Dependent prompts may fail due to missing context

---

## Programmatic Usage

```python
from src.orchestrator import ExcelOrchestrator
from src.Clients.FFMistralSmall import FFMistralSmall

# Initialize client
client = FFMistralSmall(api_key="your-api-key")

# Create orchestrator with parallel execution
orchestrator = ExcelOrchestrator(
    workbook_path="my_prompts.xlsx",
    client=client,
    config_overrides={"temperature": 0.5},  # Optional overrides
    concurrency=4,  # Run up to 4 prompts in parallel
)

# Run
results_sheet = orchestrator.run()

# Get summary
summary = orchestrator.get_summary()
print(f"Successful: {summary['successful']}")
print(f"Failed: {summary['failed']}")
```

### With Progress Callback

```python
def on_progress(completed, total, success, failed, current_name=None, running=0):
    pct = (completed / total) * 100
    status = f"Progress: {pct:.0f}% ({success} success, {failed} failed)"
    if current_name:
        status += f" | Current: {current_name}"
    print(status)

orchestrator = ExcelOrchestrator(
    workbook_path="my_prompts.xlsx",
    client=client,
    concurrency=3,
    progress_callback=on_progress,
)
orchestrator.run()
```

**Progress Callback Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `completed` | int | Number of completed prompts |
| `total` | int | Total number of prompts |
| `success` | int | Number of successful executions |
| `failed` | int | Number of failed executions |
| `current_name` | str \| None | Name of the prompt just completed |
| `running` | int | Number of prompts currently executing |

### WorkbookBuilder

```python
from src.orchestrator import WorkbookBuilder

builder = WorkbookBuilder("new_workbook.xlsx")

# Create template
builder.create_template_workbook()

# Validate
builder.validate_workbook()

# Load data
config = builder.load_config()
prompts = builder.load_prompts()

# Write results
builder.write_results(results_list, "results_20260221")
```

---

## Test Workbook Generator

Create a test workbook with 31 prompts for testing parallel execution:

```bash
# Default: creates test_workbook_30.xlsx
python scripts/create_test_workbook.py

# Custom filename
python scripts/create_test_workbook.py my_test.xlsx
```

**Generated Workbook Structure:**

| Level | Count | Description |
|-------|-------|-------------|
| 0 | 12 | Independent prompts (6 math, 6 word) - fully parallel |
| 1 | 10 | Prompts with 1-2 dependencies (6 double, 4 compare) |
| 2 | 5 | Prompts with 2-4 dependencies (3 sum, 1 triple_check, 1 analysis) |
| 3 | 4 | Final prompts (2 synthesis, 2 bonus independent) |

**Run the test workbook:**

```bash
python scripts/run_orchestrator.py test_workbook_30.xlsx -c 3 --quiet
```

---

## Sample Workbook

A sample workbook is provided at `sample_orchestrator.xlsx` with example prompts:

1. **greeting** - Simple greeting
2. **math** - Basic math question
3. **followup** - References previous prompts via history

Run it:

```bash
python scripts/run_orchestrator.py sample_orchestrator.xlsx
```

---

## Best Practices

### Prompt Naming

- Use descriptive, unique names: `customer_context`, `problem_statement`, `solution`
- Avoid generic names: `prompt1`, `question`, `test`

### History Design

- Keep dependency chains reasonable (2-5 references)
- Consider context window limits
- Group related information in early prompts

### Parallel Execution

- Use `-c 3` or `-c 4` for optimal performance
- Set `-c 1` for debugging dependency issues
- Monitor API rate limits when increasing concurrency
- Use `--quiet` for clean output during production runs

### Logging

- Check `logs/orchestrator.log` for detailed execution info
- Use `--verbose` when debugging issues
- Use `--quiet` for automated/production runs
- Logs rotate daily with 10-day retention

### Workbook Organization

- One workbook per workflow/logical task
- Use descriptive filenames: `customer_analysis_20260221.xlsx`
- Archive completed workbooks with results

### Configuration

- Lower `temperature` (0.3-0.5) for factual/analytical tasks
- Higher `temperature` (0.7-1.0) for creative tasks
- Set `max_tokens` appropriately for expected response length

---

## Troubleshooting

### API Key Issues

```
ValueError: API key not found in environment variable: MISTRALSMALL_KEY
```

Ensure the environment variable is set:

```bash
export MISTRALSMALL_KEY="your-key-here"
```

Or use a `.env` file:

```
MISTRALSMALL_KEY=your-key-here
```

### Dependency Validation Errors

```
ValueError: Dependency validation failed:
Sequence 5: dependency 'summary' not found in any prompt_name
```

Check that:
- The prompt_name exists in the prompts sheet
- The dependency is defined before it's referenced (lower sequence)

### Workbook Locked

```
PermissionError: [Errno 13] Permission denied: 'my_prompts.xlsx'
```

Close the workbook in Excel before running the orchestrator.

### Cross-Contamination in Results

If prompts receive incorrect context from other prompts:
- This was fixed in the latest version with client cloning
- Ensure you're using the latest code
- Each parallel execution now has complete isolation

### Checking Logs

For detailed execution information, check the log file:

```bash
# View current log
cat logs/orchestrator.log

# View specific day
cat logs/orchestrator.log.2026-02-22

# Follow live (during execution)
tail -f logs/orchestrator.log
```

### Console Output Too Verbose

Use `--quiet` to suppress console logging:

```bash
python scripts/run_orchestrator.py workbook.xlsx --quiet -c 4
```

This shows only the progress indicator while logging everything to file.

---

## Architecture

```
┌─────────────────────────────────────────┐
│           run_orchestrator.py           │
│              (CLI Script)               │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│          ExcelOrchestrator              │
│  - Load/validate workbook               │
│  - Build dependency graph               │
│  - Execute prompts (parallel/sequential)│
│  - Handle retries                       │
│  - Write results sheet                  │
└─────────────────────────────────────────┘
          │                    │
          ▼                    ▼
┌──────────────────┐  ┌──────────────────┐
│ WorkbookBuilder  │  │      FFAI        │
│ - Create/validate│  │ - Context mgmt   │
│ - Read/write     │  │ - History        │
└──────────────────┘  └──────────────────┘
                              │
                              ▼
                   ┌──────────────────┐
                   │  FFMistralSmall  │
                   │  (API Client)    │
                   │  - clone() for   │
                   │    isolation     │
                   └──────────────────┘
```

---

## Support

For issues or questions, contact: antquinonez@farfiner.com
