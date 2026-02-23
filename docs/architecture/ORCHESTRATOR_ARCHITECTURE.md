# Excel Orchestrator Subsystem Architecture

## Overview

The Excel Orchestrator enables non-programmers to define and execute AI prompt workflows using Excel workbooks. It provides a declarative, spreadsheet-based interface for orchestrating multi-step AI interactions.

## Design Goals

1. **Accessibility** - Non-developers can define workflows
2. **Transparency** - All prompts and results visible in Excel
3. **Declarative** - Define *what* to execute, not *how*
4. **Traceability** - Full history of executions in workbook
5. **Flexibility** - Batch execution, multi-client support, templating

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
│   │              _init_client_registry()                     │   │
│   │  - Load clients from 'clients' sheet                     │   │
│   │  - Register named client configurations                  │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    run()                                 │   │
│   │                                                          │   │
│   │   1. Initialize workbook (create if needed)              │   │
│   │   2. Validate structure and dependencies                 │   │
│   │   3. Check for batch mode (data sheet)                   │   │
│   │   4. Check for multi-client mode (client column)         │   │
│   │   5. Execute prompts (sequential/parallel/batch)         │   │
│   │   6. Write results to new sheet                          │   │
│   │                                                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│ WorkbookBuilder │  │  ClientRegistry │  │        FFAI         │
│                 │  │                 │  │                     │
│ - load_config() │  │ - register()    │  │ - generate_response │
│ - load_prompts()│  │ - get()         │  │ - history mgmt      │
│ - load_data()   │  │ - clone()       │  │ - context assembly  │
│ - load_clients()│  │                 │  │                     │
│ - write_results │  └─────────────────┘  └─────────────────────┘
└─────────────────┘
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
| batch_mode | per_row | Batch execution mode |
| batch_output | combined | Batch output format |
| on_batch_error | continue | Error handling for batches |
| created_at | 2025-02-21T... | Workbook creation timestamp |

### prompts Sheet

| sequence | prompt_name | prompt | history | client |
|----------|-------------|--------|---------|--------|
| 1 | context | I run a coffee shop with 50 customers. | | |
| 2 | problem | My electricity bill is too high. | | fast |
| 3 | solution | Suggest 3 ways to reduce my bill based on {{region}}. | `["context", "problem"]` | |

### data Sheet (Optional)

| id | batch_name | region | product |
|----|------------|--------|---------|
| 1 | {{region}}_{{product}} | north | widget_a |
| 2 | {{region}}_{{product}} | south | widget_b |

### clients Sheet (Optional)

| name | client_type | api_key_env | model | temperature |
|------|-------------|-------------|-------|-------------|
| fast | mistral-small | MISTRALSMALL_KEY | | 0.3 |
| smart | anthropic | ANTHROPIC_TOKEN | claude-3-5-sonnet | 0.7 |

### results_{timestamp} Sheet (Generated)

| batch_id | batch_name | sequence | prompt_name | prompt | history | client | response | status | attempts | error |
|----------|------------|----------|-------------|--------|---------|--------|----------|--------|----------|-------|
| 1 | north_widget_a | 1 | context | I run... | | | Based on... | success | 1 | |
| 2 | south_widget_b | 1 | context | I run... | | | Based on... | success | 1 | |

## Data Flow

### Standard Execution Flow

```
1. INITIALIZATION
   Workbook → WorkbookBuilder.validate_workbook()
              └─► Check: config sheet exists
              └─► Check: prompts sheet exists
              └─► Check: required columns present

2. CONFIGURATION LOADING
   config sheet → WorkbookBuilder.load_config()
                  └─► Parse field/value pairs
                  └─► Type conversion (int, float)
                  └─► Apply config_overrides

3. CLIENT REGISTRY INITIALIZATION
   clients sheet → WorkbookBuilder.load_clients()
                   └─► For each client config:
                       ClientRegistry.register(name, type, config)
   
4. PROMPT LOADING
   prompts sheet → WorkbookBuilder.load_prompts()
                   └─► Read all rows
                   └─► Parse history column (JSON → list)
                   └─► Extract client column
                   └─► Sort by sequence number

5. BATCH MODE DETECTION
   data sheet → WorkbookBuilder.load_data()
                └─► If data rows exist: enable batch mode
                └─► Resolve {{variable}} templates per batch

6. DEPENDENCY VALIDATION
   Loaded Prompts → ExcelOrchestrator._validate_dependencies()
                    └─► Check: all history refs exist
                    └─► Check: refs defined before use

7. EXECUTION
   ┌─────────────────────────────────────────────────────────────┐
   │   For each prompt (per batch if batch mode):               │
   │                                                             │
   │   client_name = prompt.get("client")                        │
   │   client = ClientRegistry.get(client_name)                  │
   │                                                             │
   │   If batch mode:                                            │
   │     resolved_prompt = _resolve_variables(prompt, data_row)  │
   │                                                             │
   │   FFAI.generate_response(                                   │
   │       prompt=resolved_prompt,                               │
   │       prompt_name=prompt_name,                              │
   │       history=history                                       │
   │   )                                                         │
   │                                                             │
   └─────────────────────────────────────────────────────────────┘

8. RESULTS WRITING
   Results List → WorkbookBuilder.write_results()
                  └─► Include batch_id, batch_name, client columns
```

