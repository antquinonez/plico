# FFClients Architecture Overview

## System Context

FFClients is a declarative context handling API wrapper for AI models with Excel-based orchestration capabilities. It enables:

1. **Unified AI Client Interface** - Abstract away provider differences behind a consistent API
2. **Declarative Context Management** - Reference previous prompts by name for automatic context assembly
3. **Excel-Based Orchestration** - Define and execute prompt workflows via Excel workbooks

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER LAYER                                  │
│                                                                          │
│   ┌──────────────────┐         ┌──────────────────────────┐            │
│   │   Python Code    │         │    Excel Workbook        │            │
│   │   (FFAI API)     │         │    (Orchestrator CLI)    │            │
│   └────────┬─────────┘         └────────────┬─────────────┘            │
│            │                                │                           │
└────────────┼────────────────────────────────┼───────────────────────────┘
             │                                │
             ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FFAI CORE LAYER                                  │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         FFAI.py                                  │   │
│   │  - Declarative context assembly (history=["name1", "name2"])    │   │
│   │  - Named prompt management                                       │   │
│   │  - History persistence & DataFrame export                        │   │
│   └──────────────────────────┬──────────────────────────────────────┘   │
│                              │                                           │
│              ┌───────────────┴───────────────┐                          │
│              ▼                               ▼                           │
│   ┌─────────────────────┐       ┌─────────────────────────┐            │
│   │ OrderedPromptHistory│       │   PermanentHistory      │            │
│   │ (named, queryable)  │       │   (chronological turns) │            │
│   └─────────────────────┘       └─────────────────────────┘            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                     │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                     FFAIClientBase (ABC)                        │   │
│   │  - generate_response(prompt, **kwargs)                          │   │
│   │  - clear_conversation()                                         │   │
│   │  - get/set_conversation_history()                               │   │
│   └──────────────────────────┬──────────────────────────────────────┘   │
│                              │                                           │
│    ┌─────────────────────────┼─────────────────────────┐                │
│    │                         │                         │                │
│    ▼                         ▼                         ▼                │
│ ┌─────────────────┐   ┌─────────────┐          ┌─────────────┐         │
│ │FFLiteLLMClient  │   │   Mistral   │          │  Anthropic  │         │
│ │ (Universal)     │   │   Clients   │          │   Clients   │         │
│ │ - 100+ providers│   └─────────────┘          └─────────────┘         │
│ │ - Fallbacks     │                                                     │
│ └─────────────────┘   ┌─────────────┐          ┌─────────────┐         │
│                       │   Azure     │          │   Gemini    │         │
│                       │   Clients   │          │ Perplexity  │         │
│                       └─────────────┘          └─────────────┘         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       EXTERNAL APIS                                      │
│                                                                          │
│   Mistral API │ Anthropic API │ OpenAI API │ Azure AI │ Google AI │ ...│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Subsystems

### Subsystem 1: Client Wrappers
**Purpose:** Abstract away AI provider differences behind a unified interface.

**Key Components:**
- `FFAIClientBase` - Abstract base class defining the contract
- `FFLiteLLMClient` - Universal client supporting 100+ providers via LiteLLM (recommended)
- `FFMistral`, `FFAnthropic`, `FFPerplexity`, etc. - Provider-specific implementations
- `FFAzureClientBase` - Azure-specific base class (inherits from FFAIClientBase)
- `FFAzureLiteLLM` - Factory for creating Azure LiteLLM clients

**Features:**
- Unified `generate_response()` interface
- Conversation history management
- `clone()` method for thread-safe parallel execution
- Automatic fallback support (FFLiteLLMClient)
- Model-specific defaults for common configurations

**See:** [CLIENTS_ARCHITECTURE.md](./CLIENTS_ARCHITECTURE.md)

### Subsystem 2: Excel Orchestrator
**Purpose:** Enable non-programmers to define and execute AI prompt workflows.

**Key Components:**
- `ExcelOrchestrator` - Main orchestration engine with parallel execution
- `WorkbookBuilder` - Excel file creation, validation, and I/O
- `ClientRegistry` - Client factory and multi-client support
- `DocumentProcessor` - Document parsing and checksum-based caching
- `DocumentRegistry` - Document lookup and reference injection
- `ConditionEvaluator` - Conditional expression evaluation for prompt execution

