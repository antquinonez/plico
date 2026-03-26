# Plico

**Declarative AI orchestration. One manifest protocol. Three authoring paths: Excel, Python, or AI.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Core Idea

Plico is a declarative orchestration framework for AI workflows. At its center is a **YAML manifest** — a machine-readable, version-controllable specification that defines:

| What | How |
|------|-----|
| **What to ask** | Prompts with templating |
| **How prompts relate** | Dependencies, conditions, branching |
| **What data to use** | Batch variables, document references, RAG queries |
| **Which models to use** | Named client configurations per prompt |

**The manifest is the protocol.** How you create it is up to you:

| Author | Tool | Best For |
|--------|------|----------|
| **Human** | Excel | Non-developers, visual editing, ad-hoc analysis |
| **Program** | Python | Generated workflows, data-driven pipelines |
| **AI Agent** | YAML direct | Self-evolving workflows, autonomous orchestration |

Same manifest. Same execution engine. Same audit trail.

---

## Three Paths to a Manifest

```
+-------------------------------------------------------------------------------------------------+
|                                        AUTHORING SURFACES                                       |
|                                                                                                 |
|   +---------------------+          +---------------------+         +-------------------------+  |
|   |       Excel         |          |       Python        |         |        AI Agent         |  |
|   |      Workbook       |          |        Script       |         |     (writes YAML)       |  |
|   |                     |          |                     |         |                         |  |
|   |   Human-friendly    |          |   Programmatic      |         |   Autonomous            |  |
|   |   visual editor     |          |   generation        |         |   composition           |  |
|   +----------+----------+          +----------+----------+         +------------+------------+  |
|              |                                |                                  |              |
|              +--------------------------------+----------------------------------+              |
|                                               v                                                 |
|                             +-------------------------------------+                             |
|                             |          YAML MANIFEST              |                             |
|                             |                                     |                             |
|                             |  manifest.yaml   (metadata)         |                             |
|                             |  config.yaml     (settings)         |                             |
|                             |  prompts.yaml    (workflow)         |                             |
|                             |  data.yaml       (batches)          |                             |
|                             |  clients.yaml    (models)           |                             |
|                             |  documents.yaml  (resources)        |                             |
|                             |                                     |                             |
|                             |  <-- Git versioned -->              |                             |
|                             |  <-- AI readable -->                |                             |
|                             |  <-- AI writable -->                |                             |
|                             +------------------+------------------+                             |
|                                                |                                                |
+------------------------------------------------+------------------------------------------------+
                                                 v
+-------------------------------------------------------------------------------------------------+
|                                        EXECUTION LAYER                                          |
|                                                                                                 |
|                                        ManifestOrchestrator                                     |
|                                               |                                                 |
|                                               v                                                 |
|                           +-------------------------------------+                               |
|                           |      Timestamped Parquet            |                               |
|                           |      (analytics-ready)              |                               |
|                           |                                     |                               |
|                           |  <-- AI can analyze -->             |                               |
|                           |  <-- AI can iterate -->             |                               |
|                           +-------------------------------------+                               |
|                                                                                                 |
+-------------------------------------------------------------------------------------------------+
```

### Path 1: Excel (Human Authoring)

Excel is Plico's human-friendly authoring surface. Define prompts as rows, dependencies as cell references, and conditions as expressions. Export to manifest when ready.

**Sample prompts worksheet:**

| sequence | prompt_name | prompt | history | client | condition | references | semantic_query |
|----------|-------------|--------|---------|--------|-----------|------------|----------------|
| 1 | intro | What is your name? | | | | | |
| 2 | question | What is interesting about AI? | `["intro"]` | | | | |
| 3 | summarize | Summarize our conversation in one sentence. | `["intro", "question"]` | | | | |

```bash
# Create workbook template (exits after creating if file doesn't exist)
python scripts/run_orchestrator.py my_analysis.xlsx
# ... edit prompts sheet in Excel ...

# Option A: Run directly (results written to timestamped sheet)
python scripts/run_orchestrator.py my_analysis.xlsx -c 4

# Option B: Export to manifest for execution
python scripts/export_manifest.py my_analysis.xlsx
# Creates: ./manifests/manifest_my_analysis/
python scripts/run_manifest.py ./manifests/manifest_my_analysis/
```

**When to use:** Non-developers, ad-hoc analysis, visual workflow design, stakeholders who live in spreadsheets.

### Path 2: Python (Programmatic Generation)

Generate manifests programmatically from data, databases, or other systems.

```python
import yaml
from pathlib import Path

manifest_dir = Path("manifests/manifest_generated")
manifest_dir.mkdir(parents=True, exist_ok=True)

# Generate prompts from data
prompts = []
for i, topic in enumerate(["sales", "marketing", "engineering"]):
    prompts.append({
        "sequence": i + 1,
        "prompt_name": f"analyze_{topic}",
        "prompt": f"Analyze {topic} performance and suggest improvements.",
        "client": "analytical"
    })

# Write prompts.yaml
with open(manifest_dir / "prompts.yaml", "w") as f:
    yaml.dump({"prompts": prompts}, f)

# Write minimal config.yaml
with open(manifest_dir / "config.yaml", "w") as f:
    yaml.dump({"model": "mistral-small-2503", "temperature": 0.7}, f)

# Write manifest.yaml
with open(manifest_dir / "manifest.yaml", "w") as f:
    yaml.dump({"name": "generated_analysis", "version": "1.0"}, f)
```

