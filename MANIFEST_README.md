# Plico Manifest Guide for AI Agents

This document provides everything an AI agent needs to create, modify, and process Plico manifests.

---

## What is a Manifest?

A **manifest** is a folder of YAML files that defines an AI workflow declaratively. It specifies:
- What prompts to send to AI models
- How prompts depend on each other
- Which AI models/clients to use
- Conditions for conditional execution
- Batch data for repeated execution
- Document references for RAG

**Manifests are the canonical, version-controllable representation of a workflow.**

---

## Manifest File Structure

```
manifest_my_workflow/
├── manifest.yaml      # Required — metadata
├── config.yaml        # Required — runtime settings
├── prompts.yaml       # Required — prompt graph
├── data.yaml          # Optional — batch data
├── clients.yaml       # Optional — named client configurations
├── documents.yaml     # Optional — document references
└── tools.yaml         # Optional — tool definitions for agent mode
```

The optional files are only needed when the workflow requires them. The `has_data`, `has_clients`, `has_documents`, and `has_tools` flags in `manifest.yaml` control which optional files are loaded.

---

## Creating a Manifest from Scratch

An AI agent can create a manifest by writing YAML files directly to a folder. No Excel workbook is required.

### Step 1: Create the manifest folder

```
mkdir -p manifests/manifest_my_workflow
```

### Step 2: Write manifest.yaml

```yaml
name: "my_workflow"
description: "An AI-generated workflow"
version: "1.0"
source_workbook: ""
exported_at: "2025-01-15T10:00:00"
has_data: false
has_clients: false
has_documents: false
prompt_count: 3
```

### Step 3: Write config.yaml

```yaml
client_type: "litellm-mistral-small"
model: "mistral-small-latest"
temperature: 0.7
max_tokens: 4096
max_retries: 3
system_instructions: "You are a helpful assistant."
```

### Step 4: Write prompts.yaml

```yaml
prompts:
  - sequence: 1
    prompt_name: "intro"
    prompt: "What is your name?"
    history: []
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 2
    prompt_name: "question"
    prompt: "What is interesting about AI?"
    history: ["intro"]
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 3
    prompt_name: "summarize"
    prompt: "Summarize our conversation in one sentence."
    history: ["intro", "question"]
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null
```

---

## Running a Manifest

### Command Line

```bash
# Run with default settings
python scripts/manifest_run.py ./manifests/manifest_my_workflow

# Run with specific client and concurrency
python scripts/manifest_run.py ./manifests/manifest_my_workflow --client mistral-small -c 4

# Dry run to validate
python scripts/manifest_run.py ./manifests/manifest_my_workflow --dry-run
```

### Python API

```python
from src.orchestrator import ManifestOrchestrator
from src.Clients.FFLiteLLMClient import FFLiteLLMClient

client = FFLiteLLMClient(model_string="openai/gpt-4o-mini")
orchestrator = ManifestOrchestrator(
    manifest_dir="./manifests/manifest_my_workflow",
    client=client,
    concurrency=4
)
parquet_path = orchestrator.run()

summary = orchestrator.get_summary()
print(f"Success: {summary['successful']}, Failed: {summary['failed']}")
```

### Output

Results are written to a timestamped Parquet file:
```
./outputs/20250115100000_my_workflow.parquet
```

**Parquet columns:**

| Column | Description |
|--------|-------------|
| `prompt` | Original prompt template as written (with `{{variable}}` placeholders intact) |
| `resolved_prompt` | Fully-resolved prompt sent to the AI (all `{{}}` variables substituted, conversation history assembled) |
| `response` | AI-generated response text |
| `status` | `"success"`, `"failed"`, or `"skipped"` |
| `condition` | Condition expression (if any) |
| `condition_result` | Evaluated condition value |
| `error` | Error message (if failed) |
| `attempts` | Number of retry attempts |
| `client` | Client name used (multi-client mode) |
| `batch_id` / `batch_name` | Batch identifiers (batch mode) |
| `references` | Document references (JSON array) |
| `semantic_query` | RAG query used |
| `rerank` / `query_expansion` | RAG settings |
| `sequence` / `prompt_name` / `history` | Execution metadata |

