# Manifest Workflow Architecture

## Overview

The Manifest Workflow provides a separation between workbook parsing and execution, enabling version control of prompt configurations and efficient parquet output for analytics. It consists of two main components:

1. **WorkbookManifestExporter** - Converts Excel workbooks to YAML manifest folders
2. **ManifestOrchestrator** - Executes prompts from manifests and outputs to parquet

## Design Goals

1. **Version Control** - Store prompts as YAML files in git
2. **Separation of Concerns** - Parse workbooks once, execute many times
3. **Analytics-Ready Output** - Parquet format for data analysis
4. **CI/CD Integration** - Command-line tools for automation
5. **Reproducibility** - Manifest captures full execution configuration

## Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MANIFEST WORKFLOW                                    │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    WorkbookManifestExporter                          │   │
│   │                                                                      │   │
│   │   Excel Workbook → YAML Manifest Folder                             │   │
│   │                                                                      │   │
│   │   - validate_workbook()                                              │   │
│   │   - load_config/prompts/data/clients/documents()                    │   │
│   │   - _write_*_yaml() methods for each component                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                   │                                          │
│                                   ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      Manifest Folder                                 │   │
│   │                                                                      │   │
│   │   manifest.yaml      - Metadata (version, source, timestamps)       │   │
│   │   config.yaml        - Execution configuration                      │   │
│   │   prompts.yaml       - All prompt definitions                       │   │
│   │   data.yaml          - Batch data (optional)                        │   │
│   │   clients.yaml       - Client configurations (optional)             │   │
│   │   documents.yaml     - Document references (optional)               │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                   │                                          │
│                                   ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    ManifestOrchestrator                              │   │
│   │                                                                      │   │
│   │   Manifest Folder → Parquet Results                                 │   │
│   │                                                                      │   │
│   │   - _load_manifest()                                                 │   │
│   │   - _init_client/registry/documents()                               │   │
│   │   - execute() / execute_parallel()                                  │   │
│   │   - execute_batch() / execute_batch_parallel()                      │   │
│   │   - _write_parquet()                                                 │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Manifest Folder Structure

### Directory Layout

```
manifests/
└── manifest_my_prompts/
    ├── manifest.yaml      # Metadata
    ├── config.yaml        # Configuration
    ├── prompts.yaml       # Prompt definitions
    ├── data.yaml          # Batch data (if applicable)
    ├── clients.yaml       # Client configs (if applicable)
    └── documents.yaml     # Document refs (if applicable)
```

### manifest.yaml

```yaml
version: '1.0'
source_workbook: /path/to/my_prompts.xlsx
exported_at: '2025-03-01T10:30:00.000000'
has_data: true
has_clients: true
has_documents: false
prompt_count: 15
```

### config.yaml

```yaml
model: mistral-small-2503
api_key_env: MISTRALSMALL_KEY
max_retries: 3
temperature: 0.7
max_tokens: 4096
system_instructions: You are a helpful assistant.
batch_mode: per_row
batch_output: combined
on_batch_error: continue
```

### prompts.yaml

```yaml
prompts:
  - sequence: 1
    prompt_name: context
    prompt: I run a coffee shop with 50 customers.
    history: []
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 2
    prompt_name: solution
    prompt: Suggest 3 ways to reduce my bill based on {{region}}.
    history:
      - context
      - problem
    client: fast
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 3
    prompt_name: search_analysis
    prompt: What are the key authentication methods?
    history: []
    client: null
    condition: null
    references: []
    semantic_query: authentication best practices
    semantic_filter: '{"doc_type": "api"}'
    query_expansion: true
    rerank: true
```

### data.yaml (Batch Mode)

```yaml
batches:
  - id: 1
    batch_name: '{{region}}_{{product}}'
    region: north
    product: widget_a
  - id: 2
    batch_name: '{{region}}_{{product}}'
    region: south
    product: widget_b
```

### clients.yaml (Multi-Client)

```yaml
clients:
  - name: fast
    client_type: mistral-small
    api_key_env: MISTRALSMALL_KEY
    model: null
    temperature: 0.3
    max_tokens: 2048
  - name: smart
    client_type: anthropic
    api_key_env: ANTHROPIC_KEY
    model: claude-3-5-sonnet-20241022
    temperature: 0.7
    max_tokens: 4096
```

