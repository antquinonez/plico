# AGENTS.md - Plico Development Guide

Guidelines for AI coding agents working in this repository.

## Build/Lint/Test Commands

### Testing

```bash
pytest tests/ -v                           # Run all tests (excluding integration)
pytest tests/test_ffai.py -v               # Run single test file
pytest tests/test_ffai.py::TestFFAIInit -v # Run single test class
pytest tests/test_ffai.py::TestFFAIInit::test_init_basic -v  # Run single test method
pytest tests/ --cov=src --cov-report=term-missing  # Run with coverage
pytest tests/integration/ -v               # Run integration tests (requires API keys)
```

### Linting and Formatting

```bash
ruff check src tests          # Check linting
ruff check src tests --fix    # Auto-fix linting issues
ruff format src tests         # Format code
```

### Invoke Tasks (Recommended)

```bash
inv --list                    # Show all available tasks
inv test                      # Run tests (excludes integration)
inv test -p tests/test_ffai.py  # Run specific test file
inv test-all                  # Run all tests including integration
inv lint                      # Run linting
inv format                    # Run formatting
inv config-check              # Display current configuration
```

### Workbook Tasks (wb namespace)

```bash
inv wb.create                 # Create all test workbooks
inv wb.run                    # Run orchestrator on all workbooks
inv wb.run -c 4               # Run with concurrency=4
inv wb.validate               # Validate all workbook results
inv wb.clean                  # Remove all test workbooks
inv wb.all                    # Full pipeline: clean, create, run, validate
inv wb.spot-check             # Spot check responses from key prompts
inv wb.basic                  # Create, run, and validate basic workbook
inv wb.multiclient            # Create, run, and validate multiclient workbook
inv wb.conditional            # Create, run, and validate conditional workbook
inv wb.documents              # Create, run, and validate documents workbook
inv wb.batch                  # Create, run, and validate batch workbook
inv wb.max                    # Create, run, and validate max workbook
inv wb.agent                  # Create, run, and validate agent workbook
```

### RAG Tasks (rag namespace)

```bash
inv rag.status                # Show RAG indexing status
inv rag.clear                 # Clear all RAG indexes
inv rag.clear -c recursive    # Clear specific chunking strategy
inv rag.clear-strategy recursive  # Clear specific chunking strategy
inv rag.rebuild               # Rebuild indexes from documents workbook
inv rag.stats                 # Show detailed RAG statistics
```

### Pre-commit

```bash
pre-commit run --all-files    # Run all hooks on all files
pre-commit install            # Install git hooks
```

## Project Structure