> **`prompt` vs `resolved_prompt`:** The `prompt` column preserves your original template text (useful for auditing what you asked). The `resolved_prompt` column shows what was actually sent to the AI, including any `{{prompt_name.response}}` substitutions and the assembled `<conversation_history>` block. When a referenced prompt was **skipped** (condition evaluated to false), its `{{}}` pattern is replaced with an empty string in `resolved_prompt`.

Inspect results:
```bash
python scripts/manifest_inspect.py ./outputs/20250115100000_my_workflow.parquet
```

Export to Excel:
```bash
python scripts/parquet_to_excel.py ./outputs/20250115100000_my_workflow.parquet
```

---

## File Reference

### manifest.yaml — Metadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | No | Human-readable name for this workflow (used for output directory) |
| `description` | `str` | No | Brief description |
| `version` | `str` | Yes | Manifest format version (use `"1.0"`) |
| `source_workbook` | `str` | No | Path to source Excel (empty if AI-generated) |
| `exported_at` | `str` | No | ISO 8601 timestamp |
| `output_prompts` | `list[str]` | No | Prompt names to extract (e.g., `["final_post", "hashtags"]`) |
| `has_data` | `bool` | Yes | Whether `data.yaml` exists |
| `has_clients` | `bool` | Yes | Whether `clients.yaml` exists |
| `has_documents` | `bool` | Yes | Whether `documents.yaml` exists |
| `has_tools` | `bool` | No | Whether `tools.yaml` exists |
| `prompt_count` | `int` | Yes | Total number of prompts |

**Output Directory Structure:**
```
outputs/
├── <manifest_name>/
│   ├── 20260324193142.parquet      # Timestamped parquet
│   ├── 20260324193142/             # Extracted results folder
│   │   ├── final_post.md
│   │   ├── hashtags.json
│   │   └── _summary.json
│   └── 20260324194500.parquet      # Second run
```

---

### config.yaml — Runtime Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `client_type` | `str` | From config | Client type (e.g., `"litellm-mistral-small"`) |
| `model` | `str` | From client | Model identifier |
| `api_key_env` | `str` | From client | Environment variable for API key |
| `max_retries` | `int` | `3` | Retry attempts per prompt (1-10) |
| `temperature` | `float` | `0.7` | Sampling temperature (0.0-2.0) |
| `max_tokens` | `int` | `4096` | Maximum response tokens |
| `system_instructions` | `str` | `""` | System prompt for AI |
| `on_batch_error` | `str` | `"continue"` | Batch error handling: `"continue"` or `"stop"` |
| `document_cache_dir` | `str` | Auto | Override path for document cache |
| `created_at` | `str` | Auto | ISO timestamp |
| `batch_mode` | `str` | `"per_row"` | Batch mode (informational) |
| `batch_output` | `str` | `"combined"` | Batch output format (informational) |

---

### prompts.yaml — Prompt Graph

Each prompt entry is a node in the execution DAG.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sequence` | `int` | Yes | Execution order (1-based). Same-level prompts with no dependencies run in parallel. |
| `prompt_name` | `str` | Yes | Unique identifier. Referenced by `history`, `condition`, and `client`. |
| `prompt` | `str` | Yes | The prompt text. Supports `{{variable}}` templating in batch mode and `{{prompt_name.response}}` for referencing previous results. In the output parquet, `prompt` retains this original template while `resolved_prompt` contains the fully-resolved text. |
| `history` | `list[str]` | No | `prompt_name` values whose responses are injected as context. |
| `client` | `str` | No | Named client from `clients.yaml` for multi-model routing. |
| `condition` | `str` | No | Expression for conditional execution. If falsy, prompt is skipped. |
| `references` | `list[str]` | No | `reference_name` values from `documents.yaml` for full document injection. |
| `semantic_query` | `str` | No | Natural language query for RAG semantic search. |
| `semantic_filter` | `str` | No | JSON string for filtering RAG results (e.g., `'{"reference_name": "api_ref"}'`). |
| `query_expansion` | `str` | No | Enable multi-query retrieval: `"true"`, `"yes"`, `"1"`. |
| `rerank` | `str` | No | Enable cross-encoder reranking: `"true"`, `"yes"`, `"1"`. |
| `agent_mode` | `bool` | No | Enable agentic tool-call loop. Default: `false`. |
| `tools` | `list[str]` | No | Tool names available to this prompt (from `tools.yaml`). |
| `max_tool_rounds` | `int` | No | Maximum tool-call rounds. Default: from `config/main.yaml` (5). |

**Full example:**

```yaml
prompts:
  - sequence: 1
    prompt_name: "fetch"
    prompt: "Retrieve the data"
    history: []
    client: "fast"
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 2
    prompt_name: "summarize"
    prompt: "Summarize the data"
    history: ["fetch"]
    condition: '{{fetch.status}} == "success"'
    client: null
    references: ["spec"]
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null
```

---

### data.yaml — Batch Mode

Top-level key is `batches`. Each entry is a dict where any key becomes a `{{variable}}` in prompts.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Row identifier (conventional) |
| `batch_name` | `str` | Human-readable batch name |
| (any key) | `any` | Becomes `{{variable}}` in prompts |

```yaml
batches:
  - id: 1
    batch_name: "north_region"
    region: "north"
    product: "widget_a"
  - id: 2
    batch_name: "south_region"
    region: "south"
    product: "widget_b"
