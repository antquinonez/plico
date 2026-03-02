# LiteLLM Integration Plan

## Overview

This document outlines the implementation plan for integrating LiteLLM as a client layer in Plico while preserving all existing functionality including declarative context management, multiple history tracking, and the clone pattern for parallel execution.

---

## Phase 1: Core Client Implementation

### 1.1 Create FFLiteLLMClient Base Class

**File:** `src/Clients/FFLiteLLMClient.py`

```python
class FFLiteLLMClient(FFAIClientBase):
    """
    LiteLLM-backed client implementing FFAIClientBase contract.

    Translates Plico patterns to LiteLLM while maintaining:
    - Internal conversation history for get/set/clone
    - Model-specific default handling
    - Thread-safe operation support
    """

    def __init__(
        self,
        model_string: str,  # e.g., "azure/mistral-small-2503", "anthropic/claude-3-opus"
        config: dict | None = None,
        **kwargs
    ):
        # Configuration priority: kwargs > config > env > defaults
        # Initialize conversation_history
        # Store model_string and resolved settings

    def generate_response(self, prompt: str, **kwargs) -> str:
        # 1. Append user message to internal history
        # 2. Build messages list (system + history)
        # 3. Call litellm.completion()
        # 4. Extract and store assistant response
        # 5. Return response text

    def clear_conversation(self) -> None:
        self.conversation_history = []

    def get_conversation_history(self) -> list[dict]:
        return self.conversation_history.copy()

    def set_conversation_history(self, history: list[dict]) -> None:
        self.conversation_history = history.copy()

    def clone(self) -> "FFLiteLLMClient":
        return FFLiteLLMClient(
            model_string=self.model_string,
            config=self._config.copy(),
        )
```

### 1.2 Model Defaults Registry

**File:** `src/Clients/model_defaults.py`

```python
MODEL_DEFAULTS = {
    # Azure Models
    "azure/mistral-small-2503": {
        "max_tokens": 40000,
        "temperature": 0.7,
        "system_instructions": "You are a helpful assistant...",
    },
    "azure/mistral-large-2411": {
        "max_tokens": 40000,
        "temperature": 0.7,
    },
    "azure/codestral": {
        "max_tokens": 32000,
        "temperature": 0.3,
    },
    "azure/deepseek-v3": {
        "max_tokens": 32000,
        "temperature": 0.7,
    },
    "azure/phi-4": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    # Direct API Models
    "mistral/mistral-large-latest": {
        "max_tokens": 40000,
        "temperature": 0.7,
    },
    "anthropic/claude-3-opus-20240229": {
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    "gemini/gemini-pro": {
        "max_tokens": 8192,
        "temperature": 0.7,
    },
    # ... additional models
}

def get_model_defaults(model_string: str) -> dict:
    """Get defaults for a model, with fallback to generic defaults."""
    return MODEL_DEFAULTS.get(model_string, GENERIC_DEFAULTS)
```

### 1.3 Environment Variable Mapping

LiteLLM uses specific env var patterns. Create mapping layer:

```python
# Plico env vars -> LiteLLM env vars
ENV_MAPPING = {
    # Azure models need api_base, api_key, api_version
    "azure": {
        "api_key": "{PREFIX}_KEY",      # AZURE_MISTRALSMALL_KEY
        "api_base": "{PREFIX}_ENDPOINT", # AZURE_MISTRALSMALL_ENDPOINT
    },
    "anthropic": {
        "api_key": "ANTHROPIC_API_KEY",
    },
    "mistral": {
        "api_key": "MISTRAL_API_KEY",
    },
    # ... etc
}
```

---

## Phase 2: Azure Client Migration

### 2.1 Azure Model String Format

Azure models in LiteLLM use format: `azure/<deployment-name>`

```python
# Current FFAzureMistralSmall
model = "mistral-small-2503"
endpoint = os.getenv("AZURE_MISTRALSMALL_ENDPOINT")

# LiteLLM equivalent
model_string = "azure/mistral-small-2503"
api_base = os.getenv("AZURE_MISTRALSMALL_ENDPOINT")
api_key = os.getenv("AZURE_MISTRALSMALL_KEY")
api_version = "2024-02-01"  # or from env
```

### 2.2 Azure Client Factory

Create factory function for backward compatibility:

**File:** `src/Clients/FFAzureLiteLLM.py`

