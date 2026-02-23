# Excel Orchestrator Subsystem Architecture

## Overview

The Excel Orchestrator enables non-programmers to define and execute AI prompt workflows using Excel workbooks. It provides a declarative, spreadsheet-based interface for orchestrating multi-step AI interactions.

## Design Goals

1. **Accessibility** - Non-developers can define workflows
2. **Transparency** - All prompts and results visible in Excel
3. **Declarative** - Define *what* to execute, not *how*
4. **Traceability** - Full history of executions in workbook

## Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                            │
│                                                                  │
│   run_orchestrator.py (CLI)  or  Python API                     │
│                                                                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ExcelOrchestrator                           │
│                                                                  │
│   ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐  │
│   │ _init_workbook  │  │ _load_config    │  │ _init_client  │  │
│   └─────────────────┘  └─────────────────┘  └───────────────┘  │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    execute()                             │   │
│   │                                                          │   │
│   │   For each prompt:                                       │   │
│   │     1. Load prompt from workbook                         │   │
│   │     2. Resolve history dependencies                      │   │
│   │     3. Call FFAI.generate_response()                     │   │
│   │     4. Store result with metadata                        │   │
│   │                                                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    run()                                 │   │
│   │                                                          │   │
│   │   1. Initialize workbook (create if needed)              │   │
│   │   2. Validate structure and dependencies                 │   │
│   │   3. Execute all prompts                                 │   │
│   │   4. Write results to new sheet                          │   │
│   │   5. Return results sheet name                           │   │
│   │                                                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
           ┌───────────────────┴───────────────────┐
           │                                       │
           ▼                                       ▼
