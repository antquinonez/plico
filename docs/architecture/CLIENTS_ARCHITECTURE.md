# Client Wrappers Subsystem Architecture

## Overview

The Client Wrappers subsystem provides a unified interface to multiple AI providers, abstracting away provider-specific API differences while adding powerful context management capabilities.

## Design Goals

1. **Provider Agnostic** - Same API regardless of underlying AI model
2. **Extensible** - Easy to add new providers
3. **Type Safe** - Abstract base class enforces contract
4. **Testable** - Mockable interface for testing

## Class Hierarchy

### Active Clients

```
                    FFAIClientBase (ABC, in src/core/client_base.py)
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌───────────┐ ┌─────────────┐
    │  FFMistral  │ │ FFGemini  │ │FFPerplexity │
    │FFMistralSmall│ │           │ │             │
    └─────────────┘ └───────────┘ └─────────────┘
    ┌─────────────────┐
    │ FFLiteLLMClient │
    │ (Universal)     │
    └─────────────────┘
```

### Archived Clients (`src/Clients/not_maintained/`)

These clients are no longer actively maintained. They lack token usage tracking, cost estimation, and OTel span integration. They are not exported from `src/Clients/__init__.py`.

```
                    FFAIClientBase (ABC)
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌───────────┐ ┌──────────────┐
    │ FFAnthropic │ │FFNvidia   │ │FFOpenAI      │
    │FFAnthropic  │ │DeepSeek   │ │Assistant     │
    │  Cached     │ │           │ │              │
    └─────────────┘ └───────────┘ └──────────────┘

                    FFAzureClientBase (ABC)
                    [Implements FFAIClientBase interface]
                           │
     ┌───────┬───────┬─────┴─────┬───────────┬────────────┬──────────┐
     │       │       │           │           │            │          │
     ▼       ▼       ▼           ▼           ▼            ▼          ▼
 ┌───────┐┌───────┐┌───────┐┌──────────┐┌───────────┐┌─────────┐┌──────┐
 │FFAzure││FFAzure││FFAzure││FFAzure   ││FFAzure    ││FFAzure  ││FFAzure│
 │Mistral││Mistral││Code-  ││DeepSeek  ││DeepSeekV3 ││MSDeep   ││Phi   │
 │       ││Small  ││stral  ││          ││           ││SeekR1   ││      │
 └───────┘└───────┘└───────┘└──────────┘└───────────┘└─────────┘└──────┘
```

## FFAIClientBase Contract

Located in `src/core/client_base.py`. A compatibility shim at `src/FFAIClientBase.py` re-exports for backward compatibility.

```python
class FFAIClientBase(ABC):
    """Abstract base class defining the client interface."""

    # Required attributes
    model: str
    system_instructions: str

    # Token tracking (class-level defaults)
    _last_usage: TokenUsage | None = None
    _last_cost_usd: float = 0.0

    # Required methods
    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the AI model."""
        pass

    @abstractmethod
    def clear_conversation(self) -> None:
        """Clear conversation history."""
        pass

    @abstractmethod
    def get_conversation_history(self) -> list:
        """Get current conversation history."""
        pass

    @abstractmethod
    def set_conversation_history(self, history: list) -> None:
        """Set conversation history."""
        pass

    @abstractmethod
    def clone(self) -> "FFAIClientBase":
        """Create a fresh clone with empty history for thread-safe parallel execution."""
        pass

    # Token tracking methods (provided by base class)
    @property
    def last_usage(self) -> TokenUsage | None:
        """Token counts from the last generate_response() call."""

    @property
    def last_cost_usd(self) -> float:
        """Estimated cost in USD from the last generate_response() call."""

    def _reset_usage(self) -> None:
        """Reset usage tracking before each API call."""

    def _extract_token_usage(self, response, model: str) -> None:
        """Extract token usage from provider response and estimate cost."""

    def _trace_llm_call(self, prompt_name: str | None = None) -> ContextManager:
        """Context manager for OTel span emission (NoOpSpan when disabled)."""
```

### Clone Method Implementation

Each client must implement `clone()` to support parallel execution:

```python
class FFMistralSmall(FFAIClientBase):
    def clone(self) -> "FFMistralSmall":
        """Create a fresh clone with empty history."""
        return FFMistralSmall(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            system_instructions=self.system_instructions,
        )
```

**Why Clone?**
- Parallel execution requires isolated client state per thread
- Each prompt execution needs clean conversation history
- Dependency context is injected per-execution, not accumulated

## Client Categories

### 1. LiteLLM Universal Client (Recommended)

Universal client supporting 100+ LLM providers through the LiteLLM library.

| Client | Providers | Library | Features |
|--------|-----------|---------|----------|
| `FFLiteLLMClient` | Azure, OpenAI, Anthropic, Mistral, Gemini, Perplexity, 100+ | `litellm` | Fallbacks, unified interface, model defaults |

```python
from src.Clients.FFLiteLLMClient import FFLiteLLMClient

# Works with any LiteLLM-supported provider
client = FFLiteLLMClient(
    model_string="azure/mistral-small-2503",  # or "anthropic/claude-3-5-sonnet", "openai/gpt-4o"
    api_key="...",
    api_base="...",  # For Azure
    fallbacks=["openai/gpt-4"],  # Automatic fallback
)
```

**Model String Format:** `{provider}/{model}`
- `azure/{deployment_name}` - Azure OpenAI
- `openai/{model}` - OpenAI API
- `anthropic/{model}` - Anthropic API
- `mistral/{model}` - Mistral API
- `gemini/{model}` - Google Gemini
- `perplexity/{model}` - Perplexity API
- `nvidia_nim/{model}` - Nvidia NIM

### Manifest clients.yaml Fields

When using multi-client routing via manifests (or the `clients` sheet in workbooks), these additional fields are available:

| Field | Type | Description |
|-------|------|-------------|
| `api_base` | `str` | API base URL override (LiteLLM clients only) |
| `api_version` | `str` | API version override (LiteLLM clients only) |
| `fallbacks` | `list` | Fallback model configurations (LiteLLM clients only) |
| `system_instructions` | `str` | System prompt override |

Example in `clients.yaml`:
```yaml
clients:
  - name: smart
    client_type: litellm-anthropic
    model: claude-3-5-sonnet-20241022
    api_base: "https://my-proxy.example.com"
    fallbacks: ["openai/gpt-4o"]
    system_instructions: "You are a helpful assistant."
```

### 2. Direct API Clients (Active)

| Client | Provider | Library | Auth |
|--------|----------|---------|------|
| `FFMistral` | Mistral AI | `mistralai` | API Key |
| `FFMistralSmall` | Mistral AI | `mistralai` | API Key |
| `FFGemini` | Google | `openai` + `google-auth` | OAuth |
| `FFPerplexity` | Perplexity | `openai` | API Key |

### 2b. Direct API Clients (Archived, in `not_maintained/`)

These clients are archived and lack token usage tracking and cost estimation.

| Client | Provider | Library |
|--------|----------|---------|
| `FFAnthropic` | Anthropic | `anthropic` |
| `FFAnthropicCached` | Anthropic | `anthropic` |
| `FFNvidiaDeepSeek` | Nvidia NIM | `openai` |
| `FFOpenAIAssistant` | OpenAI | `openai` |

### 3. Azure AI Clients (Archived, in `not_maintained/`)

These clients are archived and lack token usage tracking. They remain available for legacy use but are not exported from `src/Clients/__init__.py`.

| Client | Model | Base Class |
|--------|-------|------------|
| `FFAzureMistral` | Mistral Large | `FFAzureClientBase` |
| `FFAzureMistralSmall` | Mistral Small | `FFAzureClientBase` |
| `FFAzureCodestral` | Codestral | `FFAzureClientBase` |
| `FFAzureDeepSeek` | DeepSeek R1 | - (standalone) |
| `FFAzureDeepSeekV3` | DeepSeek V3 | `FFAzureClientBase` |
| `FFAzureMSDeepSeekR1` | MAI-DS-R1 | - (standalone) |
| `FFAzurePhi` | Phi-4 | `FFAzureClientBase` |

### 4. Azure LiteLLM Factory (Archived, in `not_maintained/`)

Factory function for creating Azure clients with environment-based configuration. Archived alongside other Azure clients.

