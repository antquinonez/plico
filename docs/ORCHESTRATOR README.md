# Excel Orchestrator

## Overview

The Excel Orchestrator enables non-programmers to define and execute AI prompt workflows using Excel workbooks. Define prompts, dependencies, and configuration in Excel, then run the orchestrator to execute and capture results.

## Quick Start

```bash
# Create a new workbook template
python scripts/run_orchestrator.py my_prompts.xlsx

# Edit the prompts sheet in Excel, then run
python scripts/run_orchestrator.py my_prompts.xlsx --client mistral-small
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

| Option | Description |
|--------|-------------|
| `--client <type>` | AI client to use: `mistral-small` (default) or `mistral` |
| `--dry-run` | Validate workbook without executing |
| `--verbose` | Enable debug logging |

### Examples

```bash
# Create new workbook
python scripts/run_orchestrator.py analysis.xlsx

# Validate before running
python scripts/run_orchestrator.py analysis.xlsx --dry-run

# Run with verbose output
python scripts/run_orchestrator.py analysis.xlsx --verbose

# Use different client
python scripts/run_orchestrator.py analysis.xlsx --client mistral
```

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

---

## Programmatic Usage

```python
from src.orchestrator import ExcelOrchestrator
from src.Clients.FFMistralSmall import FFMistralSmall

# Initialize client
client = FFMistralSmall(api_key="your-api-key")

# Create orchestrator
orchestrator = ExcelOrchestrator(
    workbook_path="my_prompts.xlsx",
    client=client,
    config_overrides={"temperature": 0.5}  # Optional overrides
)

# Run
results_sheet = orchestrator.run()

# Get summary
summary = orchestrator.get_summary()
print(f"Successful: {summary['successful']}")
print(f"Failed: {summary['failed']}")
```

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
│  - Execute prompts sequentially         │
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
                    └──────────────────┘
```

---

## Support

For issues or questions, contact: antquinonez@farfiner.com
