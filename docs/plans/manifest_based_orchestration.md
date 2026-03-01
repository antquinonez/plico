# Manifest-Based Orchestration Plan

**Date:** 2026-02-28
**Author:** AI Assistant
**Status:** Complete

## Overview

Create a class-based solution that allows converting Excel workbooks to a manifest folder structure, then running orchestration from the manifest and outputting results to a timestamped parquet file.

## Goals

1. Decouple workbook parsing from execution
2. Enable version control of prompt configurations via YAML manifests
3. Output results to parquet files for efficient analysis
4. Provide inspection tools for parquet results

## Architecture

### Components

```
Workbook → WorkbookManifestExporter → manifest_[basename]/
                                          ├── manifest.yaml
                                          ├── config.yaml
                                          ├── prompts.yaml
                                          ├── data.yaml (optional)
                                          ├── clients.yaml (optional)
                                          └── documents.yaml (optional)

manifest/ → ManifestOrchestrator → YYYYMMDDHHMMSS_[basename].parquet
```

### Classes

#### 1. `WorkbookManifestExporter`
- **Location:** `src/orchestrator/manifest.py`
- **Purpose:** Convert workbook to manifest folder
- **Methods:**
  - `__init__(workbook_path: str)`
  - `export(manifest_dir: str | None = None) -> str` - Returns manifest path
  - `_write_manifest_yaml() -> None`
  - `_write_config_yaml() -> None`
  - `_write_prompts_yaml() -> None`
  - `_write_data_yaml() -> None`
  - `_write_clients_yaml() -> None`
  - `_write_documents_yaml() -> None`

#### 2. `ManifestOrchestrator`
- **Location:** `src/orchestrator/manifest.py`
- **Purpose:** Execute prompts from manifest and output to parquet
- **Methods:**
  - `__init__(manifest_dir: str, client: FFAIClientBase, ...)`
  - `run() -> str` - Returns parquet file path
  - `_load_manifest() -> dict`
  - `_write_parquet(results: list[dict]) -> str`

### Configuration

Added to `config/paths.yaml`:
```yaml
paths:
  output_dir: "./outputs"
  manifest_dir: "./manifests"
```

### File Formats

#### manifest.yaml
```yaml
version: "1.0"
source_workbook: ./my_prompts.xlsx
exported_at: "2026-02-28T10:30:00"
has_data: false
has_clients: true
has_documents: false
prompt_count: 31
```

#### config.yaml
```yaml
model: "mistral-small-latest"
max_retries: 2
temperature: 0.7
max_tokens: 300
system_instructions: "You are a helpful assistant..."
```

#### prompts.yaml
```yaml
prompts:
  - sequence: 1
    prompt_name: math_1
    prompt: "What is 1 + 1? Just give the number."
    history: []
  - sequence: 13
    prompt_name: double_1
    prompt: "Take the result from math_1..."
    history: ["math_1"]
```

### Output Format

**Parquet filename:** `YYYYMMDDHHMMSS_[workbook_basename].parquet`
**Location:** `{output_dir}/` (default: `./outputs/`)

**Parquet schema:**
| Column | Type | Description |
|--------|------|-------------|
| batch_id | Int64 | Batch number (nullable) |
| batch_name | String | Batch name (nullable) |
| sequence | Int64 | Execution order |
| prompt_name | String | Prompt identifier |
| prompt | String | The prompt text |
| history | String | Dependencies (JSON) |
| client | String | Client name used (nullable) |
| condition | String | Condition expression (nullable) |
| condition_result | Boolean | Condition evaluation (nullable) |
| condition_error | String | Error if condition failed (nullable) |
| response | String | AI response |
| status | String | `success`, `failed`, or `skipped` |
| attempts | Int64 | Retry attempts |
| error | String | Error message (nullable) |
| references | String | Document references (JSON, nullable) |
| semantic_query | String | RAG search query (nullable) |
| semantic_filter | String | RAG metadata filter (nullable) |
| query_expansion | String | Query expansion enabled (nullable) |
| rerank | String | Reranking enabled (nullable) |

### CLI Scripts

#### export_manifest.py
```bash
python scripts/export_manifest.py ./workbooks/my_prompts.xlsx
# Creates: ./manifests/manifest_my_prompts/

python scripts/export_manifest.py ./workbook.xlsx --output ./custom_manifest/
```

#### run_manifest.py
```bash
python scripts/run_manifest.py ./manifests/manifest_my_prompts/ -c 3
# Creates: ./outputs/20260228103000_my_prompts.parquet

python scripts/run_manifest.py ./manifests/manifest_my_prompts/ --dry-run
```

#### inspect_parquet.py
```bash
# Basic view (first/last 10 rows)
python scripts/inspect_parquet.py ./outputs/results.parquet

# Extended view with response column
python scripts/inspect_parquet.py ./outputs/results.parquet --extended

# Full view with all columns
python scripts/inspect_parquet.py ./outputs/results.parquet --full

# Summary only
python scripts/inspect_parquet.py ./outputs/results.parquet --summary

# Show only failed
python scripts/inspect_parquet.py ./outputs/results.parquet --failed

# Export to CSV
python scripts/inspect_parquet.py ./outputs/results.parquet --export csv
```

## Implementation Tasks

1. [x] Add `output_dir` and `manifest_dir` to config system
2. [x] Create `src/orchestrator/manifest.py` with classes
3. [x] Create `scripts/export_manifest.py`
4. [x] Create `scripts/run_manifest.py`
5. [x] Create `scripts/inspect_parquet.py`
6. [x] Update `src/orchestrator/__init__.py`
7. [x] Add unit tests
8. [x] Validate with sample workbook

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Manifest format | YAML | Human-readable, matches existing config pattern, git-friendly |
| Document handling | Keep references | Portable, no file duplication |
| Output format | Parquet | Efficient columnar storage, good for analytics |
| Timestamp format | YYYYMMDDHHMMSS | Sortable, unambiguous |
| Reuse strategy | Extend ExcelOrchestrator | Avoid code duplication |

## Testing Strategy

1. Unit tests for manifest export/import
2. Unit tests for parquet output
3. Integration test with basic workbook
4. Validation of parquet content structure

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Complex history parsing | Reuse existing `parse_history_string` |
| Document path resolution | Store relative paths, resolve at runtime |
| Large batch outputs | Parquet is efficient for large datasets |
