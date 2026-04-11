# Plico Architecture Overview

## System Context

Plico is a declarative AI orchestration framework. At its center is a **YAML manifest** — a machine-readable, version-controllable specification that defines what to ask, how prompts relate, what data to use, and which models to run.

**The manifest is the protocol.** How you create it is up to you:

1. **Excel (Human Authoring)** - Non-developers define workflows visually in spreadsheets, then export to manifest
2. **Python (Programmatic Generation)** - Generate manifests from data, databases, or other systems
3. **AI (Direct YAML Authoring)** - AI agents read, write, and modify manifests directly

Same manifest. Same execution engine. Same audit trail.

### Core Capabilities

- **Unified AI Client Interface** - Abstract away provider differences behind a consistent API (100+ providers via LiteLLM)
- **Declarative Context Management** - Reference previous prompts by name for automatic context assembly
- **Dependency-Aware Parallel Execution** - Automatic DAG construction with concurrent scheduling
- **Batch Processing** - Run workflows across multiple data inputs with `{{variable}}` templating
- **Per-Prompt Client Routing** - Route different prompts to different models
- **Conditional Execution** - AST-sandboxed expression language for branching without `eval()`
- **Document References & RAG** - Full document injection and semantic chunk retrieval
- **Analytics-Ready Output** - Timestamped Parquet files for downstream analysis

## High-Level Architecture

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
|   ManifestOrchestrator / ExcelOrchestrator                                                       |
|   +-- Executor (shared execution engine)                                                          |
|   +-- Dependency DAG construction (PromptNode)                                                    |
|   +-- Parallel scheduling (ThreadPoolExecutor)                                                   |
|   +-- Condition evaluation (AST-sandboxed)                                                       |
|   +-- Context assembly (declarative history)                                                     |
|   +-- Client isolation (clone pattern)                                                           |
|   +-- ExecutionState (thread-safe shared state)                                                  |
|   +-- ResultBuilder / PromptResult (structured results)                                          |
|                                                                                                  |
+------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+--------------------------------------------------------------------------------------------------+
|                                        FFAI CORE LAYER                                           |
|                                                                                                  |
|   FFAI.py                                                                                         |
|   +-- Declarative context assembly (history=["name1", "name2"])                                   |
|   +-- Named prompt management (OrderedPromptHistory)                                             |
|   +-- History persistence & DataFrame export                                                      |
|   +-- PermanentHistory (chronological turns)                                                     |
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

## Subsystems

### Subsystem 1: Client Wrappers
**Purpose:** Abstract away AI provider differences behind a unified interface.

**Key Components:**
- `FFAIClientBase` - Abstract base class defining the contract
- `FFLiteLLMClient` - Universal client supporting 100+ providers via LiteLLM (recommended)
- `FFMistral`, `FFAnthropic`, `FFPerplexity`, etc. - Provider-specific implementations
- `FFAzureClientBase` - Azure-specific base class (implements FFAIClientBase interface, inherits from ABC)
- `FFAzureLiteLLM` - Factory for creating Azure LiteLLM clients

**Features:**
- Unified `generate_response()` interface
- Conversation history management
- `clone()` method for thread-safe parallel execution
- Automatic fallback support (FFLiteLLMClient)
- Model-specific defaults for common configurations

**See:** [CLIENTS_ARCHITECTURE.md](./CLIENTS_ARCHITECTURE.md)

### Subsystem 2: Execution Engine
**Purpose:** Orchestrate prompt execution with dependency-aware scheduling, parallel execution, and multi-modal I/O.

**Key Components:**
- `OrchestratorBase` (ABC) - Shared base class for both orchestrators with `run()`, `_validate()`, `_init_client()`
- `ExcelOrchestrator` - Workbook-based orchestration engine (extends OrchestratorBase)
- `ManifestOrchestrator` - Manifest-based orchestration engine with parquet output (extends OrchestratorBase)
- `Executor` - Shared execution engine for both orchestrators (sequential, parallel, batch modes)
- `WorkbookParser` - Excel file creation, validation, and I/O
- `WorkbookFormatter` - Excel formatting utilities
- `ClientRegistry` - Client factory and multi-client support
- `DocumentProcessor` - Document parsing and checksum-based caching
- `DocumentRegistry` - Document lookup and reference injection
- `ConditionEvaluator` - AST-sandboxed conditional expression evaluation
- `OrchestratorValidator` - Startup validation with structured error reporting
- `ExecutionState` - Thread-safe shared state for parallel execution
- `PromptNode` - Dependency graph node with level assignment
- `PromptResult` / `ResultBuilder` - Structured result DTOs with fluent builder

