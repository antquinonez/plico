# Excel Orchestrator

## Overview

The Excel Orchestrator enables non-programmers to define and execute AI prompt workflows using Excel workbooks. Define prompts, dependencies, and configuration in Excel, then run the orchestrator to execute and capture results.

**Key Features:**
- Spreadsheet-based workflow definition
- Declarative context dependencies
- Parallel execution with configurable concurrency
- Real-time progress indicator
- Automatic retry on failure
- **Batch execution with variable templating**
- **Per-prompt client configuration**
- **Document reference injection**
- **Conditional execution**

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

The orchestrator supports up to five sheets: `config` (required), `prompts` (required), `data` (optional), `clients` (optional), and `documents` (optional).

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
| `batch_mode` | Batch execution mode | `per_row` |
| `batch_output` | Output format for batches | `combined` |
| `on_batch_error` | Error handling for batches | `continue` |

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

Prompt definitions with optional dependencies, client selection, document references, and RAG overrides.

| Column | Description | Required |
|--------|-------------|----------|
| `sequence` | Execution order (1, 2, 3...) | Yes |
| `prompt_name` | Name for referencing in history | No (recommended) |
| `prompt` | The prompt text (supports `{{variable}}` templating) | Yes |
| `history` | JSON array of prompt_name dependencies | No |
| `client` | Named client from `clients` sheet | No |
| `references` | JSON array of document reference names | No |
| `condition` | Conditional expression for execution | No |
| `semantic_query` | RAG search query for relevant chunks | No |
| `semantic_filter` | JSON metadata filter for RAG search | No |
| `query_expansion` | Enable multi-query retrieval (`true`/`false`) | No |
| `rerank` | Enable cross-encoder reranking (`true`/`false`) | No |

**Example:**

| sequence | prompt_name | prompt | history | client |
|----------|-------------|--------|---------|--------|
| 1 | intro | My name is Alice and I work in finance. | | |
| 2 | question | What is compound interest? | | fast |
| 3 | personalize | Based on my introduction, explain why compound interest matters to me. | `["intro", "question"]` | |

### data Sheet (Optional)

Batch data for variable templating. Each row represents a batch execution.

| Column | Description |
|--------|-------------|
| `id` | Batch identifier |
| `batch_name` | Template for naming batches (supports `{{variable}}`) |
| `...` | Any additional columns become template variables |

**Example:**

| id | batch_name | region | product | price | quantity |
|----|------------|--------|---------|-------|----------|
| 1 | {{region}}_{{product}} | north | widget_a | 10 | 100 |
| 2 | {{region}}_{{product}} | south | widget_b | 15 | 75 |

### clients Sheet (Optional)

Named client configurations for per-prompt client selection.

| Column | Description |
|--------|-------------|
| `name` | Unique identifier to reference in prompts |
| `client_type` | Client type (e.g., `mistral-small`, `anthropic`) |
| `api_key_env` | Environment variable for API key |
| `model` | Model override |
| `temperature` | Temperature override |
| `max_tokens` | Max tokens override |

**Example:**

| name | client_type | api_key_env | model | temperature | max_tokens |
|------|-------------|-------------|-------|-------------|------------|
| fast | mistral-small | MISTRALSMALL_KEY | mistral-small-2503 | 0.3 | 100 |
| smart | anthropic | ANTHROPIC_TOKEN | claude-3-5-sonnet | 0.7 | 4096 |
| creative | mistral-small | MISTRALSMALL_KEY | | 0.9 | 500 |

### documents Sheet (Optional)

Document definitions for reference injection into prompts.

| Column | Description |
|--------|-------------|
| `reference_name` | Unique identifier to reference in prompts |
| `common_name` | Human-readable name |
| `file_path` | Path to document (relative to workbook) |
| `notes` | Optional description |

**Example:**

| reference_name | common_name | file_path | notes |
|----------------|-------------|-----------|-------|
| product_spec | Product Specification | library/product_spec.md | Main product docs |
| api_guide | API Reference | library/api_reference.pdf | REST API documentation |
| config | Configuration | library/config.json | System configuration |

**How Documents Work:**