┌─────────────────────┐               ┌─────────────────────────┐
│   WorkbookBuilder   │               │         FFAI            │
│                     │               │                         │
│ - create_template() │               │ - generate_response()   │
│ - validate()        │               │ - history management    │
│ - load_config()     │               │ - context assembly      │
│ - load_prompts()    │               │                         │
│ - write_results()   │               └─────────────────────────┘
│                     │
└─────────────────────┘
```

## Workbook Structure

### config Sheet

| Field | Value | Description |
|-------|-------|-------------|
| model | mistral-small-2503 | Model identifier |
| api_key_env | MISTRALSMALL_KEY | Environment variable for API key |
| max_retries | 3 | Retry attempts per prompt |
| temperature | 0.8 | Model temperature |
| max_tokens | 4096 | Maximum response tokens |
| system_instructions | You are a... | System prompt |
| created_at | 2025-02-21T... | Workbook creation timestamp |

### prompts Sheet

| sequence | prompt_name | prompt | history |
|----------|-------------|--------|---------|
| 1 | context | I run a coffee shop with 50 customers. | |
| 2 | problem | My electricity bill is too high. What are common causes? | |
| 3 | solution | Suggest 3 ways to reduce my bill based on my context. | `["context", "problem"]` |
| 4 | prioritize | Which should I implement first? | `["solution"]` |

### results_{timestamp} Sheet (Generated)

| sequence | prompt_name | prompt | history | response | status | attempts | error |
|----------|-------------|--------|---------|----------|--------|----------|-------|
| 1 | context | I run... | | Based on your... | success | 1 | |
| 2 | problem | My electricity... | | Common causes... | success | 1 | |
| 3 | solution | Suggest 3... | `["context","problem"]` | Here are 3... | success | 1 | |
| 4 | prioritize | Which... | `["solution"]` | Implement X first... | success | 1 | |

## Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         Execution Flow                            │
└──────────────────────────────────────────────────────────────────┘

1. INITIALIZATION
   ┌─────────────┐
   │ Workbook    │──► WorkbookBuilder.validate_workbook()
   │ (input.xlsx)│    └─► Check: config sheet exists
   └─────────────┘    └─► Check: prompts sheet exists
                      └─► Check: required columns present
   
2. CONFIGURATION LOADING
   ┌─────────────┐
   │ config sheet│──► WorkbookBuilder.load_config()
   └─────────────┘    └─► Parse field/value pairs
                      └─► Type conversion (int, float)
                      └─► Apply config_overrides

3. PROMPT LOADING
   ┌─────────────┐
   │prompts sheet│──► WorkbookBuilder.load_prompts()
   └─────────────┘    └─► Read all rows
                      └─► Parse history column (JSON → list)
                      └─► Sort by sequence number

4. DEPENDENCY VALIDATION
   ┌─────────────┐
   │ Loaded      │──► ExcelOrchestrator._validate_dependencies()
   │ Prompts     │    └─► Check: all history refs exist
   └─────────────┘    └─► Check: refs defined before use

5. EXECUTION (for each prompt in sequence order)
   ┌─────────────────────────────────────────────────────────────┐
   │                                                             │
   │   Prompt: {sequence: 3, prompt_name: "solution",           │
   │            prompt: "Suggest 3...", history: ["context"]}   │
   │                                                             │
   │   ┌──────────────────────────────────────────────────────┐ │
   │   │ ExcelOrchestrator._execute_prompt()                   │ │
   │   │                                                       │ │
   │   │   For attempt in 1..max_retries:                      │ │
   │   │     ┌──────────────────────────────────────────────┐ │ │
   │   │     │ FFAI.generate_response(                       │ │ │
   │   │     │     prompt="Suggest 3...",                    │ │ │
   │   │     │     prompt_name="solution",                   │ │ │
   │   │     │     history=["context", "problem"]            │ │ │
   │   │     │ )                                             │ │ │
   │   │     └──────────────────────────────────────────────┘ │ │
   │   │                     │                                 │ │
   │   │                     ▼                                 │ │
   │   │     ┌──────────────────────────────────────────────┐ │ │
   │   │     │ FFAI assembles context:                       │ │ │
   │   │     │                                              │ │ │
   │   │     │ <conversation_history>                        │ │ │
   │   │     │ <interaction prompt_name='context'>          │ │ │
   │   │     │   USER: I run a coffee shop...               │ │ │
   │   │     │   SYSTEM: Based on your...                   │ │ │
   │   │     │ </interaction>                               │ │ │
   │   │     │ <interaction prompt_name='problem'>          │ │ │
   │   │     │   USER: My electricity bill...               │ │ │
   │   │     │   SYSTEM: Common causes are...               │ │ │
   │   │     │ </interaction>                               │ │ │
   │   │     │ </conversation_history>                      │ │ │
   │   │     │ ===                                           │ │ │
   │   │     │ Based on the conversation history above,     │ │ │
   │   │     │ please answer: Suggest 3 ways to reduce...   │ │ │
   │   │     └──────────────────────────────────────────────┘ │ │
   │   │                     │                                 │ │
   │   │                     ▼                                 │ │
   │   │     ┌──────────────────────────────────────────────┐ │ │
   │   │     │ Client.generate_response()                    │ │ │
   │   │     │   └─► API call to provider                    │ │ │
   │   │     │   └─► Return response                         │ │ │
   │   │     └──────────────────────────────────────────────┘ │ │
   │   │                                                       │ │
   │   │   Store result: {status, response, attempts, error}  │ │
   │   └───────────────────────────────────────────────────────┘ │
   │                                                             │
   └─────────────────────────────────────────────────────────────┘

6. RESULTS WRITING
   ┌─────────────┐     ┌─────────────────┐
   │ Results     │──► │WorkbookBuilder  │
   │ List        │    │.write_results() │
   └─────────────┘    └─────────────────┘
                             │
                             ▼
                      ┌─────────────────┐
                      │results_{ts} sheet│
                      │(in input.xlsx)  │
                      └─────────────────┘
```

## Class Reference

### ExcelOrchestrator

```python
class ExcelOrchestrator:
    """
    Orchestrates AI prompt execution via Excel workbook.
    
    Usage:
        orchestrator = ExcelOrchestrator("workbook.xlsx", client=FFMistralSmall())
        results_sheet = orchestrator.run()
    """
    
    def __init__(
        self,
        workbook_path: str,
        client: FFAIClientBase,
        config_overrides: Optional[Dict[str, Any]] = None,
        concurrency: int = 2,
        progress_callback: Optional[Callable[[int, int, int, int], None]] = None,
    ):
        """
        Initialize orchestrator.
        
        Args:
            workbook_path: Path to Excel workbook
            client: AI client to use for generation
            config_overrides: Optional config overrides
            concurrency: Maximum concurrent API calls (default: 2, max: 10)
            progress_callback: Optional callback for progress updates (completed, total, success, failed)
        """
    
    def run(self) -> str:
        """
        Main entry point. Execute all prompts and write results.
        
        Returns:
            Name of the results sheet created.
        """
    
    def execute(self) -> List[Dict[str, Any]]:
        """
        Execute all prompts sequentially.
        
        Returns:
            List of result dictionaries.
        """
    
    def execute_parallel(self) -> List[Dict[str, Any]]:
        """
        Execute prompts in parallel with dependency-aware scheduling.
        
        Returns:
            List of result dictionaries.
        """
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get execution summary.
        
        Returns:
            Summary dict with total_prompts, successful, failed, etc.
        """
    
    # Private methods
    def _init_workbook(self) -> None:
        """Create workbook if not exists, validate if exists."""
    
    def _load_config(self) -> None:
        """Load configuration from config sheet."""
    
    def _init_client(self) -> None:
        """Initialize FFAI wrapper with client."""
    
    def _validate_dependencies(self) -> None:
        """Validate history dependencies are resolvable."""
    
    def _build_execution_graph(self) -> Dict[int, PromptNode]:
        """Build dependency graph and assign execution levels."""
    
    def _execute_prompt(self, prompt: Dict) -> Dict:
        """Execute single prompt with retry logic."""
    
    def _execute_prompt_isolated(self, prompt: Dict) -> Dict:
        """Execute single prompt with isolated FFAI instance (thread-safe)."""
```