```
src/
├── FFAI.py                    # Main wrapper class for AI clients
├── FFAIClientBase.py          # Abstract base class for clients
├── config.py                  # Pydantic-based configuration management
├── OrderedPromptHistory.py    # Ordered prompt-response history tracking
├── PermanentHistory.py        # Chronological turn history
├── ConversationHistory.py     # Conversation management
│
├── Clients/                   # AI client implementations
│   ├── __init__.py            # Exports all client classes
│   ├── model_defaults.py      # Default model configurations
│   ├── FFAzureClientBase.py   # Base class for Azure clients
│   ├── FFMistral.py           # Mistral API client
│   ├── FFMistralSmall.py      # Mistral Small API client
│   ├── FFAnthropic.py         # Anthropic Claude client
│   ├── FFAnthropicCached.py   # Anthropic with prompt caching
│   ├── FFGemini.py            # Google Gemini client
│   ├── FFPerplexity.py        # Perplexity AI client
│   ├── FFOpenAIAssistant.py   # OpenAI Assistant API client
│   ├── FFNvidiaDeepSeek.py    # NVIDIA NIM DeepSeek client
│   ├── FFLiteLLMClient.py     # LiteLLM universal client
│   ├── FFAzureMistral.py      # Azure Mistral deployment
│   ├── FFAzureMistralSmall.py # Azure Mistral Small deployment
│   ├── FFAzureCodestral.py    # Azure Codestral deployment
│   ├── FFAzureDeepSeek.py     # Azure DeepSeek deployment
│   ├── FFAzureDeepSeekV3.py   # Azure DeepSeek V3 deployment
│   ├── FFAzureMSDeepSeekR1.py # Azure MS DeepSeek R1 deployment
│   └── FFAzurePhi.py          # Azure Phi deployment
│
├── orchestrator/              # Excel workbook orchestration
│   ├── __init__.py
│   ├── excel_orchestrator.py  # Main Excel orchestration engine
│   ├── workbook_parser.py    # Excel workbook parsing/validation
│   ├── manifest.py            # Manifest export and execution
│   ├── condition_evaluator.py # Conditional expression evaluation
│   ├── client_registry.py     # Multi-client configuration registry
│   ├── document_registry.py   # Document reference management
│   ├── document_processor.py  # Document loading and caching
│   ├── discovery.py           # Auto-discovery of documents for evaluation
│   ├── planning.py            # Planning phase artifact parsing and validation
│   ├── scoring.py             # Scoring rubric extraction and aggregation
│   ├── synthesis.py           # Cross-row synthesis for ranking/comparison
│   ├── tool_registry.py       # Tool registration and execution for agent mode
│   └── builtin_tools.py       # Built-in tool implementations
│
├── agent/                       # Agentic execution (opt-in tool-call loop)
│   ├── __init__.py              # Exports AgentResult, ToolCallRecord
│   ├── agent_result.py          # AgentResult, ToolCallRecord dataclasses
│   └── agent_loop.py            # Native agentic loop for tool-call execution
│
└── RAG/                       # Retrieval-Augmented Generation
    ├── __init__.py            # Exports all RAG components
    ├── FFRAGClient.py         # High-level RAG client
    ├── FFEmbeddings.py        # LiteLLM-based embeddings
    ├── FFVectorStore.py       # ChromaDB vector storage
    ├── text_splitter.py       # Legacy text chunking
    ├── text_splitters/        # Chunking strategies
    │   ├── __init__.py
    │   ├── base.py            # Chunker base class
    │   ├── character.py       # Character-based chunking
    │   ├── recursive.py       # Hierarchical recursive chunking
    │   ├── markdown.py        # Header-aware markdown chunking
    │   ├── code.py            # AST-style code chunking
    │   ├── hierarchical.py    # Parent-child chunk relationships
    │   └── factory.py         # Chunker factory
    ├── indexing/              # Indexing strategies
    │   ├── __init__.py
    │   ├── bm25_index.py      # BM25 keyword index
    │   ├── contextual_embeddings.py  # Context-aware embeddings
    │   ├── hierarchical_index.py     # Hierarchical indexing
    │   └── deduplication.py   # Chunk deduplication
    └── search/                # Search strategies
        ├── __init__.py
        ├── hybrid_search.py   # Vector + BM25 hybrid search
        ├── rerankers.py       # Cross-encoder reranking
        └── query_expansion.py # Query expansion utilities

tests/
├── conftest.py                # Shared fixtures
├── integration/               # Integration tests (require API keys)
│   ├── conftest.py
│   ├── test_orchestrator_integration.py
│   ├── test_batch_integration.py
│   ├── test_conditional_integration.py
│   ├── test_multiclient_integration.py
│   ├── test_documents_integration.py
│   ├── test_context_assembly.py
│   └── test_client_isolation.py
├── test_ffai.py               # FFAI wrapper tests
├── test_config.py             # Configuration tests
├── test_manifest.py           # Manifest workflow tests
├── test_excel_orchestrator.py # Orchestrator tests
├── test_workbook_parser.py    # Workbook parser tests
├── test_condition_evaluator.py # Condition evaluation tests
├── test_client_registry.py    # Client registry tests
├── test_document_processor.py # Document processor tests
├── test_document_registry.py  # Document registry tests
├── test_scoring.py            # Scoring rubric and aggregation tests
├── test_planning.py           # Planning phase orchestrator tests
├── test_planning_artifact_parser.py  # Planning artifact parser unit tests
├── test_synthesis.py          # Cross-row synthesis tests
├── test_discovery.py          # Auto-discovery utility tests
├── test_rag.py                # RAG client tests
├── test_rag_chunkers.py       # Chunking strategy tests
├── test_rag_search.py         # Search strategy tests
├── test_rag_indexing.py       # Indexing tests
├── test_rag_enhancements.py   # RAG enhancement tests
├── test_text_splitter.py      # Text splitter tests
├── test_ordered_prompt_history.py
├── test_permanent_history.py
├── test_ffmistral.py          # Mistral client tests
├── test_ffanthropic.py        # Anthropic client tests
├── test_ffgemini.py           # Gemini client tests
├── test_ffperplexity.py       # Perplexity client tests
├── test_fflitellm_client.py   # LiteLLM client tests
├── test_ffnvidia_deepseek.py  # NVIDIA client tests
├── test_ffopenai_assistant.py # OpenAI Assistant tests
├── test_ffazure_clients.py    # Azure client tests
└── test_litellm_orchestrator_integration.py

config/
├── main.yaml                  # Core application settings
├── paths.yaml                 # File system paths
├── clients.yaml               # Client type configurations
├── clients.yaml.example       # Example client config (safe to commit)
├── model_defaults.yaml        # Default model parameters
├── logging.yaml               # Logging configuration
└── sample_workbook.yaml       # Sample workbook test config

scripts/
├── run_orchestrator.py        # Run Excel orchestrator
├── export_manifest.py         # Export workbook to YAML manifest
├── run_manifest.py            # Run from manifest folder
├── inspect_parquet.py         # Inspect parquet results
├── parquet_to_excel.py        # Export parquet results to Excel workbook
├── sample_workbook_*_create_v001.py    # Workbook creation scripts
├── sample_workbook_*_validate_v001.py  # Workbook validation scripts
├── try_ai_mistralsmall_script.py       # Quick test script
└── validation/
    ├── __init__.py
    ├── validate_all.py        # Run all validations
    └── spot_check.py          # Spot check responses
```

