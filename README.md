# Plico

**Declarative AI orchestration. One manifest protocol. Three authoring paths: Excel, Python, or AI.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) *(3.13 required for RAG)*
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
+--------------------------------------------------------------------------------------------------+
|                                        AUTHORING SURFACES                                        |
|                                                                                                  |
|   +---------------------+          +---------------------+          +-------------------------+  |
|   |       Excel         |          |       Python        |          |        AI Agent         |  |
|   |      Workbook       |          |        Script       |          |     (writes YAML)       |  |
|   |                     |          |                     |          |                         |  |
|   |   Human-friendly    |          |   Programmatic      |          |   Autonomous            |  |
|   |   visual editor     |          |   generation        |          |   composition           |  |
|   +----------+----------+          +----------+----------+          +------------+------------+  |
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
+--------------------------------------------------------------------------------------------------+
|                                        EXECUTION LAYER                                            |
|                                                                                                  |
|                                        ManifestOrchestrator                                      |
|                                               |                                                  |
|                                               v                                                  |
|                           +-------------------------------------+                                |
|                           |      Timestamped Parquet            |                                |
|                           |      (analytics-ready)              |                                |
|                           |                                     |                                |
|                           |  <-- AI can analyze -->             |                                |
|                           |  <-- AI can iterate -->             |                                |
|                           +-------------------------------------+                                |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
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

### Installation

```bash
git clone https://github.com/farfiner/plico.git
cd plico
pip install -e ".[dev]"
```

### Set Your API Key

```bash
export MISTRALSMALL_KEY="your-api-key"
# Or other providers:
# export ANTHROPIC_API_KEY="..."
# export OPENAI_API_KEY="..."
```

### Run a Sample Manifest

```bash
# Run an existing manifest (if available)
python scripts/run_manifest.py ./manifests/manifest_sample_workbook_max/ -c 4

# Inspect results
python scripts/inspect_parquet.py ./outputs/<timestamp>_sample_workbook_max.parquet
```

### Create a Minimal Manifest

```bash
mkdir -p manifests/my_first

# Create config.yaml
cat > manifests/my_first/config.yaml << 'EOF'
model: mistral-small-2503
temperature: 0.7
max_tokens: 2048
EOF

# Create prompts.yaml
cat > manifests/my_first/prompts.yaml << 'EOF'
prompts:
  - sequence: 1
    prompt_name: greet
    prompt: "Introduce yourself briefly."

  - sequence: 2
    prompt_name: question
    prompt: "What is the most interesting thing about AI orchestration?"
    history: ["greet"]

  - sequence: 3
    prompt_name: summarize
    prompt: "Summarize our conversation in one sentence."
    history: ["greet", "question"]
EOF

# Create manifest.yaml (minimal metadata file)
cat > manifests/my_first/manifest.yaml << 'EOF'
version: "1.0"
EOF

# Run it
python scripts/run_manifest.py ./manifests/my_first/ -c 2
```

### Or, Start in Excel

```bash
# Create workbook template (exits after creating)
python scripts/run_orchestrator.py analysis.xlsx

# Edit the prompts sheet in Excel, then run again to execute
python scripts/run_orchestrator.py analysis.xlsx -c 4

# Results are written to a timestamped sheet in the workbook

# Optionally export to manifest for version control
python scripts/export_manifest.py analysis.xlsx
python scripts/run_manifest.py ./manifests/manifest_analysis/
```

**Try a sample workbook:**

```bash
inv basic              # Parallel execution with dependencies
inv conditional        # Conditional expressions
inv batch              # Batch execution with variables
inv multiclient        # Multi-client routing
inv documents          # Document references and RAG
inv max                # All features combined

inv create             # Create all sample workbooks
```

Sample workbooks are created in the project root (e.g., `sample_workbook.xlsx`). Run `inv --list` to see all tasks, or see [AGENTS.md](AGENTS.md) for details.

---

## The Manifest Protocol

### Folder Structure

```
manifest_analysis/
├── manifest.yaml      # Metadata: name, version, source, timestamp
├── config.yaml        # Execution settings: model, temperature, retries
├── prompts.yaml       # Workflow definition: prompts, dependencies, conditions
├── data.yaml          # Optional: batch variables for templating
├── clients.yaml       # Optional: named model configurations
└── documents.yaml     # Optional: document references for injection/RAG
```

### prompts.yaml Schema

