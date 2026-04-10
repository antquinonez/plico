# Resume Screening

Evaluate a folder of resumes against a job description using AI-powered
scoring, ranking, and synthesis.

---

## Quick Start

```bash
# 1. Put resumes in a folder and a JD in another (or same folder)
#    Supported formats: .pdf, .docx, .doc, .txt, .md

# 2. Create a workbook and run it
inv screening.run --resumes-path ./resumes/ --jd ./jd.md

#    Or create a manifest and run it (no Excel intermediary)
inv screening.manifest --resumes-path ./resumes/ --jd ./jd.md

# 3. Results are written into the workbook (Excel) or parquet (Manifest)
```

That's it. Two arguments: a folder and a file.

---

## Three Approaches

### Approach 1: Create a Workbook, Then Run (Excel)

Creates a `.xlsx` workbook you can inspect, edit prompts, and re-run.

```bash
# Create the workbook
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ \
    --jd ./job_description.md

# Run the orchestrator
python scripts/run_orchestrator.py ./screening.xlsx -c 1
```

**Why this approach:** You can open the `.xlsx`, tweak prompts, adjust scoring
weights, or add synthesis prompts before running. Results are written back
into the workbook.

### Approach 2: Create a Manifest, Then Run (YAML)

Creates a manifest folder (YAML files) directly — no Excel needed. Documents
and batch data are injected at runtime via `--resumes-path` and `--jd`.

```bash
# Create the manifest (YAML only — no baked-in data/documents)
python scripts/create_screening_manifest.py ./manifests/manifest_screening \
    --resumes-path ./resumes/ \
    --jd ./job_description.md

# Run the manifest orchestrator with runtime injection
python scripts/manifest_run.py ./manifests/manifest_screening \
    --resumes-path ./resumes/ \
    --jd ./job_description.md \
    -c 1
```

**Why this approach:** Manifests are Git-friendly, AI-composable, and the
canonical workflow representation. Documents are injected at runtime so the
same manifest can screen different resume folders. Results go to parquet.

### Approach 3: Runtime Injection (No Workbook/Manifest Modification)

Run the orchestrator with `--resumes-path` and `--jd` flags. Documents and
batch data are injected at runtime without modifying the workbook or manifest.

```bash
# Excel path
python scripts/run_orchestrator.py ./my_prompts.xlsx \
    --resumes-path ./resumes/ \
    --jd ./job_description.md \
    -c 2

# Manifest path
python scripts/manifest_run.py ./manifests/manifest_screening \
    --resumes-path ./resumes/ \
    --jd ./job_description.md \
    -c 2
```

**Why this approach:** You maintain a single reusable workbook or manifest
and swap out the resume folder per requisition.

---

## Two Scoring Modes

### Static Scoring (Default)

Predefined evaluation criteria with fixed prompts. You know exactly what
scores are extracted.

| Criteria | Weight | Source Prompt |
|----------|--------|---------------|
| skills_match | 1.0 | evaluate_skills |
| education | 0.8 | evaluate_education |
| experience_depth | 1.0 | evaluate_experience |
| employer_prestige | 0.7 | evaluate_employers |
| growth_trajectory | 0.5 | evaluate_growth |

```bash
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ \
    --jd ./jd.md
```

### Planning Phase (Auto-Derived Scoring)

The LLM reads the job description and generates evaluation criteria and
prompts. No manual scoring sheet needed.

```bash
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ \
    --jd ./jd.md \
    --planning
```

**How it works:**

1. `analyze_jd` (planning) — reads the JD, generates scoring criteria + eval prompts
2. `refine_criteria` (planning) — improves the generated criteria for clarity
3. `extract_profile` (execution) — extracts structured candidate info
4. LLM-generated eval prompts score each criterion
5. `overall_assessment` (execution) — narrative summary
6. Synthesis: rank, compare, recommend

---

## Command Reference

### `create_screening_workbook.py`

Creates a complete `.xlsx` workbook from a folder of resumes.

```bash
python scripts/create_screening_workbook.py <output_path> [options]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `output` | Yes | — | Output `.xlsx` path |
| `--resumes-path` | Yes | — | Folder containing resume documents |
| `--jd` | Yes | — | Path to job description file |
| `--planning` | No | off | Auto-derive scoring from JD via LLM |
| `--extensions` | No | `.pdf .docx .doc .txt .md` | File extensions to include |
| `--client` | No | config default | Client type from `config/clients.yaml` |
| `--system-instructions` | No | recruiter prompt | System instructions for AI |
| `--evaluation-strategy` | No | `balanced` | Scoring strategy name |
| `--verbose` | No | off | Enable verbose output |

**Examples:**

```bash
# Basic static scoring
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md

# Planning phase mode
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md --planning