## Class Reference

### ExcelOrchestrator

```python
class ExcelOrchestrator:
    """
    Orchestrates AI prompt execution via Excel workbook.
    
    Features:
    - Sequential and parallel execution
    - Batch execution with variable templating
    - Per-prompt client configuration
    """
    
    def __init__(
        self,
        workbook_path: str,
        client: FFAIClientBase,
        config_overrides: Optional[Dict[str, Any]] = None,
        concurrency: int = 2,
        progress_callback: Optional[Callable] = None,
    ):
        """
        Initialize orchestrator.
        
        Args:
            workbook_path: Path to Excel workbook
            client: Default AI client
            config_overrides: Optional config overrides
            concurrency: Maximum concurrent API calls (default: 2, max: 10)
            progress_callback: Optional callback for progress updates
        """
    
    def run(self) -> str:
        """
        Main entry point. Execute all prompts and write results.
        
        Returns:
            Name of the results sheet created.
        """
    
    def execute(self) -> List[Dict[str, Any]]:
        """Execute all prompts sequentially."""
    
    def execute_parallel(self) -> List[Dict[str, Any]]:
        """Execute prompts in parallel with dependency-aware scheduling."""
    
    def execute_batch(self) -> List[Dict[str, Any]]:
        """Execute all prompts for each batch row sequentially."""
    
    def execute_batch_parallel(self) -> List[Dict[str, Any]]:
        """Execute batches in parallel."""
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary including batch info if applicable."""
    
    # Variable resolution
    def _resolve_variables(self, text: str, data_row: Dict) -> str:
        """Replace {{variable}} placeholders with values from data row."""
    
    def _resolve_batch_name(self, data_row: Dict, batch_id: int) -> str:
        """Generate batch name from template or default."""
    
    # Client registry
    def _init_client_registry(self) -> None:
        """Initialize client registry from clients sheet."""
```

### ClientRegistry

```python
class ClientRegistry:
    """
    Registry for AI clients with lazy instantiation.
    
    Supports per-prompt client selection via named configurations.
    """
    
    CLIENT_MAP: Dict[str, Type[FFAIClientBase]] = {
        "mistral": FFMistral,
        "mistral-small": FFMistralSmall,
        "anthropic": FFAnthropic,
        "anthropic-cached": FFAnthropicCached,
        "gemini": FFGemini,
        "perplexity": FFPerplexity,
        "azure-mistral": FFAzureMistral,
        # ... more clients
    }
    
    def __init__(self, default_client: FFAIClientBase):
        """Initialize registry with a default client."""
    
    def register(
        self, 
        name: str, 
        client_type: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a named client configuration.
        
        Args:
            name: Unique identifier
            client_type: Type from CLIENT_MAP
            config: Optional configuration (api_key_env, model, temperature, etc.)
        """
    
    def get(self, name: Optional[str] = None) -> FFAIClientBase:
        """
        Get client by name or default.
        
        If name not found, returns default client with warning.
        """
    
    def clone(self, name: Optional[str] = None) -> FFAIClientBase:
        """Get a fresh clone for parallel execution."""
    
    @classmethod
    def get_available_client_types(cls) -> list:
        """Get list of available client types."""
```

### WorkbookBuilder