1. Documents are parsed (text files read directly, others via LlamaParse)
2. Parsed content is cached as parquet files with checksum-based deduplication
3. When a prompt has `references`, the document content is injected into the prompt

**Cache Directory:** `doc_cache/` (created next to workbook, or configured via `document_cache_dir` in config)

**API Key:** Set `LLAMACLOUD_TOKEN` environment variable for LlamaParse (required for PDFs and other non-text files)

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

---

## Batch Execution with Variable Templating

### Overview

Batch execution allows running the same prompt chain multiple times with different data inputs. Use `{{variable}}` syntax in prompts to reference columns from the `data` sheet.

### How It Works

1. Add a `data` sheet with your variable data
2. Use `{{column_name}}` in your prompts
3. The orchestrator executes all prompts once per data row

### Example

**data sheet:**

| id | batch_name | region | product |
|----|------------|--------|---------|
| 1 | {{region}}_{{product}} | north | widget_a |
| 2 | {{region}}_{{product}} | south | widget_b |

**prompts sheet:**

| sequence | prompt_name | prompt |
|----------|-------------|--------|
| 1 | analyze | Analyze sales for {{region}} region, {{product}} product. |
| 2 | recommend | Based on the analysis, suggest improvements. |

**Result:** Each prompt runs twice (once per data row), with `{{region}}` and `{{product}}` replaced by actual values.

### Batch Configuration

| Config Field | Options | Description |
|--------------|---------|-------------|
| `batch_mode` | `per_row` | Execute once per data row |
| `batch_output` | `combined`, `separate_sheets` | Combined results or separate sheets per batch |
| `on_batch_error` | `continue`, `stop` | Continue or stop on batch failure |

### Results Sheet with Batch Info

| Column | Description |
|--------|-------------|
| `batch_id` | Batch number |
| `batch_name` | Resolved batch name |
| `sequence` | Prompt sequence |
| `prompt_name` | Prompt name |
| `prompt` | Resolved prompt (with variables substituted) |
| `history` | Dependencies |
| `client` | Client used |
| `response` | AI response |
| `status` | `success` or `failed` |
| `attempts` | Retry attempts |
| `error` | Error message if failed |

---

## Per-Prompt Client Configuration

### Overview

Different prompts can use different AI clients or configurations. Define named clients in the `clients` sheet and reference them in prompts.

### How It Works

1. Add a `clients` sheet with named client configurations
2. Add a `client` column to your prompts sheet
3. Reference the client name, or leave empty for default

### Example

**clients sheet:**

| name | client_type | temperature | max_tokens |
|------|-------------|-------------|------------|
| fast | mistral-small | 0.3 | 100 |
| creative | mistral-small | 0.9 | 500 |

**prompts sheet:**

| sequence | prompt_name | prompt | client |
|----------|-------------|--------|--------|
| 1 | classify | Classify this sentiment | fast |
| 2 | explain | Explain why | |
| 3 | poem | Write a poem about it | creative |

**Behavior:**
- Sequence 1 uses the `fast` client (temperature=0.3, max_tokens=100)
- Sequence 2 uses the default client (from CLI)
- Sequence 3 uses the `creative` client (temperature=0.9, max_tokens=500)

### Supported Client Types

| Client Type | Description |
|-------------|-------------|
| `litellm` | Universal LiteLLM client (recommended) |
| `litellm-azure` | LiteLLM for Azure deployments |
| `litellm-anthropic` | LiteLLM for Anthropic |
| `litellm-openai` | LiteLLM for OpenAI |
| `litellm-mistral` | LiteLLM for Mistral |
| `litellm-gemini` | LiteLLM for Gemini |
| `litellm-perplexity` | LiteLLM for Perplexity |
| `mistral` | Mistral Large (native) |
| `mistral-small` | Mistral Small (native) |
| `anthropic` | Claude via Anthropic API |
| `anthropic-cached` | Claude with prompt caching |
| `gemini` | Google Gemini |
| `perplexity` | Perplexity AI |
| `nvidia-deepseek` | DeepSeek via Nvidia NIM |
| `azure-mistral` | Mistral via Azure |
| `azure-mistral-small` | Mistral Small via Azure |
| `azure-codestral` | Codestral via Azure |
| `azure-deepseek` | DeepSeek via Azure |
| `azure-deepseek-v3` | DeepSeek V3 via Azure |
| `azure-ms-deepseek-r1` | MAI-DS-R1 via Azure |
| `azure-phi` | Phi-4 via Azure |