# Only PDF and DOCX files, with Anthropic
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md \
    --extensions .pdf .docx --client anthropic

# Custom system instructions
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md \
    --system-instructions "You are a senior technical recruiter for a fintech company."
```

### `create_screening_manifest.py`

Creates a manifest folder (YAML files) directly from a folder of resumes.
No Excel intermediary. Documents and batch data are injected at runtime
via `manifest_run.py --resumes-path` and `--jd`.

```bash
python scripts/create_screening_manifest.py [output_dir] [options]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `output` | No | `./manifests/manifest_screening` | Output manifest directory |
| `--resumes-path` | Yes | — | Folder containing resume documents |
| `--jd` | Yes | — | Path to job description file |
| `--planning` | No | off | Auto-derive scoring from JD via LLM |
| `--extensions` | No | `.pdf .docx .doc .txt .md` | File extensions to include |
| `--client` | No | config default | Client type from `config/clients.yaml` |
| `--system-instructions` | No | recruiter prompt | System instructions for AI |
| `--evaluation-strategy` | No | `balanced` | Scoring strategy name |
| `--verbose` | No | off | Enable verbose output |

**Examples:**

```bash
# Basic static scoring
python scripts/create_screening_manifest.py \
    --resumes-path ./resumes/ --jd ./jd.md

# Custom output directory and planning mode
python scripts/create_screening_manifest.py ./manifests/my_screening \
    --resumes-path ./resumes/ --jd ./jd.md --planning
```

**Note:** This script validates that resumes are discovered and the JD exists,
but does *not* bake documents or batch data into the manifest. They are
injected at runtime via `manifest_run.py --resumes-path` and `--jd`.

### `run_orchestrator.py` (with discovery flags)

Runs the orchestrator. When `--resumes-path` and/or `--jd` are provided,
documents and batch data are injected at runtime.

```bash
python scripts/run_orchestrator.py <workbook> [options]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `workbook` | Yes | — | Path to `.xlsx` workbook |
| `--resumes-path` | No | — | Auto-discover documents from folder |
| `--jd` | No | — | Job description file (shared doc) |
| `--client` | No | config default | Client type override |
| `--concurrency` / `-c` | No | 2 | Max concurrent API calls |
| `--dry-run` | No | off | Validate without executing |
| `--quiet` / `-q` | No | off | Suppress console output |
| `--verbose` | No | off | Debug logging |

**Examples:**

```bash
# Standard run
python scripts/run_orchestrator.py ./screening.xlsx -c 1

# With runtime injection (no workbook modification)
python scripts/run_orchestrator.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md -c 2

# Dry run to validate before executing
python scripts/run_orchestrator.py ./screening.xlsx --dry-run

# Quiet mode (logs to file only)
python scripts/run_orchestrator.py ./screening.xlsx --quiet
```

### `manifest_run.py` (with discovery flags)

Runs the manifest orchestrator. When `--resumes-path` and/or `--jd` are
provided, documents and batch data are injected at runtime.

```bash
python scripts/manifest_run.py <manifest_dir> [options]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `manifest_dir` | Yes | — | Path to manifest folder |
| `--resumes-path` | No | — | Auto-discover documents from folder |
| `--jd` | No | — | Job description file (shared doc) |
| `--client` | No | config default | Client type override |
| `--concurrency` / `-c` | No | 2 | Max concurrent API calls |
| `--dry-run` | No | off | Validate without executing |
| `--verbose` | No | off | Debug logging |

**Examples:**

```bash
# Standard run
python scripts/manifest_run.py ./manifests/manifest_screening -c 1

# With runtime injection (no manifest modification)
python scripts/manifest_run.py ./manifests/manifest_screening \
    --resumes-path ./resumes/ --jd ./jd.md -c 2

# Dry run to validate before executing
python scripts/manifest_run.py ./manifests/manifest_screening --dry-run
```

### Invoke Tasks

```bash
# One-command create + run (Excel)
inv screening.run --resumes-path ./resumes/ --jd ./jd.md

# One-command create + run (Manifest)
inv screening.manifest --resumes-path ./resumes/ --jd ./jd.md

# Create + run with planning phase (Excel)
inv screening.run --resumes-path ./resumes/ --jd ./jd.md --planning

# Create + run with planning phase (Manifest)
inv screening.manifest --resumes-path ./resumes/ --jd ./jd.md --planning

# Just create (don't run)
inv screening.create --resumes-path ./resumes/ --jd ./jd.md --output ./my_screen.xlsx

# Inspect results after running
inv screening.inspect ./screening.xlsx
```