```python
def create_azure_client(
    deployment_name: str,
    env_prefix: str,
    model_defaults: dict | None = None,
) -> FFLiteLLMClient:
    """
    Factory for Azure clients with environment-based configuration.

    Args:
        deployment_name: Azure deployment name (e.g., "mistral-small-2503")
        env_prefix: Environment variable prefix (e.g., "AZURE_MISTRALSMALL")
        model_defaults: Optional overrides for model defaults

    Returns:
        Configured FFLiteLLMClient for Azure model
    """
    model_string = f"azure/{deployment_name}"

    config = {
        "api_key": os.getenv(f"{env_prefix}_KEY"),
        "api_base": os.getenv(f"{env_prefix}_ENDPOINT"),
        "api_version": os.getenv(f"{env_prefix}_API_VERSION", "2024-02-01"),
    }

    # Merge with model defaults
    defaults = get_model_defaults(model_string)
    config = {**defaults, **(model_defaults or {}), **config}

    return FFLiteLLMClient(model_string=model_string, config=config)
```

### 2.3 Backward Compatibility Wrappers

Create thin wrappers for existing Azure clients:

```python
# src/Clients/FFAzureMistralSmall.py (new version)
from .FFAzureLiteLLM import create_azure_client

class FFAzureMistralSmall(FFLiteLLMClient):
    """Azure AI Inference client for Mistral Small models."""

    def __init__(self, config: dict | None = None, **kwargs):
        client = create_azure_client(
            deployment_name="mistral-small-2503",
            env_prefix="AZURE_MISTRALSMALL",
            model_defaults={"max_tokens": 40000, "temperature": 0.7},
        )
        # Copy all attributes to self for interface compatibility
        self.__dict__ = client.__dict__
```

---

## Phase 3: Direct API Client Migration

### 3.1 Mistral Client Migration

```python
# src/Clients/FFMistralSmall.py (new version)
from .FFLiteLLMClient import FFLiteLLMClient

class FFMistralSmall(FFLiteLLMClient):
    """Mistral AI client for Mistral Small models."""

    def __init__(self, config: dict | None = None, **kwargs):
        super().__init__(
            model_string="mistral/mistral-small-latest",
            config=config,
            **kwargs
        )
```

### 3.2 Anthropic Client Migration

```python
# src/Clients/FFAnthropic.py (new version)
from .FFLiteLLMClient import FFLiteLLMClient

class FFAnthropic(FFLiteLLMClient):
    """Anthropic Claude client."""

    def __init__(self, config: dict | None = None, **kwargs):
        model = kwargs.pop("model", "claude-3-opus-20240229")
        super().__init__(
            model_string=f"anthropic/{model}",
            config=config,
            **kwargs
        )
```

### 3.3 Cached Variant Support

For `FFAnthropicCached`, extend base client with caching:

```python
class FFAnthropicCached(FFLiteLLMClient):
    """Anthropic client with prompt caching."""

    def generate_response(self, prompt: str, **kwargs) -> str:
        # Add caching headers to kwargs
        kwargs.setdefault("extra_headers", {})
        kwargs["extra_headers"]["anthropic-beta"] = "prompt-caching"
        return super().generate_response(prompt, **kwargs)
```

---

## Phase 3.5: Orchestrator Integration

### 3.5.1 Update ClientRegistry

Add LiteLLM client types to the registry:

```python
# src/orchestrator/client_registry.py

from ..Clients.FFLiteLLMClient import FFLiteLLMClient

CLIENT_MAP: dict[str, type[FFAIClientBase]] = {
    # Existing clients (kept for backward compatibility)
    "mistral": FFMistral,
    "mistral-small": FFMistralSmall,
    "anthropic": FFAnthropic,
    # ... etc

    # LiteLLM-based clients (new)
    "litellm": FFLiteLLMClient,
    "litellm-azure": FFLiteLLMClient,
    "litellm-anthropic": FFLiteLLMClient,
    "litellm-mistral": FFLiteLLMClient,
    "litellm-openai": FFLiteLLMClient,
    "litellm-gemini": FFLiteLLMClient,
    "litellm-perplexity": FFLiteLLMClient,
}

DEFAULT_API_KEY_ENVS = {
    # ... existing entries ...

    # LiteLLM clients use provider-specific env vars
    "litellm": "LITELLM_API_KEY",
    "litellm-azure": "AZURE_API_KEY",
    "litellm-anthropic": "ANTHROPIC_API_KEY",
    "litellm-mistral": "MISTRAL_API_KEY",
    "litellm-openai": "OPENAI_API_KEY",
    "litellm-gemini": "GEMINI_API_KEY",
}
```

### 3.5.2 Client Definition in Excel

For the `clients` sheet in Excel workbooks:

| name | client_type | model | temperature | max_tokens |
|------|-------------|-------|-------------|------------|
| fast | litellm-mistral | mistral/mistral-small-latest | 0.3 | 4096 |
| smart | litellm-anthropic | anthropic/claude-3-opus | 0.7 | 4096 |
| azure-main | litellm-azure | azure/mistral-small-2503 | 0.7 | 40000 |

### 3.5.3 Model String Handling

FFLiteLLMClient must handle both:
1. **Full model string in constructor**: `FFLiteLLMClient(model_string="anthropic/claude-3-opus")`
2. **Model override in generate_response**: `client.generate_response(prompt, model="claude-3-haiku")`