## Clients Reference

### Client Classes by Provider

| Provider | Client Class | Type | Description |
|----------|--------------|------|-------------|
| **Mistral** | `FFMistral` | native | Mistral API (mistral-large-latest) |
| | `FFMistralSmall` | native | Mistral Small API (mistral-small-2503) |
| **Anthropic** | `FFAnthropic` | native | Claude via Anthropic API |
| | `FFAnthropicCached` | native | Claude with prompt caching |
| **Google** | `FFGemini` | openai | Gemini via OpenAI-compatible API |
| **Perplexity** | `FFPerplexity` | openai | Perplexity AI via OpenAI-compatible |
| **OpenAI** | `FFOpenAIAssistant` | openai | OpenAI Assistant API |
| **NVIDIA** | `FFNvidiaDeepSeek` | openai | DeepSeek via NVIDIA NIM |
| **LiteLLM** | `FFLiteLLMClient` | litellm | Universal client for 100+ providers |
| **Azure** | `FFAzureMistral` | azure | Azure-hosted Mistral |
| | `FFAzureMistralSmall` | azure | Azure-hosted Mistral Small |
| | `FFAzureCodestral` | azure | Azure-hosted Codestral |
| | `FFAzureDeepSeek` | azure | Azure-hosted DeepSeek |
| | `FFAzureDeepSeekV3` | azure | Azure-hosted DeepSeek V3 |
| | `FFAzureMSDeepSeekR1` | azure | Azure-hosted MS DeepSeek R1 |
| | `FFAzurePhi` | azure | Azure-hosted Phi |

### Client Types

- **native**: Uses provider's official SDK
- **openai**: Uses OpenAI-compatible API via AsyncOpenAI
- **azure**: Uses Azure AI Inference SDK
- **litellm**: Uses LiteLLM universal client

### Usage Example

```python
from src.Clients import FFMistralSmall, FFAnthropic, FFLiteLLMClient

# Native Mistral client
mistral = FFMistralSmall(api_key="...", model="mistral-small-2503")

# Native Anthropic client
anthropic = FFAnthropic(api_key="...", model="claude-3-5-sonnet-20241022")

# LiteLLM universal client
litellm = FFLiteLLMClient(
    model_string="openai/gpt-4",
    api_key="...",
)

# All clients share the same interface
response = client.generate_response("Hello!")
```

## RAG Module

The RAG (Retrieval-Augmented Generation) module provides document chunking, embedding, storage, and retrieval.

### Chunking Strategies

| Strategy | Class | Best For |
|----------|-------|----------|
| Character | `CharacterChunker` | Simple text, fixed-size chunks |
| Recursive | `RecursiveChunker` | General purpose, hierarchical |
| Markdown | `MarkdownChunker` | Markdown documents, preserves headers |
| Code | `CodeChunker` | Source code, function-aware |
| Hierarchical | `HierarchicalChunker` | Parent-child relationships |

### Search Modes

| Mode | Description |
|------|-------------|
| `vector` | Pure vector similarity search |
| `hybrid` | Vector + BM25 keyword search |
| `rerank` | Vector search + cross-encoder reranking |

### Usage Example

```python
from src.RAG import FFRAGClient, MarkdownChunker

# Initialize RAG client
rag = FFRAGClient(
    chunking_strategy="markdown",
    search_mode="hybrid",
)

# Add documents
rag.add_document("Long document text...", metadata={"source": "doc.md"})

# Search
results = rag.search("What is this about?", n_results=5)

# Use in prompts (via orchestrator)
# In workbook: semantic_query column triggers RAG search
```

### RAG Configuration (config/main.yaml)

```yaml
rag:
  enabled: true
  persist_dir: "./chroma_db"
  collection_name: "plico_kb"
  embedding_model: "mistral/mistral-embed"
  chunking:
    strategy: "recursive"
    chunk_size: 1000
    chunk_overlap: 200
  search:
    mode: "vector"
    n_results_default: 5
    rerank: false
```

## Rate Limiting and Retries

The FFClients library implements a **layered retry strategy** to handle transient failures like rate limits (429 errors), service unavailability (503), and network issues.

### Architecture

The retry system operates at two layers:

1. **LiteLLM Layer** (FFLiteLLMClient): Uses LiteLLM's built-in retry mechanism
2. **Client Layer** (All clients): Uses tenacity decorators for exponential backoff with jitter

