# Orchestrator Reference

Extracted from [AGENTS.md](../AGENTS.md). Read this for config worksheet schema, workbook script conventions, and configuration file descriptions.

## Config Worksheet Reference

The config worksheet defines process-level settings for the orchestrator. The worksheet has three columns:

### Column Structure

| Column | Header | Description |
|--------|--------|-------------|
| A | field | Config field name |
| B | value | Current value for this field |
| C | notes | Documentation for the field (acceptable values, source) |

### Standard Config Fields
        | Field | Required | Default | Source | Acceptable Values |
        |-------|----------|---------|--------|-------------------|
        | `name` | No | (filename) | User | Any string - human-readable name for this process |
        | `description` | No | empty | User | Any string - brief description of the process |
        | `client_type` | No | (from config) | `config/clients.yaml` | Keys from `client_types` section |
        | `model` | No | (provider default) | Provider-specific | See `model_defaults.yaml` for examples |
        | `api_key_env` | No | (from config) | `.env` file | Environment variable name |
        | `max_retries` | No | 3 | - | `1` to `10` |
        | `temperature` | No | 0.7 | - | `0.0` to `2.0` |
        | `max_tokens` | No | 4096 | - | Positive integer |
        | `system_instructions` | No | (from config) | User | System prompt for AI |
        | `created_at` | No | (auto-generated) | - | ISO timestamp when workbook was created |

### Batch Mode Fields (only for workbooks with data sheet)
        | Field | Required | Default | Acceptable Values |
        |-------|----------|---------|-------------------|
        | `batch_mode` | No | per_row | `per_row` (execute for each data row) |
        | `batch_output` | No | combined | `combined`, `separate_sheets` |
        | `on_batch_error` | No | continue | `continue`, `stop` |

### Field Value Sources
        | Field | Where to Get Valid Values |
        |-------|----------------------------|
        | `client_type` | `config/clients.yaml` → `client_types` keys |
        | `model` | `config/model_defaults.yaml` → `models` keys |
        | `api_key_env` | `.env` file - must be set in environment |

### Example Config Sheet
        ```text
        | field            | value                           | notes                                         |
        |------------------|--------------------------------|-----------------------------------------------|
        | name             | My Analysis Process           | Human-readable name for this process          |
        | description     | Analyzes sales data by region | Brief description of what this process does    |
        | client_type      | litellm-mistral-small           | AI client type from config/clients.yaml       |
        | model            | mistral-small-latest           | Model identifier                               |
        | api_key_env      | MISTRAL_API_KEY               | Environment variable name for API key         |
        | max_retries      | 3                              | Maximum retry attempts (1-10)                |
        | temperature      | 0.7                            | Sampling temperature (0.0-2.0)               |
        | max_tokens        | 4096                           | Maximum response tokens                       |
        | system_instructions | You are a helpful assistant | System prompt for AI                    |
        | created_at        | 2025-03-22T10:30:00           | ISO timestamp when created                  |
        ```

## Workbook Scripts Naming Convention

Scripts that create or validate sample workbooks follow this naming pattern:

```
sample_workbook_<type>_<action>_v<NNN>.py
```

Where:
- `<type>`: Workbook type (`basic`, `conditional`, `documents`, `multiclient`, `batch`, `max`)
- `<action>`: `create` or `validate`
- `<NNN>`: Three-digit version number (`001`, `002`, etc.)

### Examples

| Type | Create Script | Validate Script |
|------|---------------|-----------------|
| Basic | `sample_workbook_basic_create_v001.py` | `sample_workbook_basic_validate_v001.py` |
| Conditional | `sample_workbook_conditional_create_v001.py` | `sample_workbook_conditional_validate_v001.py` |
| Documents | `sample_workbook_documents_create_v001.py` | `sample_workbook_documents_validate_v001.py` |
| Multiclient | `sample_workbook_multiclient_create_v001.py` | `sample_workbook_multiclient_validate_v001.py` |
| Batch | `sample_workbook_batch_create_v001.py` | `sample_workbook_batch_validate_v001.py` |
| Max | `sample_workbook_max_create_v001.py` | `sample_workbook_max_validate_v001.py` |
| Agent | `sample_workbook_agent_create_v001.py` | `sample_workbook_agent_validate_v001.py` |
| Screening | `sample_workbook_screening_create_v001.py` | `sample_workbook_screening_validate_v001.py` |

### Versioning Guidelines

1. **Creating a new version**: Increment the version number (e.g., `v001` → `v002`)
2. **Major changes**: When significantly changing workbook structure, conditions, or test coverage
3. **Bug fixes**: Minor fixes may not require version increment
4. **Pairing**: Create and validate scripts with the same version number are designed to work together

### Creating New Workbook Types

When creating a new workbook type:

1. Create both create and validate scripts starting with `v001`
2. Follow the pattern: `sample_workbook_<new_type>_<action>_v001.py`
3. Update `ai/agents_orchestrator.md` with the new type in the examples table
4. Include the version number in the script docstring

### Workbook Types

| Type | Description | Key Features |
|------|-------------|--------------|
| Basic | Parallel execution with dependencies | 31 prompts, 4 levels of dependency chains |
| Conditional | Conditional expression testing | 50 prompts testing string methods, JSON functions, math, type checking |
| Documents | Document reference and RAG testing | Full document injection, semantic search via RAG |
| Multiclient | Multi-client execution | Named client configurations, client-specific prompts |
| Batch | Batch execution with variables | 35 prompts x 5 batches, variable templating |
| Max | Combined features | Batch + conditional + multi-client in one workbook |
| Agent | Agentic tool-call loop | Opt-in agent mode with built-in tools, multi-round execution |
| Screening | Document evaluation pipeline | Per-row documents, scoring rubric, synthesis ranking |
| Screening v002 | Planning phase screening | Auto-derived scoring from LLM, generator prompts, refinement pattern |
| Screening skills | Per-skill planning | Exhaustive JD decomposition into individual skill prompts, `--planning-prompts screening_skills_planning` |

### Workflow

```bash
# Create a workbook
python scripts/sample_workbook_basic_create_v001.py ./test.xlsx

# Run the orchestrator
python scripts/run_orchestrator.py ./test.xlsx -c 3

# Validate the results
python scripts/sample_workbook_basic_validate_v001.py ./test.xlsx

# Or validate with JSON output for CI/CD
python scripts/sample_workbook_basic_validate_v001.py ./test.xlsx --json
```

## Configuration Files

### config/main.yaml

Core application settings: workbook sheet names, orchestrator settings, document processor config, RAG settings, pre-screening config.

### config/paths.yaml

File system paths for data storage, caches, outputs, and manifests.

```yaml
paths:
  ffai_data: "./ffai_data"
  doc_cache: "doc_cache"
  library: "library"
  output_dir: "./outputs"
  manifest_dir: "./manifests"
```

### config/clients.yaml

Client type definitions with API key environment variables, model classes, and defaults. Copy from `clients.yaml.example`.

### config/model_defaults.yaml

Default parameters for each model (temperature, max_tokens, etc.).

### config/logging.yaml

Logging configuration: log directory, file rotation, format.

### config/prompts/

Externalized prompt templates stored as YAML files. Each file defines a set of prompts for a specific use case (e.g., resume screening). When a template is provided via CLI flags, it overrides the hardcoded defaults in `scripts/sample_workbooks/screening.py`.

| File | Description | CLI Flag |
|------|-------------|----------|
| `screening_planning.yaml` | Planning-phase prompts (analyze JD, generate criteria) | `--planning-prompts` |
| `screening_skills_planning.yaml` | Per-skill planning prompts (exhaustive JD decomposition) | `--planning-prompts` |
| `screening_static.yaml` | Static evaluation prompts (fixed criteria) | `--static-prompts` |
| `screening_synthesis.yaml` | Cross-candidate synthesis and ranking | `--synthesis-prompts` |

**Usage:**

```bash
# Use default (hardcoded) prompts
python scripts/create_screening_workbook.py ./out.xlsx --jd ./jd.md --planning

# Use named template from config/prompts/
python scripts/create_screening_workbook.py ./out.xlsx --jd ./jd.md \
    --planning --planning-prompts screening_planning

# Use skills-based planning (one prompt per skill from JD)
python scripts/create_screening_workbook.py ./out.xlsx --jd ./jd.md \
    --planning --planning-prompts screening_skills_planning

# Use custom file path
python scripts/create_screening_workbook.py ./out.xlsx --jd ./jd.md \
    --planning --planning-prompts ./my_custom_planning.yaml
```

**Template YAML format:**

```yaml
name: my_template
description: "What this template does"
prompts:
  - sequence: 10
    prompt_name: analyze_jd
    prompt: |
      Analyze the job description...
    references: '["job_description"]'
    phase: planning
    generator: "true"
```

**Fallback behavior:** If a template file is not found, the hardcoded defaults are used with a log message. No error is raised.

**Loading API:**

```python
from src.prompt_templates import load_prompt_template, load_synthesis_template

# Load prompt specs by name or path
prompts = load_prompt_template("screening_planning")

# Load synthesis with variable substitution
synthesis = load_synthesis_template("screening_synthesis", top_n=5)
```

**Creating new templates:** Copy an existing template YAML from `config/prompts/`, modify the prompt texts, and reference via the CLI flag. Template names correspond to filenames (e.g., `screening_planning` → `config/prompts/screening_planning.yaml`).
