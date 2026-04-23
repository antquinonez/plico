# Plico Quick Start Guide

Get Plico installed, configured, and running in under 5 minutes.

---

## Prerequisites

- Python 3.10 or later (3.14 recommended)
- An API key for at least one AI provider (OpenAI, Anthropic, Mistral, Gemini, etc.)

---

## Installation

```bash
git clone https://github.com/antquinonez/plico.git
cd plico

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e ".[dev]"     # or: uv pip install -e ".[dev]"
```

> **Tip:** Make sure you activate the virtual environment before running any commands. If you see `ModuleNotFoundError`, the venv is not active.

---

## Configuration

### 1. Set an API key

The recommended way is to create a `.env` file in the project root. Plico scripts auto-load it via `python-dotenv`:

```bash
OPENAI_API_KEY="your-api-key"
```

Alternatively, export directly in your shell:

```bash
export OPENAI_API_KEY="your-api-key"
```

For all supported providers and their environment variable names, see `config/clients.yaml.example`.

### 2. (Optional) Customize client configuration

If you want to customize default models, temperatures, or API base URLs, copy the example config:

```bash
cp config/clients.yaml.example config/clients.yaml
```

Edit `config/clients.yaml` to configure only the providers you plan to use. If you don't need custom defaults, this step is not required — Plico works with environment variables alone.

### 3. (Optional) Install git hooks

```bash
pre-commit install
```

---

## Your First Run

The fastest way to verify everything works:

```bash
inv wb.basic --client litellm-openai
```

This creates a sample workbook, runs it against OpenAI, and validates the output. All prompts should succeed.

Pass `-c` to control concurrency (default is 3):

```bash
inv wb.basic --client litellm-openai -c 4
```

### Choosing a Client

The `--client` flag accepts any client type from `config/clients.yaml`. Common options:

| Client Flag | Provider | Notes |
|-------------|----------|-------|
| `litellm-openai` | OpenAI | `gpt-4o-mini` by default |
| `litellm-anthropic` | Anthropic | Claude models |
| `litellm-mistral` | Mistral | Mistral Small/Large |
| `litellm-gemini` | Google | Gemini models |
| `mistral-small` | Mistral (native) | Direct SDK, no LiteLLM |
| `anthropic` | Anthropic (native) | Direct SDK, no LiteLLM |
| `gemini` | Google (native) | Direct SDK, no LiteLLM |

Example with Anthropic:

```bash
# Add to .env file:
# ANTHROPIC_API_KEY="your-key"
inv wb.basic --client litellm-anthropic
```

---

## Sample Workbooks

Pre-built workbooks demonstrate every Plico feature. Each `wb.*` command creates the workbook, runs orchestration, and validates results in one step.

```bash
inv wb.basic --client litellm-openai           # 31 prompts, 4 dependency levels
inv wb.conditional --client litellm-openai     # 50 conditional expression tests
inv wb.batch --client litellm-openai           # 35 prompts x 5 batches with variable templating
inv wb.multiclient --client litellm-openai     # 13 prompts, per-prompt client selection
inv wb.documents --client litellm-openai       # 23 prompts with document references and RAG
inv wb.max --client litellm-openai             # Combined: batch + conditional + multi-client + RAG
```

All commands accept `--client` and `-c` (concurrency) flags. Omit `--client` to use the default from `config/clients.yaml`.

### Run All Workbooks

```bash
inv wb.all --client litellm-openai
```

---

## Other Ways to Use Plico

### Excel Workbook (Visual Authoring)

Best for non-developers and ad-hoc analysis.

```bash
# Create template workbook (exits after creating if file doesn't exist)
python scripts/run_orchestrator.py my_workbook.xlsx

# Open in Excel, add prompts to the 'prompts' sheet, then run:
python scripts/run_orchestrator.py my_workbook.xlsx -c 4 --client litellm-openai

# Export to manifest for version control
python scripts/manifest_export.py my_workbook.xlsx
python scripts/manifest_run.py ./manifests/manifest_my_workbook/ --client litellm-openai
```