```yaml
prompts:
  - sequence: 1                    # Execution order
    prompt_name: fetch             # Unique identifier for references
    prompt: "Retrieve the data"    # The prompt text (supports {{variable}} templating)
    history: []                    # Dependencies (prompt_names to include as context)
    client: null                   # Named client or null for default
    condition: null                # Expression for conditional execution
    references: []                 # Document reference_names for injection
    semantic_query: null           # RAG search query
    semantic_filter: null          # Metadata filter for RAG search
    query_expansion: null          # Enable query expansion (true/false)
    rerank: null                   # Enable reranking (true/false)
```

### config.yaml Schema

```yaml
model: mistral-small-2503
temperature: 0.7
max_tokens: 4096
system_instructions: "You are a helpful assistant."
max_retries: 3
created_at: "2026-03-01T12:00:00"  # Auto-generated on export
```

### data.yaml Schema (Batch Mode)

```yaml
data:
  - id: 1
    batch_name: "north_region"
    region: "north"
    product: "widget_a"
  - id: 2
    batch_name: "south_region"
    region: "south"
    product: "widget_b"
```

Use `{{region}}` and `{{product}}` in prompts for variable substitution.

### clients.yaml Schema (Multi-Model)

```yaml
clients:
  - name: fast
    client_type: litellm-mistral
    temperature: 0.3
    max_tokens: 100

  - name: creative
    client_type: litellm-anthropic
    temperature: 0.9
    max_tokens: 2000
```

Reference by name in prompts: `client: fast`

### documents.yaml Schema

```yaml
documents:
  - reference_name: spec
    common_name: "Product Specification"
    file_path: "library/product_spec.md"
    tags: "product,specification,overview"

  - reference_name: api
    common_name: "API Reference"
    file_path: "library/api_reference.pdf"
    tags: "api,reference,authentication"
```

Reference in prompts: `references: ["spec", "api"]`

**Fields:**

| Field | Description |
|-------|-------------|
| `reference_name` | Unique identifier for prompt references |
| `common_name` | Human-readable name |
| `file_path` | Path to document (relative to workbook) |
| `tags` | Comma-separated tags for RAG filtering (optional) |

**Chunking strategy is auto-inferred from file extension:**

| Extension | Strategy | Description |
|-----------|----------|-------------|
| `.md` | `markdown` | Header-aware chunking |
| `.py`, `.js`, `.ts`, etc. | `code` | Function-aware chunking |
| Others | `recursive` | General-purpose chunking |

**Note:** Chunking strategy is automatically inferred from file extension:
- `.md` files → `markdown` chunking (header-aware)
- `.py`, `.js`, `.ts`, etc. → `code` chunking (function-aware)
- Other files → `recursive` chunking (general purpose)

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
data:
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

While manifests are the protocol, Excel provides a visual interface for human authors.

### Workbook Structure

| Sheet | Purpose |
|-------|---------|
| `config` | Model, temperature, retries, system instructions |
| `prompts` | Prompt definitions with dependencies, conditions, references |
| `data` | Batch variables for templated execution |
| `clients` | Named client configurations |
| `documents` | Document references for injection and RAG |

### prompts Sheet Columns

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

### Workflow

1. **Create template:** `python scripts/run_orchestrator.py analysis.xlsx`
   - Creates template workbook if file doesn't exist, then exits
2. **Edit in Excel:** Define prompts, dependencies, conditions
3. **Run directly:** `python scripts/run_orchestrator.py analysis.xlsx -c 4`
   - Results written to a timestamped sheet in the workbook
4. **Or export to manifest:** `python scripts/export_manifest.py analysis.xlsx`
   - Then: `python scripts/run_manifest.py ./manifests/manifest_analysis/`

**Recommendation:** The manifest workflow is preferred for version control and AI composability.

---

## Supported Providers

### Via LiteLLM (Recommended)

```python
FFLiteLLMClient(model_string="azure/mistral-small-2503")
FFLiteLLMClient(model_string="anthropic/claude-3-5-sonnet-20241022")
FFLiteLLMClient(model_string="openai/gpt-4o")
FFLiteLLMClient(model_string="mistral/mistral-small-latest")
FFLiteLLMClient(model_string="gemini/gemini-1.5-pro")
FFLiteLLMClient(model_string="perplexity/llama-3.1-sonar-large-128k-online")
# + 100 more providers
```

### Native Direct-API Clients