```

In prompts:
```yaml
prompt: "Analyze sales for {{region}} region, {{product}} product."
```

Each prompt runs once per batch row. 2 prompts × 2 batches = 4 executions.

> **Output note:** In the parquet results, the `prompt` column retains the original template (`{{region}}`, `{{product}}`), while the `resolved_prompt` column shows the substituted values (e.g., "Analyze sales for north region, widget_a product.").

---

### clients.yaml — Multi-Client Routing

Define named client configurations for per-prompt model routing.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Unique identifier. Referenced by `client` in prompts.yaml. |
| `client_type` | `str` | Yes | Client type from `config/clients.yaml` |
| `api_key_env` | `str` | No | Environment variable for API key |
| `model` | `str` | No | Model override |
| `temperature` | `float` | No | Temperature override |
| `max_tokens` | `int` | No | Max tokens override |
| `system_instructions` | `str` | No | System prompt override |
| `api_base` | `str` | No | API base URL override (LiteLLM only) |
| `api_version` | `str` | No | API version override (LiteLLM only) |
| `fallbacks` | `list` | No | Fallback model configurations (LiteLLM only) |

```yaml
clients:
  - name: "fast"
    client_type: "litellm-mistral-small"
    temperature: 0.3
    max_tokens: 100

  - name: "smart"
    client_type: "litellm-claude-3-5-sonnet"
    temperature: 0.7
    max_tokens: 4096

  - name: "azure-gpt"
    client_type: "litellm-azure"
    api_base: "https://my-instance.openai.azure.com"
    fallbacks: ["openai/gpt-4o"]
```

Reference in prompts:
```yaml
client: "fast"
```

---

### documents.yaml — Document References

Documents are parsed, cached, and injected into prompts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reference_name` | `str` | Yes | Unique identifier for prompt references |
| `common_name` | `str` | No | Human-readable name |
| `file_path` | `str` | Yes | Path to document (relative to manifest or absolute) |
| `tags` | `list[str]` | No | Tags for RAG metadata filtering |
| `notes` | `str` | No | Free-text description |
| `chunking_strategy` | `str` | Auto | Chunking strategy (auto-inferred from extension) |

**Chunking strategy auto-inference:**

| Extension | Strategy |
|-----------|----------|
| `.md` | `markdown` (header-aware) |
| `.py`, `.js`, `.ts`, etc. | `code` (function-aware) |
| Others | `recursive` (general-purpose) |

```yaml
documents:
  - reference_name: "spec"
    common_name: "Product Specification"
    file_path: "./library/product_spec.md"
    tags: ["product", "docs"]
    notes: "Main product documentation"

  - reference_name: "api_ref"
    common_name: "API Reference"
    file_path: "./library/api_reference.pdf"
    tags: ["api", "reference"]
```

### tools.yaml — Tool Definitions (Agent Mode)

Define tools available for agentic execution. Tools are registered by name and can be built-in or custom Python callables.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Unique tool identifier |
| `description` | `str` | Yes | Description sent to the LLM |
| `parameters` | `dict` | Yes | JSON Schema for tool parameters |
| `implementation` | `str` | Yes | `builtin:<name>` or `python:<module.func>` |
| `enabled` | `bool` | No | Whether tool is available (default: true) |

Built-in tools: `rag_search`, `read_document`, `list_documents`, `calculate`, `json_extract`, `http_get`.