### Configuration

Configure retry behavior globally in `config/main.yaml`:

```yaml
retry:
  max_attempts: 3              # Maximum retry attempts
  min_wait_seconds: 1          # Minimum initial wait time
  max_wait_seconds: 60         # Maximum wait time cap
  exponential_base: 2          # Backoff multiplier (2x each retry)
  exponential_jitter: true     # Add randomness to prevent thundering herd
  retry_on_status_codes:       # HTTP codes to retry
    - 429                      # Rate limit
    - 503                      # Service unavailable
    - 502                      # Bad gateway
    - 504                      # Gateway timeout
  log_level: "INFO"            # Logging level for retry attempts
```

### Retry Behavior

When a rate limit or transient error occurs:

1. **Detection**: Client detects retryable error (429, 503, network timeout)
2. **Extraction**: Parses `retry-after` header if present
3. **Backoff**: Waits with exponential backoff + jitter
4. **Retry**: Retries the API call up to `max_attempts`
5. **Logging**: Logs each retry attempt with delay duration

Example log output:
```
INFO - Retrying generate_response for FFMistralSmall (attempt 2/3) after 2.5s delay
WARNING - Rate limit hit for gemini/gemini-2.5-flash-lite. Retry after 53.8s
```

### Wait Time Calculation

With default settings:
- Attempt 1: Immediate
- Attempt 2: Wait ~2s (1 × 2^1 + jitter)
- Attempt 3: Wait ~4s (1 × 2^2 + jitter)

If the API provides a `retry-after` header, that value is used instead.

### Client-Specific Behavior

**LiteLLM Clients** (FFLiteLLMClient):
- Uses LiteLLM's native `num_retries` configuration
- Automatic retry on 429, 503, 502, 504 status codes
- Respects `retry-after` headers from providers

**Native Clients** (FFMistralSmall, FFAnthropic, FFGemini, etc.):
- Tenacity decorator with exponential backoff
- Converts provider-specific rate limit errors to `RateLimitError`
- Shared retry configuration across all native clients

### Best Practices

1. **Start with defaults**: The default config (3 retries, 1-60s backoff) works for most APIs
2. **Adjust for rate limits**: Increase `max_attempts` to 5 for heavily rate-limited APIs
3. **Monitor logs**: Check `logs/orchestrator.log` for retry patterns
4. **Reduce concurrency**: If seeing many 429s, lower `--concurrency` flag
5. **Respect quotas**: Free tier APIs often have 10-60 requests/minute limits

### Example: Handling Gemini Rate Limits

```bash
# Gemini free tier: 10 requests/minute
# With 31 prompts, expect rate limits

# Option 1: Lower concurrency
python scripts/run_orchestrator.py workbook.xlsx --concurrency 1

# Option 2: Increase retries (edit config/main.yaml)
retry:
  max_attempts: 5
  min_wait_seconds: 2
  max_wait_seconds: 120

# Option 3: Use LiteLLM client (has built-in retry)
# In workbook config sheet:
# client_type: litellm-gemini
```

### Troubleshooting

**Problem**: Still seeing 429 errors
- Check `retry.max_attempts` in config
- Verify logs show retry attempts
- Reduce concurrency to 1
- Wait 60s between runs (resets quota)

**Problem**: Retries taking too long
- Lower `max_wait_seconds`
- Reduce `max_attempts`
- Check if `retry-after` header is very long

**Problem**: No retry logging
- Verify `log_level` is set to "INFO"
- Check that `src.retry_utils` is imported
- Ensure client has retry decorator

## Agent Module

The agent module provides opt-in agentic tool-call execution within the deterministic DAG orchestrator. Prompts can use tools like `calculate`, `json_extract`, and `http_get` via a multi-round LLM loop.

### Usage

Enable agent mode by setting `agent_mode=true` in the prompts sheet and specifying available tools:

| Column | Description |
|--------|-------------|
| `agent_mode` | Set to `true` to enable tool-call loop |
| `tools` | JSON array of tool names (e.g., `["calculate", "json_extract"]`) |
| `max_tool_rounds` | Max tool-call rounds (default from config, typically 5) |

Tools are defined in a `tools` sheet with columns: `name`, `description`, `parameters` (JSON Schema), `implementation` (`builtin:<name>` or `python:<module.func>`), `enabled`.

### Built-in Tools

| Tool | Description |
|------|-------------|
| `calculate` | Evaluate math expressions safely via AST |
| `json_extract` | Extract fields from JSON using dot notation |
| `http_get` | Fetch text content from a URL |
| `rag_search` | Semantic search across indexed documents |
| `read_document` | Read a document's full content |
| `list_documents` | List available document names |

### Result Fields