```python
def generate_response(self, prompt: str, model: str | None = None, **kwargs) -> str:
    # Determine final model string
    if model:
        if "/" not in model and "/" in self._model_string:
            # Short name provided, keep provider prefix
            provider = self._model_string.split("/")[0]
            model_string = f"{provider}/{model}"
        else:
            model_string = model
    else:
        model_string = self._model_string
```

---

## Phase 4: Advanced Features

### 4.1 Retry Configuration

```python
# In FFLiteLLMClient
def __init__(self, ..., retry_config: dict | None = None):
    self.retry_config = retry_config or {
        "max_retries": 3,
        "retry_on": [429, 500, 502, 503],
    }
```

### 4.2 Fallback Support

```python
class FFLiteLLMClient(FFAIClientBase):
    def __init__(
        self,
        model_string: str,
        fallbacks: list[str] | None = None,
        ...
    ):
        self.fallbacks = fallbacks or []

    def generate_response(self, prompt: str, **kwargs) -> str:
        try:
            return self._call_litellm(self.model_string, prompt, **kwargs)
        except Exception as e:
            for fallback_model in self.fallbacks:
                try:
                    return self._call_litellm(fallback_model, prompt, **kwargs)
                except:
                    continue
            raise
```

### 4.3 Streaming Support (Future)

```python
def generate_response_stream(self, prompt: str, **kwargs) -> Iterator[str]:
    """Stream response chunks."""
    self.conversation_history.append({"role": "user", "content": prompt})
    messages = self._build_messages()

    response = completion(
        model=self.model_string,
        messages=messages,
        stream=True,
        **kwargs
    )

    full_response = ""
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            full_response += content
            yield content

    self.conversation_history.append({"role": "assistant", "content": full_response})
```

---

## Phase 5: Testing Strategy

### 5.1 Unit Tests

```python
# tests/test_fflitellm_client.py

class TestFFLiteLLMClient:
    def test_implements_contract(self):
        """Verify FFAIClientBase contract is satisfied."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        assert hasattr(client, 'generate_response')
        assert hasattr(client, 'clear_conversation')
        assert hasattr(client, 'get_conversation_history')
        assert hasattr(client, 'set_conversation_history')
        assert hasattr(client, 'clone')

    def test_conversation_history_management(self):
        """Test history get/set/clear."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        client.set_conversation_history([{"role": "user", "content": "test"}])
        history = client.get_conversation_history()
        assert len(history) == 1
        client.clear_conversation()
        assert len(client.get_conversation_history()) == 0

    def test_clone_isolation(self):
        """Test that cloned clients have isolated history."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        client.set_conversation_history([{"role": "user", "content": "original"}])

        clone = client.clone()
        clone.set_conversation_history([{"role": "user", "content": "cloned"}])

        assert len(client.get_conversation_history()) == 1
        assert client.get_conversation_history()[0]["content"] == "original"
```

### 5.2 Integration Tests with FFAI

```python
# tests/test_ffai_litellm_integration.py

class TestFFAILiteLLMIntegration:
    def test_declarative_context(self):
        """Verify FFAI context assembly works with LiteLLM client."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        ffai = FFAI(client)

        ffai.generate_response("What is 2+2?", prompt_name="math")
        response = ffai.generate_response(
            "What was my question?",
            history=["math"]
        )

        assert "2+2" in response.lower() or "math" in response.lower()

    def test_parallel_execution_with_clone(self):
        """Verify clone pattern works for parallel execution."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")
        clones = [client.clone() for _ in range(5)]

        # Each clone should have empty history
        for clone in clones:
            assert len(clone.get_conversation_history()) == 0
```

### 5.3 Backward Compatibility Tests

```python
# tests/test_backward_compatibility.py

class TestBackwardCompatibility:
    def test_azure_client_interface_unchanged(self):
        """Existing Azure client usage should work unchanged."""
        client = FFAzureMistralSmall()
        assert client.model == "mistral-small-2503"
        assert hasattr(client, 'generate_response')

    def test_environment_variables_still_work(self):
        """Existing env var patterns should still resolve."""
        os.environ["AZURE_MISTRALSMALL_KEY"] = "test-key"
        os.environ["AZURE_MISTRALSMALL_ENDPOINT"] = "https://test.openai.azure.com"

        client = FFAzureMistralSmall()
        assert client.api_key == "test-key"
```

### 5.4 Orchestrator Integration Tests

