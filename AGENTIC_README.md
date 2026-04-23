# Agentic Execution in Plico

Plico prompts can now use tools. A prompt flagged with `agent_mode=true` runs a multi-turn loop: the LLM sees available tools, calls them, receives results, and continues until it has a final answer or hits a round limit.

This is fully backward-compatible. Existing prompts work identically. Agent mode is opt-in per prompt.

---

## Single-Shot vs. Agentic

**Before:** Each prompt was one LLM call. No tool use, no iteration.

```
Prompt  ──────►  LLM  ──────►  Response
```

**Now:** A prompt in agent mode runs a tool-call loop. The LLM decides whether to call a tool, and the loop continues until it's done.

```
Prompt ──►  LLM  ──►  [no tool call] ──►  Response
                │
                └── [tool call] ──► Execute ──► LLM ──► ... ──► Response
```

The DAG, conditions, batches, and multi-client routing all work the same. The only difference is the execution path for that single prompt.

---

## Built-in Tools

Six tools ship with Plico. They're available to any agent-mode prompt without additional configuration.

| Tool | What it does | Requires |
|------|-------------|----------|
| `calculate` | Evaluate math expressions safely (`2 ** 10 + 5`) | Nothing |
| `json_extract` | Extract fields from JSON via dot-notation (`data.items.0.name`) | Nothing |
| `http_get` | Fetch text content from a URL | Nothing |
| `rag_search` | Semantic search across indexed documents | RAG index |
| `read_document` | Read the full content of a registered document | `documents.yaml` |
| `list_documents` | List all registered document names | `documents.yaml` |

Custom Python callables can also be registered via `python:<module.func>` in `tools.yaml`.

---

## Manifest-Based Examples

### Example 1: Research + Calculate

A prompt that researches data, then uses the calculator to produce a precise numeric answer.

```yaml
# prompts.yaml
prompts:
  - sequence: 1
    prompt_name: intro
    prompt: "I run a coffee shop. Average order is $4.50, 50 customers/day, 6 days/week."
    history: []

  - sequence: 2
    prompt_name: revenue_analysis
    prompt: |
      Based on the coffee shop data, search for current wholesale coffee prices,
      then calculate the annual revenue and weekly gross profit if COGS is 35%.
      Show your work step by step using the calculator.
    history: ["intro"]
    agent_mode: true
    tools: ["rag_search", "calculate"]

  - sequence: 3
    prompt_name: summary
    prompt: "Summarize the revenue analysis in a short business memo."
    history: ["revenue_analysis"]
    condition: '{{revenue_analysis.status}} == "success"'
```

The LLM decides whether and when to call `rag_search` and `calculate`. The result includes tool call records for audit.

### Example 2: Document Q&A with RAG

Instead of pre-baking a semantic query, let the LLM decide what to search for.

```yaml
# documents.yaml
documents:
  - reference_name: product_spec
    common_name: "Product Specification"
    file_path: "./library/product_spec.md"

# prompts.yaml
prompts:
  - sequence: 1
    prompt_name: answer_question
    prompt: |
      A customer asks: "What are the SLA guarantees for the API?"
      Search the documentation, find the answer, and respond clearly.
    agent_mode: true
    tools: ["rag_search", "read_document"]
```

Single-shot equivalent would require the author to guess the right `semantic_query` upfront. With agent mode, the LLM formulates its own queries and reads relevant sections iteratively.

### Example 3: Multi-Step Analysis with JSON

A prompt that extracts structured data and then works with it.

```yaml
prompts:
  - sequence: 1
    prompt_name: extract
    prompt: |
      Extract the revenue, expenses, and net_income from this text
      and return them as a JSON object.

      "In Q3 2025, revenue was $2.4M, expenses were $1.8M, yielding net income of $600K."
    agent_mode: true
    tools: ["json_extract"]

  - sequence: 2
    prompt_name: analyze
    prompt: |
      Previous extraction: {{extract.response}}

      Calculate the profit margin and growth rate if Q2 net income was $450K.
      Comment on the trend.
    history: ["extract"]
    agent_mode: true
    tools: ["json_extract", "calculate"]
```

### Example 4: Full Agent Workflow with Tools Sheet

Define custom tools alongside the built-ins.

