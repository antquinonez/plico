# Configuration System

## Overview

Plico uses a centralized configuration system built on `pydantic-settings`. Configuration is loaded from YAML files in the `config/` directory with type-safe access, environment variable overrides, and runtime validation.

## Configuration Files

```
config/
├── main.yaml          # Core app settings (workbook, orchestrator, retry, document processor, RAG)
├── logging.yaml       # Logging configuration
├── paths.yaml         # File system paths
├── clients.yaml       # AI client configurations
├── model_defaults.yaml # Per-model default parameters
└── sample_workbook.yaml # Test workbook defaults and paths
```

## Usage

### Basic Access

```python
from src.config import get_config

config = get_config()

# Access configuration values
print(config.workbook.defaults.model)           # "mistral-small-2503"
print(config.orchestrator.default_concurrency)   # 2
print(config.paths.ffai_data)                    # "./ffai_data"
print(config.test.workbooks.basic)               # "./sample_workbook.xlsx"
```

### Reload Configuration

```python
from src.config import reload_config

# Reload from files (useful after config file changes)
config = reload_config()
```

### Get Client Configuration

```python
from src.config import get_config

config = get_config()

# Get named client configuration
client_config = config.get_client_config("litellm-mistral")
if client_config:
    print(client_config.model)       # "mistral-small-latest"
    print(client_config.api_key_env) # "MISTRALSMALL_KEY"
```

### Get API Key

```python
from src.config import get_config

config = get_config()

# Get API key (checks direct key first, then environment variable)
api_key = config.get_api_key("litellm-mistral")
```

## Configuration Sections

### Workbook Configuration (`main.yaml`)

```yaml
workbook:
  sheet_names:
    config: "config"
    prompts: "prompts"
    data: "data"
    clients: "clients"
    documents: "documents"
  defaults:
    model: "mistral-small-2503"
    api_key_env: "MISTRALSMALL_KEY"
    max_retries: 3
    temperature: 0.8
    max_tokens: 4096
    system_instructions: "You are a helpful assistant..."
  batch:
    mode: "per_row"
    output: "combined"
    on_error: "continue"
```

### Orchestrator Configuration (`main.yaml`)

```yaml
orchestrator:
  default_concurrency: 2
  max_concurrency: 10
```

| Field | Description |
|-------|-------------|
| `default_concurrency` | Default concurrency for parallel execution |
| `max_concurrency` | Maximum concurrent threads |

### Paths Configuration (`paths.yaml`)

```yaml
paths:
  ffai_data: "./ffai_data"
  doc_cache: "doc_cache"
  library: "library"
  output_dir: "./outputs"
  manifest_dir: "./manifests"
```

| Path | Description |
|------|-------------|
| `ffai_data` | FFAI persistence data storage |
| `doc_cache` | Document processing cache (parquet files) |
| `library` | Document library for references |
| `output_dir` | Parquet output directory for manifest orchestration |
| `manifest_dir` | Manifest folder storage for workbook exports |

### Logging Configuration (`logging.yaml`)

```yaml
logging:
  directory: "logs"
  filename: "orchestrator.log"
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  rotation:
    when: "midnight"
    interval: 1
    backup_count: 10
```

### RAG Configuration (`main.yaml`)

The RAG system supports multiple chunking strategies, hybrid search, and hierarchical indexing.

```yaml
rag:
  enabled: true
  persist_dir: "./chroma_db"
  collection_name: "plico_kb"
  embedding_model: "mistral/mistral-embed"
  local_embeddings: false
  embedding_cache_size: 256
  generate_summaries: false
  chunk_size: 1000
  chunk_overlap: 200
  n_results_default: 5

  # Chunking strategy configuration
  chunking:
    strategy: "recursive"        # recursive, markdown, code, hierarchical, character
    chunk_size: 1000
    chunk_overlap: 200
    contextual_headers: true       # Prepend document context to chunks
    dedup_enabled: false           # Enable chunk deduplication
    dedup_mode: "exact"             # or "similarity"
    # Strategy-specific options:
    markdown:
      split_headers: ["h1", "h2", "h3"]
      preserve_structure: true
      max_chunk_fallback: true
    code:
      language: "python"
      split_by: "function"
    hierarchical:
      parent_chunk_size: 1500

  # Search configuration
  search:
    mode: "vector"               # vector, hybrid
    n_results_default: 5
    hybrid_alpha: 0.6            # Vector weight for hybrid (0.0-1.0)
    rerank: false                # Enable post-retrieval reranking
    rerank_model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
    query_expansion: false        # Enable multi-query retrieval
    query_expansion_variations: 3 # Number of query variations
    summary_boost: 1.5           # Boost for summary chunk matches

  # Hierarchical indexing
  hierarchical:
    enabled: false
    parent_context: true         # Include parent chunks in results
    parent_chunk_size: 1500
    levels: 2
```

#### Chunking Strategies

