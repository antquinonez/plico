# FFClients

**Excel-Based AI Orchestration for Analysts, Researchers, and Non-Developers**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

FFClients enables you to define and execute AI prompt workflows using Excel spreadsheets—no coding required. Define prompts, dependencies, and configurations in Excel, then run the orchestrator to execute and capture results with full traceability.

---

## Why FFClients?

| For Analysts | For Researchers | For Non-Developers |
|--------------|-----------------|-------------------|
| Work in Excel, not code | Full audit trail of AI interactions | No programming required |
| Batch process data sets | Document Q&A with RAG | Familiar spreadsheet interface |
| Transparent, repeatable workflows | Literature review & synthesis | All prompts and results visible |

---

## How It Works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Excel Workbook │     │   Orchestrator   │     │  Results Sheet  │
│                 │     │                  │     │                 │
│  • prompts      │ ──► │  • Parallel exec │ ──► │  • Timestamped  │
│  • config       │     │  • Multi-model   │     │  • Full audit   │
│  • data         │     │  • RAG search    │     │  • Traceable    │
│  • documents    │     │  • Conditional   │     │  • Reproducible │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

Define your workflow in an Excel workbook, run the orchestrator from the command line, and get a timestamped results sheet with complete provenance.

---

## Key Features

### Core Capabilities
- **Spreadsheet-Based Workflows** — Define prompts, dependencies, and configuration in Excel
- **Declarative Context** — Reference previous prompts by name for automatic context assembly
- **Full Audit Trail** — All prompts, responses, and timestamps recorded in timestamped results sheets
- **100+ AI Providers** — Support via LiteLLM including OpenAI, Anthropic, Mistral, Azure, Gemini, and more

### Execution
- **Batch Execution** — Run the same workflow across multiple data sets with variable templating (`{{variable}}`)
- **Parallel Execution** — Execute independent prompts concurrently for faster results (configurable concurrency)
- **Multi-Model Support** — Use different AI models for different prompts in the same workflow
- **Conditional Execution** — Skip or run prompts based on previous results with secure AST-based expressions

### Integration
- **Document Injection** — Reference external documents (PDF, MD, JSON) in prompts with automatic parsing
- **RAG Integration** — Semantic search over document collections for relevant context retrieval
- **Pre-Indexing** — Documents automatically indexed for semantic search at orchestrator startup

---

## How FFClients Compares

| Feature | FFClients | LangChain | CrewAI | LlamaIndex |
|---------|:---------:|:---------:|:------:|:----------:|
| **No-code workflow** | ✅ Excel-native | ❌ Python only | Partial | ❌ Python only |
| **Full audit trail** | ✅ Built-in | ❌ Requires setup | ✅ Via platform | ❌ Requires setup |
| **Batch processing** | ✅ Native | Manual | Manual | Manual |
| **Learning curve** | Low | High | Medium | Medium |
| **Target user** | Analysts | Developers | Developers | Developers |
| **Multi-agent systems** | ❌ | ✅ | ✅ | Partial |
| **Tool/function calling** | ❌ | ✅ | ✅ | ✅ |
| **Real-time streaming** | ❌ | ✅ | ✅ | ✅ |

**FFClients fills a unique niche**: Making AI orchestration accessible to non-programmers while maintaining enterprise-grade traceability.

---

## When to Use FFClients

### ✅ Use FFClients if you:
- Prefer working in Excel over writing code
- Need full audit trails for compliance or reproducibility
- Want to batch process multiple data sets through the same AI workflow
- Work with a team that includes non-developers
- Need document Q&A with semantic search
- Want to compare outputs from multiple AI models side-by-side

### ⚠️ Consider alternatives if you need:
- Multi-agent collaboration (try CrewAI or AutoGen)
- Real-time chat applications (try LangChain)
- Tool/function calling capabilities (try LangChain or LlamaIndex)
- Production API services (try LangServe)

---

## Installation

```bash
# Clone the repository
git clone https://github.com/farfiner/ffclients.git
cd ffclients

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

---

## Quick Start

### Excel Orchestrator (No Code Required)

```bash
# Create a new workbook template
python scripts/run_orchestrator.py my_analysis.xlsx

# Edit the prompts sheet in Excel, then run
python scripts/run_orchestrator.py my_analysis.xlsx --client mistral-small

# Run with parallel execution (4 concurrent API calls)
python scripts/run_orchestrator.py my_analysis.xlsx -c 4
```

### Python API

```python
from src.FFAI import FFAI
from src.Clients.FFMistralSmall import FFMistralSmall

client = FFMistralSmall(api_key="your-api-key")
ffai = FFAI(client)

# Simple prompt
response = ffai.generate_response("Hello!")

