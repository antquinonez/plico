# LiteLLM Integration Analysis

## Executive Summary

This document analyzes the feasibility and approach for integrating LiteLLM as the underlying client layer for Plico, replacing the current hand-maintained client wrappers while preserving Plico' unique value-adds: declarative context management, multiple history tracking, and Excel-based orchestration.

---

## Current Architecture Analysis

### 1. Client Layer Hierarchy

```
FFAIClientBase (ABC)
├── Direct API Clients
│   ├── FFMistral / FFMistralSmall
│   ├── FFAnthropic / FFAnthropicCached
│   ├── FFGemini
│   ├── FFPerplexity
│   └── FFNvidiaDeepSeek
│
├── FFAzureClientBase (ABC)
│   ├── FFAzureMistral / FFAzureMistralSmall
│   ├── FFAzureCodestral
│   ├── FFAzureDeepSeek / FFAzureDeepSeekV3
│   ├── FFAzureMSDeepSeekR1
│   └── FFAzurePhi
│
└── Special Clients
    └── FFOpenAIAssistant
```

### 2. FFAIClientBase Contract

```python
class FFAIClientBase(ABC):
    model: str
    system_instructions: str

    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> str

    @abstractmethod
    def clear_conversation(self) -> None

    @abstractmethod
    def get_conversation_history(self) -> list[dict]

    @abstractmethod
    def set_conversation_history(self, history: list[dict]) -> None

    @abstractmethod
    def clone(self) -> "FFAIClientBase"
```

### 3. FFAI Wrapper Value-Adds

The FFAI class wraps any FFAIClientBase and provides:

| Feature | Implementation | Complexity |
|---------|---------------|------------|
| **Declarative Context** | `_build_prompt()` assembles history by name | High |
| **Multiple History Types** | 6 different history tracking mechanisms | High |
| **Thread-Safe History** | Lock-based synchronization for parallel execution | Medium |
| **JSON Extraction** | `_extract_json()` with markdown support | Medium |
| **Response Cleaning** | Think tag removal, attribute extraction | Low |
| **DataFrame Export** | Polars conversion with datetime handling | Medium |
| **Auto-Persistence** | Parquet file output | Low |

### 4. History Management Architecture

```
FFAI
├── history: list[dict]              # Raw interactions
├── clean_history: list[dict]        # Cleaned interactions
├── prompt_attr_history: list[dict]  # JSON attribute extraction (thread-safe)
├── permanent_history: PermanentHistory  # Chronological turns
├── ordered_history: OrderedPromptHistory  # Named, sequenced
└── named_prompt_ordered_history: OrderedPromptHistory
```

**Key insight:** History management is entirely within FFAI, not the client layer. The client only maintains `conversation_history` for the provider's API format.

---

## LiteLLM Capabilities Analysis

### What LiteLLM Provides

| Feature | LiteLLM | Plico Current |
|---------|---------|-------------------|
| Provider count | 100+ | 15 (manual) |
| Unified API | `completion()` | Per-provider classes |
| Model routing | `model="provider/model"` | Per-client instantiation |
| Retries | Built-in exponential backoff | None |
| Fallbacks | Model A → Model B | None |
| Rate limiting | Built-in | None |
| Cost tracking | Built-in | None |
| Streaming | Yes | No |
| Async | Yes | Partial (FFGemini) |
| Tool calling | Unified interface | Per-client implementation |

### LiteLLM Model String Format

```python
# LiteLLM uses model strings for routing
completion(model="openai/gpt-4", ...)
completion(model="anthropic/claude-3-opus-20240229", ...)
completion(model="azure/azure-deployment-name", ...)
completion(model="mistral/mistral-large-latest", ...)
completion(model="gemini/gemini-pro", ...)
completion(model="perplexity/llama-3.1-sonar-large-128k-online", ...)
```

### LiteLLM Conversation Format

```python
# LiteLLM uses standard OpenAI format
messages = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
]
response = completion(model="...", messages=messages)
```

---

## Gap Analysis

### What Plico Has That LiteLLM Lacks

