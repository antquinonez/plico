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
│         ┌────────────────────┼────────────────────┐                     │
│         │                    │                    │                      │
│         ▼                    ▼                    ▼                      │
│   ┌───────────┐      ┌─────────────┐      ┌─────────────┐              │
│   │  Mistral  │      │  Anthropic  │      │   OpenAI    │              │
│   │  Clients  │      │   Clients   │      │   Clients   │              │
│   └───────────┘      └─────────────┘      └─────────────┘              │
│                                                                          │
│   ┌───────────┐      ┌─────────────┐      ┌─────────────┐              │
│   │   Azure   │      │   Perplexity│      │   Gemini    │              │
│   │  Clients  │      │   Nvidia    │      │             │              │
│   └───────────┘      └─────────────┘      └─────────────┘              │
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

## Two Subsystems

### Subsystem 1: Client Wrappers
**Purpose:** Abstract away AI provider differences behind a unified interface.

**Key Components:**
- `FFAIClientBase` - Abstract base class defining the contract
- `FFMistral`, `FFAnthropic`, `FFPerplexity`, etc. - Concrete implementations
- `FFAzureClientBase` - Azure-specific base class (inherits from FFAIClientBase)

**Features:**
- Unified `generate_response()` interface
- Conversation history management
- `clone()` method for thread-safe parallel execution

**See:** [CLIENTS_ARCHITECTURE.md](./CLIENTS_ARCHITECTURE.md)

### Subsystem 2: Excel Orchestrator
**Purpose:** Enable non-programmers to define and execute AI prompt workflows.

**Key Components:**
- `ExcelOrchestrator` - Main orchestration engine with parallel execution
- `WorkbookBuilder` - Excel file creation, validation, and I/O
- `ClientRegistry` - Client factory and multi-client support

**Features:**
- Dependency-aware parallel execution
- Real-time progress indicator
- Configurable concurrency (default: 2, max: 10)
- Thread-safe client isolation
- Batch execution with variable templating
- Per-prompt client configuration

**See:** [ORCHESTRATOR_ARCHITECTURE.md](./ORCHESTRATOR_ARCHITECTURE.md)

## Subsystem Interaction

```
┌─────────────────────────────────────────────────────────────┐
│                   Excel Orchestrator                         │
│                                                              │
│   1. Load workbook (config + prompts + data + clients)      │
│   2. Validate dependencies                                   │
│   3. Resolve clients via ClientRegistry                      │
│   4. For each prompt (or batch iteration):                   │
│      └─► FFAI.generate_response(prompt, history=[...])      │
│   5. Write results to new sheet                              │
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
│       └── client_registry.py         # Client factory and registry
│
├── scripts/
│   ├── run_orchestrator.py            # CLI entry point for orchestrator
│   ├── create_test_workbook.py        # Generate test workbooks
│   ├── create_test_workbook_multiclient.py  # Multi-client test workbooks
│   └── try_ai_mistralsmall_script.py  # Example usage script
│
├── logs/                              # Execution logs (git-ignored)
│   └── orchestrator.log               # Current log (rotates daily)
│
├── tests/
│   ├── conftest.py                    # Shared fixtures
│   ├── test_ffai.py
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
│   ├── test_workbook_builder.py
│   └── test_client_registry.py
│
├── docs/
│   ├── architecture/
│   │   ├── ARCHITECTURE.md            # This file
│   │   ├── CLIENTS_ARCHITECTURE.md
│   │   └── ORCHESTRATOR_ARCHITECTURE.md
│   ├── designs/
│   ├── plans/
│   ├── CLIENT API USER GUIDE.md
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
  └── ClientRegistry

ClientRegistry
  └── Client classes (imports lazily)

WorkbookBuilder
  └── openpyxl (external)

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