```python
from src.Clients import create_azure_client

# Creates FFLiteLLMClient configured for Azure
client = create_azure_client(
    deployment_name="mistral-small-2503",
    env_prefix="AZURE_MISTRALSMALL",  # Uses AZURE_MISTRALSMALL_KEY, AZURE_MISTRALSMALL_ENDPOINT
)

# With optional overrides
client = create_azure_client(
    deployment_name="gpt-4o",
    env_prefix="AZURE_OPENAI",
    system_instructions="You are a helpful assistant.",
    temperature=0.7,
    max_tokens=4096,
)
```

The factory reads from environment variables:
- `{env_prefix}_KEY` - API key
- `{env_prefix}_ENDPOINT` - API base endpoint
- `{env_prefix}_API_VERSION` - API version (defaults to `"2024-02-01"`)

**Module:** `src/Clients/FFAzureLiteLLM.py`

### 5. Special Clients (Archived, in `not_maintained/`)

| Client | Purpose |
|--------|---------|
| `FFOpenAIAssistant` | Uses OpenAI Assistant API (threads, runs) |

## FFAzureClientBase Design

> **Note:** `FFAzureClientBase` and all Azure clients are archived in `src/Clients/not_maintained/`. They lack token usage tracking and cost estimation. This section is preserved for reference.

Azure clients share significant common code. `FFAzureClientBase` is an ABC that inherits directly from `ABC` (not `FFAIClientBase`) but implements the same interface contract:

```python
class FFAzureClientBase(ABC):
    """Base class for Azure AI Inference clients."""

    # Abstract properties for configuration
    @property
    @abstractmethod
    def _default_model(self) -> str: pass

    @property
    @abstractmethod
    def _default_max_tokens(self) -> int: pass

    @property
    @abstractmethod
    def _default_temperature(self) -> float: pass

    @property
    @abstractmethod
    def _default_instructions(self) -> str: pass

    @property
    @abstractmethod
    def _env_key_prefix(self) -> str: pass  # e.g., "AZURE_MISTRAL"

    # Common implementation (implements FFAIClientBase interface)
    def generate_response(self, prompt, **kwargs) -> str:
        # Full implementation shared by all Azure clients
        ...

    def clear_conversation(self) -> None: ...
    def get_conversation_history(self) -> list: ...
    def set_conversation_history(self, history: list) -> None: ...
    # Note: clone() not implemented - Azure clients have their own parallel execution strategy
```

### Concrete Azure Client Example

```python
class FFAzureMistral(FFAzureClientBase):
    """Azure AI Inference client for Mistral Large models."""

    @property
    def _default_model(self) -> str:
        return "mistral-large-2411"

    @property
    def _default_max_tokens(self) -> int:
        return 40000

    @property
    def _default_temperature(self) -> float:
        return 0.7

    @property
    def _default_instructions(self) -> str:
        return "You are a helpful assistant..."

    @property
    def _env_key_prefix(self) -> str:
        return "AZURE_MISTRAL"

    @property
    def _provider_name(self) -> str:
        return "MistralAI"
```

## Token Usage & Cost Tracking

All **active clients** (`FFMistral`, `FFMistralSmall`, `FFGemini`, `FFPerplexity`, `FFLiteLLMClient`) automatically track token usage and estimate costs after each `generate_response()` call.

### TokenUsage Dataclass

```python
from src.core.usage import TokenUsage

usage = TokenUsage(input_tokens=50, output_tokens=25, total_tokens=75)
```

| Field | Type | Description |
|-------|------|-------------|
| `input_tokens` | `int` | Tokens in the prompt |
| `output_tokens` | `int` | Tokens in the response |
| `total_tokens` | `int` | Sum of input + output |

### Cost Estimation

| Client | Cost Method | Source |
|--------|-------------|--------|
| `FFMistral`, `FFMistralSmall` | `pricing.estimate_cost()` | Static `PRICING_TABLE` in `src/core/pricing.py` |
| `FFGemini`, `FFPerplexity` | `pricing.estimate_cost()` | Static `PRICING_TABLE` in `src/core/pricing.py` |
| `FFLiteLLMClient` | `litellm.completion_cost()` | Live pricing from LiteLLM |