### WorkbookBuilder

```python
class WorkbookBuilder:
    """Creates and validates Excel workbooks for prompt orchestration."""
    
    CONFIG_SHEET = "config"
    PROMPTS_SHEET = "prompts"
    
    def __init__(self, workbook_path: str):
        """Initialize with workbook path."""
    
    def create_template_workbook(self) -> str:
        """
        Create a new workbook with template structure.
        
        Returns:
            Path to created workbook.
        """
    
    def validate_workbook(self) -> bool:
        """
        Validate workbook has required structure.
        
        Returns:
            True if valid.
            
        Raises:
            FileNotFoundError: Workbook not found
            ValueError: Missing required sheet or columns
        """
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from config sheet.
        
        Returns:
            Configuration dictionary with type conversion.
        """
    
    def load_prompts(self) -> List[Dict[str, Any]]:
        """
        Load prompts from prompts sheet.
        
        Returns:
            List of prompt dictionaries, sorted by sequence.
        """
    
    def write_results(
        self,
        results: List[Dict[str, Any]],
        sheet_name: str
    ) -> str:
        """
        Write execution results to a new sheet.
        
        Args:
            results: List of result dictionaries
            sheet_name: Desired sheet name
            
        Returns:
            Actual sheet name used (may differ if conflict).
        """
    
    def parse_history_string(self, history_str: Any) -> Optional[List[str]]:
        """
        Parse history string into list of prompt names.
        
        Supports formats:
        - JSON: '["name1", "name2"]'
        - Comma-separated: '[name1, name2]'
        - Already list: ["name1", "name2"]
        """
```

## History Dependency Resolution

### How Dependencies Work

When a prompt specifies `history: ["context", "problem"]`:

1. **Lookup** - Find interactions with `prompt_name="context"` and `prompt_name="problem"`
2. **Assembly** - Build context string with those interactions
3. **Injection** - Prepend context to the actual prompt

### Context Assembly Format

```
<conversation_history>
<interaction prompt_name='context'>
USER: I run a coffee shop with 50 customers.
SYSTEM: I understand you run a coffee shop with 50 customers. How can I help?
</interaction>
<interaction prompt_name='problem'>
USER: My electricity bill is too high. What are common causes?
SYSTEM: Common causes of high electricity bills include...
</interaction>
</conversation_history>
===
Based on the conversation history above, please answer: Suggest 3 ways to reduce my bill.
```

### Dependency Validation Rules

1. **Existence** - All referenced prompt_names must exist
2. **Ordering** - Dependencies must be defined before use

```
❌ INVALID: Sequence 3 depends on "summary" which is defined at sequence 5

✅ VALID: Sequence 3 depends on "context" defined at sequence 1
```

## Error Handling

### Validation Errors (Fail Fast)

```python
# Missing dependency
ValueError: Dependency validation failed:
Sequence 5: dependency 'summary' not found in any prompt_name

# Invalid structure
ValueError: Missing required sheet: config
ValueError: Missing required columns in prompts sheet: {'prompt_name'}
```

### Execution Errors (Retry + Continue)

```python
# Retry logic
for attempt in range(1, max_retries + 1):
    try:
        response = ffai.generate_response(...)
        break
    except Exception as e:
        if attempt == max_retries:
            # Mark as failed, continue to next prompt
            result["status"] = "failed"
            result["error"] = str(e)
```

### Error in Results Sheet

| sequence | prompt_name | prompt | response | status | attempts | error |
|----------|-------------|--------|----------|--------|----------|-------|
| 5 | broken | Test | | failed | 3 | API Error: Rate limit exceeded |

## CLI Usage

### Create New Workbook