Agent execution populates additional fields on the result:
- `agent_mode`: `true` if agent loop was used
- `tool_calls`: List of tool call records (name, arguments, result, duration, errors)
- `total_rounds`: Number of agentic loop rounds
- `total_llm_calls`: Total LLM API calls within the loop

### Condition Properties

Conditions can reference agent result properties:
```
{{research.tool_calls_count}} > 0
{{research.total_rounds}} <= 3
{{research.last_tool_name}} == "rag_search"
{{research.agent_mode}} == True
```

### Configuration (config/main.yaml)

```yaml
agent:
  enabled: true
  max_tool_rounds: 5
  tool_timeout: 30.0
  continue_on_tool_error: true
```

## Planning Phase (Dynamic Prompt Generation)

The planning phase enables the orchestrator to derive scoring criteria and evaluation prompts from documents (e.g., a job description) via LLM calls, eliminating the need for a manual scoring worksheet. Planning prompts run in a dedicated phase before batch execution.

### Prompts Sheet: Planning Columns

| Column | Values | Description |
|--------|--------|-------------|
| `phase` | `planning` or `execution` (default) | Controls when the prompt runs |
| `generator` | `true` or `false` (default) | Whether the prompt returns structured JSON artifacts |

### Generator Response Schema

Generator prompts (`generator=true`) return JSON with optional `scoring_criteria` and `prompts` arrays:

```json
{
  "scoring_criteria": [
    {"criteria_name": "skills_match", "description": "...", "scale_min": 1, "scale_max": 10, "weight": 1.0, "source_prompt": "evaluate_skills"}
  ],
  "prompts": [
    {"prompt_name": "evaluate_skills", "prompt": "Evaluate {{candidate_name}}'s skills.", "references": ["job_desc"]}
  ]
}
```

### Phase Rules

- Planning prompts execute **sequentially** (never parallel), regardless of concurrency.
- Planning prompts **cannot** use `{{variable}}` batch references (validated as error).
- Planning prompts **can** use `references` for document injection and `history` for chaining.
- Execution prompts **can** use `{{planning_prompt.response}}` to interpolate planning results.
- If a manual scoring sheet exists, it takes priority over auto-derived criteria (logged as warning).
- Generated prompts are tagged with `_generated: true` and assigned sequence numbers automatically.

### History Compatibility Note

Generator prompts return JSON which FFAI flattens by key into `shared_prompt_attr_history`. The orchestrator manually appends a history entry with the original `prompt_name` for each generator prompt, enabling `{{generator_name.response}}` interpolation in downstream prompts.

### Configuration (config/main.yaml)

```yaml
planning:
  enabled: true
  save_artifacts: false
  generated_sequence_base: "auto"
  generated_sequence_step: 10
  continue_on_parse_error: true
```

## Evaluation Module (Scoring and Synthesis)

The evaluation module enables structured document evaluation workflows: score extraction, weighted aggregation, and cross-row comparison/ranking.

### New Workbook Sheets

**Scoring sheet** — defines evaluation criteria extracted from LLM JSON responses:

| Column | Description |
|--------|-------------|
| `criteria_name` | Machine-readable key (e.g., `skills_match`) |
| `description` | Human-readable description |
| `scale_min` / `scale_max` | Score range (uniform across all criteria, enforced by validation) |
| `weight` | Base weight for aggregation |
| `source_prompt` | Which prompt response contains this score |

**Synthesis sheet** — post-batch prompts that compare/rank entries:

| Column | Description |
|--------|-------------|
| `sequence` | Execution order |
| `prompt_name` | Unique name |
| `prompt` | The prompt text |
| `source_scope` | `all` or `top:N` — which batch entries to include |
| `source_prompts` | JSON array of prompt names whose responses to include |
| `include_scores` | Include scoring breakdown (default: true) |
| `history` | Synthesis prompt dependencies (other synthesis prompts) |
| `condition` | Condition for execution |

### Per-Row Document Binding

Data rows can declare per-row documents via the `_documents` column. Values are **additively merged** with each prompt's `references` at execution time:

```
| id | batch_name | candidate_name | _documents       |
|----|------------|----------------|------------------|
| 1  | alice_chen | Alice Chen     | ["resume_alice"] |
```

### Evaluation Strategies

Strategy-based weight overrides are configured in `config/main.yaml` under `evaluation.strategies` (not in the workbook). The `evaluation_strategy` field in the config sheet selects which strategy to use for the run.

### New Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `scores` | JSON | Extracted scores per criteria |
| `composite_score` | Float | Weighted average |
| `scoring_status` | String | `ok`, `partial`, `failed`, or `skipped` |
| `strategy` | String | Strategy name used |
| `result_type` | String | `batch`, `synthesis`, or `planning` |

### Auto-Discovery Utility