```yaml
tools:
  - name: calculate
    description: "Evaluate a mathematical expression safely."
    parameters:
      type: object
      properties:
        expression:
          type: string
          description: "Math expression (e.g., '2 + 3 * 4')"
      required: ["expression"]
    implementation: "builtin:calculate"
    enabled: true

  - name: fetch_url
    description: "Fetch content from a URL."
    parameters:
      type: object
      properties:
        url:
          type: string
        max_length:
          type: integer
          default: 5000
      required: ["url"]
    implementation: "python:my_tools.fetch_url"
    enabled: true
```

---

## Conditional Execution

Skip or run prompts based on previous results using a secure expression language.

### Syntax

```
{{prompt_name.property}} == "value"
{{prompt_name.property}} != "value"
{{prompt_name.property}} contains "substring"
{{prompt_name.property}} not contains "substring"
{{prompt_name.property}} matches "regex"
len({{prompt_name.response}}) > 100
{{a.status}} == "success" and {{b.status}} == "success"
{{a.status}} == "success" or {{b.status}} == "success"
not {{prompt_name.has_response}}
```

### Available Properties

| Property | Type | Description |
|----------|------|-------------|
| `status` | `str` | `"success"`, `"failed"`, or `"skipped"` |
| `response` | `str` | The AI response text |
| `attempts` | `int` | Number of retry attempts |
| `error` | `str` | Error message if failed |
| `has_response` | `bool` | True if response exists and non-empty |

### Operators

- Comparison: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Membership: `in`, `not in`
- Boolean: `and`, `or`, `not`
- Regex: `%` (matches operator)

### Built-in Functions

**Type conversion:**
- `len(x)`, `int(x)`, `float(x)`, `str(x)`, `bool(x)`

**String functions:**
- `lower(s)`, `upper(s)`, `trim(s)`, `strip(s)`
- `split(s, sep)`, `replace(s, old, new)`
- `count(s, sub)`, `find(s, sub)`

**Math functions:**
- `abs(x)`, `min(x, y)`, `max(x, y)`, `round(x)`

**Type checking:**
- `is_null(x)`, `is_empty(x)`

**JSON functions:**
- `json_parse(s)` — Parse JSON string to object
- `json_get(s, path)` — Get value at path (e.g., `"data.items[0].name"`)
- `json_get_default(s, path, default)` — Get with fallback
- `json_has(s, path)` — Check if path exists
- `json_keys(s)` — Get list of keys
- `json_values(s)` — Get list of values
- `json_type(s, path)` — Get type name at path

### String Methods

```python
{{prompt_name.response}}.startswith("prefix")
{{prompt_name.response}}.endswith("suffix")
{{prompt_name.response}}.lower() == "value"
{{prompt_name.response}}.split(",")[0]
```

Allowed methods: `startswith`, `endswith`, `strip`, `lower`, `upper`, `title`, `capitalize`, `replace`, `count`, `find`, `split`, `isalpha`, `isdigit`, `isalnum`, etc.

### Examples

```yaml
prompts:
  - sequence: 1
    prompt_name: "fetch"
    prompt: "Retrieve the data"

  - sequence: 2
    prompt_name: "process"
    prompt: "Process the results"
    condition: '{{fetch.status}} == "success"'

  - sequence: 3
    prompt_name: "fallback"
    prompt: "Generate sample data"
    condition: '{{fetch.status}} == "failed"'

  - sequence: 4
    prompt_name: "report"
    prompt: "Write a summary"
    condition: '{{fetch.has_response}} and len({{fetch.response}}) > 100'

  - sequence: 5
    prompt_name: "json_check"
    prompt: "Extract JSON data"
    condition: 'json_has({{fetch.response}}, "data.items")'

  - sequence: 6
    prompt_name: "revise"
    prompt: "Revise based on score"
    condition: 'json_get({{evaluate.response}}, "overall_score") < 7.5'

  - sequence: 7
    prompt_name: "final"
    prompt: "Final version"
    condition: 'json_get({{evaluate.response}}, "ready") == True'
```

**Note:** When accessing JSON values from responses, always use `json_get()` or `json_has()` functions. You cannot use dot notation like `{{evaluate.overall_score}}` — use `json_get({{evaluate.response}}, "overall_score")` instead.

