# Client Wrappers Subsystem Architecture

## Overview

The Client Wrappers subsystem provides a unified interface to multiple AI providers, abstracting away provider-specific API differences while adding powerful context management capabilities.

## Design Goals

1. **Provider Agnostic** - Same API regardless of underlying AI model
2. **Extensible** - Easy to add new providers
3. **Type Safe** - Abstract base class enforces contract
4. **Testable** - Mockable interface for testing

## Class Hierarchy

```
                    FFAIClientBase (ABC)
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌─────────────┐ ┌───────────┐ ┌─────────────┐
    │  FFMistral  │ │FFAnthropic│ │FFOpenAI     │ ...
    │FFMistralSmall│ │          │ │Assistant    │
    └─────────────┘ └───────────┘ └─────────────┘
           │
           ▼
    FFAzureClientBase (ABC)
           │
     ┌─────┴─────┬─────────────┬──────────────┐
     │           │             │              │
     ▼           ▼             ▼              ▼
┌──────────┐┌──────────┐┌───────────┐┌────────────┐
│FFAzure   ││FFAzure   ││FFAzure    ││FFAzurePhi  │
│Mistral   ││Codestral ││DeepSeekV3 ││            │
└──────────┘└──────────┘└───────────┘└────────────┘
```

## FFAIClientBase Contract

```python
class FFAIClientBase(ABC):
    """Abstract base class defining the client interface."""

    # Required attributes
    model: str
    system_instructions: str

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
        """
        Create a fresh clone of this client with empty history.

        Used for thread-safe parallel execution where each thread
        needs an isolated client instance with the same configuration.

        Returns:
            New client instance with same config, empty history.
        """
        pass
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

### 1. Direct API Clients

Connect directly to provider APIs.

| Client | Provider | Library | Auth |
|--------|----------|---------|------|
| `FFMistral` | Mistral AI | `mistralai` | API Key |
| `FFMistralSmall` | Mistral AI | `mistralai` | API Key |
| `FFAnthropic` | Anthropic | `anthropic` | API Key |
| `FFAnthropicCached` | Anthropic | `anthropic` | API Key + Caching |
| `FFGemini` | Google | `openai` + `google-auth` | OAuth |
| `FFPerplexity` | Perplexity | `openai` | API Key |
| `FFNvidiaDeepSeek` | Nvidia NIM | `openai` | API Key |

### 2. Azure AI Clients

Connect via Azure AI Inference API.

| Client | Model | Base Class |
|--------|-------|------------|
| `FFAzureMistral` | Mistral Large | `FFAzureClientBase` |
| `FFAzureMistralSmall` | Mistral Small | `FFAzureClientBase` |
| `FFAzureCodestral` | Codestral | `FFAzureClientBase` |
| `FFAzureDeepSeek` | DeepSeek R1 | - (standalone) |
| `FFAzureDeepSeekV3` | DeepSeek V3 | `FFAzureClientBase` |
| `FFAzureMSDeepSeekR1` | MAI-DS-R1 | - (standalone) |
| `FFAzurePhi` | Phi-4 | `FFAzureClientBase` |

### 3. Special Clients

| Client | Purpose |
|--------|---------|
| `FFOpenAIAssistant` | Uses OpenAI Assistant API (threads, runs) |

## FFAzureClientBase Design

Azure clients share significant common code. `FFAzureClientBase` is an ABC that inherits from `FFAIClientBase` and provides:

```python
class FFAzureClientBase(FFAIClientBase):
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

    # Common implementation
    def generate_response(self, prompt, **kwargs) -> str:
        # Full implementation shared by all Azure clients
        ...
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
| FFAnthropic | `ANTHROPIC_TOKEN` | `ANTHROPIC_MODEL` | `ANTHROPIC_TEMPERATURE` |
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
from typing import Optional, List, Dict, Any

from ..FFAIClientBase import FFAIClientBase

logger = logging.getLogger(__name__)

class FFNewProvider(FFAIClientBase):
    def __init__(self, config: Optional[dict] = None, **kwargs):
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
        self.conversation_history = []
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
            self.conversation_history.append({"role": "user", "content": prompt})

            response = self.client.generate(
                messages=self.conversation_history,
                model=self.model,
                **kwargs
            )

            assistant_response = response.text
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            return assistant_response

        except Exception as e:
            logger.error(f"Error: {e}")
            raise RuntimeError(f"Error from NewProvider: {e}")

    def clear_conversation(self) -> None:
        self.conversation_history = []

    def get_conversation_history(self) -> List[Dict]:
        return self.conversation_history

    def set_conversation_history(self, history: List[Dict]) -> None:
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

```python
# src/Clients/__init__.py
from .FFNewProvider import FFNewProvider

__all__ = [..., "FFNewProvider"]
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

### FFAzureCodestral - Code Specialization

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

### FFAnthropicCached - Prompt Caching

```python
client = FFAnthropicCached(api_key="...")

# Uses Anthropic's prompt caching for long contexts
response = client.generate_response("Analyze this document...")
```

### FFOpenAIAssistant - Thread-Based

```python
client = FFOpenAIAssistant(api_key="...", assistant_name="my-assistant")

# Uses OpenAI Assistant API with persistent threads
response = client.generate_response("Hello!")

# Thread is automatically managed
```

### FFGemini - Async + OAuth

```python
client = FFGemini()  # Uses Google Application Default Credentials

# Async interface
response = await client.generate_response("Hello!")

# Sync wrapper
response = client.generate_response_sync("Hello!")
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