| Task | Description |
|------|-------------|
| `inv screening.create` | Create workbook from folder (don't run) |
| `inv screening.run` | Create workbook from folder and run (Excel) |
| `inv screening.manifest` | Create manifest from folder and run (YAML) |
| `inv screening.inspect` | Inspect results in a workbook |

| Option | Flag | Description |
|--------|------|-------------|
| Resumes folder | `--resumes-path` / `-r` | Folder containing resumes |
| Job description | `--jd` / `-j` | Path to JD file |
| Output path | `--output` / `-o` | Workbook path (default: `./screening.xlsx`) |
| Planning mode | `--planning` / `-p` | Auto-derive scoring from JD |
| Extensions | `--extensions` / `-e` | File extensions (space-separated) |
| Client | `--client` / `-c` | Client type from config |
| Concurrency | `--concurrency` / `-n` | Max concurrent API calls |

---

## Output

After running, the workbook contains a timestamped results sheet with:

- **Per-candidate results**: Extracted profiles, scores per criterion, narrative assessments
- **Scoring summary**: Composite scores with weighted aggregation
- **Synthesis**: Cross-candidate ranking, comparison, and hiring recommendation

For static scoring mode, a `scores_pivot` sheet provides a summary table
with all criteria across all candidates.

---

## Preparing Your Documents

### Folder Structure

```
my_hiring/
├── job_descriptions/
│   └── senior_engineer.md
└── resumes/
    ├── alice_chen.pdf
    ├── bob_martinez.docx
    ├── carol_okafor.md
    └── david_kim.txt
```

### File Naming

File names are used to derive candidate identifiers:

| Filename | reference_name | candidate_name |
|----------|---------------|----------------|
| `alice_chen.pdf` | `alice_chen` | `alice_chen` |
| `Bob Martinez CV.docx` | `bob_martinez_cv` | `Bob Martinez CV` |
| `resume-v2-final.md` | `resume_v2_final` | `resume-v2-final` |

**Tip:** Use consistent, human-readable filenames. The stem becomes the
candidate name in results.

### Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| Plain text | `.txt` | Read directly |
| Markdown | `.md` | Read directly |
| Word | `.docx` | Requires LlamaParse (see config) |
| Word (legacy) | `.doc` | Requires LlamaParse |
| PDF | `.pdf` | Requires LlamaParse |

For `.txt` and `.md` files, no additional configuration is needed. For
`.pdf`, `.docx`, and `.doc`, set `LLAMACLOUD_TOKEN` in your `.env`.

---

## Customizing the Evaluation

### Edit the Workbook

After creating a workbook, you can edit the `.xlsx` to customize:

- **Prompts sheet**: Change evaluation prompts, add new ones
- **Scoring sheet**: Adjust criteria, weights, score ranges
- **Synthesis sheet**: Change ranking/comparison prompts
- **Config sheet**: Change client, model, temperature, system instructions

### Custom System Instructions

```bash
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md \
    --system-instructions "You are a hiring manager at a Series A startup. Be direct and focus on impact over credentials."
```

### Evaluation Strategies

Strategies are defined in `config/main.yaml` under `evaluation.strategies`.
Each strategy can override the base weights:

```yaml
evaluation:
  strategies:
    balanced:
      skills_match: 1.0
      education: 0.8
    potential:
      skills_match: 0.8
      growth_trajectory: 1.5
```

```bash
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md \
    --evaluation-strategy potential
```

---

## Architecture: How Auto-Discovery Works

```
resumes/               job_descriptions/
  alice_chen.md          senior_engineer.md
  bob_martinez.pdf
  carol_okafor.docx
       │                      │
       v                      v
  discover_documents()   _resolve_jd_document()
       │                      │
       │  reference_name      │  reference_name
       │  common_name         │  "job_description"
       │  file_path           │  file_path (absolute)
       │  tags=["resume"]     │  tags="jd"
       │                      │
       v                      v
  create_data_rows_        Shared doc
  from_documents()         (available to all
  (one row per resume       prompts, not bound
   with _documents          to any data row)
   column binding)                │
       │                          │
        v                          v
   ┌──────────────────────────────────────────────────────┐
   │  OrchestratorBase._inject_discovery_overrides()       │
   │                                                        │
   │  1. Load workbook sheets OR manifest YAML files        │
   │  2. If resumes_path: discover & inject docs + data    │
   │  3. If jd_path: inject as shared doc                  │
   │  4. Merge with any source docs                        │
   │  5. Run validation + execution                        │
   └──────────────────────────────────────────────────────┘

   Shared by both ExcelOrchestrator and ManifestOrchestrator.
```

Key points:

- `--jd` creates a document with `reference_name="job_description"`. Reference
  it in prompts via `references: '["job_description"]'`.
- `--resumes-path` creates one data row per discovered file. Each row binds
  its document via the `_documents` column.
- Paths are stored as absolute for runtime injection, relative for workbook
  creation.
- Discovery merges with existing workbook documents/data if present.