**Features:**
- Dependency-aware parallel execution via `Executor`
- Real-time progress indicator
- Configurable concurrency (default: 2, max: 10)
- Thread-safe client isolation and shared history
- Batch execution with variable templating
- Per-prompt client configuration
- Document reference injection with LlamaParse support
- Conditional execution with expression-based prompt skipping
- Manifest export/import workflow for version control
- OrchestratorValidator for structured startup validation with ValidationError/ValidationResult

**See:** [ORCHESTRATOR_ARCHITECTURE.md](./ORCHESTRATOR_ARCHITECTURE.md)

### Subsystem 7: Agent Module
**Purpose:** Provide opt-in agentic tool-call execution within the deterministic DAG orchestrator.

**Key Components:**
- `AgentResult` - Dataclass capturing final response, tool call records, total rounds, total LLM calls
- `ToolCallRecord` - Dataclass for individual tool call results with duration and error tracking
- `AgentLoop` - Multi-round LLM loop that executes tool calls via ToolRegistry
- `ToolRegistry` - Registry of ToolDefinition objects with `builtin:` and `python:` implementations
- `builtin_tools` - 6 built-in tools: `calculate`, `json_extract`, `http_get`, `rag_search`, `read_document`, `list_documents`

**Features:**
- Opt-in via `agent_mode=true` column in prompts sheet
- Tools defined in dedicated `tools` sheet or inline via `tools` column
- Context-dependent tools (`rag_search`, `read_document`, `list_documents`) bound at runtime
- Configurable `max_tool_rounds`, `tool_timeout`, `continue_on_tool_error`
- Agent result properties accessible in condition expressions

**See:** [ORCHESTRATOR README.md](../ORCHESTRATOR%20README.md) for agent mode usage.

### Subsystem 8: Planning Phase
**Purpose:** Enable the orchestrator to derive scoring criteria and evaluation prompts from documents via LLM calls.

**Key Components:**
- `PlanningArtifactParser` - Parses generator prompt JSON responses with `json_repair`
- `GeneratedArtifact` - Dataclass holding scoring criteria and generated prompts
- Validation, merging, and sequence assignment for generated artifacts

**Features:**
- Generator prompts (`generator=true`) return structured JSON with `scoring_criteria` and `prompts`
- Planning prompts execute sequentially before batch execution
- Auto-derives `ScoringRubric` if no manual scoring sheet exists
- Generated prompts injected into execution with `_generated: true` tag

**See:** [ORCHESTRATOR README.md](../ORCHESTRATOR%20README.md) for planning phase usage.

### Subsystem 9: Evaluation Module (Scoring and Synthesis)
**Purpose:** Enable structured document evaluation workflows with score extraction, weighted aggregation, and cross-row comparison.

**Key Components:**
- `ScoringCriteria` - Dataclass for evaluation criteria definition
- `ScoringRubric` - Extracts scores from LLM JSON responses and computes composites
- `ScoreAggregator` - Aggregates scores across batch entries with strategy-based weight overrides
- `SynthesisExecutor` - Cross-row comparison and ranking with configurable scope

**Features:**
- `scoring` sheet defines criteria with scale, weight, and source prompt mapping
- `synthesis` sheet defines post-batch prompts for comparison/ranking
- Per-row document binding via `_documents` column in data sheet
- Result fields: `scores` (JSON), `composite_score`, `scoring_status`, `strategy`, `result_type`

**See:** [ORCHESTRATOR README.md](../ORCHESTRATOR%20README.md) for evaluation usage.

### Subsystem 10: Discovery Module
**Purpose:** Auto-discover documents from a folder and bootstrap evaluation workbooks.

**Key Components:**
- `discover_documents()` - Scans folders for supported file types
- `create_data_rows_from_documents()` - Generates batch data rows from discovered documents
- `create_evaluation_workbook()` - Creates complete `.xlsx` with all sheets

**Features:**
- Automatic document scanning (`.pdf`, `.docx`, `.txt`, `.md`, etc.)
- Shared document support (e.g., a job description for all rows)
- Integration with ExcelOrchestrator and ManifestOrchestrator via `documents_path`/`shared_document_path`
- Resume screening use case with dedicated invoke tasks

**See:** [ORCHESTRATOR README.md](../ORCHESTRATOR%20README.md) for discovery usage.

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

### Subsystem 6: Shared Execution Engine
**Purpose:** Provide a unified execution engine used by both `ExcelOrchestrator` and `ManifestOrchestrator`, eliminating duplicate code.

