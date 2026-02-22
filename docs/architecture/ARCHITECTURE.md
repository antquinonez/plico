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

**See:** [CLIENTS_ARCHITECTURE.md](./CLIENTS_ARCHITECTURE.md)

### Subsystem 2: Excel Orchestrator
**Purpose:** Enable non-programmers to define and execute AI prompt workflows.

**Key Components:**
- `ExcelOrchestrator` - Main orchestration engine
- `WorkbookBuilder` - Excel file creation, validation, and I/O

**See:** [ORCHESTRATOR_ARCHITECTURE.md](./ORCHESTRATOR_ARCHITECTURE.md)

## Subsystem Interaction

```
┌─────────────────────────────────────────────────────────────┐
│                   Excel Orchestrator                         │
│                                                              │
│   1. Load workbook (config + prompts sheets)                │
│   2. Validate dependencies                                   │
│   3. For each prompt:                                        │
│      └─► FFAI.generate_response(prompt, history=[...])      │
│   4. Write results to new sheet                              │
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
│       └── workbook_builder.py        # Excel I/O and validation
│
├── scripts/
│   ├── run_orchestrator.py            # CLI entry point for orchestrator
│   └── try_ai_mistralsmall_script.py  # Example usage script
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
│   └── test_workbook_builder.py
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
    ├──► For each prompt (sequential):
    │    │
    │    ├──► FFAI.generate_response()
    │    │         │
    │    │         └──► Client → API
    │    │
    │    └──► Store result
    │
    ▼
WorkbookBuilder.write_results()
    │
    ▼
Excel Workbook (with results sheet)
```

## Extension Points

### Adding a New Client
1. Create `src/Clients/FFNewProvider.py`
2. Inherit from `FFAIClientBase` (or `FFAzureClientBase` for Azure)
3. Implement required methods
4. Add to `src/Clients/__init__.py`
5. Add tests in `tests/test_ffnewprovider.py`

### Extending Orchestrator
1. Modify `WorkbookBuilder` for new sheet formats
2. Modify `ExcelOrchestrator` for new execution logic
3. Update tests

## Dependencies

```
FFAI
  ├── OrderedPromptHistory
  ├── PermanentHistory
  └── FFAIClientBase (protocol)

ExcelOrchestrator
  ├── FFAI (uses)
  └── WorkbookBuilder

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