**Available JSON functions:**

| Function | Example | Description |
|----------|---------|-------------|
| `json_get(s, path)` | `json_get({{r.response}}, "score")` | Extract value at path |
| `json_get_default(s, path, default)` | `json_get_default({{r.response}}, "items", [])` | Get with fallback |
| `json_has(s, path)` | `json_has({{r.response}}, "data.items")` | Check if path exists |
| `json_type(s, path)` | `json_type({{r.response}}, "items")` | Get type name |

**Path syntax:** Use dot notation for nested keys: `"data.items[0].name"`

### Security

Conditions are parsed via Python's AST module with a strict whitelist — no `eval()`, no imports, no arbitrary code execution.

### Skipped Prompts and Variable References

When a prompt is skipped (its condition evaluated to false), downstream prompts that reference it via `{{prompt_name.response}}` in their text will have those patterns replaced with an empty string in their `resolved_prompt`. The original template with `{{}}` placeholders is preserved in the `prompt` column.

Example: if `force_ai_rewrite` is skipped, a prompt containing `{{force_ai_rewrite.response}}` will have that placeholder removed in `resolved_prompt` but kept in `prompt`.

---

## Declarative Context Assembly

Reference previous prompts by name. The orchestrator builds structured context automatically.

```yaml
prompts:
  - sequence: 1
    prompt_name: "context"
    prompt: "I run a coffee shop with 50 daily customers."

  - sequence: 2
    prompt_name: "problem"
    prompt: "My electricity bill is too high."
    history: ["context"]

  - sequence: 3
    prompt_name: "solution"
    prompt: "Suggest 3 ways to reduce costs."
    history: ["context", "problem"]
```

The orchestrator builds:
```xml
<conversation_history>
<interaction prompt_name='context'>
USER: I run a coffee shop with 50 daily customers.
SYSTEM: [response]
</interaction>
<interaction prompt_name='problem'>
USER: My electricity bill is too high.
SYSTEM: [response]
</interaction>
</conversation_history>
===
Based on the conversation history above, please answer: Suggest 3 ways to reduce costs.
```

> **`resolved_prompt` captures this full text.** The `resolved_prompt` column in the output parquet contains the entire assembled prompt sent to the AI — including the `<conversation_history>` block with all `{{prompt_name.response}}` references resolved, the separator, and the user's prompt text. The `prompt` column only contains the original `"Suggest 3 ways to reduce costs."` template.

---

## RAG Integration

### Full Document Injection

```yaml
# documents.yaml
documents:
  - reference_name: "spec"
    file_path: "./library/product_spec.md"

# prompts.yaml
prompts:
  - sequence: 1
    prompt_name: "answer"
    prompt: "Answer based on the documentation."
    references: ["spec"]
```

Documents are parsed, cached (with SHA256 checksum invalidation), and injected as structured XML.

### Semantic Search (RAG)

For large document collections, retrieve relevant chunks instead of full documents:

```yaml
prompts:
  - sequence: 1
    prompt_name: "search"
    prompt: "What are the authentication options?"
    semantic_query: "authentication security methods"
    rerank: "true"
```

**RAG features:**
- Hybrid search (BM25 + vector similarity with Reciprocal Rank Fusion)
- 5 chunking strategies (recursive, markdown, code, hierarchical, character)
- Cross-encoder reranking
- Query expansion
- Metadata filtering

### RAG with Metadata Filtering

```yaml
prompts:
  - sequence: 1
    prompt_name: "filtered_search"
    prompt: "Find API authentication methods."
    semantic_query: "authentication methods"
    semantic_filter: '{"reference_name": "api_ref"}'
```

---

## Available Client Types

### Via LiteLLM (Recommended)

| Client Type | Provider | Default Model |
|-------------|----------|---------------|
| `litellm-mistral-small` | Mistral | `mistral-small-latest` |
| `litellm-mistral-large` | Mistral | `mistral-large-latest` |
| `litellm-claude-3-5-sonnet` | Anthropic | `claude-3-5-sonnet-20241022` |
| `litellm-gpt-4o` | OpenAI | `gpt-4o` |
| `litellm-gpt-4o-mini` | OpenAI | `gpt-4o-mini` |
| `litellm-gemini-1.5-pro` | Google | `gemini-1.5-pro` |
| `litellm-perplexity-sonar-large` | Perplexity | `llama-3.1-sonar-large-128k-online` |
| `litellm-deepseek-chat` | DeepSeek | `deepseek-chat` |
| `litellm-groq-llama-70b` | Groq | `llama-3.3-70b-versatile` |
| `litellm-ollama` | Ollama | `llama3.1` |

