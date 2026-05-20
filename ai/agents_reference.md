# Architecture and Reference

Extracted from [AGENTS.md](../AGENTS.md). Read this to understand where things live, what clients are available, and how modules relate.

## Project Structure

```
src/
├── FFAI.py                    # Main wrapper class for AI clients
├── FFAIClientBase.py          # Abstract base class for clients
├── config.py                  # Pydantic-based configuration management
├── prompt_templates.py        # YAML prompt template loader (config/prompts/)
├── OrderedPromptHistory.py    # Ordered prompt-response history tracking
├── PermanentHistory.py        # Chronological turn history
├── ConversationHistory.py     # Conversation management
│
├── core/                      # Core abstractions shared across modules
│   ├── __init__.py
│   ├── client_base.py         # FFAIClientBase ABC with usage tracking + OTel spans
│   ├── usage.py               # TokenUsage dataclass
│   └── pricing.py             # Model pricing registry for cost estimation
│
├── observability/             # Observability (token tracking, OTel telemetry)
│   ├── __init__.py            # Public API
│   └── telemetry.py           # TelemetryManager with NoOpSpan fallback
│
├── Clients/                   # AI client implementations
│   ├── __init__.py            # Exports active client classes
│   ├── model_defaults.py      # Default model configurations
│   ├── FFMistral.py           # Mistral API client (usage + OTel spans)
│   ├── FFMistralSmall.py      # Mistral Small API client (usage + OTel spans)
│   ├── FFGemini.py            # Google Gemini client (usage + OTel spans)
│   ├── FFPerplexity.py        # Perplexity AI client (usage + OTel spans)
│   ├── FFLiteLLMClient.py     # LiteLLM universal client (usage + OTel spans)
│   ├── not_maintained/        # Archived clients (Azure, Anthropic, etc.)
│   │   ├── FFAzureClientBase.py   # Base class for Azure clients
│   │   ├── FFAnthropic.py         # Anthropic Claude client
│   │   ├── FFAnthropicCached.py   # Anthropic with prompt caching
│   │   ├── FFOpenAIAssistant.py   # OpenAI Assistant API client
│   │   ├── FFNvidiaDeepSeek.py    # NVIDIA NIM DeepSeek client
│   │   ├── FFAzureMistral.py      # Azure Mistral deployment
│   │   ├── FFAzureMistralSmall.py # Azure Mistral Small deployment
│   │   ├── FFAzureCodestral.py    # Azure Codestral deployment
│   │   ├── FFAzureDeepSeek.py     # Azure DeepSeek deployment
│   │   ├── FFAzureDeepSeekV3.py   # Azure DeepSeek V3 deployment
│   │   ├── FFAzureMSDeepSeekR1.py # Azure MS DeepSeek R1 deployment
│   │   └── FFAzurePhi.py          # Azure Phi deployment
│   └──
│
├── orchestrator/              # Excel workbook orchestration
│   ├── __init__.py
│   ├── base/                  # Base orchestrator class hierarchy
│   │   ├── __init__.py
│   │   └── orchestrator_base.py  # OrchestratorBase ABC (delegates to runners)
│   ├── excel_orchestrator.py  # Main Excel orchestration engine
│   ├── workbook_parser.py    # Excel workbook parsing/validation
│   ├── manifest.py            # Manifest export and execution
│   ├── condition_evaluator.py # Conditional expression evaluation
│   ├── client_registry.py     # Multi-client configuration registry
│   ├── document_registry.py   # Document reference management
│   ├── document_processor.py  # Document loading and caching
│   ├── discovery.py           # Auto-discovery of documents for evaluation
│   ├── pre_screener.py        # Embedding-based resume pre-screening and ranking
│   ├── planning.py            # Planning phase artifact parsing and validation
│   ├── planning_runner.py     # Planning phase execution and injection
│   ├── scoring.py             # Scoring rubric extraction and aggregation
│   ├── synthesis.py           # Cross-row synthesis context formatting
│   ├── synthesis_runner.py    # Post-execution scoring and synthesis orchestration
│   ├── validation.py          # OrchestratorValidator with structured error reporting
│   ├── validation_manager.py  # Validation lifecycle management
│   ├── explain.py              # Execution plan preview and prompt preview (no API calls)
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
├── test_usage.py              # TokenUsage dataclass tests
├── test_pricing.py            # Model pricing registry tests
├── test_telemetry.py          # OTel telemetry manager tests
├── test_manifest.py           # Manifest workflow tests
├── test_excel_orchestrator.py # Orchestrator tests
├── test_workbook_parser.py    # Workbook parser tests
├── test_condition_evaluator.py # Condition evaluation tests
├── test_client_registry.py    # Client registry tests
├── test_document_processor.py # Document processor tests
├── test_document_registry.py  # Document registry tests
├── test_scoring.py            # Scoring rubric and aggregation tests
├── test_explain.py            # Execution plan preview and observability tests
├── test_planning.py           # Planning phase orchestrator tests
├── test_planning_artifact_parser.py  # Planning artifact parser unit tests
├── test_synthesis.py          # Cross-row synthesis tests
├── test_discovery.py          # Auto-discovery utility tests
├── test_pre_screener.py       # Pre-screening ranking tests
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
├── sample_workbook.yaml       # Sample workbook test config
└── prompts/                   # Externalized prompt templates
    ├── screening_planning.yaml  # Planning-phase screening prompts
    ├── screening_skills_planning.yaml  # Per-skill planning prompts (exhaustive JD decomposition)
    ├── screening_static.yaml    # Static evaluation screening prompts
    └── screening_synthesis.yaml # Synthesis/ranking screening prompts

scripts/
├── run_orchestrator.py        # Run Excel orchestrator
├── create_screening_workbook.py  # Create screening workbook from folder
├── create_screening_manifest.py  # Create screening manifest (YAML) from folder
├── manifest_export.py         # Export workbook to YAML manifest
├── manifest_run.py            # Run from manifest folder
├── inspect_parquet.py         # Inspect parquet results
├── parquet_to_excel.py        # Export parquet results to Excel workbook
├── sample_workbook_*_create_v001.py    # Workbook creation scripts
├── sample_workbook_*_validate_v001.py  # Workbook validation scripts
├── try_ai_mistralsmall_script.py       # Quick test script
└── validation/
    ├── __init__.py
    ├── validate_all.py        # Run all validations
    └── spot_check.py          # Spot check responses

USE_CASES/
└── resume_screening.md        # Resume screening guide (see below)
```