```yaml
# tools.yaml
tools:
  - name: customer_lookup
    description: "Look up a customer by ID and return their details."
    parameters:
      type: object
      properties:
        customer_id:
          type: string
          description: "The customer ID to look up."
      required: ["customer_id"]
    implementation: "python:my_tools.customer_lookup"
    enabled: true

  - name: calculate
    description: "Evaluate a mathematical expression safely."
    parameters:
      type: object
      properties:
        expression:
          type: string
          description: "Math expression (e.g., '2 + 3 * 4')"
      required: ["expression"]
    implementation: "builtin:calculate"
    enabled: true

# prompts.yaml
prompts:
  - sequence: 1
    prompt_name: lookup
    prompt: "Look up customer C-1234 and retrieve their order history."
    agent_mode: true
    tools: ["customer_lookup"]

  - sequence: 2
    prompt_name: compute
    prompt: |
      Customer data: {{lookup.response}}

      Calculate the total order value and average order size.
    history: ["lookup"]
    agent_mode: true
    tools: ["calculate"]

  - sequence: 3
    prompt_name: report
    prompt: "Write a customer profile summary."
    history: ["lookup", "compute"]
```

---

## Agent-Aware Conditions

Downstream prompts can inspect agent results in their condition expressions.

**Available agent properties:**

| Property | Type | Example |
|----------|------|---------|
| `agent_mode` | `bool` | `{{research.agent_mode}} == True` |
| `tool_calls_count` | `int` | `{{research.tool_calls_count}} > 0` |
| `total_rounds` | `int` | `{{research.total_rounds}} <= 3` |
| `total_llm_calls` | `int` | `{{research.total_llm_calls}} <= 5` |
| `last_tool_name` | `str` | `{{research.last_tool_name}} == "rag_search"` |

```yaml
prompts:
  - sequence: 1
    prompt_name: research
    prompt: "Research the topic thoroughly using the available tools."
    agent_mode: true
    tools: ["rag_search", "http_get"]

  - sequence: 2
    prompt_name: shallow
    prompt: "Provide a brief overview."
    history: ["research"]
    condition: '{{research.tool_calls_count}} == 0'

  - sequence: 3
    prompt_name: deep
    prompt: "Provide a comprehensive analysis."
    history: ["research"]
    condition: '{{research.tool_calls_count}} > 0'
```

---

## Configuration

### config/main.yaml

```yaml
agent:
  enabled: true               # Master toggle
  max_tool_rounds: 5           # Max tool-call loop rounds
  tool_timeout: 30.0           # Seconds per tool execution
  continue_on_tool_error: true # Continue loop if a tool fails
  validation:
    enabled: true              # Enable response validation
    max_retries: 2             # Max re-execution attempts on validation failure
```

### Per-Prompt Overrides

```yaml
prompts:
  - sequence: 1
    prompt_name: deep_research
    prompt: "Research extensively."
    agent_mode: true
    tools: ["rag_search", "http_get", "calculate"]
    max_tool_rounds: 10        # Override global setting
```

### Prompt Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent_mode` | `bool` | `false` | Enable agentic tool-call loop |
| `tools` | `list[str]` | `[]` | Tool names to make available |
| `max_tool_rounds` | `int` | From config | Override max rounds for this prompt |
| `validation_prompt` | `str` | `null` | Criteria for response validation (requires `agent_mode: true`) |
| `max_validation_retries` | `int` | From config | Override max validation retry attempts |
| `abort_condition` | `str` | `null` | Post-execution condition; if true, aborts remaining prompts in scope |

### Result Columns

Agent-mode prompts produce additional columns in the output parquet:

| Column | Type | Description |
|--------|------|-------------|
| `agent_mode` | `bool` | Whether agent mode was used |
| `tool_calls` | `list[dict]` | Tool call records (name, arguments, result, duration_ms, error) |
| `total_rounds` | `int` | Agentic loop rounds executed |
| `total_llm_calls` | `int` | Total LLM API calls |
| `validation_passed` | `bool or null` | Whether response passed validation (`null` if validation not enabled) |
| `validation_attempts` | `int` | Number of validation attempts (0 if validation not enabled) |
| `validation_critique` | `str or null` | Rejection reason from last failed validation |
| `abort_trace` | `str or null` | Trace of abort condition evaluation (if abort triggered) |

---

## Execution Flow