### Native Clients

| Client Type | Provider | Default Model |
|-------------|----------|---------------|
| `mistral-small` | Mistral | `mistral-small-2503` |
| `anthropic` | Anthropic | `claude-3-5-sonnet-20241022` |
| `gemini` | Google | `gemini-1.5-pro` |
| `perplexity` | Perplexity | `llama-3.1-sonar-large-128k-online` |
| `azure-mistral-small` | Azure | `mistral-small` |
| `azure-phi` | Azure | `phi-4` |

**Note:** Check `config/clients.yaml.example` for the complete list of 50+ client types.

### Environment Variables

Set these in `.env`:

```bash
# At least one required
MISTRAL_API_KEY=your-key
MISTRALSMALL_KEY=your-key
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key
GEMINI_API_KEY=your-key
PERPLEXITY_API_KEY=your-key
DEEPSEEK_API_KEY=your-key
GROQ_API_KEY=your-key
```

---

## Complete Example Manifests

### Basic Workflow

**manifests/manifest_basic/manifest.yaml:**
```yaml
name: "basic_workflow"
description: "A simple three-prompt conversation"
version: "1.0"
source_workbook: ""
exported_at: "2025-01-15T10:00:00"
has_data: false
has_clients: false
has_documents: false
prompt_count: 3
```

**manifests/manifest_basic/config.yaml:**
```yaml
client_type: "litellm-mistral-small"
model: "mistral-small-latest"
temperature: 0.7
max_tokens: 4096
max_retries: 3
```

**manifests/manifest_basic/prompts.yaml:**
```yaml
prompts:
  - sequence: 1
    prompt_name: "intro"
    prompt: "Hello, I'm starting a new project."
    history: []
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 2
    prompt_name: "question"
    prompt: "What should I consider when planning?"
    history: ["intro"]
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 3
    prompt_name: "summary"
    prompt: "Summarize the key points in a bulleted list."
    history: ["intro", "question"]
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null
```

### Batch Workflow with Variables

**manifests/manifest_batch/manifest.yaml:**
```yaml
name: "batch_analysis"
description: "Analyze multiple regions"
version: "1.0"
source_workbook: ""
exported_at: "2025-01-15T10:00:00"
has_data: true
has_clients: false
has_documents: false
prompt_count: 2
```

**manifests/manifest_batch/data.yaml:**
```yaml
batches:
  - id: 1
    batch_name: "north_region"
    region: "North"
    target: 50000
  - id: 2
    batch_name: "south_region"
    region: "South"
    target: 75000
  - id: 3
    batch_name: "east_region"
    region: "East"
    target: 60000
```

**manifests/manifest_batch/prompts.yaml:**
```yaml
prompts:
  - sequence: 1
    prompt_name: "analyze"
    prompt: |
      Analyze sales performance for the {{region}} region.
      Our target is {{target}} units.
      Provide a brief assessment.
    history: []
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 2
    prompt_name: "recommend"
    prompt: |
      Based on the analysis for {{region}}, provide 3 specific recommendations
      to improve performance toward the {{target}} unit target.
    history: ["analyze"]
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null
```

### Multi-Client Workflow

**manifests/manifest_multiclient/manifest.yaml:**
```yaml
name: "multi_model_workflow"
description: "Use different models for different tasks"
version: "1.0"
source_workbook: ""
exported_at: "2025-01-15T10:00:00"
has_data: false
has_clients: true
has_documents: false
prompt_count: 3
```

**manifests/manifest_multiclient/clients.yaml:**
```yaml
clients:
  - name: "fast"
    client_type: "litellm-mistral-small"
    temperature: 0.3
    max_tokens: 200

  - name: "creative"
    client_type: "litellm-claude-3-5-sonnet"
    temperature: 0.9
    max_tokens: 4096
```

