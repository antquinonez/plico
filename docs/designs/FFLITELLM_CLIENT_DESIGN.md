# FFLiteLLMClient Design Specification

## Class Diagram

```
                    FFAIClientBase (ABC)
                           │
                           │ implements
                           │
                    ┌──────┴──────┐
                    │             │
                    ▼             ▼
            FFLiteLLMClient   [Existing Clients]
                    │
                    │ uses
                    ▼
                LiteLLM
                    │
                    │ calls
                    ▼
         ┌──────────┼──────────┐
         │          │          │
         ▼          ▼          ▼
      OpenAI    Anthropic    Azure    ...100+ providers
```

---

## FFLiteLLMClient Implementation

### Constructor

```python
class FFLiteLLMClient(FFAIClientBase):
    """
    LiteLLM-backed AI client implementing FFAIClientBase.

    This client wraps LiteLLM's completion() function while maintaining
    the FFAIClientBase contract for compatibility with FFAI wrapper.

    Key features:
    - Internal conversation history management
    - Clone pattern for parallel execution
    - Model string routing (e.g., "azure/mistral-small-2503")
    - Retry and fallback support

    Args:
        model_string: LiteLLM model identifier (e.g., "openai/gpt-4", "azure/my-deployment")
        config: Optional configuration dictionary
        api_key: API key (overrides env var)
        api_base: API base URL (overrides env var)
        system_instructions: System prompt
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens to generate
        fallbacks: List of fallback model strings
        retry_config: Retry configuration

    Example:
        >>> client = FFLiteLLMClient(model_string="azure/mistral-small-2503")
        >>> response = client.generate_response("Hello!")
        >>>
        >>> # With fallbacks
        >>> client = FFLiteLLMClient(
        ...     model_string="anthropic/claude-3-opus",
        ...     fallbacks=["openai/gpt-4", "azure/gpt-4"]
        ... )
    """

    model: str
    system_instructions: str

    def __init__(
        self,
        model_string: str,
        config: dict | None = None,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        api_version: str | None = None,
        system_instructions: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        fallbacks: list[str] | None = None,
        retry_config: dict | None = None,
        **kwargs,
    ):
        self._model_string = model_string
        self._config = config or {}
        self._fallbacks = fallbacks or []
        self._retry_config = retry_config or {"max_retries": 3}

        # Extract model name from string (e.g., "azure/mistral-small" -> "mistral-small")
        self.model = model_string.split("/", 1)[-1] if "/" in model_string else model_string

        # Resolve settings with priority: kwargs > config > env > defaults
        self._resolve_settings(
            api_key=api_key,
            api_base=api_base,
            api_version=api_version,
            system_instructions=system_instructions,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Initialize conversation history
        self.conversation_history: list[dict[str, str]] = []
```

### Settings Resolution

```python
def _resolve_settings(
    self,
    api_key: str | None,
    api_base: str | None,
    api_version: str | None,
    system_instructions: str | None,
    temperature: float | None,
    max_tokens: int | None,
    **kwargs,
) -> None:
    """Resolve all settings with priority chain."""
    from .model_defaults import get_model_defaults

    # Get model-specific defaults
    defaults = get_model_defaults(self._model_string)

    # Resolve each setting: kwargs > config > env > defaults
    self.api_key = api_key or self._config.get("api_key") or self._get_env("API_KEY")
    self.api_base = api_base or self._config.get("api_base") or self._get_env("API_BASE")
    self.api_version = api_version or self._config.get("api_version") or self._get_env("API_VERSION")
    self.system_instructions = (
        system_instructions
        or self._config.get("system_instructions")
        or defaults.get("system_instructions", "You are a helpful assistant.")
    )
    self.temperature = (
        temperature
        if temperature is not None
        else self._config.get("temperature", defaults.get("temperature", 0.7))
    )
    self.max_tokens = (
        max_tokens
        if max_tokens is not None
        else self._config.get("max_tokens", defaults.get("max_tokens", 4096))
    )

    # Store any additional kwargs
    self._extra_kwargs = kwargs

def _get_env(self, suffix: str) -> str | None:
    """Get environment variable with provider-specific prefix."""
    import os

    provider = self._model_string.split("/")[0] if "/" in self._model_string else "openai"

    # Try provider-specific first, then generic
    prefixes = {
        "azure": f"AZURE_{self.model.upper().replace('-', '_')}",
        "anthropic": "ANTHROPIC",
        "mistral": "MISTRAL",
        "openai": "OPENAI",
        "gemini": "GEMINI",
        "perplexity": "PERPLEXITY",
    }

    prefix = prefixes.get(provider, provider.upper())

    # Try multiple env var patterns
    patterns = [
        f"{prefix}_{suffix}",
        f"{prefix}_API_KEY" if suffix == "API_KEY" else None,
        f"LITELLM_{suffix}",
    ]

    for pattern in patterns:
        if pattern and (value := os.getenv(pattern)):
            return value

    return None
```