**Features:**
- Dependency-aware parallel execution
- Real-time progress indicator
- Configurable concurrency (default: 2, max: 10)
- Thread-safe client isolation
- Batch execution with variable templating
- Per-prompt client configuration
- Document reference injection with LlamaParse support
- Conditional execution with expression-based prompt skipping

**See:** [ORCHESTRATOR_ARCHITECTURE.md](./ORCHESTRATOR_ARCHITECTURE.md)

### Subsystem 3: Document Reference System
**Purpose:** Allow prompts to reference external documents that are parsed, cached, and injected at runtime.

**Key Components:**
- `DocumentProcessor` - Checksum computation, LlamaParse integration, parquet caching
- `DocumentRegistry` - Document lookup, validation, and reference injection

**Features:**
- Automatic document parsing (text files read directly, others via LlamaParse)
- Checksum-based caching with parquet storage
- Deduplication via SHA256 hash prefix in filenames
- XML-formatted reference injection into prompts

**See:** [ORCHESTRATOR_ARCHITECTURE.md](./ORCHESTRATOR_ARCHITECTURE.md#document-reference-system)

### Subsystem 4: RAG (Retrieval-Augmented Generation)
**Purpose:** Provide semantic search over document collections for context-aware prompt augmentation.

**Key Components:**
- `FFRAGClient` - High-level RAG interface with pre-indexing support
- `FFVectorStore` - ChromaDB operations with index tracking by type/checksum
- `FFEmbeddings` - LiteLLM-based embedding generation
- `text_splitters/` - Multiple chunking strategies (recursive, markdown, code, hierarchical, character)
- `indexing/` - BM25 sparse index, hierarchical index, contextual embeddings
- `search/` - Hybrid search (vector + BM25), cross-encoder and diversity rerankers
- `RAGMCPTools` - MCP tool definitions for AI assistants

**Features:**
- Multiple chunking strategies optimized for different content types
- Hybrid search combining vector similarity with BM25 keyword matching
- Post-retrieval reranking (cross-encoder, diversity)
- Pre-indexing at orchestrator startup (all documents indexed automatically)
- Index tracking by `chunking_strategy` and `document_checksum` for clean management
- Hierarchical indexing with parent-child context
- Semantic search with configurable embedding models (Mistral, OpenAI, Azure)
- Persistent vector storage via ChromaDB
- Token-efficient context injection vs full document loading
- Integration with Excel orchestrator via `semantic_query` column
- Invoke tasks for index management (`index-status`, `index-clear`, `index-rebuild`)

**See:** [RAG_ARCHITECTURE.md](./RAG_ARCHITECTURE.md)

### Subsystem 5: Manifest Workflow
**Purpose:** Enable version control of prompt configurations and CI/CD integration by separating workbook parsing from execution.

**Key Components:**
- `WorkbookManifestExporter` - Convert Excel workbook to YAML manifest folder
- `ManifestOrchestrator` - Execute prompts from manifest and output to parquet

**Features:**
- YAML-based prompt version control
- Parquet output for analytics
- CI/CD-friendly command-line tools
- Same execution features as Excel Orchestrator (batch, multi-client, RAG, conditions)
- Reproducible execution with captured configuration

**See:** [MANIFEST_ARCHITECTURE.md](./MANIFEST_ARCHITECTURE.md)

## Subsystem Interaction

### Excel Orchestrator Flow
```
┌─────────────────────────────────────────────────────────────┐
│                   Excel Orchestrator                         │
│                                                              │
│   1. Load workbook (config + prompts + data + clients + docs)│
│   2. Validate dependencies                                   │
│   3. Resolve clients via ClientRegistry                      │
│   4. Initialize documents via DocumentRegistry               │
│   5. For each prompt (or batch iteration):                   │
│      └─► Inject document references                          │
│      └─► FFAI.generate_response(prompt, history=[...])      │
│   6. Write results to new sheet                              │
│                                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Uses
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                        FFAI                                  │
│                                                              │
│   - Assembles context from history names                    │
│   - Calls underlying client                                 │
│   - Manages ordered history                                 │
│                                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Delegates to
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Client (e.g., FFMistralSmall)            │
│                                                              │
│   - Formats messages for provider API                       │
│   - Makes API call                                          │
│   - Returns response                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Manifest Workflow Flow
```
┌─────────────────────────────────────────────────────────────┐
│                    Manifest Workflow                         │
│                                                              │
│   1. Export workbook to YAML manifest (WorkbookManifestExporter)│
│   2. Version control manifest folder                         │
│   3. Run from manifest (ManifestOrchestrator)               │
│   4. Same execution flow as Excel Orchestrator              │
│   5. Write results to parquet file                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**See:** [MANIFEST_ARCHITECTURE.md](./MANIFEST_ARCHITECTURE.md) for details.

### Client Resolution Flow
```
Prompt Definition (client column)
              │
              ▼
      ┌───────────────┐
      │ ClientRegistry│
      │  .get_client()│
      └───────┬───────┘
              │
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
Named client        Default client
 (e.g., "fast")     (from config)
    │                   │
    └─────────┬─────────┘
              │
              ▼
      Client instance
    (lazy instantiated)
```

## Directory Structure

```
FFClients/
├── src/
│   ├── __init__.py                    # Package exports
│   ├── FFAI.py                        # Core wrapper (BRIDGE between subsystems)
│   ├── FFAIClientBase.py              # Client ABC
│   ├── OrderedPromptHistory.py        # Named, queryable history
│   ├── PermanentHistory.py            # Chronological turn history
│   ├── ConversationHistory.py         # Simple turn management
│   │
│   ├── Clients/                       # SUBSYSTEM 1: Client Wrappers
│   │   ├── __init__.py
│   │   ├── FFLiteLLMClient.py         # Universal LiteLLM client (recommended)
│   │   ├── FFAzureLiteLLM.py          # Azure LiteLLM factory
│   │   ├── model_defaults.py          # Model-specific configuration defaults
│   │   ├── FFAzureClientBase.py       # Azure-specific ABC
│   │   ├── FFMistral.py
│   │   ├── FFMistralSmall.py
│   │   ├── FFAnthropic.py
│   │   ├── FFAnthropicCached.py
│   │   ├── FFGemini.py
│   │   ├── FFPerplexity.py
│   │   ├── FFOpenAIAssistant.py
│   │   ├── FFNvidiaDeepSeek.py
│   │   ├── FFAzureMistral.py
│   │   ├── FFAzureMistralSmall.py
│   │   ├── FFAzureCodestral.py
│   │   ├── FFAzureDeepSeek.py
│   │   ├── FFAzureDeepSeekV3.py
│   │   ├── FFAzureMSDeepSeekR1.py
│   │   └── FFAzurePhi.py
│   │
│   └── orchestrator/                  # SUBSYSTEM 2: Excel Orchestrator
│       ├── __init__.py
│       ├── excel_orchestrator.py      # Main orchestration engine
│       ├── workbook_builder.py        # Excel I/O and validation
│       ├── client_registry.py         # Client factory and registry
│       ├── document_processor.py      # Document parsing and caching
│       ├── document_registry.py       # Document lookup and injection
│       └── condition_evaluator.py     # Conditional expression evaluation
│   │
│   └── RAG/                           # SUBSYSTEM 4: RAG (Semantic Search)
│       ├── __init__.py
│       ├── FFRAGClient.py             # High-level RAG interface
│       ├── FFVectorStore.py           # ChromaDB operations
│       ├── FFEmbeddings.py            # LiteLLM embedding wrapper
│       ├── text_splitter.py           # DEPRECATED - backward compatibility
│       ├── mcp_tools.py               # MCP tool definitions
│       ├── text_splitters/            # Chunking strategies
│       │   ├── __init__.py
│       │   ├── base.py                # ChunkerBase, TextChunk, HierarchicalTextChunk
│       │   ├── character.py           # Word-boundary aware
│       │   ├── recursive.py           # Hierarchical separators
│       │   ├── markdown.py            # Header-aware
│       │   ├── code.py                # AST-style for code
│       │   ├── hierarchical.py        # Parent-child
│       │   └── factory.py             # get_chunker(), chunk_text()
│       ├── indexing/                  # Index implementations
│       │   ├── __init__.py
│       │   ├── bm25_index.py          # Sparse keyword index
│       │   ├── hierarchical_index.py  # Parent-child storage
│       │   └── contextual_embeddings.py
│       └── search/                    # Search strategies
│           ├── __init__.py
│           ├── hybrid_search.py       # Vector + BM25 fusion
│           └── rerankers.py           # Cross-encoder, diversity
│
├── scripts/
│   ├── run_orchestrator.py            # CLI entry point for orchestrator
│   ├── export_manifest.py             # Export workbook to YAML manifest
│   ├── run_manifest.py                # Run from manifest folder
│   ├── inspect_parquet.py             # Inspect parquet results
│   ├── sample_workbook_*_create_v001.py    # Workbook creation scripts
│   ├── sample_workbook_*_validate_v001.py  # Workbook validation scripts
│   ├── try_ai_mistralsmall_script.py  # Example usage script
│   └── validation/                   # Validation scripts
│       ├── __init__.py
│       ├── validate_all.py            # Validate all test workbook results
│       └── spot_check.py              # Spot check responses
│
├── tasks.py                            # Invoke task runner (Python-based Makefile alternative)
├── Makefile                            # GNU Make task runner
│
├── config/                            # Configuration files (pydantic-settings)
│   ├── main.yaml                      # Core app settings
│   ├── logging.yaml                   # Logging configuration
│   ├── paths.yaml                     # File system paths
│   ├── clients.yaml                   # AI client configurations
│   ├── model_defaults.yaml            # Per-model defaults
│   └── sample_workbook.yaml           # Sample workbook settings
│
├── logs/                              # Execution logs (git-ignored)
│   └── orchestrator.log               # Current log (rotates daily)
│
├── tests/
│   ├── conftest.py                    # Shared fixtures
│   ├── fixtures/                      # Test fixtures (documents, etc.)
│   │   └── documents/
│   ├── integration/                   # Integration tests
│   │   ├── conftest.py
│   │   ├── test_orchestrator_integration.py
│   │   ├── test_batch_integration.py
│   │   ├── test_multiclient_integration.py
│   │   ├── test_conditional_integration.py
│   │   ├── test_context_assembly.py
│   │   └── test_client_isolation.py
│   ├── test_ffai.py
│   ├── test_fflitellm_client.py
│   ├── test_ffmistral.py
│   ├── test_ffanthropic.py
│   ├── test_ffperplexity.py
│   ├── test_ffnvidia_deepseek.py
│   ├── test_ffazure_clients.py
│   ├── test_ffgemini.py
│   ├── test_ffopenai_assistant.py
│   ├── test_ordered_prompt_history.py
│   ├── test_permanent_history.py
│   ├── test_excel_orchestrator.py
│   ├── sample_workbook_builder.py
│   ├── test_client_registry.py
│   ├── test_document_processor.py
│   ├── test_document_registry.py
│   ├── test_condition_evaluator.py
│   ├── test_rag.py                     # RAG subsystem tests
│   ├── test_rag_chunkers.py            # Chunking strategy tests
│   ├── test_rag_indexing.py            # BM25, hierarchical index tests
│   ├── test_rag_search.py              # Hybrid search, reranker tests
│   └── test_litellm_orchestrator_integration.py
│
│   ├── chroma_db/                      # RAG vector database (git-ignored)
│
├── docs/
│   ├── architecture/
│   │   ├── ARCHITECTURE.md            # This file
│   │   ├── CLIENTS_ARCHITECTURE.md
│   │   ├── ORCHESTRATOR_ARCHITECTURE.md
│   │   ├── MANIFEST_ARCHITECTURE.md   # Manifest workflow architecture
│   │   ├── RAG_ARCHITECTURE.md        # RAG subsystem architecture
│   │   └── SHARED_HISTORY_DESIGN.md   # Shared history design doc
│   ├── designs/
│   ├── plans/
│   ├── readmes/
│   ├── CLIENT API USER GUIDE.md
│   ├── CONDITIONAL EXPRESSIONS USER GUIDE.md
│   ├── CONFIGURATION.md
│   └── ORCHESTRATOR README.md
│
├── pyproject.toml
├── requirements.txt
├── README.md
└── sample_orchestrator.xlsx
```

## Key Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| Abstract Base Class | `FFAIClientBase`, `FFAzureClientBase` | Define client contract |
| Facade | `FFAI` | Simplify client interaction, add context management |
| Builder | `WorkbookBuilder` | Construct Excel workbooks |
| Strategy | Client implementations | Interchangeable AI providers |
| Template Method | `FFAzureClientBase._initialize_client()` | Allow subclasses to customize |
| Registry | `ClientRegistry` | Lazy client instantiation, name-to-factory mapping |
| Singleton | `get_config()` | Global configuration instance |

## Data Flow

### Python API Flow
```
User Code
    │
    ▼
FFAI.generate_response(prompt, history=["math"])
    │
    ├──► Lookup "math" in OrderedPromptHistory
    │
    ├──► Assemble context string
    │
    ▼
Client.generate_response(prompt_with_context)
    │
    ├──► Format for provider API
    │
    ├──► Call external API
    │
    ▼
Response returned to user
```

### Excel Orchestrator Flow
```
Excel Workbook
    │
    ▼
WorkbookBuilder.load_prompts()
    │
    ▼
ExcelOrchestrator.run()
    │
    ├──► _build_execution_graph() ← Assign dependency levels
    │
    ├──► If concurrency > 1:
    │    │
    │    └──► execute_parallel()
    │         │
    │         ├──► ThreadPoolExecutor (max_workers=concurrency)
    │         │
    │         ├──► For each ready prompt (same level):
    │         │    │
    │         │    ├──► Clone client for isolation
    │         │    │
    │         │    ├──► Inject dependency context
    │         │    │
    │         │    └──► FFAI.generate_response()
    │         │              │
    │         │              └──► Client → API
    │         │
    │         └──► Collect results, update progress
    │
    ├──► Else (concurrency = 1):
    │    │
    │    └──► execute() ← Sequential execution
    │
    ▼
WorkbookBuilder.write_results()
    │
    ▼
Excel Workbook (with results sheet)
```

### Parallel Execution Data Flow
```
┌─────────────────────────────────────────────────────────────────┐
│                    ExecutionState (Shared)                       │
│                                                                  │
│  completed: Set[int]      ← Completed sequence numbers          │
│  in_progress: Set[int]    ← Currently running                   │
│  results_by_name: Dict    ← Results indexed by prompt_name      │
│  results_lock: Lock       ← Thread-safe access                  │
│                                                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
   ┌───────────┐       ┌───────────┐       ┌───────────┐
   │  Thread 1 │       │  Thread 2 │       │  Thread 3 │
   │           │       │           │       │           │
   │ Clone     │       │ Clone     │       │ Clone     │
   │ Client    │       │ Client    │       │ Client    │
   │           │       │           │       │           │
   │ Inject    │       │ Inject    │       │ Inject    │
   │ Deps      │       │ Deps      │       │ Deps      │
   │           │       │           │       │           │
   │ Execute   │       │ Execute   │       │ Execute   │
   │ Prompt    │       │ Prompt    │       │ Prompt    │
   └───────────┘       └───────────┘       └───────────┘
```

## Extension Points

### Adding a New Client
1. Create `src/Clients/FFNewProvider.py`
2. Inherit from `FFAIClientBase` (or `FFAzureClientBase` for Azure)
3. Implement required methods
4. Add to `src/Clients/__init__.py`
5. Register in `ClientRegistry._CLIENT_MAP` (for orchestrator use)
6. Add to CLI `CLIENT_MAP` in `scripts/run_orchestrator.py`
7. Add tests in `tests/test_ffnewprovider.py`

### Extending Orchestrator
1. Modify `WorkbookBuilder` for new sheet formats
2. Modify `ExcelOrchestrator` for new execution logic
3. Update `ClientRegistry` if new client configuration needed
4. Update tests

## Dependencies

```
FFAI
  ├── OrderedPromptHistory
  ├── PermanentHistory
  └── FFAIClientBase (protocol)

ExcelOrchestrator
  ├── FFAI (uses)
  ├── WorkbookBuilder
  ├── ClientRegistry
  ├── DocumentProcessor
  └── DocumentRegistry

ClientRegistry
  └── Client classes (imports lazily)

DocumentProcessor
  ├── polars (external)
  └── llama-parse (optional, for non-text files)

DocumentRegistry
  └── DocumentProcessor

FFRAGClient
├── FFVectorStore
│   ├── chromadb (external)
│   └── FFEmbeddings
│       └── litellm (external)
├── text_splitters (internal)
│   └── langchain-text-splitters (optional, for some strategies)
├── indexing (internal)
│   └── rank_bm25 (external, for BM25Index)
└── search (internal)
    └── sentence-transformers (optional, for cross-encoder reranking)

RAGMCPTools
└── FFRAGClient

WorkbookBuilder
  └── openpyxl (external)

FFLiteLLMClient (recommended)
  └── litellm (external)

FFMistral, FFMistralSmall
  └── mistralai (external)

FFAnthropic, FFAnthropicCached
  └── anthropic (external)

FFAzureClientBase
  ├── azure-ai-inference (external)
  └── azure-core (external)

FFGemini
  ├── google-auth (external)
  └── openai (external)

FFPerplexity, FFOpenAIAssistant, FFNvidiaDeepSeek
  └── openai (external)
```