`src/orchestrator/discovery.py` provides `discover_documents()`, `create_data_rows_from_documents()`, and `create_evaluation_workbook()` for auto-generating evaluation workbooks from a folder of documents.

### Execution Order

```
run() → _load_source() → _validate_pre_planning() → _init_client()

─── Planning Phase (if has_planning) ──────────────
_execute_planning_phase()
  ├── Execute planning prompts sequentially
  ├── Parse generator artifacts (scoring_criteria, prompts)
  ├── Inject generated prompts into self.prompts
  ├── Auto-derive ScoringRubric (if no manual scoring sheet)
  └── _validate_post_planning()

─── Execution Phase ───────────────────────────────
batch execution (or sequential/parallel)
  → All execution-phase prompts (static + generated)

─── Post-Execution ────────────────────────────────
_aggregate_scores() → _execute_synthesis() → _write_results()
```

When no planning prompts exist, the flow is the same as before:
`run() → _load_source() → _validate() → _init_client() → execution → results`

## Manifest Workflow

**For comprehensive manifest documentation, see [MANIFEST_README.md](./MANIFEST_README.md)**

The manifest workflow separates workbook parsing from execution, enabling version control of prompts.

### Export Workbook to Manifest

```bash
# Export to default manifest directory
python scripts/manifest_export.py ./workbooks/my_prompts.xlsx

# Export to custom directory
python scripts/manifest_export.py ./workbook.xlsx --output ./custom_manifest/
```

Creates a folder with:
- `manifest.yaml` - Metadata
- `config.yaml` - Configuration
- `prompts.yaml` - All prompts
- `data.yaml` - Batch data (if present, preserves `_documents`)
- `clients.yaml` - Client configs (if present)
- `documents.yaml` - Document refs (if present)
- `scoring.yaml` - Scoring criteria (if present)
- `synthesis.yaml` - Synthesis prompts (if present)

### Run from Manifest

```bash
# Run with default settings
python scripts/manifest_run.py ./manifests/manifest_my_prompts

# Run with specific client and concurrency
python scripts/manifest_run.py ./manifests/manifest_my_prompts --client mistral-small -c 4

# Dry run to validate
python scripts/manifest_run.py ./manifests/manifest_my_prompts --dry-run
```

### Inspect Results

```bash
python scripts/manifest_inspect.py ./outputs/20250301120000_my_prompts.parquet

# Extract final post, hashtags, image_prompt, and source_url
python scripts/manifest_extract.py ./outputs/20250301120000_my_prompts.parquet

# Export results to files
python scripts/manifest_extract.py ./outputs/results.parquet --output-dir ./extracted

# Export parquet to Excel (includes resolved_prompt column)
python scripts/parquet_to_excel.py ./outputs/results.parquet
```

## Config Worksheet Reference

The config worksheet defines process-level settings for the orchestrator. The worksheet has three columns:

### Column Structure

| Column | Header | Description |
|--------|--------|-------------|
| A | field | Config field name |
| B | value | Current value for this field |
| C | notes | Documentation for the field (acceptable values, source) |

### Standard Config Fields
        | Field | Required | Default | Source | Acceptable Values |
        |-------|----------|---------|--------|-------------------|
        | `name` | No | (filename) | User | Any string - human-readable name for this process |
        | `description` | No | empty | User | Any string - brief description of the process |
        | `client_type` | No | (from config) | `config/clients.yaml` | Keys from `client_types` section |
        | `model` | No | (provider default) | Provider-specific | See `model_defaults.yaml` for examples |
        | `api_key_env` | No | (from config) | `.env` file | Environment variable name |
        | `max_retries` | No | 3 | - | `1` to `10` |
        | `temperature` | No | 0.7 | - | `0.0` to `2.0` |
        | `max_tokens` | No | 4096 | - | Positive integer |
        | `system_instructions` | No | (from config) | User | System prompt for AI |
        | `created_at` | No | (auto-generated) | - | ISO timestamp when workbook was created |

### Batch Mode Fields (only for workbooks with data sheet)
        | Field | Required | Default | Acceptable Values |
        |-------|----------|---------|-------------------|
        | `batch_mode` | No | per_row | `per_row` (execute for each data row) |
        | `batch_output` | No | combined | `combined`, `separate_sheets` |
        | `on_batch_error` | No | continue | `continue`, `stop` |

### Field Value Sources
        | Field | Where to Get Valid Values |
        |-------|----------------------------|
        | `client_type` | `config/clients.yaml` → `client_types` keys |
        | `model` | `config/model_defaults.yaml` → `models` keys |
        | `api_key_env` | `.env` file - must be set in environment |