**When to use:** Data-driven workflows, CI/CD pipelines, dynamic prompt generation, integration with existing systems.

### Path 3: AI (Direct YAML Authoring)

AI agents can read, write, and modify manifests directly — no Excel, no Python intermediary.

```yaml
# AI writes this directly based on user request
# manifests/manifest_ai_generated/prompts.yaml

prompts:
  - sequence: 1
    prompt_name: understand
    prompt: |
      Analyze the user's request and identify the core problem.
      Request: {{user_request}}
    client: analytical

  - sequence: 2
    prompt_name: research
    prompt: |
      Based on the problem analysis, identify what information is needed.
      Previous analysis: {{understand.response}}
    history: ["understand"]
    semantic_query: "problem solving methodologies"

  - sequence: 3
    prompt_name: synthesize
    prompt: |
      Synthesize a solution based on the problem analysis and research.
      Provide actionable recommendations.
    history: ["understand", "research"]
    condition: '{{understand.status}} == "success"'
    client: creative
```

**When to use:** Self-improving workflows, autonomous agents, AI-assisted prompt engineering, iterative refinement loops.

---

## Quick Start

Install, configure, and run your first workflow in under 5 minutes. See [QUICKSTART.md](QUICKSTART.md) for the full guide.

```bash
git clone https://github.com/antquinonez/plico.git
cd plico
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Set your API key in .env:
echo 'OPENAI_API_KEY="your-key"' > .env

# Run a sample workbook to verify everything works:
inv wb.basic --client litellm-openai
```

For provider options, Excel/manifest/Python workflows, troubleshooting, and more, see the **[Quick Start Guide](QUICKSTART.md)**.

---

## The Manifest Protocol

The manifest directory is the canonical, version-controllable representation of a workflow. A manifest is a folder of YAML files — six total, though only three are required.

### Folder Structure

```
manifest_my_workflow/
├── manifest.yaml      # Required — metadata
├── config.yaml        # Required — runtime settings
├── prompts.yaml       # Required — prompt graph
├── data.yaml          # Optional — batch rows
├── clients.yaml       # Optional — named client configs
└── documents.yaml     # Optional — document references for injection/RAG
```

The optional files are only created when the source workbook contains the corresponding sheet with data rows. The `manifest.yaml` flags (`has_data`, `has_clients`, `has_documents`) control which optional files are loaded at runtime.

### manifest.yaml — Metadata

| Field | Type | Description |
|-------|------|-------------|
| `version` | `str` | Manifest format version (currently `"1.0"`) |
| `source_workbook` | `str` | Absolute path to the original Excel workbook |
| `exported_at` | `str` | ISO 8601 timestamp of export |
| `has_data` | `bool` | Whether `data.yaml` exists (batch mode enabled) |
| `has_clients` | `bool` | Whether `clients.yaml` exists (multi-client mode) |
| `has_documents` | `bool` | Whether `documents.yaml` exists (document injection/RAG) |
| `prompt_count` | `int` | Total number of prompts |

### config.yaml — Runtime Settings

Flat key-value dictionary. Keys come from the workbook's config sheet; only non-empty values are written.

| Field | Type | Description |
|-------|------|-------------|
| `client_type` | `str` | Client type to use (overrides CLI `--client`) |
| `model` | `str` | Model name (falls back to client-type default) |
| `api_key_env` | `str` | Environment variable for the API key |
| `max_retries` | `int` | Retry attempts per prompt (default: 3) |
| `temperature` | `float` | Sampling temperature (0–2) |
| `max_tokens` | `int` | Maximum response tokens |
| `system_instructions` | `str` | System prompt |
| `on_batch_error` | `str` | Batch error handling: `"continue"` or `"stop"` (default: `"continue"`) |
| `document_cache_dir` | `str` | Override path for document cache |
| `created_at` | `str` | Timestamp (informational only) |
| `batch_mode` | `str` | Batch mode setting (informational; actual batch mode is determined by presence of `data.yaml`) |
| `batch_output` | `str` | Batch output format (informational) |

The orchestrator retries failed prompts up to `max_retries` times (default: 3).

### prompts.yaml — Prompt Graph

Each prompt entry defines a node in the execution DAG. Dependencies are declared via `history` references to `prompt_name` values.

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | `int` | Execution order (1-based). Prompts at the same level with no dependencies run in parallel. |
| `prompt_name` | `str` | Unique identifier. Referenced by `history`, `condition` expressions, and `client` routing. |
| `prompt` | `str` | The prompt text. Supports `{{variable}}` templating in batch mode and `{{prompt_name.response}}` for referencing previous results. In output, `prompt` retains the original template while `resolved_prompt` contains the fully-resolved text. |
| `history` | `list[str]` | `prompt_name` values whose responses are injected as conversation context. |
| `client` | `str` | Name from `clients.yaml` to route this prompt to a specific client. `null` = default. |
| `condition` | `str` | Expression evaluated at runtime. If falsy, the prompt is skipped (status: `"skipped"`). |
| `references` | `list[str]` | `reference_name` values from `documents.yaml` for full document injection. |
| `semantic_query` | `str` | Natural language query for RAG semantic search (retrieves relevant chunks). |
| `semantic_filter` | `str` | JSON string for filtering RAG results (e.g., `'{"reference_name": "api_ref"}'`). |
| `query_expansion` | `str` | Enable multi-query retrieval: `"true"`, `"yes"`, `"1"` = enabled. |
| `rerank` | `str` | Enable cross-encoder reranking: `"true"`, `"yes"`, `"1"` = enabled. |