```
                           ┌─────────────────────┐
                           │  Manifest Parser    │
                           │  (tools.yaml)        │
                           └──────────┬──────────┘
                                      │
                           ┌──────────▼──────────┐
                           │  Tool Registry      │
                           │                     │
                           │  Register builtins   │
                           │  Register customs    │
                           │  Bind executors     │
                           └──────────┬──────────┘
                                      │
               agent_mode=false          │          agent_mode=true
                     │                   │                │
                     ▼                   ▼                ▼
               ┌──────────┐        ┌────────────────────────────────┐
               │  LLM call │        │         Agent Loop             │
               │  (1 shot) │        │                                │
               └────┬─────┘        │  ┌──────────────────────────┐  │
                    │               │  │  LLM + tools schema      │  │
                    │               │  └────────────┬─────────────┘  │
                    │               │               │                │
                    │               │        no tool calls          │
                    │               │               │                │
                    │               │               ▼                │
                    │               │  ┌──────────────────────────┐  │
                    │               │  │  Response                │  │
                    │               │  └──────────────────────────┘  │
                    │               │                                │
                    │               │        tool calls detected     │
                    │               │               │                │
                    │               │               ▼                │
                    │               │  ┌──────────────────────────┐  │
                    │               │  │  Execute each tool       │  │
                    │               │  │  Feed results back       │  │
                    │               │  └────────────┬─────────────┘  │
                    │               │               │                │
                    │               │          repeat loop          │
                    │               │               │                │
                    │               └───────────────┘                │
                    │                                     │
                    │                              no more tools
                    │                                     │
                    ▼                                     ▼
               ┌──────────────────────────────────────────────┐
               │              AgentResult                   │
               │  response + tool_calls + rounds + status   │
               └──────────────────────────────────────────────┘
```

---

## Response Validation

Agent-mode prompts can opt into response validation — an automated quality gate that re-executes the agent loop if the response doesn't meet criteria.

### How It Works

1. After the agent loop completes, a separate validator LLM (isolated, `temperature=0.1`) evaluates the response against your `validation_prompt` criteria.
2. The validator replies with `PASS` or `FAIL: <reason>`.
3. On `FAIL`, the entire agent loop is re-executed with an augmented prompt that includes the rejected response and the failure reason.
4. This repeats up to `max_validation_retries + 1` total attempts (default: 3).
5. Results are recorded in `validation_passed`, `validation_attempts`, and `validation_critique`.

### Example

```yaml
# prompts.yaml
prompts:
  - sequence: 1
    prompt_name: calculate_result
    prompt: "Calculate 2 + 3 * 4 using the available tools."
    agent_mode: true
    tools: ["calculate"]
    validation_prompt: "The final response must be exactly the digits 14."
    max_validation_retries: 2
```

### Configuration

Global defaults in `config/main.yaml`:

```yaml
agent:
  validation:
    enabled: true       # Set false to skip validation even if validation_prompt is set
    max_retries: 2      # Max re-execution attempts (3 total = 1 initial + 2 retries)
```

Per-prompt override: `max_validation_retries` field on the prompt entry.

> **Note:** `validation_prompt` requires `agent_mode: true`. Setting `validation_prompt` without agent mode triggers a validation warning.

---

## Abort Conditions

Any prompt (agent mode or single-shot) can define an `abort_condition` — a post-execution expression that, when true, short-circuits all remaining prompts in the current scope.

Unlike `condition` (evaluated *before* execution to decide whether to run), `abort_condition` is evaluated *after* a prompt succeeds. If it evaluates to true, all remaining prompts are set to `status: "aborted"` with a configurable default response.

### Example

```yaml
prompts:
  - sequence: 10
    prompt_name: gate_evaluation
    prompt: |
      Quick screening: does this candidate meet minimum requirements?
      Return JSON: {"proceed": true/false, "reason": "..."}
    agent_mode: true
    tools: ["json_extract"]
    abort_condition: 'json_get({{gate_evaluation.response}}, "proceed") == False'

  - sequence: 20
    prompt_name: detailed_evaluation
    prompt: "Evaluate this candidate in depth."
    # This prompt is aborted if gate_evaluation's abort_condition triggers
```

### Status Values

| Status | Description |
|--------|-------------|
| `success` | Prompt executed successfully |
| `failed` | Prompt execution failed (after retries) |
| `skipped` | Pre-execution `condition` evaluated to false |
| `aborted` | Upstream `abort_condition` triggered; prompt not executed |

### Configuration

The default response for aborted prompts is configured in `config/main.yaml`:

```yaml
orchestrator:
  abort:
    response_default: "-1"
```

---

## When to Use Agent Mode

| Scenario | Agent Mode | Single-Shot |
|----------|-----------|-------------|
| Fixed question, known context | No benefit | Use single-shot |
| Need to search documents dynamically | Use `rag_search` tool | Use `semantic_query` |
| Multi-step calculation | Use `calculate` tool | Use a single complex prompt |
| Fetch live data from URLs | Use `http_get` tool | N/A (not possible) |
| Extract then transform JSON | Use `json_extract` tool | Use a single detailed prompt |
| Mix of the above | Use multiple tools | Multiple chained prompts |
| Quality gate on response | Use `validation_prompt` | Manual review |

**Rule of thumb:** Use agent mode when the LLM needs to decide *which* tools to use and *when*. Use `validation_prompt` when the response must meet specific criteria. Use `abort_condition` when a prompt's result should short-circuit downstream work. Use single-shot prompts when you already know the shape of the request.