```python
# tests/test_orchestrator_litellm_integration.py

class TestOrchestratorLiteLLMIntegration:
    def test_client_registry_recognizes_litellm(self):
        """ClientRegistry should recognize LiteLLM client types."""
        from src.orchestrator.client_registry import ClientRegistry

        assert "litellm" in ClientRegistry.get_available_client_types()
        assert "litellm-azure" in ClientRegistry.get_available_client_types()

    def test_registry_creates_litellm_client(self):
        """Registry should create FFLiteLLMClient instances."""
        from src.orchestrator.client_registry import ClientRegistry
        from src.Clients.FFLiteLLMClient import FFLiteLLMClient

        default = FFLiteLLMClient(model_string="openai/gpt-4")
        registry = ClientRegistry(default)
        registry.register("test", "litellm", {"model": "anthropic/claude-3-opus"})

        client = registry.get("test")
        assert isinstance(client, FFLiteLLMClient)

    def test_registry_clones_litellm_client(self):
        """Registry should clone FFLiteLLMClient for parallel execution."""
        from src.orchestrator.client_registry import ClientRegistry
        from src.Clients.FFLiteLLMClient import FFLiteLLMClient

        default = FFLiteLLMClient(model_string="openai/gpt-4")
        registry = ClientRegistry(default)
        registry.register("test", "litellm", {"model": "anthropic/claude-3-opus"})

        # Get once to create
        original = registry.get("test")
        original.set_conversation_history([{"role": "user", "content": "test"}])

        # Clone should have empty history
        clone = registry.clone("test")
        assert len(clone.get_conversation_history()) == 0

    @pytest.mark.integration
    def test_orchestrator_parallel_execution(self):
        """ExcelOrchestrator should work with LiteLLM client in parallel mode."""
        from src.orchestrator import ExcelOrchestrator
        from src.Clients.FFLiteLLMClient import FFLiteLLMClient

        client = FFLiteLLMClient(model_string="openai/gpt-4")
        orchestrator = ExcelOrchestrator(
            "sample_workbook.xlsx",
            client=client,
            concurrency=3
        )

        results = orchestrator.run()
        assert all(r["status"] in ("success", "skipped") for r in results)
```

---

## Migration Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Phase 1 | 1 week | FFLiteLLMClient, model defaults, env mapping |
| Phase 2 | 1 week | Azure client migration, backward compat wrappers |
| Phase 3 | 1 week | Direct API client migration |
| Phase 4 | 1 week | Advanced features (retry, fallback) |
| Phase 5 | Ongoing | Testing, documentation, deprecation notices |

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `src/Clients/FFLiteLLMClient.py` | Core LiteLLM client implementation |
| `src/Clients/model_defaults.py` | Model defaults registry |
| `src/Clients/FFAzureLiteLLM.py` | Azure client factory |
| `tests/test_fflitellm_client.py` | Unit tests |
| `tests/test_ffai_litellm_integration.py` | Integration tests |

### Modified Files

| File | Change |
|------|--------|
| `src/orchestrator/client_registry.py` | Add LiteLLM client types to CLIENT_MAP |
| `src/Clients/FFAzureMistralSmall.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFAzureMistral.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFAzureCodestral.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFAzurePhi.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFAzureDeepSeekV3.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFMistral.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFMistralSmall.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFAnthropic.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFAnthropicCached.py` | Reimplement with caching support |
| `src/Clients/FFGemini.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFPerplexity.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/FFNvidiaDeepSeek.py` | Reimplement using FFLiteLLMClient |
| `src/Clients/__init__.py` | Export FFLiteLLMClient |
| `pyproject.toml` | Add litellm dependency |

### Unchanged Files

| File | Reason |
|------|--------|
| `src/FFAI.py` | Works with any FFAIClientBase implementation |
| `src/FFAIClientBase.py` | Interface contract unchanged |
| `src/OrderedPromptHistory.py` | History management unchanged |
| `src/PermanentHistory.py` | History management unchanged |
| `src/Clients/FFOpenAIAssistant.py` | Uses different API pattern, keep separate |
| `src/FFAzureClientBase.py` | Deprecate but keep for reference |

---

## Dependency Changes

### Add to pyproject.toml

```toml
[project.dependencies]
litellm = ">=1.0.0"
```

### Optional: Remove (after migration)

```toml
# These become optional as LiteLLM handles the API calls
# Keep for fallback or special cases
mistralai = { version = ">=1.0.0", optional = true }
anthropic = { version = ">=0.18.0", optional = true }
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LiteLLM breaking changes | Pin version, extensive testing |
| Azure-specific behavior lost | Maintain Azure factory with custom config |
| Performance regression | Benchmark before/after |
| Missing provider features | Keep original clients as fallback |

---

## Success Criteria

1. All existing tests pass with new implementation
2. FFAI wrapper requires zero changes
3. Parallel execution (clone pattern) works correctly
4. All Azure clients maintain backward compatibility
5. At least 10 new models available via LiteLLM routing
6. Retry/fallback features functional
7. **ClientRegistry recognizes LiteLLM client types**
8. **Excel orchestrator works with LiteLLM clients**
9. **Model override from config sheet works correctly**