### Usage After API Call

```python
client = FFMistralSmall(api_key="...")
client.generate_response("Hello!")

print(client.last_usage)       # TokenUsage(input_tokens=50, output_tokens=25, total_tokens=75)
print(f"${client.last_cost_usd:.6f}")  # $0.000011
```

### FFAI Integration

`FFAI.generate_response()` returns a `ResponseResult` dataclass that includes usage and cost:

```python
from src.FFAI import FFAI

ffai = FFAI(client)
result = ffai.generate_response("Hello!")
print(result.response)     # The text response
print(result.usage)        # TokenUsage or None
print(result.cost_usd)     # Estimated cost
print(result.duration_ms)  # Wall-clock duration
```

### Architecture

```
generate_response() called
        │
        ▼
  _reset_usage()  ← Sets _last_usage=None, _last_cost_usd=0.0
        │
        ▼
  Provider API call
        │
        ▼
  _extract_token_usage(response, model)  ← For native clients
  OR _extract_usage(response)            ← For FFLiteLLMClient
        │
        ├──► TokenUsage(input, output, total)
        └──► estimate_cost() or litellm.completion_cost()
        │
        ▼
  FFAI wraps in ResponseResult
```

## Message Format Conversion

Each client converts from internal format to provider format:

```
Internal Format (dict):
{
    "role": "user",
    "content": "Hello"
}

Anthropic Format:
{"role": "user", "content": "Hello"}

Mistral/OpenAI Format:
{"role": "user", "content": "Hello"}

Azure Format:
UserMessage(content="Hello")
```

## Configuration Flow

```
1. Constructor called with kwargs/config
        │
        ▼
2. Merge with environment variables
        │
        ▼
3. Apply defaults for missing values
        │
        ▼
4. Initialize provider client
        │
        ▼
5. Ready for use
```

### Configuration Priority

1. **kwargs** (highest)
2. **config dict**
3. **environment variables**
4. **class defaults** (lowest)

### Environment Variables

Each client follows the pattern: `{PREFIX}_{SETTING}`

| Client | Key Env Var | Model Env Var | Temp Env Var |
|--------|-------------|---------------|--------------|
| FFMistral | `MISTRAL_API_KEY` | `MISTRAL_MODEL` | `MISTRAL_TEMPERATURE` |
| FFAnthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` | `ANTHROPIC_TEMPERATURE` |
| FFAzureMistral | `AZURE_MISTRAL_KEY` | `AZURE_MISTRAL_MODEL` | `AZURE_MISTRAL_TEMPERATURE` |
| FFPerplexity | `PERPLEXITY_TOKEN` | `PERPLEXITY_MODEL` | `PERPLEXITY_TEMPERATURE` |

## Error Handling Pattern

```python
def generate_response(self, prompt: str, **kwargs) -> str:
    try:
        # Validate input
        if not prompt.strip():
            raise ValueError("Empty prompt provided")

        # Make API call
        response = self.client.some_api_call(...)

        # Process response
        return response.content

    except ProviderSpecificError as e:
        # Handle provider-specific errors
        logger.error(f"Provider error: {e}")
        raise RuntimeError(f"Error from {provider}: {e}")

    except Exception as e:
        # Catch-all
        logger.error(f"Unexpected error: {e}")
        raise RuntimeError(f"Error generating response: {e}")
```

## Adding a New Client

### Step 1: Create the Client File

```python
# src/Clients/FFNewProvider.py

import os
import logging
from typing import Any

from ..FFAIClientBase import FFAIClientBase

logger = logging.getLogger(__name__)