### documents.yaml (Document References)

```yaml
documents:
  - reference_name: product_spec
    common_name: Product Specification
    file_path: library/product_spec.md
    notes: Main product documentation
  - reference_name: api_guide
    common_name: API Reference
    file_path: library/api_reference.pdf
    notes: REST API documentation
```

## Parquet Output

### Output Path Pattern

```
outputs/{timestamp}_{workbook_name}.parquet
```

Example: `outputs/20250301103000_my_prompts.parquet`

### Parquet Schema

| Column | Type | Description |
|--------|------|-------------|
| `batch_id` | int64 | Batch number (null if not batch mode) |
| `batch_name` | string | Batch name from template |
| `sequence` | int64 | Prompt execution order |
| `prompt_name` | string | Prompt identifier |
| `prompt` | string | The prompt text |
| `history` | string | JSON array of history references |
| `client` | string | Named client used |
| `condition` | string | Conditional expression |
| `condition_result` | string | Condition evaluation result |
| `condition_error` | string | Condition evaluation error |
| `response` | string | AI response |
| `status` | string | `success`, `failed`, or `skipped` |
| `attempts` | int64 | Number of API attempts |
| `error` | string | Error message if failed |
| `references` | string | JSON array of document references |
| `semantic_query` | string | RAG search query |
| `semantic_filter` | string | JSON metadata filter |
| `query_expansion` | string | Query expansion override |
| `rerank` | string | Rerank override |

### Inspecting Results

```bash
python scripts/inspect_parquet.py ./outputs/20250301103000_my_prompts.parquet
```

## Data Flow

### Export Flow

```
Excel Workbook (my_prompts.xlsx)
         │
         ▼
WorkbookManifestExporter.__init__(workbook_path)
         │
         ▼
export(manifest_dir)
         │
         ├──► validate_workbook()
         │
         ├──► load_config() → _write_config_yaml()
         │
         ├──► load_prompts() → _write_prompts_yaml()
         │
         ├──► load_data() → _write_data_yaml() (if exists)
         │
         ├──► load_clients() → _write_clients_yaml() (if exists)
         │
         ├──► load_documents() → _write_documents_yaml() (if exists)
         │
         └──► _write_manifest_yaml()
         │
         ▼
Manifest Folder (manifests/manifest_my_prompts/)
```

### Execution Flow

```
Manifest Folder
         │
         ▼
ManifestOrchestrator.__init__(manifest_dir, client)
         │
         ▼
run()
         │
         ├──► _load_manifest()
         │         │
         │         ├──► Load manifest.yaml
         │         ├──► Load config.yaml
         │         ├──► Load prompts.yaml
         │         ├──► Load data.yaml (if has_data)
         │         └──► Determine batch_mode
         │
         ├──► _validate_dependencies()
         │
         ├──► _init_client()
         │
         ├──► _init_client_registry() (if has_clients)
         │
         ├──► _init_documents() (if has_documents)
         │         │
         │         └──► Pre-index documents for RAG
         │
         ├──► Execute (based on mode):
         │         │
         │         ├──► [batch + parallel] → execute_batch_parallel()
         │         ├──► [batch + sequential] → execute_batch()
         │         ├──► [single + parallel] → execute_parallel()
         │         └──► [single + sequential] → execute()
         │
         └──► _write_parquet()
         │
         ▼
Parquet File (outputs/{timestamp}_{workbook_name}.parquet)
```

## Class Reference

### WorkbookManifestExporter

```python
class WorkbookManifestExporter:
    """Export Excel workbook to a YAML manifest folder structure."""

    def __init__(self, workbook_path: str) -> None:
        """Initialize with workbook path."""

    def export(self, manifest_dir: str | None = None) -> str:
        """
        Export workbook to manifest folder.

        Args:
            manifest_dir: Optional override for manifest directory.
                         Defaults to config paths.manifest_dir.

        Returns:
            Path to the created manifest folder.
        """
```

### ManifestOrchestrator