### LiteLLM Client Configuration

LiteLLM clients support additional configuration options:

**clients sheet with LiteLLM:**

| name | client_type | model | api_base | fallbacks |
|------|-------------|-------|----------|-----------|
| smart | litellm-anthropic | claude-3-5-sonnet-20241022 | | `["openai/gpt-4o"]` |
| azure-gpt | litellm-azure | gpt-4-deployment | https://my-instance.openai.azure.com | |

**Example prompts sheet with LiteLLM:**

| sequence | prompt_name | prompt | client |
|----------|-------------|--------|--------|
| 1 | analyze | Analyze this data | smart |
| 2 | summarize | Summarize the analysis | azure-gpt |

### Fallback Behavior

If a prompt references a client name that doesn't exist:
- A warning is logged
- The default client (from CLI) is used instead

---

## Document References

### Overview

Document references allow prompts to include content from external documents (PDFs, markdown files, JSON, etc.). Documents are parsed, cached, and injected into prompts at runtime.

### How It Works

1. Add a `documents` sheet with your document definitions
2. Add a `references` column to your prompts sheet
3. Reference documents by name in the `references` column

### Example

**documents sheet:**

| reference_name | common_name | file_path | notes |
|----------------|-------------|-----------|-------|
| product_spec | Product Spec | library/product_spec.md | Main spec |
| api_guide | API Reference | library/api_reference.pdf | REST API |

**prompts sheet:**

| sequence | prompt_name | prompt | references |
|----------|-------------|--------|------------|
| 1 | spec_summary | Summarize the key features. | `["product_spec"]` |
| 2 | api_overview | List the available endpoints. | `["api_guide"]` |
| 3 | combined | How does the API implement the spec? | `["product_spec", "api_guide"]` |

### Reference Injection Format

When documents are referenced, they are injected into the prompt as:

```xml
<REFERENCES>
<DOC name='product_spec'>
Document content here...
</DOC>
</REFERENCES>

===
Based on the documents above, please answer: [your prompt]
```

### Supported File Types

| Type | Handling |
|------|----------|
| `.md`, `.txt` | Read directly |
| `.json`, `.xml`, `.yaml` | Read directly |
| `.pdf` | Parsed via LlamaParse |
| `.docx`, `.pptx` | Parsed via LlamaParse |
| Other | Parsed via LlamaParse |

### Caching

- Documents are cached as parquet files in `doc_cache/`
- Filename format: `{checksum8}|{basename}.parquet`
- Re-parsing only occurs if source file checksum changes
- Set `document_cache_dir` in config sheet to customize location

### Error Handling

| Error | Behavior |
|-------|----------|
| Missing document file | Fail prompt immediately |
| Invalid reference name | Fail validation at startup |
| Parse failure | Raise exception with details |

### API Key for LlamaParse

Set the `LLAMACLOUD_TOKEN` environment variable for parsing non-text files:

```bash
export LLAMACLOUD_TOKEN="your-token-here"
```

---

## RAG Semantic Search

### Overview

RAG (Retrieval-Augmented Generation) semantic search allows prompts to retrieve relevant document chunks rather than injecting entire documents. This improves response quality and reduces token usage for large document libraries.

### How It Works

1. Documents are chunked and embedded into a vector store
2. Add a `semantic_query` column to your prompts sheet
3. The orchestrator searches for relevant chunks and injects them as context

### Example

**prompts sheet:**

| sequence | prompt_name | prompt | semantic_query |
|----------|-------------|--------|----------------|
| 1 | search | What authentication methods are available? | authentication security |

### Context Injection Format

When `semantic_query` is present:

```xml
<RELEVANT_CONTEXT>
[1] (source: api_guide) Score: 0.85
The API supports OAuth 2.0 authentication with refresh tokens...

[2] (source: product_spec) Score: 0.78
Authentication endpoints require Bearer token...
</RELEVANT_CONTEXT>

===
[original prompt]
```

