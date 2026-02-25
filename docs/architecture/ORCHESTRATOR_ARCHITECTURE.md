# Excel Orchestrator Subsystem Architecture

## Overview

The Excel Orchestrator enables non-programmers to define and execute AI prompt workflows using Excel workbooks. It provides a declarative, spreadsheet-based interface for orchestrating multi-step AI interactions.

## Design Goals

1. **Accessibility** - Non-developers can define workflows
2. **Transparency** - All prompts and results visible in Excel
3. **Declarative** - Define *what* to execute, not *how*
4. **Traceability** - Full history of executions in workbook
5. **Flexibility** - Batch execution, multi-client support, templating
6. **Document References** - Inject external documents into prompts

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
│   │              _init_documents()                           │   │
│   │  - Load documents from 'documents' sheet                 │   │
│   │  - Initialize DocumentProcessor & DocumentRegistry       │   │
│   │  - Validate all document paths exist                     │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    run()                                 │   │
│   │                                                          │   │
│   │   1. Initialize workbook (create if needed)              │   │
│   │   2. Validate structure and dependencies                 │   │
│   │   3. Check for batch mode (data sheet)                   │   │
│   │   4. Check for multi-client mode (client column)         │   │
│   │   5. Check for document references (documents sheet)     │   │
│   │   6. Execute prompts (sequential/parallel/batch)         │   │
│   │   7. Write results to new sheet                          │   │
│   │                                                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┬─────────────────┐
         │                     │                     │                 │
         ▼                     ▼                     ▼                 ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ WorkbookBuilder │  │  ClientRegistry │  │ DocumentRegistry│  │      FFAI       │
│                 │  │                 │  │                 │  │                 │
│ - load_config() │  │ - register()    │  │ - get_content() │  │ - generate_resp │
│ - load_prompts()│  │ - get()         │  │ - inject_refs() │  │ - history mgmt  │
│ - load_data()   │  │ - clone()       │  │ - validate()    │  │ - context assem │
│ - load_clients()│  │                 │  │                 │  │                 │
│ - load_documents│  └─────────────────┘  └────────┬────────┘  └─────────────────┘
│ - write_results │                                │
└─────────────────┘                                ▼
                                    ┌─────────────────────────┐
                                    │   DocumentProcessor     │
                                    │                         │
                                    │ - compute_checksum()    │
                                    │ - parse_document()      │
                                    │ - load_cached()         │
                                    │ - save_to_parquet()     │
                                    └─────────────────────────┘
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

| sequence | prompt_name | prompt | history | client | references |
|----------|-------------|--------|---------|--------|------------|
| 1 | context | I run a coffee shop with 50 customers. | | | |
| 2 | problem | My electricity bill is too high. | | fast | |
| 3 | solution | Suggest 3 ways to reduce my bill based on {{region}}. | `["context", "problem"]` | | |
| 4 | spec_analysis | Summarize the key features. | | | `["product_spec", "api_guide"]` |

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

### documents Sheet (Optional)

| reference_name | common_name | file_path | notes |
|----------------|-------------|-----------|-------|
| product_spec | Product Specification | library/product_spec.md | Main product docs |
| api_guide | API Reference | library/api_reference.pdf | REST API documentation |
| config | Configuration | library/config.json | System configuration |

### results_{timestamp} Sheet (Generated)

| batch_id | batch_name | sequence | prompt_name | prompt | history | client | condition | condition_result | response | status | attempts | error | references |
|----------|------------|----------|-------------|--------|---------|--------|-----------|------------------|----------|--------|----------|-------|------------|
| 1 | north_widget_a | 1 | context | I run... | | | | | Based on... | success | 1 | | |
| 2 | south_widget_b | 1 | context | I run... | | | | | Based on... | success | 1 | | |
| 3 | | 4 | spec_analysis | Summarize... | | | | | Key features are... | success | 1 | | `["product_spec", "api_guide"]` |

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

## Document Reference System

### Overview

The Document Reference System allows prompts to reference external documents. Documents are parsed, cached as parquet files, and injected into prompts at runtime.

### Components

**DocumentProcessor** (`document_processor.py`):
- Computes SHA256 checksums (first 8 chars for filenames)
- Parses documents using LlamaParse (or direct read for text files)
- Stores parsed content as parquet files with checksum prefix

**DocumentRegistry** (`document_registry.py`):
- Loads document definitions from workbook sheet
- Validates all document paths exist
- Provides content lookup and prompt injection

### Document Storage

```
workbook.xlsx
doc_cache/
  ├── a3f2b1c8|Technical_Spec.parquet
  └── d7e8f9a2|API_Guide.parquet
library/
  ├── product_spec.md
  ├── api_reference.pdf
  └── config.json
```

### Parquet Schema

| Column | Type | Description |
|--------|------|-------------|
| reference_name | string | Unique identifier |
| common_name | string | Human-readable name |
| original_path | string | Source file path |
| checksum | string | Full SHA256 hash |
| content | string | Parsed content (markdown) |
| parsed_at | timestamp | Parse timestamp |
| file_size | int64 | Original file size |

### Reference Injection Format

When a prompt references documents, they are injected as:

```xml
<REFERENCES>
<DOC name='product_spec'>
Document content here...
</DOC>

<DOC name='api_guide'>
More content...
</DOC>
</REFERENCES>

===
Based on the documents above, please answer: [original prompt]
```

### Configuration

| Config Field | Default | Description |
|--------------|---------|-------------|
| `document_cache_dir` | `{workbook_dir}/doc_cache` | Directory for parquet cache |

### API Key

LlamaParse requires `LLAMACLOUD_TOKEN` environment variable for parsing non-text files.

### Error Handling

| Error | Behavior |
|-------|----------|
| Missing file | Fail prompt immediately |
| Parse failure | Raise exception with details |
| Invalid reference | Fail validation at startup |
| Checksum mismatch | Re-parse document |

### Class Reference

```python
class DocumentProcessor:
    def __init__(self, cache_dir: str, api_key: Optional[str] = None):
        """Initialize with cache directory and optional LlamaParse API key."""

    def compute_checksum(self, file_path: str) -> str:
        """Compute SHA256 checksum of file."""

    def needs_parsing(self, file_path: str, cache_dir: str) -> bool:
        """Check if document needs re-parsing based on checksum."""

    def parse_document(self, file_path: str) -> str:
        """Parse document to markdown (LlamaParse or direct read)."""

    def save_to_parquet(self, doc_info: Dict, content: str) -> str:
        """Save parsed content to parquet file."""

    def load_cached(self, reference_name: str) -> Optional[str]:
        """Load cached content from parquet."""

class DocumentRegistry:
    def __init__(self, documents: List[Dict], processor: DocumentProcessor, workbook_dir: str):
        """Initialize with document definitions and processor."""

    def validate_documents(self) -> None:
        """Validate all document paths exist."""

    def get_reference_names(self) -> List[str]:
        """Get list of all reference names."""

    def inject_references_into_prompt(self, prompt: str, ref_names: List[str]) -> str:
        """Inject document content into prompt."""
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
6. **DocumentProcessor Tests** - Checksum, parsing, caching
7. **DocumentRegistry Tests** - Validation, injection

### Test Workbook Generators

- `create_test_workbook.py` - 31 prompts for parallel testing
- `create_test_workbook_batch.py` - 35 prompts × 5 batches
- `create_test_workbook_multiclient.py` - 13 prompts with multiple clients
- `create_test_workbook_documents.py` - 7 prompts with document references
- `create_test_workbook_conditional.py` - 30 prompts with conditional execution
- `create_test_workbook_max.py` - 100 executions for stress testing