```yaml
prompts:
  - sequence: 1
    prompt_name: fetch
    prompt: "Retrieve the data"
    history: []
    client: fast
    condition: null
    references: []
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null
  - sequence: 2
    prompt_name: summarize
    prompt: "Summarize the data"
    history: ["fetch"]
    condition: "{{fetch.response.contains.error}} == false"
    client: null
    references: ["spec"]
    semantic_query: null
    semantic_filter: null
    query_expansion: null
    rerank: null
```

### data.yaml — Batch Mode (Optional)

Top-level key is `batches`. Entries are open-schema dicts — any column becomes a `{{variable}}` available in prompt text and `prompt_name`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Row identifier (conventional, not consumed by orchestrator) |
| `batch_name` | `str` | Human-readable batch name. Falls back to `batch_<id>` if absent. |
| (any key) | `any` | Arbitrary columns become `{{variable}}` placeholders in prompts. |

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

Use `{{region}}` and `{{product}}` in prompts for variable substitution. Each prompt runs once per batch row.

### clients.yaml — Multi-Client Routing (Optional)

Define named client configurations that prompts can reference via the `client` field.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique identifier. Referenced by `client` in prompts.yaml. |
| `client_type` | `str` | Client type from `config/clients.yaml` (e.g., `"litellm-openai"`, `"anthropic"`) |
| `api_key_env` | `str` | Environment variable for API key (falls back to client-type default) |
| `model` | `str` | Model override (falls back to client-type default) |
| `temperature` | `float` | Temperature override |
| `max_tokens` | `int` | Max tokens override |
| `system_instructions` | `str` | System prompt override |
| `api_base` | `str` | API base URL override (LiteLLM clients only) |
| `api_version` | `str` | API version override (LiteLLM clients only) |
| `fallbacks` | `list` | Fallback model configurations (LiteLLM clients only) |

```yaml
clients:
  - name: fast
    client_type: litellm-openai
    temperature: 0.3
    max_tokens: 100

  - name: creative
    client_type: litellm-anthropic
    temperature: 0.9
    max_tokens: 2000

  - name: azure-gpt
    client_type: litellm-azure
    api_base: "https://my-instance.openai.azure.com"
    fallbacks: ["openai/gpt-4o"]
```

Reference by name in prompts: `client: fast`

**Client Type Configuration** (`config/clients.yaml`):

The full configuration supports 50+ client types across providers:

```yaml
default_client: "litellm-openai"

client_types:
  # Native clients (direct API)
  mistral-small:
    client_class: "FFMistralSmall"
    type: "native"
    api_key_env: "MISTRALSMALL_KEY"
    default_model: "mistral-small-2503"

  anthropic:
    client_class: "FFAnthropic"
    type: "native"
    api_key_env: "ANTHROPIC_API_KEY"
    default_model: "claude-3-5-sonnet-20241022"

  gemini:
    client_class: "FFGemini"
    type: "native"
    api_key_env: "GEMINI_API_KEY"
    default_model: "gemini-1.5-pro"

  # LiteLLM clients (100+ providers)
  litellm-openai:
    client_class: "FFLiteLLMClient"
    type: "litellm"
    provider_prefix: "openai/"
    api_key_env: "OPENAI_API_KEY"
    default_model: "gpt-4o-mini"

  litellm-claude-3-5-sonnet:
    client_class: "FFLiteLLMClient"
    type: "litellm"
    provider_prefix: "anthropic/"
    api_key_env: "ANTHROPIC_API_KEY"
    default_model: "claude-3-5-sonnet-20241022"

  # ... 50+ more client types (see config/clients.yaml.example)
```

Each client type has:
- `client_class`: Python class name (e.g., `FFMistralSmall`, `FFLiteLLMClient`)
- `type`: Either `native` (direct API) or `litellm` (via LiteLLM routing)
- `api_key_env`: Environment variable name for API key
- `provider_prefix`: LiteLLM provider prefix (for `litellm` type only)
- `default_model`: Default model identifier

**Note:** Check `config/clients.yaml.example` for the exact environment variable name for each client type.

### documents.yaml — Document References (Optional)

Documents are parsed, cached, and injected into prompts at runtime. Full documents are injected via `references`; relevant chunks are retrieved via RAG `semantic_query`.

| Field | Type | Description |
|-------|------|-------------|
| `reference_name` | `str` | Unique identifier for prompt references |
| `common_name` | `str` | Human-readable name |
| `file_path` | `str` | Path to document (resolved relative to source workbook) |
| `tags` | `list[str]` | Tags for RAG metadata filtering (optional) |
| `notes` | `str` | Free-text description (informational) |
| `chunking_strategy` | `str` | Auto-inferred from file extension (see below) |

