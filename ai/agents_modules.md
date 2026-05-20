# Module Documentation

Extracted from [AGENTS.md](../AGENTS.md). Read this for details on rate limiting, agent mode, planning phase, observability, and evaluation modules.

## Rate Limiting and Retries

The FFClients library implements a **layered retry strategy** to handle transient failures like rate limits (429 errors), service unavailability (503), and network issues.

### Architecture

The retry system operates at two layers:

1. **LiteLLM Layer** (FFLiteLLMClient): Uses LiteLLM's built-in retry mechanism
2. **Client Layer** (All clients): Uses tenacity decorators for exponential backoff with jitter

### Configuration

Configure retry behavior globally in `config/main.yaml`:

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
  log_level: "INFO"            # Logging level for retry attempts
```

### Retry Behavior

When a rate limit or transient error occurs:

1. **Detection**: Client detects retryable error (429, 503, network timeout)
2. **Extraction**: Parses `retry-after` header if present
3. **Backoff**: Waits with exponential backoff + jitter
4. **Retry**: Retries the API call up to `max_attempts`
5. **Logging**: Logs each retry attempt with delay duration

Example log output:
```
INFO - Retrying generate_response for FFMistralSmall (attempt 2/3) after 2.5s delay
WARNING - Rate limit hit for gemini/gemini-2.5-flash-lite. Retry after 53.8s
```

### Wait Time Calculation

With default settings:
- Attempt 1: Immediate
- Attempt 2: Wait ~2s (1 × 2^1 + jitter)
- Attempt 3: Wait ~4s (1 × 2^2 + jitter)

If the API provides a `retry-after` header, that value is used instead.

### Client-Specific Behavior

**LiteLLM Clients** (FFLiteLLMClient):
- Uses LiteLLM's native `num_retries` configuration
- Automatic retry on 429, 503, 502, 504 status codes
- Respects `retry-after` headers from providers

**Native Clients** (FFMistralSmall, FFAnthropic, FFGemini, etc.):
- Tenacity decorator with exponential backoff
- Converts provider-specific rate limit errors to `RateLimitError`
- Shared retry configuration across all native clients

### Best Practices

1. **Start with defaults**: The default config (3 retries, 1-60s backoff) works for most APIs
2. **Adjust for rate limits**: Increase `max_attempts` to 5 for heavily rate-limited APIs
3. **Monitor logs**: Check `logs/orchestrator.log` for retry patterns
4. **Reduce concurrency**: If seeing many 429s, lower `--concurrency` flag
5. **Respect quotas**: Free tier APIs often have 10-60 requests/minute limits

### Example: Handling Gemini Rate Limits

```bash
# Gemini free tier: 10 requests/minute
# With 31 prompts, expect rate limits

# Option 1: Lower concurrency
python scripts/run_orchestrator.py workbook.xlsx --concurrency 1

# Option 2: Increase retries (edit config/main.yaml)
retry:
  max_attempts: 5
  min_wait_seconds: 2
  max_wait_seconds: 120