## Clients Reference

### Client Classes by Provider

**Active clients** (usage tracking + OTel spans):

| Provider | Client Class | Type | Description |
|----------|--------------|------|-------------|
| **Mistral** | `FFMistral` | native | Mistral API (mistral-large-latest) |
| | `FFMistralSmall` | native | Mistral Small API (mistral-small-2503) |
| **Google** | `FFGemini` | openai | Gemini via OpenAI-compatible API |
| **Perplexity** | `FFPerplexity` | openai | Perplexity AI via OpenAI-compatible |
| **LiteLLM** | `FFLiteLLMClient` | litellm | Universal client for 100+ providers |

**Archived clients** (in `not_maintained/`, no usage tracking):

| Provider | Client Class | Type | Description |
|----------|--------------|------|-------------|
| **Anthropic** | `FFAnthropic` | native | Claude via Anthropic API |
| | `FFAnthropicCached` | native | Claude with prompt caching |
| **OpenAI** | `FFOpenAIAssistant` | openai | OpenAI Assistant API |
| **NVIDIA** | `FFNvidiaDeepSeek` | openai | DeepSeek via NVIDIA NIM |
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
from src.Clients import FFMistralSmall, FFLiteLLMClient

# Native Mistral client
mistral = FFMistralSmall(api_key="...", model="mistral-small-2503")

# LiteLLM universal client
litellm = FFLiteLLMClient(
    model_string="openai/gpt-4",
    api_key="...",
)

# All clients share the same interface
response = client.generate_response("Hello!")

# After a call, usage and cost are available on all active clients
print(client.last_usage)       # TokenUsage(input_tokens=50, output_tokens=25, total_tokens=75)
print(f"${client.last_cost_usd:.6f}")  # $0.000011
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