### Direct Manifest (YAML Authoring)

Create a manifest folder with YAML files for fine-grained control over prompts, batch data, and client routing:

```bash
mkdir -p manifests/my_first

cat > manifests/my_first/config.yaml << 'EOF'
model: gpt-4o-mini
temperature: 0.7
max_tokens: 512
EOF

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

cat > manifests/my_first/manifest.yaml << 'EOF'
version: "1.0"
EOF
```

Run it:

```bash
python scripts/manifest_run.py ./manifests/my_first/ --client litellm-openai -c 2
```

### Python API (Programmatic)

Best for integration into applications.

```python
from src.FFAI import FFAI
from src.Clients.FFLiteLLMClient import FFLiteLLMClient

client = FFLiteLLMClient(model_string="openai/gpt-4o-mini")
ffai = FFAI(client)

ffai.generate_response("My name is Alice.", prompt_name="intro")
ffai.generate_response("I like data science.", prompt_name="interest")
response = ffai.generate_response(
    "What do you know about me?",
    prompt_name="recall",
    history=["intro", "interest"]
)
print(response)
```

Or use the manifest orchestrator:

```python
from src.orchestrator import ManifestOrchestrator
from src.Clients.FFLiteLLMClient import FFLiteLLMClient

client = FFLiteLLMClient(model_string="openai/gpt-4o-mini")
orchestrator = ManifestOrchestrator(
    manifest_dir="./manifests/my_workflow/",
    client=client,
    concurrency=4
)
parquet_path = orchestrator.run()
```

---

## Key Features

| Feature | How |
|---------|-----|
| **Parallel execution** | `-c 4` flag (concurrency) |
| **Dependency chains** | `history: ["prev_prompt"]` in prompts.yaml |
| **Conditional execution** | `condition: '{{prev.status}} == "success"'` |
| **Batch processing** | Add `data.yaml` with variable rows |
| **Multi-model routing** | Add `clients.yaml`, reference by name |
| **Document injection** | Add `documents.yaml`, use `references` in prompts |
| **RAG search** | Use `semantic_query` field in prompts |

---

## Inspecting Results

All runs produce a timestamped Parquet file in `outputs/`. Inspect the latest run:

```bash
python scripts/inspect_parquet.py outputs/$(ls -t outputs/*.parquet | head -1)
```

Or to see only the summary and response columns:

```bash
python -c "
import polars as pl
df = pl.read_parquet(outputs/$(ls -t outputs/*.parquet | head -1))
for row in df.iter_rows(named=True):
    print(f'=== {row[\"prompt_name\"]} ===')
    print(row['response'])
    print()
"
```

---

## Dry Run (Validate Without Calling APIs)

```bash
python scripts/manifest_run.py ./manifests/my_first/ --dry-run
python scripts/run_orchestrator.py my_workbook.xlsx --dry-run
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'src'` | Activate the virtual environment: `source .venv/bin/activate` |
| `POLARS_SKIP_CPU_CHECK` error | Set the environment variable: `export POLARS_SKIP_CPU_CHECK=1` |
| `429` rate limit errors | Reduce concurrency with `-c 1` or increase retries in `config/main.yaml` |
| `Client type not found` | Run `cp config/clients.yaml.example config/clients.yaml` and verify the client type exists |

---

## Common Commands

```bash
inv --list          # Show all available tasks
inv test            # Run unit tests
inv lint            # Check linting
inv format          # Format code
```

---

## Next Steps

- **[ORCHESTRATOR README](ORCHESTRATOR%20README.md)** — Full Excel and manifest execution guide
- **[CLIENT API USER GUIDE](CLIENT%20API%20USER%20GUIDE.md)** — Python API reference
- **[CONDITIONAL EXPRESSIONS](CONDITIONAL%20EXPRESSIONS%20USER%20GUIDE.md)** — Condition syntax and functions
- **[CONFIGURATION](CONFIGURATION.md)** — All configuration options
- **[ARCHITECTURE](architecture/ARCHITECTURE.md)** — System design