**Chunking strategy is auto-inferred from file extension:**

| Extension | Strategy | Description |
|-----------|----------|-------------|
| `.md` | `markdown` | Header-aware chunking |
| `.py`, `.js`, `.ts`, etc. | `code` | Function-aware chunking |
| Others | `recursive` | General-purpose chunking |

---

## Why Manifests?

| Benefit | Description |
|---------|-------------|
| **Git-friendly** | YAML diffs are readable and mergeable. Track prompt evolution. |
| **AI-composable** | Machines can read, write, and modify directly. |
| **Version-controllable** | Pin exact configurations for reproducibility. |
| **Separation of concerns** | Author in any tool, execute consistently. |
| **Analytics-ready** | Output to Parquet for analysis and iteration. |

---

## Declarative Features

Plico is declarative across multiple dimensions:

| Dimension | Declaration | Effect |
|-----------|-------------|--------|
| **Prompts** | Define what to ask, not how to chain | Automatic dependency resolution |
| **Dependencies** | `history: ["context", "problem"]` | Context assembled automatically |
| **Conditions** | `{{fetch.status}} == "success"` | Branching without imperative logic |
| **Batches** | Data rows with `{{variables}}` | Parallel batch execution |
| **Clients** | Named configurations per prompt | Multi-model orchestration |
| **Documents** | Reference names in prompts | Automatic injection/indexing |
| **RAG** | Semantic queries per prompt | Relevant chunk retrieval |

**Result:** You describe *what* you want; Plico figures out *how* to execute it.

---

## Declarative Context Assembly

Reference previous prompts by name. Plico assembles the context automatically.

```yaml
prompts:
  - sequence: 1
    prompt_name: context
    prompt: "I run a coffee shop with 50 daily customers."

  - sequence: 2
    prompt_name: problem
    prompt: "My electricity bill is too high."
    history: ["context"]

  - sequence: 3
    prompt_name: solution
    prompt: "Suggest 3 ways to reduce costs."
    history: ["context", "problem"]
```

The orchestrator builds structured context:

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

---

## Conditional Execution

Skip or run prompts based on previous results using a secure expression language:

```yaml
prompts:
  - sequence: 1
    prompt_name: fetch
    prompt: "Retrieve the data"

  - sequence: 2
    prompt_name: process
    prompt: "Process the results"
    condition: '{{fetch.status}} == "success"'

  - sequence: 3
    prompt_name: fallback
    prompt: "Generate sample data"
    condition: '{{fetch.status}} == "failed"'

  - sequence: 4
    prompt_name: report
    prompt: "Write a summary"
    condition: '{{fetch.has_response}} and len({{fetch.response}}) > 100'
```

**Available properties:** `status`, `response`, `attempts`, `error`, `has_response`

**Operators:** `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not in`, `and`, `or`, `not`, `%` (regex)

**35+ functions:** `len()`, `lower()`, `upper()`, `json_get()`, `json_has()`, `contains()`, `starts_with()`, `int()`, `float()`, and more.

**Security:** Expressions are parsed via Python's AST module with a strict whitelist — no `eval()`, no imports, no arbitrary code execution.

---

## Batch Execution

Run the same workflow across multiple data rows:

```yaml
# data.yaml
batches:
  - id: 1
    region: "north"
    product: "widget_a"
  - id: 2
    region: "south"
    product: "widget_b"

# prompts.yaml
prompts:
  - sequence: 1
    prompt_name: analyze
    prompt: "Analyze sales for {{region}} region, {{product}} product."
```

Result: Each prompt runs once per data row. 2 prompts × 2 rows = 4 executions.

---

## Per-Prompt Client Routing

Route different prompts to different models:

```yaml
# clients.yaml
clients:
  - name: fast
    client_type: litellm-mistral
    temperature: 0.3
    max_tokens: 100

  - name: smart
    client_type: litellm-anthropic
    temperature: 0.7
    max_tokens: 4096

# prompts.yaml
prompts:
  - sequence: 1
    prompt_name: classify
    prompt: "Classify the sentiment"
    client: fast

  - sequence: 2
    prompt_name: explain
    prompt: "Explain the reasoning"
    client: smart

  - sequence: 3
    prompt_name: summarize
    prompt: "Write a summary"
    # No client = uses default from config.yaml
```

---

## Document References & RAG

### Full Document Injection

```yaml
# documents.yaml
documents:
  - reference_name: spec
    file_path: "library/product_spec.md"
  - reference_name: api
    file_path: "library/api_reference.pdf"

# prompts.yaml
prompts:
  - sequence: 1
    prompt_name: answer
    prompt: "Answer based on the documentation."
    references: ["spec", "api"]
```

Documents are parsed, cached (with SHA256 checksum invalidation), and injected as structured XML.

### Semantic Search (RAG)

For large document collections, retrieve relevant chunks instead:

```yaml
prompts:
  - sequence: 1
    prompt_name: search
    prompt: "What are the authentication options?"
    semantic_query: "authentication security methods"
    rerank: true
```