# Named prompt with declarative context
ffai.generate_response("What is 2+2?", prompt_name="math")
ffai.generate_response(
    "What was my math question?",
    prompt_name="followup",
    history=["math"]  # Automatically includes "math" as context
)
```

---

## Excel Workbook Structure

Define your workflow in an Excel workbook with these sheets:

### config Sheet
| Field | Value |
|-------|-------|
| model | mistral-small-2503 |
| temperature | 0.7 |
| max_tokens | 4096 |
| system_instructions | You are a helpful assistant. |

### prompts Sheet
| sequence | prompt_name | prompt | history |
|----------|-------------|--------|---------|
| 1 | context | I run a coffee shop with 50 customers. | |
| 2 | problem | My electricity bill is too high. | `["context"]` |
| 3 | solution | Suggest 3 ways to reduce my bill. | `["context", "problem"]` |

### data Sheet (Batch Execution)
| id | region | product |
|----|--------|---------|
| 1 | north | widget_a |
| 2 | south | widget_b |

Use `{{region}}` and `{{product}}` in prompts for variable substitution.

### clients Sheet (Multi-Model)
| name | client_type | temperature | max_tokens |
|------|-------------|-------------|------------|
| fast | mistral-small | 0.3 | 100 |
| creative | anthropic | 0.9 | 500 |

Reference in prompts with the `client` column.

### documents Sheet
| reference_name | file_path |
|----------------|-----------|
| product_spec | library/product_spec.pdf |
| api_guide | docs/api_reference.md |

Reference in prompts with `["product_spec"]` in the `references` column.

---

## Supported AI Providers

| Provider | Client Type | Notes |
|----------|-------------|-------|
| **LiteLLM (Recommended)** | `litellm-*` | 100+ providers with fallback support |
| Mistral | `mistral`, `mistral-small` | Native API |
| Anthropic | `anthropic`, `anthropic-cached` | Claude models |
| OpenAI | via `litellm-openai` | GPT-4, GPT-4o |
| Google | `gemini` | Gemini models |
| Perplexity | `perplexity` | Sonar models |
| Azure OpenAI | `azure-*` | Various deployments |
| NVIDIA NIM | `nvidia-deepseek` | DeepSeek via NIM |

---

## Example Use Cases

### Research Workflow
```
1. Load research documents → Document injection
2. Extract key findings → Named prompts
3. Synthesize across sources → History context
4. Generate summary report → Conditional on success
```

### Batch Data Analysis
```
1. Define analysis prompts once
2. Provide data sheet with 100 rows
3. Execute with {{variable}} templating
4. All 100 results in timestamped sheet
```

### Document Q&A with RAG
```
1. Index document library (automatic on orchestrator run)
2. Use semantic_query column for retrieval
3. Get relevant chunks, not entire documents
4. Full audit of what context was used
```

### RAG Index Management
```bash
inv index-status           # View indexed documents
inv index-rebuild          # Rebuild all indexes
inv index-clear-type markdown  # Clear specific index type
inv rag-stats              # View RAG statistics
```

---

## Documentation

- [Orchestrator User Guide](docs/ORCHESTRATOR%20README.md) — Excel-based workflow execution
- [Client API Guide](docs/CLIENT%20API%20USER%20GUIDE.md) — Python API for developers
- [Configuration](docs/CONFIGURATION.md) — YAML-based configuration system
- [Conditional Expressions](docs/CONDITIONAL%20EXPRESSIONS%20USER%20GUIDE.md) — Branching logic
- [Architecture Overview](docs/architecture/ARCHITECTURE.md) — System design
- [RAG Architecture](docs/architecture/RAG_ARCHITECTURE.md) — Semantic search integration

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_ffai.py -v
```

---

## Project Structure

```
src/
├── FFAI.py              # Main wrapper class
├── FFAIClientBase.py    # Abstract base class
├── config.py            # Configuration management
├── Clients/             # AI client implementations
│   ├── FFLiteLLMClient.py
│   ├── FFMistral.py
│   ├── FFAnthropic.py
│   └── ...
├── orchestrator/        # Excel orchestration
│   ├── excel_orchestrator.py
│   ├── workbook_builder.py
│   ├── condition_evaluator.py
│   └── ...
└── RAG/                 # Semantic search (RAG)
    ├── FFRAGClient.py
    ├── FFVectorStore.py
    ├── text_splitters/  # Chunking strategies
    ├── indexing/        # BM25, hierarchical indexes
    └── search/          # Hybrid search, rerankers

config/                  # YAML configuration files
docs/                    # Documentation
tests/                   # Test suite
scripts/                 # Utility scripts
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License - Copyright (c) 2025 Antonio Quinonez / Far Finer LLC

See [LICENSE](LICENSE) for details.

---

## Contact

Antonio Quinonez - [antquinonez@farfiner.com](mailto:antquinonez@farfiner.com)

---

**FFClients** — Making AI workflows accessible to everyone, one spreadsheet at a time.