### Core Methods

```python
def generate_response(
    self,
    prompt: str,
    model: str | None = None,
    system_instructions: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs,
) -> str:
    """
    Generate a response from the AI model.

    Args:
        prompt: The user prompt
        model: Override model (appends to provider prefix)
        system_instructions: Override system instructions
        temperature: Override temperature
        max_tokens: Override max tokens
        **kwargs: Additional LiteLLM parameters

    Returns:
        The generated response text
    """
    from litellm import completion

    if not prompt.strip():
        raise ValueError("Empty prompt provided")

    # Add user message to history
    self.conversation_history.append({"role": "user", "content": prompt})

    # Build messages list
    messages = self._build_messages(system_instructions)

    # Determine model string
    model_string = self._model_string
    if model:
        # If model is provided, it might be just the model name
        # Preserve the provider prefix
        if "/" not in model and "/" in self._model_string:
            provider = self._model_string.split("/")[0]
            model_string = f"{provider}/{model}"
        else:
            model_string = model

    # Build API parameters
    api_params = {
        "model": model_string,
        "messages": messages,
        "temperature": temperature if temperature is not None else self.temperature,
        "max_tokens": max_tokens or self.max_tokens,
    }

    # Add provider-specific settings
    if self.api_key:
        api_params["api_key"] = self.api_key
    if self.api_base:
        api_params["api_base"] = self.api_base
    if self.api_version:
        api_params["api_version"] = self.api_version

    # Merge additional kwargs
    api_params.update(self._extra_kwargs)
    api_params.update(kwargs)

    try:
        # Call LiteLLM
        response = completion(**api_params)

        # Extract response text
        assistant_response = response.choices[0].message.content

        # Add to history
        self.conversation_history.append({"role": "assistant", "content": assistant_response})

        return assistant_response

    except Exception as e:
        # Try fallbacks if available
        return self._try_fallbacks(messages, api_params, str(e))

def _build_messages(self, system_instructions: str | None = None) -> list[dict]:
    """Build messages list for LiteLLM API call."""
    messages = []

    # Add system message
    system = system_instructions or self.system_instructions
    if system:
        messages.append({"role": "system", "content": system})

    # Add conversation history
    messages.extend(self.conversation_history)

    return messages

def _try_fallbacks(
    self,
    messages: list[dict],
    original_params: dict,
    original_error: str,
) -> str:
    """Try fallback models if primary fails."""
    from litellm import completion

    for fallback_model in self._fallbacks:
        try:
            params = original_params.copy()
            params["model"] = fallback_model
            response = completion(**params)
            assistant_response = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            return assistant_response
        except Exception:
            continue

    raise RuntimeError(f"All models failed. Primary error: {original_error}")
```

### History Management

```python
def clear_conversation(self) -> None:
    """Clear the conversation history."""
    self.conversation_history = []

def get_conversation_history(self) -> list[dict[str, str]]:
    """Get the conversation history."""
    return self.conversation_history.copy()

def set_conversation_history(self, history: list[dict[str, str]]) -> None:
    """Set the conversation history."""
    self.conversation_history = list(history)  # Make a copy
```

### Clone Pattern