class FFNewProvider(FFAIClientBase):
    def __init__(self, config: dict[str, Any] | None = None, **kwargs):
        # 1. Define defaults
        defaults = {
            'model': "default-model",
            'max_tokens': 4096,
            'temperature': 0.7,
            'instructions': "You are a helpful assistant."
        }

        # 2. Merge config sources
        all_config = {**(config or {}), **kwargs}

        # 3. Extract configuration
        self.api_key = all_config.get('api_key', os.getenv('NEWPROVIDER_KEY'))
        self.model = all_config.get('model', os.getenv('NEWPROVIDER_MODEL', defaults['model']))
        # ... etc

        # 4. Initialize client
        self.conversation_history: list[dict[str, str]] = []
        self.client = self._initialize_client()

    def _initialize_client(self):
        """Initialize the provider's SDK client."""
        if not self.api_key:
            raise ValueError("API key not found")
        return ProviderSDK(api_key=self.api_key)

    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response."""
        if not prompt.strip():
            raise ValueError("Empty prompt")

        try:
            self._reset_usage()  # Reset token tracking
            self.conversation_history.append({"role": "user", "content": prompt})

            response = self.client.generate(
                messages=self.conversation_history,
                model=self.model,
                **kwargs
            )

            assistant_response = response.text
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            # Extract token usage and estimate cost
            self._extract_token_usage(response, self.model)

            return assistant_response

        except Exception as e:
            logger.error(f"Error: {e}")
            raise RuntimeError(f"Error from NewProvider: {e}")

    def clear_conversation(self) -> None:
        self.conversation_history = []

    def get_conversation_history(self) -> list[dict[str, str]]:
        return self.conversation_history

    def set_conversation_history(self, history: list[dict[str, str]]) -> None:
        self.conversation_history = history

    def clone(self) -> "FFNewProvider":
        """Create a fresh clone for parallel execution."""
        return FFNewProvider(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            system_instructions=self.system_instructions,
        )
```

### Step 2: Export in `__init__.py`

Only active clients (with usage tracking) are exported:

```python
# src/Clients/__init__.py
from .FFNewProvider import FFNewProvider

__all__ = [
    "FFGemini",
    "FFLiteLLMClient",
    "FFMistral",
    "FFMistralSmall",
    "FFPerplexity",
    "FFNewProvider",
]
```

### Step 3: Add Tests

```python
# tests/test_ffnewprovider.py
import pytest
from unittest.mock import MagicMock, patch

class TestFFNewProvider:
    def test_init_with_api_key(self):
        # Test initialization

    def test_generate_response(self):
        # Test response generation

    # ... more tests
```

## Client-Specific Features

### FFAzureCodestral - Code Specialization (Archived)

> **Note:** Archived in `src/Clients/not_maintained/`. Lacks token usage tracking.

```python
client = FFAzureCodestral(api_key="...", endpoint="...")

# Code generation with language hint
code = client.generate_code("Write a sorting algorithm", language="python")

# Code explanation
explanation = client.explain_code("def foo(): ...")

# Code review
review = client.review_code("def foo(): ...")

# Code translation
translated = client.translate_code(code, "python", "rust")
```

### FFAnthropicCached - Prompt Caching (Archived)

> **Note:** Archived in `src/Clients/not_maintained/`. Lacks token usage tracking.

```python
client = FFAnthropicCached(api_key="...")

# Uses Anthropic's prompt caching for long contexts
response = client.generate_response("Analyze this document...")
```

### FFOpenAIAssistant - Thread-Based (Archived)

> **Note:** Archived in `src/Clients/not_maintained/`. Lacks token usage tracking.

```python
client = FFOpenAIAssistant(api_key="...", assistant_name="my-assistant")

# Uses OpenAI Assistant API with persistent threads
response = client.generate_response("Hello!")

# Thread is automatically managed
```

### FFGemini - OpenAI-Compatible

```python
client = FFGemini()  # Uses GEMINI_KEY env var, OpenAI-compatible API

response = client.generate_response("Hello!")
print(client.last_usage)  # TokenUsage with input/output/total
```

## Testing Strategy

### Unit Tests with Mocking

```python
def test_generate_response(self, mock_client):
    with patch("src.Clients.FFMistral.Mistral") as MockMistral:
        MockMistral.return_value = mock_client

        client = FFMistral(api_key="test-key")
        response = client.generate_response("Hello!")

        assert response == "Expected response"
        mock_client.chat.complete.assert_called_once()
```

### Test Categories

1. **Initialization Tests** - Config handling, defaults, env vars
2. **Response Generation Tests** - Basic calls, error handling
3. **History Management Tests** - Get/set/clear
4. **Error Handling Tests** - API errors, validation errors
5. **Special Feature Tests** - Client-specific functionality