### Example Config Sheet
        ```text
        | field            | value                           | notes                                         |
        |------------------|--------------------------------|-----------------------------------------------|
        | name             | My Analysis Process           | Human-readable name for this process          |
        | description     | Analyzes sales data by region | Brief description of what this process does    |
        | client_type      | litellm-mistral-small           | AI client type from config/clients.yaml       |
        | model            | mistral-small-latest           | Model identifier                               |
        | api_key_env      | MISTRAL_API_KEY               | Environment variable name for API key         |
        | max_retries      | 3                              | Maximum retry attempts (1-10)                |
        | temperature      | 0.7                            | Sampling temperature (0.0-2.0)               |
        | max_tokens        | 4096                           | Maximum response tokens                       |
        | system_instructions | You are a helpful assistant | System prompt for AI                    |
        | created_at        | 2025-03-22T10:30:00           | ISO timestamp when created                  |
        ```

## Workbook Scripts Naming Convention

Scripts that create or validate sample workbooks follow this naming pattern:

```
sample_workbook_<type>_<action>_v<NNN>.py
```

Where:
- `<type>`: Workbook type (`basic`, `conditional`, `documents`, `multiclient`, `batch`, `max`)
- `<action>`: `create` or `validate`
- `<NNN>`: Three-digit version number (`001`, `002`, etc.)

### Examples

| Type | Create Script | Validate Script |
|------|---------------|-----------------|
| Basic | `sample_workbook_basic_create_v001.py` | `sample_workbook_basic_validate_v001.py` |
| Conditional | `sample_workbook_conditional_create_v001.py` | `sample_workbook_conditional_validate_v001.py` |
| Documents | `sample_workbook_documents_create_v001.py` | `sample_workbook_documents_validate_v001.py` |
| Multiclient | `sample_workbook_multiclient_create_v001.py` | `sample_workbook_multiclient_validate_v001.py` |
| Batch | `sample_workbook_batch_create_v001.py` | `sample_workbook_batch_validate_v001.py` |
| Max | `sample_workbook_max_create_v001.py` | `sample_workbook_max_validate_v001.py` |
| Agent | `sample_workbook_agent_create_v001.py` | `sample_workbook_agent_validate_v001.py` |
| Screening | `sample_workbook_screening_create_v001.py` | `sample_workbook_screening_validate_v001.py` |

### Versioning Guidelines

1. **Creating a new version**: Increment the version number (e.g., `v001` → `v002`)
2. **Major changes**: When significantly changing workbook structure, conditions, or test coverage
3. **Bug fixes**: Minor fixes may not require version increment
4. **Pairing**: Create and validate scripts with the same version number are designed to work together

### Creating New Workbook Types

When creating a new workbook type:

1. Create both create and validate scripts starting with `v001`
2. Follow the pattern: `sample_workbook_<new_type>_<action>_v001.py`
3. Update this AGENTS.md with the new type in the examples table
4. Include the version number in the script docstring

### Workbook Types

| Type | Description | Key Features |
|------|-------------|--------------|
| Basic | Parallel execution with dependencies | 31 prompts, 4 levels of dependency chains |
| Conditional | Conditional expression testing | 50 prompts testing string methods, JSON functions, math, type checking |
| Documents | Document reference and RAG testing | Full document injection, semantic search via RAG |
| Multiclient | Multi-client execution | Named client configurations, client-specific prompts |
| Batch | Batch execution with variables | 35 prompts x 5 batches, variable templating |
| Max | Combined features | Batch + conditional + multi-client in one workbook |
| Agent | Agentic tool-call loop | Opt-in agent mode with built-in tools, multi-round execution |
| Screening | Document evaluation pipeline | Per-row documents, scoring rubric, synthesis ranking |
| Screening v002 | Planning phase screening | Auto-derived scoring from LLM, generator prompts, refinement pattern |

### Workflow

```bash
# Create a workbook
python scripts/sample_workbook_basic_create_v001.py ./test.xlsx

# Run the orchestrator
python scripts/run_orchestrator.py ./test.xlsx -c 3

# Validate the results
python scripts/sample_workbook_basic_validate_v001.py ./test.xlsx

# Or validate with JSON output for CI/CD
python scripts/sample_workbook_basic_validate_v001.py ./test.xlsx --json
```

## Code Style Guidelines

### Python Version and Type Hints

- Target Python 3.10+ (Python 3.14 recommended)
- Use modern union syntax: `str | None` instead of `Optional[str]`
- Use `list[str]` instead of `List[str]`
- Always include return type hints for functions/methods
- Use `from __future__ import annotations` for forward references

### Imports

```python
# Standard library first
import json
import logging
from collections.abc import Callable
from typing import Any

# Third-party packages second
import polars as pl
from pydantic import Field

# Local imports last (use relative for same package)
from .FFAIClientBase import FFAIClientBase
from ..config import get_config
```

### Formatting

- Line length: 100 characters
- Use ruff for formatting (Black-compatible)
- Indent with 4 spaces, single quotes for strings