```python
def clone(self) -> "FFLiteLLMClient":
    """
    Create a fresh clone of this client with empty history.

    Used for thread-safe parallel execution where each thread
    needs an isolated client instance with the same configuration.

    Returns:
        New FFLiteLLMClient with same config, empty history.
    """
    return FFLiteLLMClient(
        model_string=self._model_string,
        config=self._config.copy(),
        api_key=self.api_key,
        api_base=self.api_base,
        api_version=self.api_version,
        system_instructions=self.system_instructions,
        temperature=self.temperature,
        max_tokens=self.max_tokens,
        fallbacks=self._fallbacks.copy() if self._fallbacks else None,
        retry_config=self._retry_config.copy(),
        **self._extra_kwargs,
    )
```

---

## Azure Factory Implementation

```python
# src/Clients/FFAzureLiteLLM.py

from typing import Any
from .FFLiteLLMClient import FFLiteLLMClient
from .model_defaults import get_model_defaults
import os


def create_azure_client(
    deployment_name: str,
    env_prefix: str,
    *,
    model_defaults: dict[str, Any] | None = None,
    system_instructions: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs,
) -> FFLiteLLMClient:
    """
    Factory for Azure AI clients with environment-based configuration.

    This provides backward compatibility with existing Azure client patterns
    while using LiteLLM under the hood.

    Args:
        deployment_name: Azure deployment name (e.g., "mistral-small-2503")
        env_prefix: Environment variable prefix (e.g., "AZURE_MISTRALSMALL")
        model_defaults: Optional model-specific defaults
        system_instructions: System prompt override
        temperature: Temperature override
        max_tokens: Max tokens override
        **kwargs: Additional FFLiteLLMClient parameters

    Returns:
        Configured FFLiteLLMClient for Azure model

    Example:
        >>> client = create_azure_client(
        ...     deployment_name="mistral-small-2503",
        ...     env_prefix="AZURE_MISTRALSMALL"
        ... )
    """
    model_string = f"azure/{deployment_name}"

    # Get defaults for this model
    defaults = get_model_defaults(model_string)
    if model_defaults:
        defaults = {**defaults, **model_defaults}

    # Resolve from environment
    api_key = os.getenv(f"{env_prefix}_KEY")
    api_base = os.getenv(f"{env_prefix}_ENDPOINT")
    api_version = os.getenv(f"{env_prefix}_API_VERSION", "2024-02-01")

    # Environment-based defaults
    env_temperature = os.getenv(f"{env_prefix}_TEMPERATURE")
    env_max_tokens = os.getenv(f"{env_prefix}_MAX_TOKENS")
    env_instructions = os.getenv(f"{env_prefix}_ASSISTANT_INSTRUCTIONS")

    return FFLiteLLMClient(
        model_string=model_string,
        api_key=api_key,
        api_base=api_base,
        api_version=api_version,
        system_instructions=system_instructions or env_instructions or defaults.get("system_instructions"),
        temperature=temperature if temperature is not None else (float(env_temperature) if env_temperature else defaults.get("temperature")),
        max_tokens=max_tokens or (int(env_max_tokens) if env_max_tokens else defaults.get("max_tokens")),
        **kwargs,
    )
```

---

## Model Defaults Registry