### Per-Prompt RAG Overrides

Override RAG settings for specific prompts:

| Column | Values | Description |
|--------|--------|-------------|
| `semantic_filter` | JSON object | Filter by metadata (e.g., `{"doc_type": "api"}`) |
| `query_expansion` | `true`, `false` | Generate multiple query variations |
| `rerank` | `true`, `false` | Re-score results with cross-encoder |

**Example with overrides:**

| sequence | prompt_name | prompt | semantic_query | semantic_filter | query_expansion | rerank |
|----------|-------------|--------|----------------|-----------------|-----------------|--------|
| 1 | api_search | Find auth endpoints | authentication | `{"doc_type": "api"}` | true | true |
| 2 | quick | Quick lookup | pricing | | false | |

### Semantic Filter Syntax

```json
{"reference_name": "product_spec"}
{"doc_type": "api", "version": "v2"}
```

### Combining References and Semantic Search

Both `references` (full document) and `semantic_query` (relevant chunks) can be used together:

| sequence | prompt_name | prompt | references | semantic_query |
|----------|-------------|--------|------------|----------------|
| 1 | combined | Summarize the spec and find related API info | `["product_spec"]` | pricing features |

---

## Execution

### Run Command

```bash
python scripts/run_orchestrator.py <workbook_path> [options]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--client <type>` | | AI client to use (see supported types above) |
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

# Run with quiet mode (clean progress indicator)
python scripts/run_orchestrator.py analysis.xlsx -c 4 --quiet

# Use different client
python scripts/run_orchestrator.py analysis.xlsx --client anthropic

# Run batch workbook
python scripts/run_orchestrator.py batch_analysis.xlsx -c 3
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

### Progress Indicator

```
Starting orchestration with concurrency=4
Total prompts: 30
Log file: /path/to/logs/orchestrator.log

[████████░░░░░░░░░░░░] 15/30 (48%) | ✓14 ✗0 | →compare_9 | ⏳2 | ETA: 4s
```

---

## Results

After execution, a new sheet is added to the workbook with a timestamped name (e.g., `results_20260221_143052`).

### Results Sheet Columns

| Column | Description |
|--------|-------------|
| `batch_id` | Batch number (if batch mode) |
| `batch_name` | Batch name (if batch mode) |
| `sequence` | Execution order |
| `prompt_name` | Name of the prompt |
| `prompt` | The prompt text (resolved if batch mode) |
| `history` | Dependencies (JSON array) |
| `client` | Client name used |
| `condition` | Condition expression (if any) |
| `condition_result` | Result of condition evaluation |
| `condition_error` | Error if condition evaluation failed |
| `response` | AI response |
| `status` | `success`, `failed`, or `skipped` |
| `attempts` | Number of retry attempts |
| `error` | Error message (if failed) |
| `references` | Document references (JSON array) |
| `semantic_query` | RAG search query used |
| `semantic_filter` | RAG metadata filter (JSON) |
| `query_expansion` | Whether query expansion was enabled |
| `rerank` | Whether reranking was enabled |

---

## Error Handling

### Retry Logic

Failed prompts are retried up to `max_retries` times (default: 3). Configure in the `config` sheet.

### Batch Error Handling

When running in batch mode, configure `on_batch_error`:
- `continue` (default) - Continue to next batch on failure
- `stop` - Stop all processing on first batch failure

### Validation Errors

The orchestrator validates before execution:

- **Missing sheet**: `config` or `prompts` sheet not found
- **Missing columns**: Required columns not in prompts sheet
- **Invalid dependencies**: Referenced prompt_name doesn't exist
- **Dependency order**: Dependency defined after its use

---

## Programmatic Usage