**RAG features:**
- Hybrid search (BM25 + vector similarity with Reciprocal Rank Fusion)
- 5 chunking strategies (recursive, markdown, code, hierarchical, character)
- Cross-encoder reranking
- Query expansion
- Metadata filtering

---

## Parallel Execution

The orchestrator builds a dependency DAG and executes independent prompts concurrently:

```bash
python scripts/run_manifest.py ./manifests/my_workflow/ -c 4
```

```
[████████████░░░░░░░░] 18/30 (60%) | ✓17 ✗0 | →analyze_5 | ⏳3 | ETA: 4s
```

**How it works:**
1. Dependency analysis builds a directed acyclic graph
2. Prompts at the same level have no dependencies on each other
3. Concurrent execution via ThreadPoolExecutor
4. Thread isolation — each execution gets a fresh client clone

---

## Excel: A Human-Friendly Authoring Surface

While manifests are the protocol, Excel is the visual authoring layer. The sheets map directly
to the manifest files you export.

### Workbook Structure

| Sheet | Purpose |
|-------|---------|
| `config` | Model, temperature, retries, system instructions |
| `prompts` | Prompt definitions with dependencies, conditions, references |
| `data` | Batch variables for templated execution |
| `clients` | Named client configurations |
| `documents` | Document references for injection and RAG |

### prompts Sheet Columns

These columns map to `prompts.yaml` fields.

| Column | Description |
|--------|-------------|
| `sequence` | Execution order |
| `prompt_name` | Unique identifier for references |
| `prompt` | Prompt text; supports `{{variable}}` templating |
| `history` | JSON array of prompt_names to include as context |
| `client` | Named client from clients sheet |
| `condition` | Expression for conditional execution |
| `references` | JSON array of document reference_names |
| `semantic_query` | RAG search query |
| `semantic_filter` | Metadata filter for RAG search |
| `query_expansion` | Override query expansion (`true`/`false`) |
| `rerank` | Override reranking (`true`/`false`) |

**Output columns** (written to results sheet in Excel, or as parquet columns via manifest):

| Column | Description |
|--------|-------------|
| `prompt` | Original prompt template (with `{{}}` placeholders intact) |
| `resolved_prompt` | Fully-resolved prompt sent to the AI (variables substituted, conversation history assembled) |
| `response` | AI response text |
| `status` | `success`, `failed`, or `skipped` |
| `error` / `attempts` / `condition` / `condition_result` | Execution details |

### Workflow

1. **Create template:** `python scripts/run_orchestrator.py analysis.xlsx`
   - Creates template workbook if file doesn't exist, then exits
2. **Edit in Excel:** Define prompts, dependencies, conditions, and optional RAG/client fields
3. **Run directly:** `python scripts/run_orchestrator.py analysis.xlsx -c 4`
   - Writes results to a timestamped workbook sheet
4. **Or export + run manifest:**
   - `python scripts/export_manifest.py analysis.xlsx`
   - `python scripts/run_manifest.py ./manifests/manifest_analysis/`

**Recommendation:** Use the manifest workflow for version control, code review, and repeatable runs.

---

## Supported Providers

### Via LiteLLM (Recommended)

`FFLiteLLMClient` gives you one interface for 100+ providers.

```python
FFLiteLLMClient(model_string='openai/gpt-4o-mini')
FFLiteLLMClient(model_string='mistral/mistral-small-latest')
FFLiteLLMClient(model_string='anthropic/claude-3-5-sonnet-20241022')
FFLiteLLMClient(model_string='gemini/gemini-1.5-pro')
FFLiteLLMClient(model_string='azure/gpt-4o')
```

Common provider families include Mistral, Anthropic, OpenAI, Gemini, Azure, Perplexity,
DeepSeek, Groq, Cohere, Together AI, OpenRouter, Ollama, and others.

For the full list of configured client types, see `config/clients.yaml.example`.

**Retry behavior:** native and LiteLLM clients both support automatic retries with exponential backoff.

### Native Direct-API Clients

| Client | Provider | SDK / Interface |
|--------|----------|-----------------|
| `FFMistral` / `FFMistralSmall` | Mistral AI | Mistral SDK (`mistralai`) |
| `FFAnthropic` / `FFAnthropicCached` | Anthropic | Anthropic SDK with optional prompt caching |
| `FFGemini` | Google Gemini | OpenAI-compatible via Vertex AI (`openai` + `google.auth`) |
| `FFPerplexity` | Perplexity AI | OpenAI-compatible (`openai` pointed at `api.perplexity.ai`) |
| `FFNvidiaDeepSeek` | DeepSeek via NVIDIA NIM | OpenAI-compatible (`openai` pointed at NVIDIA NIM) |
| `FFOpenAIAssistant` | OpenAI | OpenAI Assistants API (`openai` beta) |
| `FFAzureMistral` / `FFAzureCodestral` / `FFAzurePhi` | Azure | Azure AI Inference SDK (`azure-ai-inference`) |

### Azure via LiteLLM

`create_azure_client()` (from `FFAzureLiteLLM`) is a factory that returns a pre-configured `FFLiteLLMClient` for Azure deployments. It resolves API key, endpoint, and API version from environment variables using a configurable prefix.