```python
class WorkbookBuilder:
    """Creates and validates Excel workbooks for prompt orchestration."""
    
    CONFIG_SHEET = "config"
    PROMPTS_SHEET = "prompts"
    DATA_SHEET = "data"
    CLIENTS_SHEET = "clients"
    
    def create_template_workbook(
        self, 
        with_data_sheet: bool = False,
        with_clients_sheet: bool = False
    ) -> str:
        """Create a new workbook with template structure."""
    
    def validate_workbook(self) -> bool:
        """Validate workbook has required structure."""
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from config sheet."""
    
    def load_prompts(self) -> List[Dict[str, Any]]:
        """
        Load prompts from prompts sheet.
        
        Returns prompts with: sequence, prompt_name, prompt, history, client
        """
    
    def load_data(self) -> List[Dict[str, Any]]:
        """Load batch data from data sheet."""
    
    def load_clients(self) -> List[Dict[str, Any]]:
        """Load client configurations from clients sheet."""
    
    def has_data_sheet(self) -> bool:
        """Check if workbook has a data sheet."""
    
    def has_clients_sheet(self) -> bool:
        """Check if workbook has a clients sheet."""
    
    def write_results(
        self, 
        results: List[Dict[str, Any]], 
        sheet_name: str
    ) -> str:
        """Write execution results to a new sheet."""
    
    def write_batch_results(
        self,
        results: List[Dict[str, Any]],
        batch_name: str,
        base_sheet_name: str = "results"
    ) -> str:
        """Write results for a single batch to a separate sheet."""
```

## Batch Execution

### Variable Templating

Variables in prompts use `{{variable}}` syntax:

```python
def _resolve_variables(self, text: str, data_row: Dict[str, Any]) -> str:
    """Replace {{variable}} placeholders with values from data row."""
    pattern = r'\{\{(\w+)\}\}'
    
    def replacer(match):
        var_name = match.group(1)
        if var_name in data_row and data_row[var_name] is not None:
            return str(data_row[var_name])
        return match.group(0)  # Keep placeholder if not found
    
    return re.sub(pattern, replacer, text)
```

### Batch Name Resolution

```python
def _resolve_batch_name(self, data_row: Dict, batch_id: int) -> str:
    """Generate batch name from template or default."""
    if "batch_name" in data_row and data_row["batch_name"]:
        name = self._resolve_variables(str(data_row["batch_name"]), data_row)
        return re.sub(r'[^\w\-]', '_', name)[:50]
    return f"batch_{batch_id}"
```

### Error Handling in Batch Mode

```python
# Config: on_batch_error = "continue" | "stop"

if result["status"] == "failed":
    on_error = self.config.get("on_batch_error", "continue")
    if on_error == "stop":
        logger.error(f"Stopping batch execution due to failure")
        break
    # else: continue to next batch
```

## Multi-Client Execution

### Client Selection Flow

```
Prompt with client="fast"
         │
         ▼
ClientRegistry.get("fast")
         │
         ├─► If "fast" registered:
         │       Return cached or create new client
         │
         └─► If "fast" not registered:
                 Log warning, return default client
```

### Thread-Safe Client Isolation

```python
def _execute_prompt_isolated(self, prompt: Dict, state: ExecutionState):
    client_name = prompt.get("client")
    
    if client_name:
        isolated_client = self.client_registry.clone(client_name)
    else:
        isolated_client = self.client.clone()
    
    ffai = FFAI(isolated_client)
    # ... execute with isolated client
```

## CLI Usage

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--client` | | AI client to use (default: mistral-small) |
| `--concurrency` | `-c` | Maximum concurrent API calls |
| `--dry-run` | | Validate without executing |
| `--quiet` | `-q` | Suppress console logging |
| `--verbose` | | Enable debug logging |

### Supported Client Types

```
mistral, mistral-small, anthropic, anthropic-cached, gemini, 
perplexity, nvidia-deepseek, azure-mistral, azure-mistral-small, 
azure-codestral, azure-deepseek, azure-deepseek-v3, azure-phi
```

## Programmatic Usage

```python
from src.orchestrator import ExcelOrchestrator, ClientRegistry
from src.Clients.FFMistralSmall import FFMistralSmall

client = FFMistralSmall(api_key="...")

orchestrator = ExcelOrchestrator(
    workbook_path="my_workbook.xlsx",
    client=client,
    concurrency=4,
)

results_sheet = orchestrator.run()
summary = orchestrator.get_summary()

if summary.get("batch_mode"):
    print(f"Batches: {summary['total_batches']}")
```

## Testing Strategy

### Test Categories

1. **WorkbookBuilder Tests** - Creation, validation, loading
2. **ExcelOrchestrator Tests** - Execution, dependencies, parallel
3. **ClientRegistry Tests** - Registration, retrieval, fallback
4. **Batch Execution Tests** - Variable resolution, batch naming
5. **Multi-Client Tests** - Per-prompt client selection

### Test Workbook Generators

- `create_test_workbook.py` - 31 prompts for parallel testing
- `create_test_workbook_batch.py` - 35 prompts × 5 batches
- `create_test_workbook_multiclient.py` - 13 prompts with multiple clients