| Strategy | Best For | Description |
|----------|----------|-------------|
| `recursive` | General text | Hierarchical separator splitting (default) |
| `markdown` | Documentation | Header-aware, preserves section structure |
| `code` | Source code | Language-specific, function/class boundaries |
| `hierarchical` | Long documents | Parent-child with context retrieval |
| `character` | Simple text | Word-boundary aware fixed-size chunks |

#### Search Modes

| Mode | Description |
|------|-------------|
| `vector` | Pure semantic similarity search |
| `bm25` | Sparse keyword matching only |
| `hybrid` | Combines vector + BM25 with Reciprocal Rank Fusion |

### Client Configuration (`clients.yaml`)

The client configuration defines available client types with their API keys and default models.

```yaml
default_client: "litellm-mistral-small"

client_types:
  # ===========================================
  # NATIVE CLIENTS (Direct API, no LiteLLM)
  # ===========================================
  mistral-small:
    client_class: "FFMistralSmall"
    type: "native"
    api_key_env: "MISTRALSMALL_KEY"
    default_model: "mistral-small-2503"

  anthropic:
    client_class: "FFAnthropic"
    type: "native"
    api_key_env: "ANTHROPIC_API_KEY"
    default_model: "claude-3-5-sonnet-20241022"

  gemini:
    client_class: "FFGemini"
    type: "native"
    api_key_env: "GEMINI_API_KEY"
    default_model: "gemini-1.5-pro"

  # ===========================================
  # LITELLM CLIENTS (via LiteLLM routing)
  # ===========================================
  litellm-mistral-small:
    client_class: "FFLiteLLMClient"
    type: "litellm"
    provider_prefix: "mistral/"
    api_key_env: "MISTRAL_API_KEY"
    default_model: "mistral-small-latest"

  litellm-anthropic:
    client_class: "FFLiteLLMClient"
    type: "litellm"
    provider_prefix: "anthropic/"
    api_key_env: "ANTHROPIC_API_KEY"
    default_model: "claude-3-5-sonnet-20241022"

  litellm-gpt-4o:
    client_class: "FFLiteLLMClient"
    type: "litellm"
    provider_prefix: "openai/"
    api_key_env: "OPENAI_API_KEY"
    default_model: "gpt-4o"

  # ... 50+ more client types (see config/clients.yaml.example)
```

Each client type has:

| Field | Description |
|-------|-------------|
| `client_class` | Python class (e.g., `FFMistralSmall`, `FFLiteLLMClient`) |
| `type` | `native` for direct API, `litellm` for routing |
| `api_key_env` | Environment variable name for API key |
| `provider_prefix` | LiteLLM provider prefix (`litellm` type only) |
| `default_model` | Default model identifier |

**All clients include automatic retry** with exponential backoff for rate limits (429) and service unavailability (503) errors. See Retry Configuration section below.

See `config/clients.yaml.example` for the full list of 50+ client types across Mistral, Anthropic, OpenAI, Gemini, Azure, and more.

### Retry Configuration (`main.yaml`)

The retry system handles transient failures like rate limits (429 errors) and service unavailability (503) errors with exponential backoff.

```yaml
retry:
  max_attempts: 3              # Maximum retry attempts
  min_wait_seconds: 1          # Minimum initial wait time
  max_wait_seconds: 60         # Maximum wait time cap
  exponential_base: 2          # Backoff multiplier (2x each retry)
  exponential_jitter: true     # Add randomness to prevent thundering herd
  retry_on_status_codes:       # HTTP codes to retry
    - 429                      # Rate limit
    - 503                      # Service unavailable
    - 502                      # Bad gateway
    - 504                      # Gateway timeout
  log_level: "info"             # Logging level for retry attempts
```

**Configuration fields:**

| Field | Type | Description |
|-------|------|-------------|
| `max_attempts` | int | Maximum retry attempts (default: 3) |
| `min_wait_seconds` | float | Minimum initial wait time (default: 1s) |
| `max_wait_seconds` | float | Maximum wait time cap (default: 60s) |
| `exponential_base` | float | Backoff multiplier (default: 2) |
| `exponential_jitter` | bool | Add randomness to prevent thundering herd (default: `true`) |
| `retry_on_status_codes` | list | HTTP codes to retry (default: [429, 503, 502, 504]) |
| `log_level` | str | Logging level for retry attempts (default: `INFO`) |

**Retry behavior:**

When a rate limit or transient error occurs:
1. **Detection**: Client detects retryable error (429, 503, network timeout)
2. **extraction**: Parses `retry-after` header if present
3. **backoff**: Waits with exponential backoff + jitter
4. **retry**: Retries the API call up to `max_attempts`
5. **logging**: Each retry attempt is logged with delay duration
6. **result**: If all attempts fail, the request fails gracefully