```python
class ManifestOrchestrator:
    """Execute prompts from manifest folder and output to parquet."""

    def __init__(
        self,
        manifest_dir: str,
        client: FFAIClientBase,
        config_overrides: dict[str, Any] | None = None,
        concurrency: int | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> None:
        """
        Initialize the ManifestOrchestrator.

        Args:
            manifest_dir: Path to the manifest folder.
            client: Default AI client for prompt execution.
            config_overrides: Optional config overrides.
            concurrency: Maximum concurrent API calls.
            progress_callback: Optional callback for progress updates.
        """

    def run(self) -> str:
        """
        Initialize, validate, execute prompts, and write results.

        Returns:
            Path to the created parquet file.
        """

    def execute(self) -> list[dict[str, Any]]:
        """Execute all prompts sequentially."""

    def execute_parallel(self) -> list[dict[str, Any]]:
        """Execute prompts in parallel with dependency-aware scheduling."""

    def execute_batch(self) -> list[dict[str, Any]]:
        """Execute all prompts for each batch row sequentially."""

    def execute_batch_parallel(self) -> list[dict[str, Any]]:
        """Execute batches in parallel."""

    def get_summary(self) -> dict[str, Any]:
        """Get execution summary."""
```

## CLI Usage

### Export Workbook to Manifest

```bash
# Export to default manifest directory
python scripts/export_manifest.py ./workbooks/my_prompts.xlsx

# Export to custom directory
python scripts/export_manifest.py ./workbook.xlsx --output ./custom_manifest/

# Options
python scripts/export_manifest.py ./workbook.xlsx -o ./manifests/
```

### Run from Manifest

```bash
# Run with default settings
python scripts/run_manifest.py ./manifests/manifest_my_prompts

# Run with specific client and concurrency
python scripts/run_manifest.py ./manifests/manifest_my_prompts \
    --client mistral-small \
    --concurrency 4

# Dry run to validate
python scripts/run_manifest.py ./manifests/manifest_my_prompts --dry-run

# Quiet mode
python scripts/run_manifest.py ./manifests/manifest_my_prompts -q
```

### CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `--client` | | AI client to use (default: mistral-small) |
| `--concurrency` | `-c` | Maximum concurrent API calls |
| `--dry-run` | | Validate without executing |
| `--output` | `-o` | Output directory (export only) |
| `--quiet` | `-q` | Suppress console logging |
| `--verbose` | | Enable debug logging |

## Programmatic Usage

### Export and Run

```python
from src.Clients import FFMistralSmall
from src.orchestrator import WorkbookManifestExporter, ManifestOrchestrator

# Step 1: Export workbook to manifest
exporter = WorkbookManifestExporter("./workbooks/my_prompts.xlsx")
manifest_path = exporter.export()
print(f"Manifest created at: {manifest_path}")

# Step 2: Run from manifest
client = FFMistralSmall(api_key="...")
orchestrator = ManifestOrchestrator(
    manifest_dir=manifest_path,
    client=client,
    concurrency=4,
)

parquet_path = orchestrator.run()
summary = orchestrator.get_summary()

print(f"Results: {parquet_path}")
print(f"Success: {summary['successful']}, Failed: {summary['failed']}")
```

### Direct Execution (No Export)

```python
from src.Clients import FFMistralSmall
from src.orchestrator import ManifestOrchestrator

client = FFMistralSmall(api_key="...")

orchestrator = ManifestOrchestrator(
    manifest_dir="./manifests/manifest_my_prompts",
    client=client,
    config_overrides={"temperature": 0.5},
    concurrency=3,
)

parquet_path = orchestrator.run()
```

### With Progress Callback

```python
def progress_callback(completed, total, success, failed, current_name, running):
    pct = (completed / total) * 100
    print(f"\rProgress: {pct:.1f}% | {success} success | {failed} failed", end="")

orchestrator = ManifestOrchestrator(
    manifest_dir="./manifests/manifest_my_prompts",
    client=client,
    progress_callback=progress_callback,
)
parquet_path = orchestrator.run()
```

## Use Cases

### 1. Version Control for Prompts

```bash
# Export workbook to version-controlled manifest
python scripts/export_manifest.py ./workbooks/experiments.xlsx -o ./manifests/

# Commit to git
git add manifests/manifest_experiments/
git commit -m "Update experiment prompts"

# Compare changes over time
git diff HEAD~1 manifests/manifest_experiments/prompts.yaml
```

### 2. CI/CD Integration