# Option 3: Use LiteLLM client (has built-in retry)
# In workbook config sheet:
# client_type: litellm-gemini
```

### Troubleshooting

**Problem**: Still seeing 429 errors
- Check `retry.max_attempts` in config
- Verify logs show retry attempts
- Reduce concurrency to 1
- Wait 60s between runs (resets quota)

**Problem**: Retries taking too long
- Lower `max_wait_seconds`
- Reduce `max_attempts`
- Check if `retry-after` header is very long

**Problem**: No retry logging
- Verify `log_level` is set to "INFO"
- Check that `src.retry_utils` is imported
- Ensure client has retry decorator

## Agent Module

The agent module provides opt-in agentic tool-call execution within the deterministic DAG orchestrator. Prompts can use tools like `calculate`, `json_extract`, and `http_get` via a multi-round LLM loop.

### Usage

Enable agent mode by setting `agent_mode=true` in the prompts sheet and specifying available tools:

| Column | Description |
|--------|-------------|
| `agent_mode` | Set to `true` to enable tool-call loop |
| `tools` | JSON array of tool names (e.g., `["calculate", "json_extract"]`) |
| `max_tool_rounds` | Max tool-call rounds (default from config, typically 5) |
| `validation_prompt` | Criteria for response validation (requires `agent_mode=true`) |
| `max_validation_retries` | Override max validation retry attempts (default from config: 2) |
| `abort_condition` | Post-execution condition; if true, aborts all remaining prompts in scope |

Tools are defined in a `tools` sheet with columns: `name`, `description`, `parameters` (JSON Schema), `implementation` (`builtin:<name>` or `python:<module.func>`), `enabled`.

### Built-in Tools

| Tool | Description |
|------|-------------|
| `calculate` | Evaluate math expressions safely via AST |
| `json_extract` | Extract fields from JSON using dot notation |
| `http_get` | Fetch text content from a URL |
| `rag_search` | Semantic search across indexed documents |
| `read_document` | Read a document's full content |
| `list_documents` | List available document names |

### Result Fields

Agent execution populates additional fields on the result:
- `agent_mode`: `true` if agent loop was used
- `tool_calls`: List of tool call records (name, arguments, result, duration, errors)
- `total_rounds`: Number of agentic loop rounds
- `total_llm_calls`: Total LLM API calls within the loop
- `validation_passed`: Whether response passed validation (`null` if not enabled)
- `validation_attempts`: Number of validation attempts
- `validation_critique`: Rejection reason from last failed validation
- `abort_trace`: Trace of abort condition evaluation (if abort triggered)

### Condition Properties

Conditions can reference agent result properties:
```
{{research.tool_calls_count}} > 0
{{research.total_rounds}} <= 3
{{research.last_tool_name}} == "rag_search"
{{research.agent_mode}} == True
```

### Configuration (config/main.yaml)

```yaml
agent:
  enabled: true
  max_tool_rounds: 5
  tool_timeout: 30.0
  continue_on_tool_error: true
  validation:
    enabled: true
    max_retries: 2
```

### Abort Conditions

Any prompt (agent mode or single-shot) can define `abort_condition` — a post-execution expression evaluated after the prompt succeeds. If true, all remaining prompts in scope are set to `status: "aborted"`. The abort response default is configurable: `orchestrator.abort.response_default: "-1"`.

## Planning Phase (Dynamic Prompt Generation)

The planning phase enables the orchestrator to derive scoring criteria and evaluation prompts from documents (e.g., a job description) via LLM calls, eliminating the need for a manual scoring worksheet. Planning prompts run in a dedicated phase before batch execution.

### Prompts Sheet: Planning Columns

| Column | Values | Description |
|--------|--------|-------------|
| `phase` | `planning` or `execution` (default) | Controls when the prompt runs |
| `generator` | `true` or `false` (default) | Whether the prompt returns structured JSON artifacts |

### Generator Response Schema

Generator prompts (`generator=true`) return JSON with optional `scoring_criteria` and `prompts` arrays:

```json
{
  "scoring_criteria": [
    {"criteria_name": "skills_match", "description": "...", "scale_min": 1, "scale_max": 10, "weight": 1.0, "source_prompt": "evaluate_skills"}
  ],
  "prompts": [
    {"prompt_name": "evaluate_skills", "prompt": "Evaluate {{candidate_name}}'s skills.", "references": ["job_desc"]}
  ]
}
```

### Phase Rules

- Planning prompts execute **sequentially** (never parallel), regardless of concurrency.
- Planning prompts **cannot** use `{{variable}}` batch references (validated as error), except generator prompts (`generator=true`) which may reference batch variables in instructions to the LLM for generated prompt templates.
- Planning prompts **can** use `references` for document injection and `history` for chaining.
- Execution prompts **can** use `{{planning_prompt.response}}` to interpolate planning results.
- If a manual scoring sheet exists, it takes priority over auto-derived criteria (logged as warning).
- Generated prompts are tagged with `_generated: true` and assigned sequence numbers automatically.

### History Compatibility Note

Generator prompts return JSON which FFAI flattens by key into `shared_prompt_attr_history`. The orchestrator manually appends a history entry with the original `prompt_name` for each generator prompt, enabling `{{generator_name.response}}` interpolation in downstream prompts.

### Configuration (config/main.yaml)

```yaml
planning:
  enabled: true
  save_artifacts: false
  generated_sequence_base: "auto"
  generated_sequence_step: 10
  continue_on_parse_error: true