| Feature | Impact if Lost |
|---------|----------------|
| **Clone pattern** | Critical - required for parallel execution |
| **Conversation history get/set** | High - FFAI manages history, needs to inject |
| **Azure deployment endpoint mode** | Medium - specific Azure configuration |
| **Per-client default properties** | Low - can be moved to FFAI |
| **System instructions per-client** | Low - FFAI handles this |

### What LiteLLM Has That Plico Lacks

| Feature | Benefit |
|---------|---------|
| Automatic provider support | Zero maintenance for new models |
| Built-in retries | More reliable execution |
| Fallbacks | Graceful degradation |
| Cost tracking | Usage analytics |
| Streaming | Real-time output |

---

## Integration Approaches

### Option A: Full Replacement

Replace all client wrappers with a single `FFLiteLLMClient`.

**Pros:**
- Minimal code to maintain
- All LiteLLM benefits

**Cons:**
- Loses per-client optimizations
- Azure deployment endpoint complexity
- Must handle all edge cases in one place

### Option B: Hybrid - LiteLLM as Base Client

Create `FFLiteLLMClient` implementing FFAIClientBase, keep existing clients for edge cases.

**Pros:**
- Gradual migration
- Best of both worlds
- Can deprecate clients over time

**Cons:**
- Two code paths to maintain temporarily
- More complex testing

### Option C: LiteLLM as Provider Adapter (Recommended)

Create a translation layer that maps Plico patterns to LiteLLM calls while preserving the FFAIClientBase contract.

**Pros:**
- Preserves existing architecture
- FFAI unchanged
- Existing clients can coexist

**Cons:**
- Additional abstraction layer

---

## Key Integration Challenges

### 1. Clone Pattern

**Current:**
```python
def clone(self) -> "FFMistralSmall":
    return FFMistralSmall(
        api_key=self.api_key,
        model=self.model,
        temperature=self.temperature,
        ...
    )
```

**LiteLLM Challenge:** LiteLLM doesn't have a stateful client object to clone.

**Solution:** Clone becomes configuration cloning, not client cloning:
```python
def clone(self) -> "FFLiteLLMClient":
    return FFLiteLLMClient(
        model_string=self.model_string,
        config=self._config.copy(),
    )
```

### 2. Conversation History

**Current:** Client maintains `conversation_history` list.

**LiteLLM:** Stateless - messages passed on each call.

**Solution:** FFLiteLLMClient maintains its own history, passes to LiteLLM on each call:
```python
def generate_response(self, prompt: str, **kwargs) -> str:
    self.conversation_history.append({"role": "user", "content": prompt})
    messages = self._build_messages()  # system + history
    response = completion(model=self.model_string, messages=messages, **kwargs)
    self.conversation_history.append({"role": "assistant", "content": response})
    return response
```

### 3. Azure Deployment Endpoints

**Current:** Special handling for Azure deployment endpoints with URL construction.

**LiteLLM:** Uses `azure/deployment-name` format with `api_base`.

**Solution:** Map Azure clients to LiteLLM format:
```python
# FFAzureMistralSmall config
model_string = "azure/mistral-small-2503"
api_base = os.getenv("AZURE_MISTRALSMALL_ENDPOINT")
api_key = os.getenv("AZURE_MISTRALSMALL_KEY")
api_version = "2024-02-01"
```

### 4. Model-Specific Defaults

**Current:** Each client has `_default_model`, `_default_temperature`, etc.

**Solution:** Create a model defaults registry:
```python
MODEL_DEFAULTS = {
    "mistral-small-2503": {"max_tokens": 40000, "temperature": 0.7},
    "claude-3-opus-20240229": {"max_tokens": 4096, "temperature": 0.7},
    ...
}
```

---

## Recommended Approach: Option C

Create `FFLiteLLMClient` that:

1. **Implements FFAIClientBase contract** - Drop-in replacement
2. **Maintains internal conversation history** - Supports get/set/clone
3. **Translates to LiteLLM format** - Model string routing
4. **Preserves model defaults** - Via registry or config
5. **Works with FFAI unchanged** - No modifications to FFAI.py

This allows:
- Gradual migration (replace one client at a time)
- Coexistence (FFOpenAIAssistant stays separate)
- Testing parity (same test suite works)
- Zero changes to FFAI or orchestration layer