| Client | Provider |
|--------|----------|
| `FFMistral` / `FFMistralSmall` | Mistral AI |
| `FFAnthropic` / `FFAnthropicCached` | Anthropic (with prompt caching) |
| `FFGemini` | Google Gemini |
| `FFPerplexity` | Perplexity AI |
| `FFNvidiaDeepSeek` | DeepSeek via Nvidia NIM |
| `FFAzureMistral` / `FFAzureCodestral` / `FFAzurePhi` | Azure AI Inference |
| `FFOpenAIAssistant` | OpenAI Assistant API |

### Automatic Fallbacks

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

**Auditability.** Every execution recorded: prompt, response, model, condition, error, retry. Manifest + Parquet = complete provenance.

**Batch processing.** Purpose-built for running workflows across multiple data inputs at the workflow definition level.

### Where Others Win

**Agent capabilities.** LangChain, AutoGen, CrewAI excel at dynamic agent systems with tool use and autonomous reasoning. Plico is for structured workflows.

**RAG depth.** LlamaIndex offers more index types and agentic retrieval.

**Prompt optimization.** DSPy can automatically improve prompts through compilation.

---

## Architecture

```
+--------------------------------------------------------------------------------------------------+
|                                        AUTHORING LAYER                                            |
|                                                                                                  |
|   Excel Workbook              Python Script              AI Agent                                 |
|   (human visual)              (programmatic)             (autonomous)                             |
|                                                                                                  |
+------------------------------------------------+-------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                        MANIFEST LAYER                                             |
|                                                                                                  |
|   YAML Manifest (manifest.yaml, config.yaml, prompts.yaml, ...)                                  |
|                                                                                                  |
|   <-- Git versioned -->    <-- AI readable -->    <-- AI writable -->                           |
|                                                                                                  |
+------------------------------------------------+-------------------------------------------------+
                                                 |
                                                 v
+--------------------------------------------------------------------------------------------------+
|                                        EXECUTION LAYER                                            |
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
|                                        CLIENT LAYER                                               |
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
|                                        OUTPUT LAYER                                               |
|                                                                                                  |
|   Timestamped Parquet (analytics-ready)                                                          |
|   <-- AI can analyze -->    <-- AI can iterate -->                                               |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

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
client = FFLiteLLMClient(model_string="anthropic/claude-3-5-sonnet-20241022")
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
│   ├── FFAI.py                    # Core wrapper — context assembly, history
│   ├── FFAIClientBase.py          # Client abstract base class
│   ├── config.py                  # Pydantic-settings configuration
│   ├── Clients/                   # Provider implementations
│   │   ├── FFLiteLLMClient.py     # Universal client (recommended)
│   │   ├── FFMistral.py, FFAnthropic.py, FFGemini.py, ...
│   │   └── FFAzureClientBase.py   # Azure-specific ABC
│   ├── orchestrator/              # Orchestration engine
│   │   ├── excel_orchestrator.py  # Excel execution
│   │   ├── manifest.py            # Manifest export/execution
│   │   ├── condition_evaluator.py # AST-based expression evaluator
│   │   ├── client_registry.py     # Client factory and routing
│   │   ├── document_processor.py  # Document parsing and caching
│   │   └── document_registry.py   # Document lookup and injection
│   └── RAG/                       # Retrieval-augmented generation
│       ├── FFRAGClient.py         # High-level RAG interface
│       ├── FFVectorStore.py       # ChromaDB operations
│       ├── text_splitters/        # Chunking strategies
│       ├── indexing/              # BM25, hierarchical indexing
│       └── search/                # Hybrid search, re-ranking
├── config/                        # YAML configuration files
├── scripts/                       # CLI tools
├── tests/                         # Unit and integration tests
├── manifests/                     # Exported YAML manifests
├── outputs/                       # Parquet results
└── docs/                          # Architecture and user guides
```

---

## Documentation

| Document | Description |
|----------|-------------|
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

Plico uses a Pydantic-based configuration system with YAML files:

```python
from src.config import get_config

config = get_config()
config.orchestrator.default_concurrency  # 2
config.workbook.defaults.model           # "mistral-small-2503"
config.rag.enabled                       # True
```

Configuration priority: init arguments > environment variables > YAML files > defaults.

---

## License

MIT License — Copyright (c) 2025 Antonio Quinonez / Far Finer LLC

---

## Contact

Antonio Quinonez — [antquinonez@farfiner.com](mailto:antquinonez@farfiner.com)

---

**Plico** — Declarative AI orchestration through Excel. Fold your intent, unfold your workflow.
