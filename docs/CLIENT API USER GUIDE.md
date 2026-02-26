# Client API User Guide

## Overview

The FFClients library provides a declarative context handling API wrapper for AI clients. It consists of:

- **FFAIClientBase** - Abstract base class defining the client interface
- **FFMistral / FFMistralSmall** - Concrete client implementations for Mistral AI
- **FFAI** - High-level wrapper that adds history management, context assembly, and DataFrame export

## Installation

```bash
pip install -e . --break-system-packages
```

## Quick Start

```python
from src.FFAI import FFAI
from src.Clients.FFMistralSmall import FFMistralSmall

# Create a client
client = FFMistralSmall(
    api_key="your-api-key",
    model="mistral-small-2503"
)

# Wrap with FFAI for context management
ffai = FFAI(client)

# Generate a response
response = ffai.generate_response("What is 2 + 2?")
print(response)
```

---

## Client Configuration

### FFLiteLLMClient (Recommended)

Universal client supporting 100+ LLM providers through LiteLLM. Use this for maximum flexibility and fallback support.

```python
from src.Clients.FFLiteLLMClient import FFLiteLLMClient

# Azure OpenAI
client = FFLiteLLMClient(
    model_string="azure/mistral-small-2503",
    api_key=os.getenv("AZURE_MISTRALSMALL_KEY"),
    api_base=os.getenv("AZURE_MISTRALSMALL_ENDPOINT"),
)

# Anthropic Claude
client = FFLiteLLMClient(
    model_string="anthropic/claude-3-5-sonnet-20241022",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
)

# OpenAI GPT-4
client = FFLiteLLMClient(
    model_string="openai/gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY"),
)

# With fallbacks (automatic retry on failure)
client = FFLiteLLMClient(
    model_string="anthropic/claude-3-opus-20240229",
    fallbacks=["openai/gpt-4", "azure/gpt-4"],
)
```

**Key Features:**
- Unified interface for Azure, OpenAI, Anthropic, Mistral, Gemini, Perplexity, and 100+ providers
- Automatic fallback support when primary model fails
- Model-specific defaults (max_tokens, temperature, system_instructions)
- Thread-safe cloning for parallel execution

**LiteLLM Model String Format:**

| Provider | Format | Example |
|----------|--------|---------|
| Azure | `azure/{deployment}` | `azure/mistral-small-2503` |
| OpenAI | `openai/{model}` | `openai/gpt-4o` |
| Anthropic | `anthropic/{model}` | `anthropic/claude-3-5-sonnet-20241022` |
| Mistral | `mistral/{model}` | `mistral/mistral-small-latest` |
| Gemini | `gemini/{model}` | `gemini/gemini-1.5-pro` |
| Perplexity | `perplexity/{model}` | `perplexity/llama-3.1-sonar-large-128k-online` |

**Environment Variables:**

| Variable | Description |
|----------|-------------|
| `LITELLM_API_KEY` | Default API key |
| `AZURE_{MODEL}_KEY` | Azure model-specific key |
| `AZURE_{MODEL}_ENDPOINT` | Azure endpoint |
| `ANTHROPIC_API_KEY` | Anthropic key |
| `OPENAI_API_KEY` | OpenAI key |
| `MISTRAL_API_KEY` | Mistral key |

### FFMistralSmall

Optimized for Mistral Small models with extended context windows.

```python
from src.Clients.FFMistralSmall import FFMistralSmall

client = FFMistralSmall(
    api_key="your-api-key",           # Or set MISTRALSMALL_KEY env var
    model="mistral-small-2503",       # Default
    temperature=0.8,                  # Default
    max_tokens=128000,                # Default
    system_instructions="You are a helpful assistant."
)
```

**Environment Variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| `MISTRALSMALL_KEY` | API key | Required |
| `MISTRALSMALL_MODEL` | Model name | mistral-small-2503 |
| `MISTRALSMALL_TEMPERATURE` | Temperature | 0.8 |
| `MISTRALSMALL_MAX_TOKENS` | Max tokens | 128000 |
| `MISTRALSMALL_SYSTEM_INSTRUCTIONS` | System prompt | (default message) |

### FFMistral

Standard Mistral client for large models.