### Naming Conventions

- **Classes**: PascalCase (`FFMistral`, `ExcelOrchestrator`)
- **Functions/Methods**: snake_case (`generate_response`, `get_config`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_MODEL`, `MAX_RETRIES`)
- **Private methods**: prefix with underscore (`_initialize_client`)
- **Files**: snake_case (`excel_orchestrator.py`, `test_ffai.py`)

### Docstrings

```python
def generate_response(self, prompt: str, prompt_name: str | None = None) -> str:
    """Generate a response from the AI client.

    Args:
        prompt: The user prompt to send.
        prompt_name: Optional name for this prompt.

    Returns:
        The AI-generated response string.

    Raises:
        ValueError: If the client is not initialized.

    """
```

### Error Handling and Logging

```python
import logging

logger = logging.getLogger(__name__)

if not api_key:
    logger.error("API key not found")
    raise ValueError("API key not found")
```

- Use specific exception types
- Log errors with `logger.error()` before raising
- Use f-strings for error messages

### Testing Conventions

- Use pytest with class-based test organization
- Place shared fixtures in `conftest.py`
- Name test files as `test_<module>.py`, classes as `Test<Feature>`, methods as `test_<description>`
- Import modules inside test methods when mocking is needed

```python
class TestFFAIGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_basic(self, mock_ffmistralsmall):
        """Test basic response generation."""
        from src.FFAI import FFAI

        ffai = FFAI(mock_ffmistralsmall)
        response = ffai.generate_response("Hello!")

        assert response == "This is a test response."
```

### Ruff Rules Enabled

```toml
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM", "PLC", "PLW", "RET", "RUF"]
```

### Dead Code Detection (Vulture)

Vulture is used to detect unreachable code and unused definitions.

```bash
vulture src vulture_whitelist.py --min-confidence 80
```

Add false positives to `vulture_whitelist.py` with a `# noqa: V103` comment explaining why the item is intentionally unused.

### Key Patterns

- AI clients inherit from `FFAIClientBase`
- Use `match` statements for configuration parsing (Python 3.10+)
- DataFrame operations prefer Polars over Pandas
- Excel workbooks use openpyxl
- Access configuration via `get_config()` from `src.config`
- RAG operations use `FFRAGClient` from `src.RAG`

## Configuration Files

### config/main.yaml

Core application settings: workbook sheet names, orchestrator settings, document processor config, RAG settings.

### config/paths.yaml

File system paths for data storage, caches, outputs, and manifests.

```yaml
paths:
  ffai_data: "./ffai_data"
  doc_cache: "doc_cache"
  library: "library"
  output_dir: "./outputs"
  manifest_dir: "./manifests"
```

### config/clients.yaml

Client type definitions with API key environment variables, model classes, and defaults. Copy from `clients.yaml.example`.

### config/model_defaults.yaml

Default parameters for each model (temperature, max_tokens, etc.).

### config/logging.yaml

Logging configuration: log directory, file rotation, format.

## Dependencies

### Core Dependencies

- `mistralai` - Mistral API SDK
- `anthropic` - Anthropic API SDK
- `openai` - OpenAI API SDK
- `azure-ai-inference` - Azure AI SDK
- `litellm>=1.0.0` - Universal LLM client
- `chromadb>=0.4.0` - Vector database for RAG
- `pydantic-settings>=2.0.0` - Configuration management
- `polars[rtcompat]` - DataFrame operations
- `openpyxl` - Excel workbook handling
- `json-repair>=0.30.0` - JSON parsing with repair

### Dev Dependencies

- `pytest`, `pytest-cov` - Testing
- `ruff` - Linting and formatting
- `pre-commit` - Git hooks
- `invoke>=2.0.0` - Task runner
- `vulture>=2.16` - Dead code detection

## Environment

- Virtual environment: `.venv/` (Python 3.14)
  - Activate: `source .venv/bin/activate`
  - Install: `uv pip install -e ".[dev]"`
- Environment variables: Load via `python-dotenv` (`load_dotenv()`)
- Set `POLARS_SKIP_CPU_CHECK=1` for Polars compatibility

### Required Environment Variables (in .env)

```bash
# At least one API key required
MISTRALSMALL_KEY=your-key-here
MISTRAL_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
GEMINI_KEY=your-key-here
PERPLEXITY_KEY=your-key-here
NVIDIA_KEY=your-key-here
OPENAI_KEY=your-key-here

# Azure deployments
AZURE_MISTRAL_KEY=your-key-here
AZURE_PHI_KEY=your-key-here
# ... etc
```

## Notes

- This is proprietary code - do not share externally
- Integration tests require real API keys in `.env`
- Use `inv --list` to see all available commands
- Use `inv help` for detailed task documentation