**manifests/manifest_multiclient/prompts.yaml:**
```yaml
prompts:
  - sequence: 1
    prompt_name: "classify"
    prompt: "Classify this topic in exactly one word: artificial intelligence"
    history: []
    client: "fast"
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 2
    prompt_name: "explain"
    prompt: "Explain why this classification makes sense."
    history: ["classify"]
    client: "creative"
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 3
    prompt_name: "summarize"
    prompt: "Write a one-sentence summary."
    history: ["classify", "explain"]
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null
```

### Conditional Workflow

**manifests/manifest_conditional/manifest.yaml:**
```yaml
name: "conditional_workflow"
description: "Branching based on previous results"
version: "1.0"
source_workbook: ""
exported_at: "2025-01-15T10:00:00"
has_data: false
has_clients: false
has_documents: false
prompt_count: 4
```

**manifests/manifest_conditional/prompts.yaml:**
```yaml
prompts:
  - sequence: 1
    prompt_name: "fetch"
    prompt: "Return a JSON object with a 'success' field set to true or false."
    history: []
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 2
    prompt_name: "process_success"
    prompt: "The fetch was successful. Process the data."
    history: ["fetch"]
    client: null
    condition: '{{fetch.status}} == "success"'
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 3
    prompt_name: "process_failure"
    prompt: "The fetch failed. Generate fallback data."
    history: []
    client: null
    condition: '{{fetch.status}} == "failed"'
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 4
    prompt_name: "report"
    prompt: "Summarize what happened."
    history: ["fetch"]
    client: null
    condition: '{{fetch.has_response}} and len({{fetch.response}}) > 10'
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null
```

### Document + RAG Workflow

**manifests/manifest_rag/manifest.yaml:**
```yaml
name: "rag_workflow"
description: "Use documents and semantic search"
version: "1.0"
source_workbook: ""
exported_at: "2025-01-15T10:00:00"
has_data: false
has_clients: false
has_documents: true
prompt_count: 3
```

**manifests/manifest_rag/documents.yaml:**
```yaml
documents:
  - reference_name: "product_spec"
    common_name: "Product Specification"
    file_path: "./library/product_spec.md"
    tags: ["product", "specification"]

  - reference_name: "api_docs"
    common_name: "API Documentation"
    file_path: "./library/api_docs.md"
    tags: ["api", "reference"]
```

**manifests/manifest_rag/prompts.yaml:**
```yaml
prompts:
  - sequence: 1
    prompt_name: "full_context"
    prompt: "Based on the product specification, summarize the key features."
    history: []
    client: null
    condition: null
    references: ["product_spec"]
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null

  - sequence: 2
    prompt_name: "semantic_search"
    prompt: "What authentication methods are available?"
    history: []
    client: null
    condition: null
    references: []
    semantic_query: "authentication security login methods"
    semantic_filter: '{"reference_name": "api_docs"}'
    query_expansion: "true"
    rerank: "true"

  - sequence: 3
    prompt_name: "synthesize"
    prompt: |
      Synthesize the product features and authentication options
      into a unified overview document.
    history: ["full_context", "semantic_search"]
    client: null
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null
```

---

## Parallel Execution

The orchestrator builds a dependency DAG and executes independent prompts concurrently.

```bash
python scripts/manifest_run.py ./manifests/manifest_my_workflow -c 4
```

**How it works:**
1. Dependency analysis builds a directed acyclic graph
2. Prompts at the same level have no dependencies on each other
3. Concurrent execution via ThreadPoolExecutor
4. Thread isolation — each execution gets a fresh client clone

---

## Exporting from Excel

If you have an Excel workbook, export it to manifest:

```bash
# Export to default manifest directory
python scripts/manifest_export.py ./workbooks/my_prompts.xlsx

# Export to custom directory
python scripts/manifest_export.py ./workbook.xlsx --output ./custom_manifest/
```

This creates a manifest folder from the Excel workbook's sheets:
- `config` sheet → `config.yaml`
- `prompts` sheet → `prompts.yaml`
- `data` sheet → `data.yaml` (if present)
- `clients` sheet → `clients.yaml` (if present)
- `documents` sheet → `documents.yaml` (if present)

---

## Troubleshooting

### Manifest not loading

Check that:
1. `manifest.yaml`, `config.yaml`, and `prompts.yaml` exist
2. `has_data`, `has_clients`, `has_documents` flags match actual files
3. YAML syntax is valid (no tabs, proper indentation)

### Conditions not working