```

Generator prompts produce large JSON outputs (scoring criteria + evaluation prompts).
When using `--planning` mode, `create_screening_workbook.py` sets `max_tokens=16000`
to avoid response truncation. For non-planning workbooks, the default (4096) is used.

## Observability Module

The observability module provides zero-cost previews, execution traces, and automatic token/cost tracking — no API calls required for previews.

### Execution Plan Preview (`--explain`)

Shows the full execution DAG, dependency edges (history vs. condition), prompt metadata, and cost estimates before running any prompts.

```bash
# Preview execution plan
python scripts/run_orchestrator.py workbook.xlsx --explain

# Preview a specific resolved prompt (with variable substitution)
python scripts/run_orchestrator.py workbook.xlsx --explain --prompt analyze
python scripts/run_orchestrator.py workbook.xlsx --explain --prompt analyze --batch-row 1
```

### Resolved Prompt Preview (`--explain --prompt <name>`)

Simulates variable substitution for a single prompt showing template variables, upstream references, history context, and injected documents — exactly as the LLM would receive it.

### Token Usage & Cost Tracking

All active clients (`FFMistral`, `FFMistralSmall`, `FFGemini`, `FFPerplexity`, `FFLiteLLMClient`) automatically extract token counts and estimate cost after each `generate_response()` call. This data is available as side-channel attributes on the client and the FFAI wrapper:

```python
client.generate_response("Hello!")
print(client.last_usage)       # TokenUsage(input_tokens=50, output_tokens=25, total_tokens=75)
print(f"${client.last_cost_usd:.6f}")  # $0.000011
```

**Architecture:**

- `FFAIClientBase` provides class-level `_last_usage` / `_last_cost_usd` defaults, `_reset_usage()`, and `_extract_token_usage()` (shared by FFMistral, FFMistralSmall, FFGemini, FFPerplexity)
- `FFLiteLLMClient` has its own `_extract_usage()` using `litellm.completion_cost()` for live pricing
- `src/core/pricing.py` provides a static pricing table for native clients
- The orchestrator captures usage via `getattr(ffai, "last_usage", None)` and writes it to parquet columns

**Parquet columns:** `input_tokens`, `output_tokens`, `total_tokens`, `cost_usd`, `duration_ms`

### OpenTelemetry Integration

Plico emits OTLP spans at multiple levels when observability is enabled. Default is `false` — users opt in.

| Span Level | Span Name Pattern | Key Attributes |
|------------|-------------------|----------------|
| Run | `run.<name>` | total_prompts, successful, failed, tokens, cost |
| Planning | `planning.<name>` | phase, generator count |
| Execution | `execution` | concurrency, batch mode |
| Prompt | `prompt.<prompt_name>` | status, attempts, condition, tokens, cost |
| LLM call | `llm.<client_class>` | model, input_tokens, output_tokens, cost_usd |

**Zero overhead when disabled.** All span creation is replaced with no-op context managers — no performance impact, no hard OTel dependency.

### Configuration (config/main.yaml)

```yaml
observability:
  enabled: false              # Default off; set true to emit OTLP spans
  otel:
    service_name: "plico"
    endpoint: "http://localhost:4317"
    export_traces: true
    insecure: true
  token_tracking: true         # Per-prompt token counts in parquet (always on)
  cost_tracking: true          # Per-prompt cost estimation in parquet (always on)