**Key Components:**
- `Executor` (`executor.py`) - Handles all four execution modes:
  - `execute_sequential()` - Sequential with dependency-aware ordering
  - `execute_parallel()` - Parallel via `ThreadPoolExecutor` with level-based scheduling
  - `execute_batch()` - Sequential batch execution with variable templating
  - `execute_batch_parallel()` - Parallel batch execution
- `ExecutionState` (`state/execution_state.py`) - Thread-safe tracking of completed, in-progress, pending prompts; results indexed by prompt_name
- `PromptNode` (`state/prompt_node.py`) - Dependency graph node with `is_ready()` and level assignment
- `PromptResult` (`results/result.py`) - 18-field dataclass for structured results with `to_dict()` / `from_dict()`
- `ResultBuilder` (`results/builder.py`) - Fluent builder for constructing `PromptResult` objects

**See:** [ORCHESTRATOR_ARCHITECTURE.md](./ORCHESTRATOR_ARCHITECTURE.md) for detailed data flows.

## Subsystem Interaction

### Execution Flow (shared by both orchestrators)
```
Workbook/Manifest
       │
       ▼
Orchestrator.run()
       │
       ├──► Parse and validate prompts
       │
       ├──► Resolve clients via ClientRegistry
       │
       ├──► Initialize documents via DocumentRegistry (with RAG pre-indexing)
       │
       ├──► Executor.execute_parallel() or execute_batch_parallel()
       │    │
       │    ├──► Build dependency DAG (PromptNode level assignment)
       │    │
       │    ├──► ThreadPoolExecutor (max_workers=concurrency)
       │    │
       │    ├──► For each ready prompt (same level):
       │    │    │
       │    │    ├──► Clone client for isolation
       │    │    │
       │    │    ├──► Inject dependency context + document references
       │    │    │
       │    │    ├──► Evaluate condition (AST-sandboxed)
       │    │    │
       │    │    ├──► FFAI.generate_response()
       │    │    │              │
       │    │    │              └──► Client → API
       │    │    │
       │    │    └──► ResultBuilder.build() → update ExecutionState
       │    │
       │    └──► Collect results, update progress
       │
       ▼
Results → Parquet (Manifest) or Excel sheet (Workbook)
```

### Three Authoring Paths

All three paths produce the same YAML manifest format:

```
Excel Workbook → manifest_export.py → Manifest Folder → ManifestOrchestrator → Parquet
Python Script                         → Manifest Folder → ManifestOrchestrator → Parquet
AI Agent      → (writes YAML directly) → Manifest Folder → ManifestOrchestrator → Parquet
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
Plico/
├── src/
│   ├── __init__.py                    # Package exports
│   ├── FFAI.py                        # Core wrapper (BRIDGE between subsystems)
│   ├── FFAIClientBase.py              # Client ABC
│   ├── retry_utils.py                 # Retry decorators, rate-limit handling (tenacity)
│   ├── config.py                      # Pydantic-based configuration management
│   ├── OrderedPromptHistory.py        # Named, queryable history
│   ├── PermanentHistory.py            # Chronological turn history
│   ├── ConversationHistory.py         # Simple turn management
│   │
│   ├── Clients/                       # SUBSYSTEM 1: Client Wrappers
│   │   ├── __init__.py
│   │   ├── FFLiteLLMClient.py         # Universal LiteLLM client (recommended)
│   │   ├── FFAzureLiteLLM.py          # Azure LiteLLM factory (create_azure_client)
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
│   ├── agent/                         # SUBSYSTEM 7: Agent (Agentic Tool-Call Loop)
│   │   ├── __init__.py                # Exports AgentResult, ToolCallRecord
│   │   ├── agent_result.py            # AgentResult, ToolCallRecord dataclasses
│   │   └── agent_loop.py              # Native agentic loop for tool-call execution
│   │
│   ├── orchestrator/                  # SUBSYSTEM 2: Execution Engine
│   │   ├── __init__.py
│   │   ├── base/                      # Base orchestrator class hierarchy
│   │   │   ├── __init__.py
│   │   │   └── orchestrator_base.py   #   OrchestratorBase ABC (shared run/init/validate)
│   │   ├── executor.py                # Shared execution engine (sequential/parallel/batch)
│   │   ├── excel_orchestrator.py      # Workbook-based orchestration
│   │   ├── manifest.py                # Manifest export/execution
│   │   ├── workbook_parser.py         # Excel I/O and validation
│   │   ├── workbook_formatter.py      # Excel formatting utilities
│   │   ├── client_registry.py         # Client factory and registry
│   │   ├── document_processor.py      # Document parsing and caching
│   │   ├── document_registry.py       # Document lookup and injection
│   │   ├── condition_evaluator.py     # AST-sandboxed conditional expression evaluation
│   │   ├── validation.py              # OrchestratorValidator, ValidationError, ValidationResult
│   │   ├── planning.py                # Planning phase (generator prompts, artifact parsing)
│   │   ├── scoring.py                 # Scoring rubric extraction and weighted aggregation
│   │   ├── synthesis.py               # Cross-row synthesis for ranking/comparison
│   │   ├── discovery.py               # Auto-discovery of documents for evaluation
│   │   ├── tool_registry.py           # Tool registration and execution for agent mode
│   │   ├── builtin_tools.py           # Built-in tool implementations
│   │   ├── state/                     # Execution state and dependency nodes
│   │   │   ├── __init__.py
│   │   │   ├── execution_state.py     #   Thread-safe ExecutionState dataclass
│   │   │   └── prompt_node.py         #   PromptNode with is_ready() and level assignment
│   │   └── results/                   # Result builders and DTOs
│   │       ├── __init__.py
│   │       ├── result.py              #   PromptResult dataclass (18+ fields)
│   │       └── builder.py             #   ResultBuilder fluent builder
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
│       │   ├── contextual_embeddings.py
│       │   └── deduplication.py       # Chunk deduplication
│       └── search/                    # Search strategies
│           ├── __init__.py
│           ├── hybrid_search.py       # Vector + BM25 fusion
│           ├── rerankers.py           # Cross-encoder, diversity
│           └── query_expansion.py     # Multi-query retrieval
│
├── scripts/
│   ├── run_orchestrator.py            # Execute workbook directly
│   ├── manifest_export.py             # Export workbook to YAML manifest
│   ├── manifest_run.py                # Run from manifest folder
│   ├── manifest_inspect.py            # Inspect/export parquet results
│   ├── manifest_extract.py            # Extract fields from parquet results
│   ├── parquet_to_excel.py            # Export parquet results to Excel workbook
│   ├── create_screening_workbook.py   # Create screening workbook from folder
│   ├── create_screening_manifest.py   # Create screening manifest (YAML) from folder
│   ├── sample_workbook_*_create_v001.py    # Workbook creation scripts
│   ├── sample_workbook_*_validate_v001.py  # Workbook validation scripts
│   ├── sample_workbooks/              # Shared workbook infrastructure
│   │   ├── __init__.py
│   │   ├── base.py                    #   PromptSpec, SectionDefinition, constants
│   │   ├── builders.py                #   Shared workbook builders
│   │   ├── validators.py              #   Shared validation utilities
│   │   ├── utils.py                   #   Shared utility functions
│   │   └── screening.py               #   Screening workbook helpers
│   ├── _shared/                       # Shared script utilities
│   │   ├── __init__.py
│   │   ├── client.py                  #   Client creation helpers
│   │   ├── logging.py                 #   Logging setup
│   │   └── progress.py                #   Progress indicator
│   ├── try_ai_mistralsmall_script.py  # Example usage script
│   └── validation/                   # Validation scripts
│       ├── __init__.py
│       ├── validate_all.py            # Validate all test workbook results
│       └── spot_check.py              # Spot check responses
│
├── tasks.py                            # Invoke task runner (recommended)
├── Makefile                            # GNU Make task runner (fallback)
│
├── config/                            # Configuration files (pydantic-settings)
│   ├── main.yaml                      # Core app settings
│   ├── logging.yaml                   # Logging configuration
│   ├── paths.yaml                     # File system paths
│   ├── clients.yaml                   # AI client configurations
│   ├── clients.yaml.example           # Example client config (safe to commit)
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
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_orchestrator_integration.py
│   │   ├── test_batch_integration.py
│   │   ├── test_multiclient_integration.py
│   │   ├── test_conditional_integration.py
│   │   ├── test_context_assembly.py
│   │   ├── test_client_isolation.py
│   │   ├── test_agent_integration.py
│   │   ├── test_ffgemini_parameters.py
│   │   └── test_ffmistralsmall_integration.py
│   ├── test_ffai.py
│   ├── test_config.py
│   ├── test_manifest.py
│   ├── test_manifest_comprehensive.py
│   ├── test_fflitellm_client.py
│   ├── test_ffmistral.py
│   ├── test_ffanthropic.py
│   ├── test_ffanthropic_cached.py
│   ├── test_ffperplexity.py
│   ├── test_ffnvidia_deepseek.py
│   ├── test_ffazure_clients.py
│   ├── test_ffazure_litellm.py
│   ├── test_ffaiclient_base.py
│   ├── test_ffgemini.py
│   ├── test_ffopenai_assistant.py
│   ├── test_retry_utils.py
│   ├── test_ordered_prompt_history.py
│   ├── test_permanent_history.py
│   ├── test_excel_orchestrator.py
│   ├── test_orchestrator_base.py
│   ├── test_workbook_parser.py
│   ├── test_client_registry.py
│   ├── test_document_processor.py
│   ├── test_document_registry.py
│   ├── test_condition_evaluator.py
│   ├── test_validation.py
│   ├── test_planning.py
│   ├── test_planning_artifact_parser.py
│   ├── test_scoring.py
│   ├── test_synthesis.py
│   ├── test_discovery.py
│   ├── test_discovery_injection.py
│   ├── test_agent.py
│   ├── test_builtin_tools.py
│   ├── test_results.py
│   ├── test_state.py
│   ├── test_rag.py                     # RAG subsystem tests
│   ├── test_rag_chunkers.py            # Chunking strategy tests
│   ├── test_rag_indexing.py            # BM25, hierarchical index tests
│   ├── test_rag_search.py              # Hybrid search, reranker tests
│   ├── test_rag_enhancements.py        # RAG enhancement tests
│   ├── test_text_splitter.py           # Legacy text splitter tests
│   └── test_litellm_orchestrator_integration.py
│
├── manifests/                          # Exported YAML manifests
├── outputs/                            # Parquet results
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
│   ├── ORCHESTRATOR README.md
│   └── TEST_COVERAGE.md
│
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Key Design Patterns

| Pattern | Location | Purpose |
|---------|----------|---------|
| Abstract Base Class | `FFAIClientBase`, `FFAzureClientBase`, `OrchestratorBase` | Define client/orchestrator contract |
| Facade | `FFAI` | Simplify client interaction, add context management |
| Builder | `WorkbookParser`, `ResultBuilder` | Construct Excel workbooks, build result DTOs |
| Strategy | Client implementations | Interchangeable AI providers |
| Template Method | `FFAzureClientBase._initialize_client()` | Allow subclasses to customize |
| Registry | `ClientRegistry`, `ToolRegistry` | Lazy client/tool instantiation, name-to-factory mapping |
| Singleton | `get_config()` | Global configuration instance |
| Clone | All clients | Thread-safe isolated instances for parallel execution |

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

### Orchestrator Data Flow
```
Workbook or Manifest
    │
    ▼