```python
from src.Clients.FFMistral import FFMistral

client = FFMistral(
    api_key="your-api-key",           # Or set MISTRAL_API_KEY env var
    model="mistral-large-latest",     # Default
    temperature=0.8,                  # Default
    max_tokens=4096,                  # Default
    system_instructions="You are a helpful assistant."
)
```

**Environment Variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| `MISTRAL_API_KEY` | API key | Required |
| `MISTRAL_MODEL` | Model name | mistral-large-latest |
| `MISTRAL_TEMPERATURE` | Temperature | 0.8 |
| `MISTRAL_MAX_TOKENS` | Max tokens | 4096 |
| `MISTRAL_SYSTEM_INSTRUCTIONS` | System prompt | (default message) |

---

## Client Methods

### generate_response()

Generate a response from the AI model.

```python
response = client.generate_response(
    prompt="What is machine learning?",
    model="mistral-small-2503",       # Optional override
    system_instructions="Be concise.", # Optional override
    temperature=0.5,                  # Optional override
    max_tokens=1000,                  # Optional override
    response_format={"type": "json_object"},  # JSON mode
    stop=["END"],                     # Stop sequences
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | str | User's input text (required) |
| `model` | str | Model to use (overrides default) |
| `system_instructions` | str | System prompt (overrides default) |
| `temperature` | float | Randomness control (0-2) |
| `max_tokens` | int | Maximum tokens to generate |
| `response_format` | dict | `{"type": "json_object"}` for JSON mode |
| `stop` | list | Stop sequences |
| `tools` | list | Tool definitions for function calling |
| `tool_choice` | str | Tool selection strategy |

### FFLiteLLMClient-Specific Features

**Fallback Support:**

```python
client = FFLiteLLMClient(
    model_string="anthropic/claude-3-opus-20240229",
    fallbacks=["openai/gpt-4", "azure/gpt-4"],
)

# If claude-3-opus fails, automatically tries gpt-4, then azure/gpt-4
response = client.generate_response("Hello!")
```

**Model Override:**

```python
client = FFLiteLLMClient(model_string="azure/mistral-small-2503")

# Override to different deployment (keeps azure/ prefix)
response = client.generate_response("Hello!", model="mistral-large-2411")
# Calls: azure/mistral-large-2411
```

**API Parameters:**

```python
client = FFLiteLLMClient(
    model_string="azure/mistral-small-2503",
    api_key=os.getenv("AZURE_KEY"),
    api_base=os.getenv("AZURE_ENDPOINT"),
    api_version="2024-02-01",
)
```

### Conversation Management

```python
# Get conversation history
history = client.get_conversation_history()

# Set conversation history
client.set_conversation_history([
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
])

# Clear conversation
client.clear_conversation()

# Clone client (creates fresh instance with empty history)
new_client = client.clone()
```

### Client Cloning

The `clone()` method creates a fresh client instance with the same configuration but empty conversation history. This is essential for parallel execution scenarios where each thread needs isolated state.

```python
# Original client with conversation history
client = FFMistralSmall(api_key="...")
client.generate_response("Hello")  # History now has 1 turn

# Clone creates isolated instance
isolated = client.clone()  # Empty history, same config
isolated.generate_response("Hi")  # Independent conversation
```

**Use Cases:**
- Parallel prompt execution
- Isolated conversation contexts
- Thread-safe client instances

### Connection Testing

```python
if client.test_connection():
    print("Connection successful!")
else:
    print("Connection failed")
```

---

## FFAI Wrapper

The `FFAI` class wraps any client and adds powerful context management features.

### Basic Usage

```python
from src.FFAI import FFAI
from src.Clients.FFMistralSmall import FFMistralSmall

client = FFMistralSmall(api_key="...")
ffai = FFAI(client)

# Simple response
response = ffai.generate_response("Hello!")
```

### Named Prompts

Assign names to prompts for later reference:

```python
response = ffai.generate_response(
    "What is 2 + 2?",
    prompt_name="math"
)

response = ffai.generate_response(
    "How are you?",
    prompt_name="greeting"
)
```

### Declarative Context (History)

Reference previous prompts by name to include them as context:

```python
response = ffai.generate_response(
    "What was my math question about?",
    prompt_name="followup",
    history=["math", "greeting"]  # Includes these in context
)
```

The system automatically assembles the context:

```
<conversation_history>
<interaction prompt_name='math'>
USER: What is 2 + 2?
SYSTEM: The sum of 2 + 2 is 4.
</interaction>
<interaction prompt_name='greeting'>
USER: How are you?
SYSTEM: I'm functioning well, thank you!
</interaction>
</conversation_history>
===
Based on the conversation history above, please answer: What was my math question about?
```

### Persistence

```python
ffai = FFAI(
    client,
    persist_dir="./data",      # Directory for saved data
    persist_name="session1",   # Base name for files
    auto_persist=True          # Auto-save on DataFrame operations
)