```yaml
# .github/workflows/run_prompts.yml
name: Run Prompt Experiments

on:
  push:
    paths:
      - 'manifests/**'

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run manifest
        env:
          MISTRALSMALL_KEY: ${{ secrets.MISTRALSMALL_KEY }}
        run: python scripts/run_manifest.py ./manifests/manifest_experiments -c 4
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: parquet-results
          path: outputs/
```

### 3. Batch Processing Pipeline

```python
from src.orchestrator import ManifestOrchestrator
from src.Clients import FFMistralSmall

client = FFMistralSmall(api_key="...")

# Run large batch job
orchestrator = ManifestOrchestrator(
    manifest_dir="./manifests/manifest_batch_1000",
    client=client,
    concurrency=5,  # Process 5 batches in parallel
)

parquet_path = orchestrator.run()
summary = orchestrator.get_summary()

print(f"Processed {summary['total_batches']} batches")
print(f"Total prompts: {summary['total_prompts']}")
```

### 4. A/B Testing with Different Clients

```python
from src.Clients import FFMistralSmall, FFAnthropic
from src.orchestrator import ManifestOrchestrator

manifest_dir = "./manifests/manifest_experiments"

# Run with Mistral
mistral_client = FFMistralSmall(api_key="...")
orchestrator_mistral = ManifestOrchestrator(
    manifest_dir=manifest_dir,
    client=mistral_client,
)
mistral_results = orchestrator_mistral.run()

# Run with Anthropic
anthropic_client = FFAnthropic(api_key="...")
orchestrator_anthropic = ManifestOrchestrator(
    manifest_dir=manifest_dir,
    client=anthropic_client,
)
anthropic_results = orchestrator_anthropic.run()

# Compare results in parquet files
```

## Feature Parity with Excel Orchestrator

| Feature | Excel Orchestrator | Manifest Orchestrator |
|---------|-------------------|----------------------|
| Sequential execution | ✅ | ✅ |
| Parallel execution | ✅ | ✅ |
| Batch mode | ✅ | ✅ |
| Multi-client support | ✅ | ✅ |
| Document references | ✅ | ✅ |
| RAG semantic search | ✅ | ✅ |
| Conditional execution | ✅ | ✅ |
| Per-prompt RAG overrides | ✅ | ✅ |
| Shared history | ✅ | ✅ |
| Output format | Excel sheet | Parquet file |
| Version control | ❌ | ✅ |
| CI/CD friendly | ❌ | ✅ |

## Comparison: Excel vs Manifest

| Aspect | Excel Orchestrator | Manifest Orchestrator |
|--------|-------------------|----------------------|
| **Input** | Excel workbook (.xlsx) | YAML manifest folder |
| **Output** | New sheet in workbook | Parquet file |
| **Version Control** | Binary diff | Text diff (YAML) |
| **Parsing** | Each run | Once at export |
| **CI/CD** | Difficult | Easy |
| **Analytics** | Manual export | Parquet-native |
| **Configuration** | In workbook | Separate YAML files |

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing manifest.yaml | Raise ValueError on load |
| Invalid YAML syntax | Raise yaml.YAMLError |
| Missing dependency | Fail validation before execution |
| API error | Retry up to max_retries, mark as failed |
| Condition evaluation error | Log warning, mark as failed |
| Document not found | Raise ValueError on validation |
| ChromaDB unavailable | Disable RAG, log warning |

## Dependencies

```
ManifestOrchestrator
├── FFAI (internal)
│   ├── FFAIClientBase
│   └── OrderedPromptHistory
├── ClientRegistry (internal)
├── DocumentProcessor (internal)
├── DocumentRegistry (internal)
├── ConditionEvaluator (internal)
├── WorkbookParser (internal, for loading reference)
├── polars (external, parquet output)
└── pyyaml (external, manifest parsing)

WorkbookManifestExporter
├── WorkbookParser (internal)
└── pyyaml (external, manifest writing)
```

## Testing

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| WorkbookManifestExporter | 8 | Export, YAML writing, optional sheets |
| ManifestOrchestrator | 12 | Load, execute, batch, parallel, error handling |

### Running Tests

```bash
# Run manifest tests
pytest tests/test_manifest.py -v

# Run with coverage
pytest tests/test_manifest.py --cov=src/orchestrator/manifest.py --cov-report=term-missing
```
