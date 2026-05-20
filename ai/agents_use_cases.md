# Use Cases

Extracted from [AGENTS.md](../AGENTS.md). Read this for resume screening and manifest workflow documentation.

## Resume Screening Use Case

**For comprehensive screening documentation, see [USE_CASES/resume_screening.md](../USE_CASES/resume_screening.md)**

Auto-discover resumes from a folder and evaluate against a job description.

### Auto-Discovery

`src/orchestrator/discovery.py` provides three functions:

| Function | Purpose |
|----------|---------|
| `discover_documents(folder)` | Scan folder for supported files |
| `create_data_rows_from_documents(docs)` | Generate batch data rows |
| `create_evaluation_workbook(path, folder)` | Create full `.xlsx` from folder |

### CLI Integration

**Create a self-contained workbook (JD + resumes baked in):**

```bash
python scripts/run_orchestrator.py workbook.xlsx -c 3
python scripts/run_orchestrator.py workbook.xlsx --explain            # Preview execution plan (no API calls)
python scripts/run_orchestrator.py workbook.xlsx --explain --prompt analyze  # Preview resolved prompt
```

**Create a template workbook (reusable across requisitions):**

```bash
# JD baked in, resumes injected at runtime
python scripts/create_screening_workbook.py ./template.xlsx \
    --jd ./job_description.md

# Generic template (nothing baked in)
python scripts/create_screening_workbook.py ./template.xlsx
```

**Runtime injection (use template with different data):**

```bash
# Template with JD baked in
python scripts/run_orchestrator.py ./template.xlsx \
    --documents-path ./resumes/ -c 1

# Generic template
python scripts/run_orchestrator.py ./template.xlsx \
    --shared-document ./jd.md --shared-document-name job_description \
    --documents-path ./resumes/ -c 1
```

**Invoke tasks:**

```bash
inv screening.run --resumes-path ./resumes/ --jd ./jd.md
inv screening.manifest --resumes-path ./resumes/ --jd ./jd.md
inv screening.create --jd ./jd.md --output ./template.xlsx
inv screening.inspect ./screening.xlsx
```

### ExcelOrchestrator Discovery Parameters

```python
orchestrator = ExcelOrchestrator(
    workbook_path="screening.xlsx",
    client=client,
    documents_path="./resumes/",          # Auto-discover documents
    shared_document_path="./jd.md",      # Shared document (name derived from filename)
)
orchestrator.run()
```

### ManifestOrchestrator Discovery Parameters

```python
orchestrator = ManifestOrchestrator(
    manifest_dir="./manifests/manifest_screening",
    client=client,
    documents_path="./resumes/",          # Auto-discover documents
    shared_document_path="./jd.md",      # Shared document (name derived from filename)
)
orchestrator.run()
```

### Pre-Screening (Cost Reduction)

Embedding-based resume ranking filters candidates before the expensive LLM pipeline. Two-tier pipeline: Tier 1 is a **hard exclusion** gate using BM25 keyword matching — candidates below threshold are removed entirely. Tier 2 uses dense embedding cosine similarity to rank survivors. BM25 is used only as a hard filter; final ranking is determined entirely by embedding similarity.

```bash
# Pre-screen top 20 resumes before LLM evaluation
python scripts/create_screening_manifest.py ./resumes/ --jd ./jd.md --pre-screen 20

# Pre-screen top 10 with planning mode
python scripts/create_screening_manifest.py ./resumes/ --jd ./jd.md --pre-screen 10 --planning

# Shell script with pre-screening
./convenience/screening_manifest.sh --pre-screen 10 small
```

**Configuration (`config/main.yaml`):**

```yaml
pre_screening:
  enabled: true
  embedding_model: "mistral/mistral-embed"
  bm25_min_score: 0.0
  bm25_min_overlap_ratio: 0.05
  embedding_cache_size: 512
```

**Outputs:** `data.yaml` (top-K batch rows), `documents.yaml` (top-K document refs), `pre_screening_report.yaml` (full ranking with scores).

## Manifest Workflow

**For comprehensive manifest documentation, see [MANIFEST_README.md](../MANIFEST_README.md)**

The manifest workflow separates workbook parsing from execution, enabling version control of prompts.

### Export Workbook to Manifest

```bash
# Export to default manifest directory
python scripts/manifest_export.py ./workbooks/my_prompts.xlsx

# Export to custom directory
python scripts/manifest_export.py ./workbook.xlsx --output ./custom_manifest/
```

Creates a folder with:
- `manifest.yaml` - Metadata
- `config.yaml` - Configuration
- `prompts.yaml` - All prompts
- `data.yaml` - Batch data (if present, preserves `_documents`)
- `clients.yaml` - Client configs (if present)
- `documents.yaml` - Document refs (if present)
- `scoring.yaml` - Scoring criteria (if present)
- `synthesis.yaml` - Synthesis prompts (if present)

### Run from Manifest

```bash
# Run with default settings
python scripts/manifest_run.py ./manifests/manifest_my_prompts

# Run with specific client and concurrency
python scripts/manifest_run.py ./manifests/manifest_my_prompts --client mistral-small -c 4

# Dry run to validate
python scripts/manifest_run.py ./manifests/manifest_my_prompts --dry-run
```

### Inspect Results

```bash
python scripts/manifest_inspect.py ./outputs/20250301120000_my_prompts.parquet

# Extract final post, hashtags, image_prompt, and source_url
python scripts/manifest_extract.py ./outputs/20250301120000_my_prompts.parquet

# Export results to files
python scripts/manifest_extract.py ./outputs/results.parquet --output-dir ./extracted

# Export parquet to Excel (includes resolved_prompt column)
python scripts/parquet_to_excel.py ./outputs/results.parquet
```
