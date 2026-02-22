# Excel Workbook Orchestrator Design

## Overview

A class-based solution for orchestrating AI prompt execution via Excel workbooks. Users define prompts, dependencies, and configuration in Excel; the system executes and writes results back to the workbook.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Script                            │
│  (Points to workbook, triggers execution)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  ExcelOrchestrator                           │
│  - Load/validate workbook                                    │
│  - Execute prompts in sequence                               │
│  - Handle retries, errors                                    │
│  - Write results sheet                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     FFAI Layer                               │
│  - Declarative context handling                              │
│  - History management                                        │
│  - Client abstraction                                        │
└─────────────────────────────────────────────────────────────┘
```

## Workbook Structure

### Sheet: `config`
Configuration for the orchestration run.

| Field | Value |
|-------|-------|
| model | mistral-small-2503 |
| api_key_env | MISTRALSMALL_KEY |
| max_retries | 3 |
| temperature | 0.8 |
| max_tokens | 4096 |
| system_instructions | You are a helpful assistant... |
| created_at | 2025-02-21T20:00:00 |

### Sheet: `prompts`
Prompt definitions with dependencies.

| sequence | prompt_name | prompt | history |
|----------|-------------|--------|---------|
| 1 | greeting | How are you? | |
| 2 | math | What is 2+2? | |
| 3 | followup | What was the answer to the math problem? | ["math", "greeting"] |

### Sheet: `results_{timestamp}`
Execution output (created at runtime).

| sequence | prompt_name | prompt | history | response | status | attempts | error |
|----------|-------------|--------|---------|----------|--------|----------|-------|
| 1 | greeting | How are you? | | I'm well! | success | 1 | |
| 2 | math | What is 2+2? | | 4 | success | 1 | |
| 3 | followup | ... | ["math"] | The answer was 4 | success | 1 | |

## Class Design

### ExcelOrchestrator

```python
class ExcelOrchestrator:
    """
    Orchestrates prompt execution via Excel workbook.
    
    Usage:
        orchestrator = ExcelOrchestrator("my_prompts.xlsx", client=FFMistralSmall())
        orchestrator.run()  # Creates results sheet
    """
    
    def __init__(self, workbook_path: str, client: FFAIClientBase, retry_count: int = 3)
    
    def create_workbook(self) -> None
        """Create new workbook with expected structure."""
    
    def validate_workbook(self) -> bool
        """Validate workbook has required sheets/columns."""
    
    def load_config(self) -> dict
        """Load configuration from config sheet."""
    
    def load_prompts(self) -> list[dict]
        """Load prompts from prompts sheet, parse history dependencies."""
    
    def execute(self) -> None
        """Execute all prompts sequentially, write results sheet."""
    
    def run(self) -> str
        """Main entry point: validate, execute, return results sheet name."""
```

### WorkbookManager (enhanced)

A new `WorkbookBuilder` class handles workbook creation and validation.

## Execution Flow

```
1. Load workbook
   ├─ If not exists → create new workbook with template
   └─ If exists → validate structure

2. Load config sheet → configure FFAI client

3. Load prompts sheet → parse into execution order
   └─ Validate dependencies exist before their use

4. For each prompt (in sequence order):
   ├─ Build context from history dependencies
   ├─ Call FFAI.generate_response()
   ├─ On failure: retry up to config.max_retries
   └─ Record result (success/failure, attempts, response/error)

5. Create results sheet with timestamp
   └─ Write all execution records

6. Save workbook
```

## Error Handling

- **Validation errors**: Raise immediately with clear message
- **Execution errors**: Retry N times, record final status
- **Dependency errors**: If referenced prompt_name not found, fail validation

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| model | Model identifier | mistral-small-2503 |
| api_key_env | Environment variable for API key | MISTRALSMALL_KEY |
| max_retries | Retry attempts per prompt | 3 |
| temperature | Model temperature | 0.8 |
| max_tokens | Max response tokens | 4096 |
| system_instructions | System prompt | "You are a helpful assistant..." |

## History Format

Dependencies specified as JSON-like string:
```
["prompt_name1", "prompt_name2"]
```

Parsed into Python list for `FFAI.generate_response(history=...)`.

## File Locations

```
src/
  orchestrator/
    __init__.py
    excel_orchestrator.py    # Main orchestrator class
    workbook_builder.py      # Workbook creation/validation
    
scripts/
  run_orchestrator.py        # CLI entry point
  
docs/
  designs/
    excel-orchestrator-design.md
  plans/
    excel-orchestrator-plan.md
```