```python
# src/Clients/model_defaults.py

GENERIC_DEFAULTS = {
    "max_tokens": 4096,
    "temperature": 0.7,
    "system_instructions": "You are a helpful assistant. Respond accurately to user queries.",
}

MODEL_DEFAULTS: dict[str, dict] = {
    # Azure Models
    "azure/mistral-small-2503": {
        "max_tokens": 40000,
        "temperature": 0.7,
        "system_instructions": "You are a helpful assistant. Respond accurately to user queries. Be concise and clear.",
    },
    "azure/mistral-large-2411": {
        "max_tokens": 40000,
        "temperature": 0.7,
    },
    "azure/codestral": {
        "max_tokens": 32000,
        "temperature": 0.3,
        "system_instructions": "You are an expert programmer. Write clean, efficient, well-documented code.",
    },
    "azure/deepseek-v3": {
        "max_tokens": 32000,
        "temperature": 0.7,
    },
    "azure/deepseek-r1": {
        "max_tokens": 32000,
        "temperature": 0.7,
    },
    "azure/phi-4": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },

    # Mistral Direct
    "mistral/mistral-small-latest": {
        "max_tokens": 32000,
        "temperature": 0.7,
    },
    "mistral/mistral-large-latest": {
        "max_tokens": 40000,
        "temperature": 0.7,
    },
    "mistral/codestral-latest": {
        "max_tokens": 32000,
        "temperature": 0.3,
    },

    # Anthropic
    "anthropic/claude-3-opus-20240229": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "anthropic/claude-3-sonnet-20240229": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "anthropic/claude-3-haiku-20240307": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "anthropic/claude-3-5-sonnet-20241022": {
        "max_tokens": 8192,
        "temperature": 0.7,
    },

    # OpenAI
    "openai/gpt-4": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "openai/gpt-4-turbo": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "openai/gpt-4o": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },

    # Google
    "gemini/gemini-pro": {
        "max_tokens": 8192,
        "temperature": 0.7,
    },
    "gemini/gemini-1.5-pro": {
        "max_tokens": 8192,
        "temperature": 0.7,
    },

    # Perplexity
    "perplexity/llama-3.1-sonar-large-128k-online": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },

    # Nvidia NIM
    "nvidia_nim/deepseek-ai/deepseek-r1": {
        "max_tokens": 32000,
        "temperature": 0.7,
    },
}


def get_model_defaults(model_string: str) -> dict:
    """
    Get defaults for a model string.

    Args:
        model_string: LiteLLM model identifier (e.g., "azure/mistral-small-2503")

    Returns:
        Dictionary with default settings
    """
    # Try exact match first
    if model_string in MODEL_DEFAULTS:
        return MODEL_DEFAULTS[model_string].copy()

    # Try partial match (e.g., "mistral-small" matches "azure/mistral-small-2503")
    model_name = model_string.split("/")[-1] if "/" in model_string else model_string
    for key, defaults in MODEL_DEFAULTS.items():
        if model_name in key:
            return defaults.copy()

    return GENERIC_DEFAULTS.copy()


def register_model_defaults(model_string: str, defaults: dict) -> None:
    """
    Register custom defaults for a model.

    Args:
        model_string: LiteLLM model identifier
        defaults: Dictionary of default settings
    """
    MODEL_DEFAULTS[model_string] = defaults
```

---

## Backward Compatibility Wrappers

Example for FFAzureMistralSmall:

```python
# src/Clients/FFAzureMistralSmall.py

from .FFAzureLiteLLM import create_azure_client
from .FFLiteLLMClient import FFLiteLLMClient


class FFAzureMistralSmall(FFLiteLLMClient):
    """
    Azure AI Inference client for Mistral Small models.

    This class provides backward compatibility with existing FFAzureMistralSmall
    usage patterns while using LiteLLM under the hood.
    """

    def __init__(self, config: dict | None = None, **kwargs):
        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_MISTRALSMALL",
            model_defaults={
                "max_tokens": 40000,
                "temperature": 0.7,
                "system_instructions": (
                    "You are a helpful assistant. "
                    "Respond accurately to user queries. Be concise and clear."
                ),
            },
            **kwargs,
        )
        # Copy all attributes from the created client
        self.__dict__ = client.__dict__
        self._client = client

    def __getattr__(self, name):
        # Delegate to underlying client
        return getattr(self._client, name)
```

---

## Orchestrator Compatibility

### Requirements from ExcelOrchestrator

The orchestrator requires clients to implement `FFAIClientBase` and support these patterns:

#### 1. Clone Pattern (Critical for Parallel Execution)

```python
# excel_orchestrator.py:136-146
def _get_isolated_ffai(self, client_name: str | None = None) -> FFAI:
    if client_name and self.client_registry:
        client = self.client_registry.clone(client_name)
    else:
        client = self.client.clone()  # <-- Each thread gets a clone
    return FFAI(client, shared_prompt_attr_history=..., history_lock=...)
```

**FFLiteLLMClient must implement `clone()` that returns a fresh instance with:**
- Same configuration (model_string, api_key, temperature, etc.)
- Empty conversation_history
- No shared state with parent

#### 2. ClientRegistry Integration

Add to `src/orchestrator/client_registry.py`:

```python
from ..Clients.FFLiteLLMClient import FFLiteLLMClient

CLIENT_MAP: dict[str, type[FFAIClientBase]] = {
    # ... existing entries ...

    # LiteLLM-based clients
    "litellm": FFLiteLLMClient,
    "litellm-azure": FFLiteLLMClient,
    "litellm-anthropic": FFLiteLLMClient,
    "litellm-mistral": FFLiteLLMClient,
    "litellm-openai": FFLiteLLMClient,
    "litellm-gemini": FFLiteLLMClient,
}
```

#### 3. Constructor Signature Compatibility

The registry creates clients with kwargs (client_registry.py:174-184):

```python
kwargs = {
    "api_key": api_key,
    "model": config.get("model"),
    "temperature": float(config.get("temperature")),
    "max_tokens": int(config.get("max_tokens")),
    "system_instructions": config.get("system_instructions"),
}
return client_class(**kwargs)
```

**FFLiteLLMClient must accept these kwargs in constructor.**

#### 4. FFAI Wrapper Compatibility

FFAI calls `client.generate_response()` with these parameters:

```python
# FFAI.py:316-318
response = self.client.generate_response(
    prompt=final_prompt,
    model=used_model,
    **kwargs  # temperature, max_tokens, system_instructions, etc.
)
```

**FFLiteLLMClient.generate_response must accept:**
- `prompt: str` (required)
- `model: str | None` (optional override)
- `temperature: float | None`
- `max_tokens: int | None`
- `system_instructions: str | None`
- Additional kwargs for provider-specific options

### Execution Flow

```
ExcelOrchestrator.run()
    │
    ├─► _get_isolated_ffai()
    │       │
    │       ├─► client.clone()  [FFLiteLLMClient returns fresh instance]
    │       │
    │       └─► FFAI(client, shared_history=..., history_lock=...)
    │
    └─► ffai.generate_response(prompt, prompt_name=..., history=...)
            │
            ├─► FFAI._build_prompt()  [assembles declarative context]
            │
            └─► client.generate_response(final_prompt, **kwargs)
                    │
                    └─► litellm.completion(model=..., messages=...)
```

### Model Override Handling

The orchestrator can override the model via config:

```python
# excel_orchestrator.py:414-416
response = ffai.generate_response(
    model=self.config.get("model"),  # Can override client's default model
    ...
)
```

**FFLiteLLMClient must handle model override:**
- If `model` parameter provided, use it instead of default
- Handle both full model strings ("anthropic/claude-3-opus") and short names ("claude-3-opus")

---

## Usage Examples

### Basic Usage

```python
from src.Clients.FFLiteLLMClient import FFLiteLLMClient

# Direct LiteLLM usage
client = FFLiteLLMClient(model_string="anthropic/claude-3-opus")
response = client.generate_response("Hello!")

# Azure model
client = FFLiteLLMClient(
    model_string="azure/mistral-small-2503",
    api_key=os.getenv("AZURE_MISTRALSMALL_KEY"),
    api_base=os.getenv("AZURE_MISTRALSMALL_ENDPOINT"),
)
```

### With FFAI Wrapper

```python
from src.FFAI import FFAI
from src.Clients.FFLiteLLMClient import FFLiteLLMClient

client = FFLiteLLMClient(model_string="mistral/mistral-large-latest")
ffai = FFAI(client)

# Use declarative context
ffai.generate_response("What is 2+2?", prompt_name="math")
response = ffai.generate_response("What was my question?", history=["math"])
```

### Parallel Execution

```python
from concurrent.futures import ThreadPoolExecutor

client = FFLiteLLMClient(model_string="azure/mistral-small-2503")

def process_prompt(prompt_data):
    clone = client.clone()  # Isolated history
    ffai = FFAI(clone)
    return ffai.generate_response(prompt_data["prompt"], prompt_name=prompt_data["name"])

with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(process_prompt, prompts))
```

### With Fallbacks

```python
client = FFLiteLLMClient(
    model_string="anthropic/claude-3-opus",
    fallbacks=["openai/gpt-4", "azure/gpt-4"],
    api_key=os.getenv("ANTHROPIC_API_KEY"),
)
# Will try claude-3-opus, then gpt-4, then azure/gpt-4 on failure
response = client.generate_response("Hello!")
```