WorkbookParser.load_prompts() or ManifestOrchestrator._load_manifest()
    │
    ▼
Orchestrator.run()
    │
    ├──► Executor.execute_parallel() or execute_batch_parallel()
    │    │
    │    ├──► _build_execution_graph() ← PromptNode level assignment
    │    │
    │    ├──► ThreadPoolExecutor (max_workers=concurrency)
    │    │
    │    ├──► For each ready prompt (same level):
    │    │    │
    │    │    ├──► Clone client for isolation
    │    │    │
    │    │    ├──► Inject dependency context + document references
    │    │    │
    │    │    ├──► Evaluate condition (if present)
    │    │    │
    │    │    ├──► FFAI.generate_response()
    │    │    │              │
    │    │    │              └──► Client → API
    │    │    │
    │    │    └──► ResultBuilder.build() → update ExecutionState
    │    │
    │    └──► Collect results, update progress
    │
    ▼
Parquet (Manifest) or Excel sheet (Workbook)
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
1. Modify `WorkbookParser` for new sheet formats
2. Modify `ExcelOrchestrator` for new execution logic
3. Update `ClientRegistry` if new client configuration needed
4. Update tests

## Dependencies

```
FFAI
  ├── OrderedPromptHistory
  ├── PermanentHistory
  └── FFAIClientBase (protocol)

Executor (shared by both orchestrators)
  ├── ExecutionState
  ├── PromptNode
  ├── ResultBuilder
  ├── PromptResult
  └── ConditionEvaluator (for condition evaluation)

ExcelOrchestrator
  ├── OrchestratorBase (extends)
  ├── FFAI (uses)
  ├── Executor (delegates to)
  ├── WorkbookParser
  ├── ClientRegistry
  ├── DocumentProcessor
  ├── DocumentRegistry
  ├── ToolRegistry (agent mode)
  ├── DiscoveryModule (auto-discovery)

ManifestOrchestrator
  ├── OrchestratorBase (extends)
  ├── FFAI (uses)
  ├── Executor (delegates to)
  ├── ClientRegistry
  ├── DocumentProcessor
  ├── DocumentRegistry
  ├── ToolRegistry (agent mode)
  ├── DiscoveryModule (auto-discovery)
  └── polars (external, parquet output)

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

WorkbookParser
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