# Manually persist all histories
ffai.persist_all_histories()
```

---

## History Access

### Raw History

```python
# List of interaction dictionaries
history = ffai.get_interaction_history()
clean_history = ffai.get_clean_interaction_history()  # Cleaned responses
attr_history = ffai.get_prompt_attr_history()  # JSON attributes extracted
```

### Ordered History

```python
# Get all interactions in sequence order
all_interactions = ffai.get_all_interactions()

# Get last N interactions
last_5 = ffai.get_last_n_interactions(5)

# Get specific interaction by sequence
interaction = ffai.get_interaction(sequence_number=3)

# Get interactions by model
model_interactions = ffai.get_model_interactions("mistral-small-2503")

# Get interactions by prompt name
named_interactions = ffai.get_interactions_by_prompt_name("math")
```

### Latest Responses

```python
# Get latest interaction for a prompt name
latest = ffai.get_latest_interaction_by_prompt_name("math")

# Get latest responses for multiple prompt names
responses = ffai.get_latest_responses_by_prompt_names(["math", "greeting"])

# Get formatted string output
formatted = ffai.get_formatted_responses(["math", "greeting"])
# Output: <prompt:What is 2 + 2?>The sum of 2 + 2 is 4.</prompt:What is 2 + 2?>
```

---

## DataFrame Export

Convert history to Polars DataFrames for analysis:

```python
# Convert to DataFrames
df = ffai.history_to_dataframe()
clean_df = ffai.clean_history_to_dataframe()
ordered_df = ffai.ordered_history_to_dataframe()
attr_df = ffai.prompt_attr_history_to_dataframe()

# Search history
results = ffai.search_history(
    text="math",              # Search in prompts/responses
    prompt_name="greeting",   # Filter by name
    model="mistral-small-2503",  # Filter by model
)

# Statistics
model_stats = ffai.get_model_usage_stats()
prompt_stats = ffai.get_prompt_name_usage_stats()
date_counts = ffai.interaction_counts_by_date()
```

---

## Client Conversation History

Access the raw conversation history from the underlying client:

```python
# Get raw history (format depends on client)
raw_history = ffai.get_client_conversation_history()

# Set raw history
ffai.set_client_conversation_history([
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hi"},
])

# Add a single message
ffai.add_client_message("user", "Hello again")
```

---

## Switching Clients

```python
from src.Clients.FFMistral import FFMistral
from src.Clients.FFMistralSmall import FFMistralSmall

# Start with one client
ffai = FFAI(FFMistralSmall(api_key="..."))

# Switch to another client (history preserved)
ffai.set_client(FFMistral(api_key="..."))
```

---

## Error Handling

```python
try:
    response = ffai.generate_response("Hello")
except RuntimeError as e:
    print(f"API error: {e}")
except ValueError as e:
    print(f"Invalid input: {e}")
```

---

## Full Example

```python
import os
from dotenv import load_dotenv
from src.FFAI import FFAI
from src.Clients.FFMistralSmall import FFMistralSmall

load_dotenv()

# Initialize
client = FFMistralSmall(
    api_key=os.getenv("MISTRALSMALL_KEY"),
    model="mistral-small-2503",
    temperature=0.7
)

ffai = FFAI(client, persist_dir="./data", persist_name="demo")

# Execute prompts with declarative context
ffai.generate_response("My name is Alice.", prompt_name="intro")
ffai.generate_response("I like pizza.", prompt_name="food")
ffai.generate_response(
    "What do you know about me based on our conversation?",
    prompt_name="recall",
    history=["intro", "food"]
)

# Export to DataFrame
df = ffai.ordered_history_to_dataframe()
print(df)

# Persist
ffai.persist_all_histories()
```

---

## Logging

The library uses Python's standard logging. Enable debug output:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or for specific modules:

```python
logging.getLogger("src.FFAI").setLevel(logging.DEBUG)
logging.getLogger("src.Clients").setLevel(logging.INFO)
```
