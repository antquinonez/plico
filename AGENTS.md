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
inv create                    # Create all test workbooks
inv run                       # Run orchestrator on all workbooks
inv all                       # Full pipeline: clean, create, run, validate
inv config-check              # Display current configuration
inv spot-check                # Spot check responses from key prompts
```

### RAG Indexing Tasks

```bash
inv index-status              # Show RAG indexing status
inv index-clear               # Clear all RAG indexes
inv index-clear -c recursive  # Clear specific chunking strategy
inv index-rebuild             # Rebuild indexes from documents workbook
inv rag-stats                 # Show detailed RAG statistics
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
│   └── document_processor.py  # Document loading and caching
│
└── RAG/                       # Retrieval-Augmented Generation
    ├── __init__.py            # Exports all RAG components
    ├── FFRAGClient.py         # High-level RAG client
    ├── FFEmbeddings.py        # LiteLLM-based embeddings
    ├── FFVectorStore.py       # ChromaDB vector storage
    ├── mcp_tools.py           # MCP tool definitions
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

## Manifest Workflow

The manifest workflow separates workbook parsing from execution, enabling version control of prompts.

### Export Workbook to Manifest

```bash
# Export to default manifest directory
python scripts/export_manifest.py ./workbooks/my_prompts.xlsx

# Export to custom directory
python scripts/export_manifest.py ./workbook.xlsx --output ./custom_manifest/
```

Creates a folder with:
- `manifest.yaml` - Metadata
- `config.yaml` - Configuration
- `prompts.yaml` - All prompts
- `data.yaml` - Batch data (if present)
- `clients.yaml` - Client configs (if present)
- `documents.yaml` - Document refs (if present)

### Run from Manifest

```bash
# Run with default settings
python scripts/run_manifest.py ./manifests/manifest_my_prompts

# Run with specific client and concurrency
python scripts/run_manifest.py ./manifests/manifest_my_prompts --client mistral-small -c 4

# Dry run to validate
python scripts/run_manifest.py ./manifests/manifest_my_prompts --dry-run
```

### Inspect Results

```bash
python scripts/inspect_parquet.py ./outputs/20250301120000_my_prompts.parquet
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
| Batch | Batch execution with variables | 35 prompts × 5 batches, variable templating |
| Max | Combined features | Batch + conditional + multi-client in one workbook |

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

- Target Python 3.10+
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
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]
```

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

## Environment

- Virtual environment: `.venv313/` (Python 3.13)
  - Activate: `source .venv313/bin/activate`
  - Install: `uv pip install -e ".[dev]"`
- Environment variables: Load via `python-dotenv` (`load_dotenv()`)
- Set `POLARS_SKIP_CPU_CHECK=1` for Polars compatibility

### Required Environment Variables (in .env)

```bash
# At least one API key required
MISTRALSMALL_KEY=your-key-here
MISTRAL_KEY=your-key-here
ANTHROPIC_KEY=your-key-here
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