1. Use `{{prompt_name.property}}` syntax (double braces)
2. Property must be one of: `status`, `response`, `attempts`, `error`, `has_response`
3. String comparisons require quotes: `'{{status}} == "success"'`
4. Check logs for syntax errors

### Batch variables not substituting

1. Ensure `has_data: true` in `manifest.yaml`
2. Ensure `data.yaml` exists with `batches:` top-level key
3. Use `{{variable}}` syntax in prompt text

### Rate limiting

1. Reduce concurrency: `-c 1`
2. Increase retries in `config/main.yaml`
3. Use LiteLLM clients (built-in retry)

---

## Quick Reference

### Minimal Manifest

```
manifest_minimal/
├── manifest.yaml   # name, version, has_data=false, has_clients=false, has_documents=false, prompt_count
├── config.yaml     # client_type
└── prompts.yaml    # prompts: [{sequence, prompt_name, prompt, history}]
```

### CLI Commands

```bash
# Export Excel to manifest
python scripts/manifest_export.py ./workbook.xlsx

# Run manifest (outputs to ./outputs/<manifest_name>/<timestamp>.parquet)
python scripts/manifest_run.py ./manifests/manifest_name/ -c 4

# Validate manifest (dry run)
python scripts/manifest_run.py ./manifests/manifest_name/ --dry-run

# Inspect parquet
python scripts/manifest_inspect.py ./outputs/linkedin_ai_post/20260324193142.parquet

# List all prompt names in parquet
python scripts/manifest_extract.py ./outputs/linkedin_ai_post/20260324193142.parquet --list

# Extract output prompts (auto-detect or from manifest output_prompts)
python scripts/manifest_extract.py ./outputs/linkedin_ai_post/20260324193142.parquet

# Extract specific prompts
python scripts/manifest_extract.py ./outputs/results.parquet --prompts final_post,hashtags

# Save extracted results to files (outputs to <parquet_dir>/<timestamp>/)
python scripts/manifest_extract.py ./outputs/results.parquet --save

# Export parquet to Excel (includes resolved_prompt column)
python scripts/parquet_to_excel.py ./outputs/results.parquet

# Export specific columns to Excel
python scripts/parquet_to_excel.py ./outputs/results.parquet --columns prompt_name,resolved_prompt,response

# Export with status filter
python scripts/parquet_to_excel.py ./outputs/results.parquet --status success
```

**Output structure:**
```
outputs/
├── linkedin_ai_post/
│   ├── 20260324193142.parquet
│   └── 20260324193142/
│       ├── final_post.md
│       ├── hashtags.json
│       ├── image_prompt.json
│       └── _summary.json
├── basic_workflow/
│   ├── 20260324120000.parquet
│   └── 20260324120000/
│       └── ...
```

### Python API

```python
from src.orchestrator import ManifestOrchestrator
from src.Clients import FFLiteLLMClient

client = FFLiteLLMClient(model_string="mistral/mistral-small-latest")
orchestrator = ManifestOrchestrator(
    manifest_dir="./manifests/manifest_name",
    client=client,
    concurrency=4
)
parquet_path = orchestrator.run()
```

---

## Sample Manifests

Sample manifests are available in `manifest_samples/`:

### linkedin_ai_post

**Purpose:** Research trending AI news, draft authentic posts with anti-cliché checks, and generate image prompts.

**Features demonstrated:**
- Topic validation gates (`validate_stories_ai_focus`, `validate_ai_topic`, `force_ai_rewrite`)
- Multi-draft creation (hook-first, story-first, contrarian)
- 3 revision cycles with conditional execution
- URL extraction from Perplexity research
- Multi-client routing (Perplexity, OpenAI, Mistral)
- 25 prompts across 11 phases

**Run:**
```bash
# Run the manifest
python scripts/manifest_run.py ./manifest_samples/linkedin_ai_post -c 2

# Extract results (auto-detects output prompts from manifest.yaml)
python scripts/manifest_extract.py ./outputs/linkedin_ai_post/<timestamp>.parquet --save
```

**Output:**
```
outputs/linkedin_ai_post/
├── 20260324193142.parquet
└── 20260324193142/
    ├── final_post.md
    ├── hashtags.json
    ├── image_prompt.json
    └── _summary.json
```

**See:** `manifest_samples/README.md` for full documentation.