```bash
python scripts/run_orchestrator.py new_workbook.xlsx
```

Creates:
- `new_workbook.xlsx` with `config` and `prompts` sheets

### Execute Workbook

```bash
python scripts/run_orchestrator.py new_workbook.xlsx --client mistral-small
```

Outputs:
```
ORCHESTRATION COMPLETE
============================================================
Workbook:     new_workbook.xlsx
Results sheet: results_20250221_143052
Total prompts: 5
Successful:    5
Failed:        0
============================================================
```

### Dry Run (Validate Only)

```bash
python scripts/run_orchestrator.py new_workbook.xlsx --dry-run
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--client` | | AI client to use (mistral-small, mistral) |
| `--concurrency` | `-c` | Maximum concurrent API calls (default: 2, max: 10) |
| `--dry-run` | | Validate without executing |
| `--quiet` | `-q` | Suppress console logging (logs to file only) |
| `--verbose` | | Enable debug logging |

### Parallel Execution

```bash
# Run with 4 concurrent API calls
python scripts/run_orchestrator.py new_workbook.xlsx --concurrency 4

# Run with quiet mode (clean output)
python scripts/run_orchestrator.py new_workbook.xlsx -c 4 --quiet
```

Output with progress indicator:
```
Starting orchestration with concurrency=4
Total prompts: 30
Log file: /path/to/logs/orchestrator.log

[████████░░░░░░░░░░░░] 15/30 (48%) | ✓14 ✗0 | →compare_9 | ⏳2 | ETA: 4s
```

The parallel executor respects dependencies - prompts at the same dependency level run concurrently, while dependent prompts wait for their prerequisites to complete.

### Logging

All execution logs are written to `logs/orchestrator.log` with daily rotation and 10-day retention.

```bash
# View logs
cat logs/orchestrator.log

# Follow live
tail -f logs/orchestrator.log
```

## Programmatic Usage

```python
from src.orchestrator import ExcelOrchestrator
from src.Clients.FFMistralSmall import FFMistralSmall

# Initialize client
client = FFMistralSmall(api_key="...")

# Create orchestrator with parallel execution
orchestrator = ExcelOrchestrator(
    workbook_path="my_workbook.xlsx",
    client=client,
    config_overrides={"temperature": 0.5},
    concurrency=4,  # Run up to 4 prompts in parallel
)

# Run execution
results_sheet = orchestrator.run()

# Get summary
summary = orchestrator.get_summary()
print(f"Success rate: {summary['successful']}/{summary['total_prompts']}")
```

## Extension Points

### Custom Result Processing

```python
class CustomOrchestrator(ExcelOrchestrator):
    def _execute_prompt(self, prompt):
        result = super()._execute_prompt(prompt)
        
        # Custom post-processing
        if result["status"] == "success":
            result["word_count"] = len(result["response"].split())
        
        return result
```

### Custom Validation

```python
class StrictOrchestrator(ExcelOrchestrator):
    def _validate_dependencies(self):
        super()._validate_dependencies()
        
        # Additional validation
        for prompt in self.prompts:
            if not prompt.get("prompt_name"):
                raise ValueError(f"Sequence {prompt['sequence']}: prompt_name required")
```

### Custom Output Format

```python
class JSONOrchestrator(ExcelOrchestrator):
    def run(self) -> str:
        results_sheet = super().run()
        
        # Also export to JSON
        import json
        with open("results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        return results_sheet
```

## Testing Strategy

### Unit Tests

```python
# Test workbook creation
def test_create_template_workbook(self, temp_workbook):
    builder = WorkbookBuilder(temp_workbook)
    builder.create_template_workbook()
    assert os.path.exists(temp_workbook)

# Test validation
def test_validate_missing_config_raises(self, temp_workbook):
    builder = WorkbookBuilder(temp_workbook)
    with pytest.raises(ValueError, match="Missing required sheet: config"):
        builder.validate_workbook()

# Test execution
def test_execute_all_prompts(self, temp_workbook_with_data, mock_client):
    orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_client)
    results = orchestrator.execute()
    assert len(results) == 3
    assert all(r["status"] == "success" for r in results)
```

### Integration Tests

```python
# Test full flow with mock API
def test_full_orchestration_flow(self, temp_workbook):
    builder = WorkbookBuilder(temp_workbook)
    builder.create_template_workbook()
    
    # Add prompts programmatically
    
    orchestrator = ExcelOrchestrator(temp_workbook, mock_client)
    results_sheet = orchestrator.run()
    
    assert results_sheet.startswith("results_")
```