```python
from src.Clients import create_azure_client

client = create_azure_client(
    deployment_name="mistral-small-2503",
    env_prefix="AZURE_MISTRALSMALL",  # reads AZURE_MISTRALSMALL_KEY, _ENDPOINT, _API_VERSION
)
```

### Automatic Fallbacks (LiteLLM only)

```python
client = FFLiteLLMClient(
    model_string="anthropic/claude-3-opus-20240229",
    fallbacks=["openai/gpt-4", "azure/gpt-4"],
)
```

---

## How Plico Compares

| Capability | Plico | LangGraph | DSPy | LlamaIndex | Flowise | CrewAI |
|------------|:---------:|:---------:|:----:|:----------:|:-------:|:------:|
| **Non-dev accessible** | ★★★★★ | ★★ | ★½ | ★★ | ★★★★ | ★★½ |
| **AI-composable** | ★★★★★ | ⚠️ Code gen | ★★★★ | ⚠️ Code gen | ★ | ⚠️ Code gen |
| **Audit trail** | ★★★★★ | ★★★ | ★★½ | ★★½ | ★★ | ★★ |
| **Batch processing** | ★★★★★ | ★½ | ★ | ★ | ★★ | ★ |
| **Declarative design** | ★★★★★ | ★★½ | ★★★½ | ★★ | ★★★ | ★★ |
| **Provider coverage** | ★★★★½ | ★★★★½ | ★★½ | ★★★½ | ★★★★ | ★★★½ |
| **RAG depth** | ★★★½ | ★★★★ | ★★ | ★★★★★ | ★★★ | ★★½ |

### Where Plico Wins

**Multiple authoring paths.** The only framework where humans use Excel, programs use Python, and AI writes YAML — all producing the same manifest protocol.

**AI-composability.** YAML manifests are machine-writable. AI systems can author, modify, and evolve workflows without code generation.

**Auditability.** Every execution recorded: prompt, resolved_prompt, response, model, condition, error, retry. Manifest + Parquet = complete provenance.

**Batch processing.** Purpose-built for running workflows across multiple data inputs at the workflow definition level.

### Where Others Win

**Agent capabilities.** LangChain, AutoGen, CrewAI excel at dynamic agent systems with tool use and autonomous reasoning. Plico is for structured workflows.

**RAG depth.** LlamaIndex offers more index types and agentic retrieval.

**Prompt optimization.** DSPy can automatically improve prompts through compilation.

---

## Architecture

```
+--------------------------------------------------------------------------------------------------+
|                                        AUTHORING LAYER                                           |
|                                                                                                  |
|   Excel Workbook              Python Script              AI Agent                                |
|   (human visual)              (programmatic)             (autonomous)                            |
|                                                                                                  |
+------------------------------------------------+-------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                        MANIFEST LAYER                                            |
|                                                                                                  |
|   YAML Manifest (manifest.yaml, config.yaml, prompts.yaml, ...)                                  |
|                                                                                                  |
|   <-- Git versioned -->    <-- AI readable -->    <-- AI writable -->                            |
|                                                                                                  |
+------------------------------------------------+-------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                        EXECUTION LAYER                                           |
|                                                                                                  |
|   ManifestOrchestrator                                                                           |
|   +-- Dependency DAG construction                                                                |
|   +-- Parallel scheduling (ThreadPoolExecutor)                                                   |
|   +-- Condition evaluation (AST-sandboxed)                                                       |
|   +-- Context assembly (declarative history)                                                     |
|   +-- Client isolation (clone pattern)                                                           |
|                                                                                                  |
+------------------------------------------------+-------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                        CLIENT LAYER                                              |
|                                                                                                  |
|   FFAIClientBase (ABC)                                                                           |
|   +-- FFLiteLLMClient (100+ providers via LiteLLM)                                               |
|   +-- FFMistral, FFAnthropic, FFGemini, FFPerplexity                                             |
|   +-- FFAzureClientBase --> FFAzureMistral, FFAzurePhi, ...                                      |
|                                                                                                  |
+------------------------------------------------+-------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                        OUTPUT LAYER                                              |
|                                                                                                  |
|   Timestamped Parquet (analytics-ready)                                                          |
|   <-- AI can analyze -->    <-- AI can iterate -->                                               |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

**Execution pipeline:**
- Parse workbook or manifest into prompt graph + runtime config
- Build dependency DAG and evaluate conditions safely (AST sandbox)
- Schedule prompts sequentially or in parallel with isolated client clones
- Assemble declarative context from `history` references
- Persist run results for analysis and iteration

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Manifest as protocol** | YAML is the canonical spec; Excel is one authoring surface |
| **Clone-based concurrency** | Each parallel execution gets a fresh client clone; no shared mutable state |
| **AST-sandboxed conditions** | No `eval()`, no imports, no arbitrary code execution |
| **Parquet output** | Analytics-ready format for downstream analysis and AI iteration |

---

## When to Use Plico

### Use Plico if you:

- Want workflows that humans AND AI can author
- Need full audit trails for compliance or reproducibility
- Batch process data through AI pipelines
- Work with teams that include non-developers
- Prefer declarative configuration over imperative code
- Need version-controllable prompt configurations
- Want document Q&A with semantic search

### Consider alternatives if you need:

- Multi-agent collaboration (CrewAI, AutoGen)
- Real-time streaming chat (LangChain)
- Tool/function calling at runtime (LangChain, LlamaIndex)
- Production API services (LangServe)

---

## Python API

```python
from src.FFAI import FFAI
from src.Clients.FFLiteLLMClient import FFLiteLLMClient