```python
from src.orchestrator import ExcelOrchestrator, ClientRegistry
from src.Clients.FFMistralSmall import FFMistralSmall

# Initialize client
client = FFMistralSmall(api_key="your-api-key")

# Create orchestrator with parallel execution
orchestrator = ExcelOrchestrator(
    workbook_path="my_prompts.xlsx",
    client=client,
    config_overrides={"temperature": 0.5},
    concurrency=4,
)

# Run
results_sheet = orchestrator.run()

# Get summary
summary = orchestrator.get_summary()
print(f"Successful: {summary['successful']}")
print(f"Failed: {summary['failed']}")
if summary.get("batch_mode"):
    print(f"Total batches: {summary['total_batches']}")
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

---

## Sample Workbook Generators

Sample workbooks demonstrate orchestrator features and provide test cases for validation. Each workbook type has paired create and validate scripts following the naming convention:

```
sample_workbook_<type>_<action>_v<NNN>.py
```

### Workbook Types

| Type | Prompts | Description |
|------|---------|-------------|
| **basic** | 31 | Parallel execution with 4 dependency levels |
| **conditional** | 50 | Conditional expression testing (string, JSON, math, type checking) |
| **documents** | 23 | Document reference injection and RAG semantic search |
| **multiclient** | 13 | Multi-client execution with named configurations |
| **batch** | 35 | Batch execution with variable templating (35 × 5 = 175 executions) |
| **max** | 27 | Combined features: batch + conditional + multi-client + RAG |

### Using Invoke Tasks (Recommended)

```bash
# Show all available tasks
inv --list

# Full pipeline for all workbooks: clean → create → run → validate
inv all

# Create all workbooks in parallel
inv create --parallel

# Run orchestrator on all workbooks
inv run --parallel

# Validate all workbook results
inv validate

# Individual workbook (create + run + validate)
inv basic
inv multiclient
inv conditional
inv documents
inv batch
inv max
```

### Using Makefile

```bash
# Show available commands
make help

# Full pipeline for all workbooks: clean → create → run → validate
make all

# Create all workbooks
make create

# Run orchestrator on all workbooks
make run

# Validate all workbook results
make validate

# Individual workbook (create + run + validate)
make basic
make batch CONCURRENCY=5
make max
```

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make create` | Create all 6 sample workbooks |
| `make run` | Run orchestrator on all workbooks |
| `make validate` | Validate all workbook results using individual validation scripts |
| `make spot-check` | Spot check responses from key prompts |
| `make all` | Full pipeline: clean → create → run → validate |
| `make clean` | Remove all sample workbooks |
| `make basic` | Create, run, and validate basic workbook |
| `make multiclient` | Create, run, and validate multiclient workbook |
| `make conditional` | Create, run, and validate conditional workbook |
| `make documents` | Create, run, and validate documents workbook |
| `make batch` | Create, run, and validate batch workbook |
| `make max` | Create, run, and validate max workbook |

### Invoke Tasks

| Task | Description |
|------|-------------|
| `inv create` | Create all sample workbooks |
| `inv create --parallel` | Create workbooks in parallel |
| `inv run` | Run orchestrator on all workbooks |
| `inv run -c N` | Run with custom concurrency |
| `inv run --parallel` | Run workbooks in parallel |
| `inv validate` | Validate all workbook results |
| `inv validate --parallel` | Validate workbooks in parallel |
| `inv spot-check` | Spot check responses |
| `inv all` | Full pipeline: clean → create → run → validate |
| `inv clean` | Remove all sample workbooks |
| `inv basic` | Create, run, and validate basic workbook |
| `inv multiclient` | Create, run, and validate multiclient workbook |
| `inv conditional` | Create, run, and validate conditional workbook |
| `inv documents` | Create, run, and validate documents workbook |
| `inv batch` | Create, run, and validate batch workbook |
| `inv max` | Create, run, and validate max workbook |

### Options

| Option | Description |
|--------|-------------|
| `CONCURRENCY=N` (Makefile) | Set parallel execution (default: 3) |
| `-c N` (Invoke) | Set parallel execution (default: varies by workbook) |

### Validation Scripts

Each workbook type has a dedicated validation script:

| Script | Purpose |
|--------|---------|
| `sample_workbook_basic_validate_v001.py` | Validates basic workbook (31 prompts, 4 dependency levels) |
| `sample_workbook_multiclient_validate_v001.py` | Validates multiclient workbook (client assignment verification) |
| `sample_workbook_conditional_validate_v001.py` | Validates conditional workbook (50 prompts, condition evaluation) |
| `sample_workbook_documents_validate_v001.py` | Validates documents workbook (references vs semantic_query) |
| `sample_workbook_batch_validate_v001.py` | Validates batch workbook (35 prompts × 5 batches) |
| `sample_workbook_max_validate_v001.py` | Validates max workbook (batch + conditional + multi-client + RAG) |

Validation scripts check:
- Execution status (success/failed/skipped)
- Dependency chain resolution
- Condition evaluation results
- Client assignment (for multiclient)
- Batch count verification (for batch mode)

### Individual Scripts

#### Basic Sample Workbook

```bash
python scripts/sample_workbook_basic_create_v001.py [output_path]
python scripts/sample_workbook_basic_validate_v001.py [workbook_path]
```

31 prompts with 4 dependency levels for testing parallel execution.

#### Conditional Sample Workbook

```bash
python scripts/sample_workbook_conditional_create_v001.py [output_path]
python scripts/sample_workbook_conditional_validate_v001.py [workbook_path]
```

50 prompts testing conditional expressions: string methods, JSON functions, math operations, type checking.

#### Documents Sample Workbook

```bash
python scripts/sample_workbook_documents_create_v001.py [output_path]
python scripts/sample_workbook_documents_validate_v001.py [workbook_path]
```

23 prompts demonstrating document reference injection and RAG semantic search.

#### Multi-Client Sample Workbook

```bash
python scripts/sample_workbook_multiclient_create_v001.py [output_path]
python scripts/sample_workbook_multiclient_validate_v001.py [workbook_path]
```

13 prompts using different client configurations (default, fast, creative).

#### Batch Sample Workbook

```bash
python scripts/sample_workbook_batch_create_v001.py [output_path]
python scripts/sample_workbook_batch_validate_v001.py [workbook_path]
```

35 prompts × 5 batches = 175 total executions with variable templating.

#### Max Sample Workbook

```bash
python scripts/sample_workbook_max_create_v001.py [output_path]
python scripts/sample_workbook_max_validate_v001.py [workbook_path]
```

27 prompts combining batch execution, conditional branching, multi-client configuration, and RAG semantic search with 13 documents.

---

## Best Practices

### Prompt Naming

- Use descriptive, unique names: `customer_context`, `problem_statement`, `solution`
- Avoid generic names: `prompt1`, `question`, `test`

### Batch Mode

- Use `batch_name` column for meaningful batch identifiers
- Set `on_batch_error: continue` for resilient batch processing
- Test with small batches first

### Multi-Client Usage

- Define clients with descriptive names reflecting their purpose
- Use lower temperature for classification tasks
- Use higher temperature for creative tasks

### Parallel Execution

- Use `-c 3` or `-c 4` for optimal performance
- Set `-c 1` for debugging dependency issues
- Monitor API rate limits when increasing concurrency

---

## Troubleshooting

### API Key Issues

```bash
export MISTRALSMALL_KEY="your-key-here"
```

Or use a `.env` file.

### Unknown Client Warning

If you see `Client 'name' not found in registry, falling back to default client`:
- Check spelling of client name in prompts sheet
- Verify the client is defined in the clients sheet

### Dependency Validation Errors

```
ValueError: Dependency validation failed:
Sequence 5: dependency 'summary' not found in any prompt_name
```

Check that the prompt_name exists and is defined before it's referenced.

---

## Architecture

```
┌─────────────────────────────────────────┐
│           run_orchestrator.py           │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│          ExcelOrchestrator              │
│  - Load/validate workbook               │
│  - Build dependency graph               │
│  - Execute prompts (parallel/sequential)│
│  - Batch execution with templating      │
│  - Per-prompt client selection          │
│  - Document reference injection         │
└─────────────────────────────────────────┘
      │           │           │           │
      ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Workbook  │ │ClientReg │ │Document  │ │   FFAI   │
│Builder   │ │          │ │Registry  │ │          │
└──────────┘ └──────────┘ └────┬─────┘ └──────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │Document      │
                    │Processor     │
                    └──────────────┘
```

---

## Support

For issues or questions, contact: antquinonez@farfiner.com