```

### Condition Trace

Every prompt with a `condition` field records a `condition_trace` in the result showing the resolved expression with variables replaced by actual values. Example: `{{fetch.status}} == "success"` → trace shows `"success" == "success"`.

### Scoring Extraction Trace

Every prompt that has scores extracted records an `extraction_trace` describing which format matched and how the score was parsed: `flat: skills_match=8`, `nested_object: scores.python.score=6`, or `key 'baz' not found in top-level keys ['foo']`.

### New Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `condition_trace` | String or None | Resolved condition expression with values substituted |
| `extraction_trace` | Dict or None | Per-criteria scoring extraction traces |
| `input_tokens` | int | Tokens in the prompt sent to the model |
| `output_tokens` | int | Tokens in the model's response |
| `total_tokens` | int | Sum of input + output tokens |
| `cost_usd` | float | Estimated cost in USD for this prompt execution |
| `duration_ms` | float | Wall-clock LLM call duration in milliseconds |

## Evaluation Module (Scoring and Synthesis)

The evaluation module enables structured document evaluation workflows: score extraction, weighted aggregation, and cross-row comparison/ranking.

### New Workbook Sheets

**Scoring sheet** — defines evaluation criteria extracted from LLM JSON responses:

| Column | Description |
|--------|-------------|
| `criteria_name` | Machine-readable key (e.g., `skills_match`) |
| `description` | Human-readable description |
| `scale_min` / `scale_max` | Score range (uniform across all criteria, enforced by validation) |
| `weight` | Base weight for aggregation |
| `source_prompt` | Which prompt response contains this score |

**Synthesis sheet** — post-batch prompts that compare/rank entries:

| Column | Description |
|--------|-------------|
| `sequence` | Execution order |
| `prompt_name` | Unique name |
| `prompt` | The prompt text |
| `source_scope` | `all` or `top:N` — which batch entries to include |
| `source_prompts` | JSON array of prompt names whose responses to include |
| `include_scores` | Include scoring breakdown (default: true) |
| `history` | Synthesis prompt dependencies (other synthesis prompts) |
| `condition` | Condition for execution |

### Per-Row Document Binding

Data rows can declare per-row documents via the `_documents` column. Values are **additively merged** with each prompt's `references` at execution time:

```
| id | batch_name | candidate_name | _documents       |
|----|------------|----------------|------------------|
| 1  | alice_chen | Alice Chen     | ["resume_alice"] |
```

### Evaluation Strategies

Strategy-based weight overrides are configured in `config/main.yaml` under `evaluation.strategies` (not in the workbook). The `evaluation_strategy` field in the config sheet selects which strategy to use for the run.

### New Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `scores` | JSON | Extracted scores per criteria |
| `composite_score` | Float | Weighted average |
| `scoring_status` | String | `ok`, `partial`, `failed`, or `skipped` |
| `strategy` | String | Strategy name used |
| `result_type` | String | `batch`, `synthesis`, or `planning` |

### Auto-Discovery Utility

`src/orchestrator/discovery.py` provides `discover_documents()`, `create_data_rows_from_documents()`, and `create_evaluation_workbook()` for auto-generating evaluation workbooks from a folder of documents.

### Execution Order

```
run() → _load_source() → ValidationManager.validate_pre_planning() → _init_client()

─── Planning Phase (if has_planning) ──────────────
PlanningPhaseRunner.execute()
  ├── Execute planning prompts sequentially
  ├── Parse generator artifacts (scoring_criteria, prompts)
  ├── Inject generated prompts into self.prompts
  ├── Auto-derive ScoringRubric (if no manual scoring sheet)
  └── ValidationManager.validate_post_planning()

─── Execution Phase ───────────────────────────────
batch execution (or sequential/parallel)
  → All execution-phase prompts (static + generated)

─── Post-Execution ────────────────────────────────
SynthesisRunner.aggregate_scores() → SynthesisRunner.execute_synthesis() → _write_results()
```

When no planning prompts exist, the flow is the same as before:
`run() → _load_source() → ValidationManager.validate() → _init_client() → execution → results`