**Example log output:**
```
2026-03-04 18:05:00 - Rate limit hit. Retrying in 59.1s delay
2026-03-04 18:06:00 - Rate limit hit. Retrying in 2.5s delay
2026-03-04 18:07:00 - All retries exhausted
```

**Tips:**
- Start with default settings (3 retries, 1-60s backoff)
- For rate-limited APIs (e.g., Gemini free tier: 10-20 requests/minute), reduce concurrency
- For free tier quotas, lower concurrency or use LiteLLM client (has built-in retry)
- Wait 60s between runs to resets quota

### Model Defaults (`model_defaults.yaml`)

```yaml
model_defaults:
  generic:
    max_tokens: 4096
    temperature: 0.7
    system_instructions: "You are a helpful assistant..."

  models:
    mistral-small-latest:
      max_tokens: 128000
      temperature: 0.7
    claude-3-5-sonnet:
      max_tokens: 8192
      temperature: 0.7
```

### Test Configuration (`sample_workbook.yaml`)

```yaml
sample_workbooks:
  default_model: "mistral-small-latest"
  default_temperature: 0.7
  default_max_tokens: 300
  default_retries: 2
  default_system_instructions: "You are a helpful assistant..."
  output_dir: "."
  workbooks:
    basic: "./sample_workbook.xlsx"
    multiclient: "./sample_workbook_multiclient.xlsx"
    conditional: "./sample_workbook_conditional.xlsx"
    documents: "./sample_workbook_documents.xlsx"
    batch: "./sample_workbook_batch.xlsx"
    max: "./sample_workbook_max.xlsx"
  sample_clients:
    default:
      client_type: "litellm-mistral"
      api_key_env: "MISTRAL_API_KEY"
      model: "mistral-small-latest"
      temperature: 0.7
      max_tokens: 300
    fast:
      client_type: "litellm-mistral"
      api_key_env: "MISTRAL_API_KEY"
      model: "mistral-small-latest"
      temperature: 0.3
      max_tokens: 100
    creative:
      client_type: "litellm-mistral"
      api_key_env: "MISTRAL_API_KEY"
      model: "mistral-small-latest"
      temperature: 0.9
      max_tokens: 500
    analytical:
      client_type: "litellm-mistral"
      api_key_env: "MISTRAL_API_KEY"
      model: "mistral-small-latest"
      temperature: 0.2
      max_tokens: 400
```

**Sample client types:**

| Client | Temperature | Max Tokens | Purpose |
|--------|-------------|------------|---------|
| `default` | 0.7 | 300 | General processing |
| `fast` | 0.3 | 100 | Classification, yes/no, simple extraction |
| `creative` | 0.9 | 500 | Generative, expansive responses |
| `analytical` | 0.2 | 400 | Analysis, structured responses |

## Environment Variable Overrides

All configuration values can be overridden with environment variables using uppercase names with double underscores as separators:

```bash
# Override orchestrator concurrency
export ORCHESTRATOR__DEFAULT_CONCURRENCY=4

# Override workbook default model
export WORKBOOK__DEFAULTS__MODEL="claude-3-5-sonnet"

# Override path
export PATHS__FFAI_DATA="/custom/path"
```

## Type-Safe Access

The configuration system uses Pydantic models for type safety:

```python
from src.config import get_config

config = get_config()

# These are type-checked
concurrency: int = config.orchestrator.default_concurrency  # int
model: str = config.workbook.defaults.model                  # str
temperature: float = config.workbook.defaults.temperature    # float
```

## Adding New Configuration

### 1. Add to YAML File

```yaml
# config/main.yaml
my_feature:
  enabled: true
  threshold: 100
```

### 2. Add Pydantic Model

```python
# src/config.py

class MyFeatureConfig(BaseSettings):
    """My feature configuration."""
    enabled: bool = True
    threshold: int = 100


class Config(BaseSettings):
    # ... existing fields ...
    my_feature: MyFeatureConfig = Field(default_factory=MyFeatureConfig)
```

### 3. Update Loader

```python
# src/config.py

def _load_all_configs() -> dict[str, Any]:
    return {
        # ... existing loads ...
        "my_feature": _load_yaml_file("main.yaml").get("my_feature", {}),
    }
```

## Configuration Priority

Configuration values are resolved in this order (highest priority first):

1. **Init arguments** - Values passed directly to `Config()`
2. **Environment variables** - `SECTION__KEY` format (12-factor app methodology)
3. **YAML files** - Values from `config/*.yaml` (committed defaults)
4. **Pydantic defaults** - Fallback values in model classes

## Example: Custom Configuration

```python
from src.config import Config, get_config

# Custom configuration instance
config = Config(
    orchestrator={"default_concurrency": 5},
    workbook={"defaults": {"model": "gpt-4o"}}
)

print(config.orchestrator.default_concurrency)  # 5
print(config.workbook.defaults.model)           # "gpt-4o"

# Or use global instance
global_config = get_config()
```