# Initialize
client = FFLiteLLMClient(model_string="openai/gpt-4o-mini")
ffai = FFAI(client)

# Named prompts with declarative context
ffai.generate_response("My name is Alice.", prompt_name="intro")
ffai.generate_response("I like data science.", prompt_name="interest")

ffai.generate_response(
    "What do you know about me?",
    prompt_name="recall",
    history=["intro", "interest"]  # Automatically assembles context
)
```

### Manifest Orchestration

```python
from src.orchestrator import ManifestOrchestrator
from src.Clients.FFMistralSmall import FFMistralSmall

client = FFMistralSmall(api_key="your-key")
orchestrator = ManifestOrchestrator(
    manifest_dir="./manifests/my_workflow/",
    client=client,
    concurrency=4
)
parquet_path = orchestrator.run()

summary = orchestrator.get_summary()
print(f"Success: {summary['successful']}, Failed: {summary['failed']}")
```

---

## Project Structure

```
Plico/
├── src/
│   ├── FFAI.py                        # Core wrapper — context assembly, history
│   ├── FFAIClientBase.py              # Client abstract base class
│   ├── config.py                      # Pydantic-settings configuration
│   ├── retry_utils.py                 # Retry decorators and rate-limit handling
│   ├── Clients/                       # Provider implementations
│   │   ├── FFLiteLLMClient.py         # Universal client (recommended)
│   │   ├── FFMistral.py...
│   │   └── FFAzureClientBase.py       # Azure-specific ABC
│   ├── orchestrator/                  # Orchestration engine
│   │   ├── workbook_parser.py         # Excel/workbook parsing and validation
│   │   ├── excel_orchestrator.py      # Excel execution
│   │   ├── manifest.py                # Manifest export/execution
│   │   ├── executor.py                # Shared execution engine
│   │   ├── state/                     # Execution state and dependency nodes
│   │   ├── results/                   # Result builders and DTOs
│   │   ├── condition_evaluator.py     # AST-based expression evaluator
│   │   ├── client_registry.py         # Client factory and routing
│   │   ├── document_processor.py      # Document parsing and caching
│   │   └── document_registry.py       # Document lookup and injection
│   └── RAG/                           # Retrieval-augmented generation
│       ├── FFRAGClient.py             # High-level RAG interface
│       ├── FFVectorStore.py           # ChromaDB operations
│       ├── text_splitters/            # Chunking strategies
│       ├── indexing/                  # BM25, hierarchical indexing
│       └── search/                    # Hybrid search, re-ranking
├── config/                            # YAML configuration files
│   ├── main.yaml                      # Workbook, orchestrator, retry, RAG settings
│   ├── paths.yaml                     # File system paths (outputs, manifests, etc.)
│   ├── clients.yaml                   # Client type registry (copy from .example)
│   ├── model_defaults.yaml            # Per-model temperature, max_tokens defaults
│   ├── logging.yaml                   # Log directory, rotation, format
│   └── sample_workbook.yaml           # Sample workbook creation defaults
├── scripts/                           # CLI tools and workbook utilities
│   ├── run_orchestrator.py            # Execute workbook directly
│   ├── export_manifest.py             # Convert workbook to manifest folder
│   ├── run_manifest.py                # Execute manifest and write parquet
│   ├── inspect_parquet.py             # Inspect/export parquet results
│   ├── parquet_to_excel.py            # Export parquet results to Excel workbook
│   └── sample_workbooks/              # Shared builders and validators
├── tests/                             # Unit and integration tests
├── manifests/                         # Exported YAML manifests
├── outputs/                           # Parquet results
└── docs/                              # Architecture and user guides
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART](QUICKSTART.md) | Installation, configuration, and first run |
| [ORCHESTRATOR README](https://github.com/antquinonez/plico/blob/main/docs/ORCHESTRATOR%20README.md) | Excel and manifest execution guide |
| [CLIENT API USER GUIDE](https://github.com/antquinonez/plico/blob/main/docs/CLIENT%20API%20USER%20GUIDE.md) | Python API reference |
| [CONDITIONAL EXPRESSIONS](https://github.com/antquinonez/plico/blob/main/docs/CONDITIONAL%20EXPRESSIONS%20USER%20GUIDE.md) | Condition syntax and security |
| [CONFIGURATION](https://github.com/antquinonez/plico/blob/main/docs/CONFIGURATION.md) | Configuration system reference |
| [ARCHITECTURE](https://github.com/antquinonez/plico/blob/main/docs/architecture/ARCHITECTURE.md) | System design and data flows |
| [RAG ARCHITECTURE](https://github.com/antquinonez/plico/blob/main/docs/architecture/RAG_ARCHITECTURE.md) | Semantic search subsystem |
| [CLIENTS ARCHITECTURE](https://github.com/antquinonez/plico/blob/main/docs/architecture/CLIENTS_ARCHITECTURE.md) | Adding new providers |

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Specific test
pytest tests/test_manifest.py -v
```

---

## Configuration

Plico uses a Pydantic-based configuration system with YAML files. Settings are layered: workbook/manifest values override config files, which override environment variables, which override class defaults.

```python
from src.config import get_config

config = get_config()
config.orchestrator.default_concurrency  # 2
config.workbook.defaults.model           # "mistral-small-2503"
config.rag.enabled                       # True
```

### Config Files

| File | Purpose |
|------|---------|
| `config/main.yaml` | Orchestrator, workbook defaults, RAG, retry, document processing |
| `config/clients.yaml` | Client type registry (API keys, models, provider prefixes) |
| `config/model_defaults.yaml` | Per-model temperature, max_tokens, system instructions |
| `config/paths.yaml` | File system paths (outputs, manifests, document cache) |
| `config/logging.yaml` | Log directory, rotation, format |

### config/main.yaml

The central configuration file. Key sections:

**Orchestrator** — controls parallel execution:

| Setting | Default | Description |
|---------|---------|-------------|
| `orchestrator.default_concurrency` | `2` | Concurrent API calls |
| `orchestrator.max_concurrency` | `10` | Hard upper limit |

**Workbook defaults** — used when a workbook/manifest doesn't specify a value:

| Setting | Default | Description |
|---------|---------|-------------|
| `workbook.defaults.model` | `"mistral-small-2503"` | Default model |
| `workbook.defaults.api_key_env` | `"MISTRALSMALL_KEY"` | Default API key env var |
| `workbook.defaults.max_retries` | `3` | Retry attempts per prompt |
| `workbook.defaults.temperature` | `0.8` | Sampling temperature |
| `workbook.defaults.max_tokens` | `4096` | Maximum response tokens |

**RAG** — retrieval-augmented generation settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `rag.enabled` | `true` | Enable/disable RAG subsystem |
| `rag.persist_dir` | `"./chroma_db"` | ChromaDB storage location |
| `rag.embedding_model` | `"mistral/mistral-embed"` | Embedding model for vector search |
| `rag.chunking.strategy` | `"recursive"` | Default chunking: `recursive`, `markdown`, `code`, `character`, `hierarchical` |
| `rag.chunking.chunk_size` | `1000` | Max characters per chunk |
| `rag.chunking.chunk_overlap` | `200` | Overlap between chunks |
| `rag.search.mode` | `"vector"` | Search mode: `vector`, `hybrid`, or `rerank` |
| `rag.search.n_results_default` | `5` | Number of chunks to retrieve |

**Document processor** — file handling and caching:

| Setting | Default | Description |
|---------|---------|-------------|
| `document_processor.checksum_length` | `8` | SHA256 prefix length for cache invalidation |
| `document_processor.text_extensions` | `.txt`, `.md`, `.py`, ... | Recognized text file extensions |

### config/clients.yaml

Defines client types and their API connections. See the [Manifest Protocol](#the-manifest-protocol) section for the full schema and available client types. Copy from `config/clients.yaml.example` to get started.

### config/model_defaults.yaml

Per-model overrides for `temperature`, `max_tokens`, and `system_instructions`. When a model is instantiated, its defaults are merged: class defaults → generic defaults → model-specific defaults → workbook/manifest config → kwargs.

```yaml
model_defaults:
  generic:
    max_tokens: 4096
    temperature: 0.7
  models:
    azure/codestral:
      max_tokens: 32000
      temperature: 0.3
    anthropic/claude-3-5-sonnet-20241022:
      max_tokens: 8192
      temperature: 0.7
```

### config/paths.yaml

| Setting | Default | Description |
|---------|---------|-------------|
| `paths.output_dir` | `"./outputs"` | Parquet result files |
| `paths.manifest_dir` | `"./manifests"` | Exported manifest folders |
| `paths.doc_cache` | `"doc_cache"` | Parsed document cache |
| `paths.library` | `"library"` | Shared document library |

### config/logging.yaml

| Setting | Default | Description |
|---------|---------|-------------|
| `logging.directory` | `"logs"` | Log file directory |
| `logging.filename` | `"orchestrator.log"` | Log file name |
| `logging.level` | `"INFO"` | Console log level |
| `logging.rotation.when` | `"midnight"` | Rotation interval |
| `logging.rotation.backup_count` | `10` | Rotated files to keep |

### Retry Configuration

Retries operate at two layers with exponential backoff:

1. **Client layer** (`config/main.yaml`): Up to `max_attempts` retries per API call
2. **Orchestrator layer** (workbook/manifest `max_retries`): Retries the full prompt execution

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

Wait times: 1s, 2s, 4s... (capped at `max_wait_seconds`). APIs that provide `retry-after` headers are respected.

For full details, see [CONFIGURATION.md](docs/CONFIGURATION.md).

---

## License

MIT License — Copyright (c) 2025 Antonio Quinonez / Far Finer LLC

---

## Contact

Antonio Quinonez — [antquinonez@farfiner.com](mailto:antquinonez@farfiner.com)

---

**Plico** — Declarative AI orchestration. One manifest protocol. Three authoring paths: Excel, Python, or AI
