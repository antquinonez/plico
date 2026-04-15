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

## Creation Modes

Both creation scripts support optional `--resumes-path` and `--jd` arguments,
giving you control over what gets baked in vs injected at runtime.

### Workbook Modes

| Mode | JD | Resumes | Creation | Runtime |
|------|----|---------|----------|---------|
| **Self-contained** | `--jd` | `--resumes-path` | `create_screening_workbook.py ./out.xlsx --jd ./jd.md --resumes-path ./resumes/` | `run_orchestrator.py ./out.xlsx` |
| **Template (JD baked)** | `--jd` | *(omit)* | `create_screening_workbook.py ./template.xlsx --jd ./jd.md` | `run_orchestrator.py ./template.xlsx --documents-path ./resumes/` |
| **Template (generic)** | *(omit)* | *(omit)* | `create_screening_workbook.py ./template.xlsx` | `run_orchestrator.py ./template.xlsx --shared-document ./jd.md --shared-document-name job_description --documents-path ./resumes/` |

### Manifest Modes

| Mode | JD | Resumes | Creation | Runtime |
|------|----|---------|----------|---------|
| **Template (JD baked)** | `--jd` | *(omit)* | `create_screening_manifest.py --jd ./jd.md` | `manifest_run.py ./manifest_screening --documents-path ./resumes/` |
| **Template (generic)** | *(omit)* | *(omit)* | `create_screening_manifest.py` | `manifest_run.py ./manifest_screening --shared-document ./jd.md --shared-document-name job_description --documents-path ./resumes/` |

`--resumes-path` on the manifest script is optional and used only for sizing
the synthesis `top_n` count. Resumes are always injected at runtime.

---

## Three Approaches

### Approach 1: Self-Contained Workbook (Excel)

Creates a `.xlsx` workbook with all documents and batch data baked in.

```bash
# Create the workbook (JD + resumes baked in)
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ \
    --jd ./job_description.md

# Run the orchestrator (no flags needed)
python scripts/run_orchestrator.py ./screening.xlsx -c 1
```

**Why this approach:** Self-contained file you can share, email, or version.
Results are written back into the workbook.

### Approach 2: Template Workbook (Excel)

Creates a `.xlsx` workbook with prompts and scoring but no baked-in data.
Reusable across different JDs and resume folders.

```bash
# Template with JD baked in
python scripts/create_screening_workbook.py ./template.xlsx \
    --jd ./job_description.md

# Run with resumes injected at runtime
python scripts/run_orchestrator.py ./template.xlsx \
    --documents-path ./resumes/ -c 1

# Generic template (nothing baked in)
python scripts/create_screening_workbook.py ./template.xlsx

python scripts/run_orchestrator.py ./template.xlsx \
    --shared-document ./jd.md --shared-document-name job_description \
    --documents-path ./resumes/ -c 2
```

**Why this approach:** Edit prompts once in the template, screen different
requisitions by swapping `--documents-path` and `--shared-document` at runtime.

### Approach 3: Template Manifest (YAML)

Creates a manifest folder (YAML files) directly — no Excel needed. The JD
can optionally be baked into `documents.yaml`; resumes are always injected
at runtime.

```bash
# Template with JD baked in
python scripts/create_screening_manifest.py ./manifests/manifest_screening \
    --jd ./job_description.md

# Run with resumes injected at runtime
python scripts/manifest_run.py ./manifests/manifest_screening \
    --documents-path ./resumes/ -c 1

# Generic template (nothing baked in)
python scripts/create_screening_manifest.py ./manifests/manifest_screening

python scripts/manifest_run.py ./manifests/manifest_screening \
    --shared-document ./jd.md --shared-document-name job_description \
    --documents-path ./resumes/ -c 1
```

**Why this approach:** Manifests are Git-friendly, AI-composable, and the
canonical workflow representation. Prompts, scoring, and synthesis travel in
version control; data stays on disk. Results go to parquet.

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

### Skills-Based Planning (Per-Skill Decomposition)

Instead of generic criteria buckets, the JD is exhaustively decomposed into
individual skill requirements. Each skill gets its own evaluation prompt and
scoring criterion.

```bash
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ \
    --jd ./jd.md \
    --planning --planning-prompts screening_skills_planning
```

**How it differs from standard planning:**

For a data analyst JD mentioning Python, SQL, Tableau, Excel, and stakeholder
management, the LLM would generate:

| Generated Prompt | Score Key | Weight |
|------------------|-----------|--------|
| `evaluate_python` | `{"python": 7, "reasoning": "..."}` | 1.5 |
| `evaluate_sql` | `{"sql": 8, "reasoning": "..."}` | 1.5 |
| `evaluate_tableau` | `{"tableau": 5, "reasoning": "..."}` | 1.0 |
| `evaluate_excel` | `{"excel": 9, "reasoning": "..."}` | 0.8 |
| `evaluate_stakeholder_management` | `{"stakeholder_management": 6, "reasoning": "..."}` | 0.5 |

**How it works:**

1. `analyze_jd` (planning) — extracts every discrete skill (hard, soft, domain,
   certs, methodologies), creates one prompt + one criterion per skill
2. `refine_criteria` (planning) — deduplicates, calibrates weights, verifies
   no skills were missed
3. `extract_profile` (execution) — extracts structured candidate info
4. One LLM-generated eval prompt per skill scores that skill individually
5. `overall_assessment` (execution) — narrative summary referencing all skill scores
6. Synthesis: rank, compare, recommend

**Why use this:** Composite scores from generic criteria (e.g., "skills_match: 7")
can mask critical gaps. Per-skill scoring surfaces exactly where a candidate
excels or falls short — useful for technical roles with distinct must-have skills.

---

## Prompt Templates

All prompt instructions are externalized as YAML files in `config/prompts/`.
You can use the built-in templates, customize them, or create your own.

### Available Templates

| Template | File | Use With | Description |
|----------|------|----------|-------------|
| **screening_planning** | `screening_planning.yaml` | `--planning-prompts` | Standard planning: 4-6 generic criteria from JD |
| **screening_skills_planning** | `screening_skills_planning.yaml` | `--planning-prompts` | Per-skill planning: one prompt per skill from JD |
| **screening_static** | `screening_static.yaml` | `--static-prompts` | Static evaluation prompts (7 fixed criteria) |
| **screening_synthesis** | `screening_synthesis.yaml` | `--synthesis-prompts` | Cross-candidate ranking and recommendation |

### CLI Flags

| Flag | Applies To | Description |
|------|-----------|-------------|
| `--planning-prompts <name_or_path>` | `--planning` mode only | Planning prompt template (name or file path) |
| `--static-prompts <name_or_path>` | Default (non-planning) | Static evaluation prompt template |
| `--synthesis-prompts <name_or_path>` | Both modes | Synthesis prompt template |

All flags are optional. When omitted, hardcoded defaults are used (same prompts
as before this feature was added). When a template name is given (e.g.,
`screening_skills_planning`), it is resolved to `config/prompts/<name>.yaml`.
You can also pass an explicit file path.

### Usage Examples

```bash
# Default planning (hardcoded prompts, same as before)
python scripts/create_screening_workbook.py ./out.xlsx --jd ./jd.md --planning

# Skills-based planning (one prompt per skill from JD)
python scripts/create_screening_workbook.py ./out.xlsx --jd ./jd.md \
    --planning --planning-prompts screening_skills_planning

# Standard planning with custom synthesis prompts
python scripts/create_screening_workbook.py ./out.xlsx --jd ./jd.md \
    --planning --planning-prompts screening_planning \
    --synthesis-prompts screening_synthesis

# Custom template from file path
python scripts/create_screening_workbook.py ./out.xlsx --jd ./jd.md \
    --planning --planning-prompts ./my_custom_planning.yaml

# Same flags work for manifests
python scripts/create_screening_manifest.py --jd ./jd.md \
    --planning --planning-prompts screening_skills_planning
```

### Creating Custom Templates

1. Copy an existing template from `config/prompts/`:

```bash
cp config/prompts/screening_skills_planning.yaml config/prompts/my_custom.yaml
```

2. Edit the prompt texts in the YAML file. Each prompt has:

| Field | Required | Description |
|-------|----------|-------------|
| `sequence` | Yes | Execution order |
| `prompt_name` | Yes | Unique identifier |
| `prompt` | Yes | The prompt text (use `{{candidate_name}}` for runtime substitution) |
| `references` | No | JSON list of document references (e.g., `'["job_description"]'`) |
| `history` | No | JSON list of dependency prompt names |
| `phase` | No | `"planning"` or omit for execution |
| `generator` | No | `"true"` if this planning prompt returns structured JSON artifacts |

3. Reference by name or path:

```bash
python scripts/create_screening_workbook.py ./out.xlsx --jd ./jd.md \
    --planning --planning-prompts my_custom
```

### Programmatic Access

```python
from src.prompt_templates import load_prompt_template, load_synthesis_template

# Load prompt specs (returns PromptSpec instances)
prompts = load_prompt_template("screening_skills_planning")

# Load synthesis with variable substitution
synthesis = load_synthesis_template("screening_synthesis", top_n=5)
```

---

## Command Reference

### `create_screening_workbook.py`

Creates a `.xlsx` workbook with prompts, scoring, and synthesis sheets.

```bash
python scripts/create_screening_workbook.py <output_path> [options]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `output` | Yes | — | Output `.xlsx` path |
| `--resumes-path` | No | — | Folder containing resume documents (baked in if provided) |
| `--jd` | No | — | Path to job description file (baked in if provided) |
| `--planning` | No | off | Auto-derive scoring from JD via LLM |
| `--planning-prompts` | No | hardcoded | Planning prompt template (name in `config/prompts/` or file path) |
| `--static-prompts` | No | hardcoded | Static prompt template (name or file path) |
| `--synthesis-prompts` | No | hardcoded | Synthesis prompt template (name or file path) |
| `--extensions` | No | `.pdf .docx .doc .txt .md` | File extensions to include |
| `--client` | No | config default | Client type from `config/clients.yaml` |
| `--system-instructions` | No | recruiter prompt | System instructions for AI |
| `--evaluation-strategy` | No | `balanced` | Scoring strategy name |
| `--verbose` | No | off | Enable verbose output |

**Examples:**

```bash
# Self-contained (JD + resumes baked in)
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md

# Planning phase mode
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md --planning

# Skills-based planning (one prompt per skill from JD)
python scripts/create_screening_workbook.py ./screening.xlsx \
    --resumes-path ./resumes/ --jd ./jd.md \
    --planning --planning-prompts screening_skills_planning

# Template with JD baked in (resumes injected at runtime)
python scripts/create_screening_workbook.py ./template.xlsx \
    --jd ./jd.md

# Generic template (nothing baked in)
python scripts/create_screening_workbook.py ./template.xlsx
```

### `create_screening_manifest.py`

Creates a manifest folder (YAML files) directly. The JD can optionally be
baked into `documents.yaml`; resumes are always injected at runtime.

```bash
python scripts/create_screening_manifest.py [output_dir] [options]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `output` | No | `./manifests/manifest_screening` | Output manifest directory |
| `--resumes-path` | No | — | Folder for top_n sizing (not baked in) |
| `--jd` | No | — | Path to JD file (baked into `documents.yaml` if provided) |
| `--planning` | No | off | Auto-derive scoring from JD via LLM |
| `--planning-prompts` | No | hardcoded | Planning prompt template (name in `config/prompts/` or file path) |
| `--static-prompts` | No | hardcoded | Static prompt template (name or file path) |
| `--synthesis-prompts` | No | hardcoded | Synthesis prompt template (name or file path) |
| `--extensions` | No | `.pdf .docx .doc .txt .md` | File extensions to include |
| `--client` | No | config default | Client type from `config/clients.yaml` |
| `--system-instructions` | No | recruiter prompt | System instructions for AI |
| `--evaluation-strategy` | No | `balanced` | Scoring strategy name |
| `--verbose` | No | off | Enable verbose output |

**Examples:**

```bash
# Template with JD baked in
python scripts/create_screening_manifest.py \
    --jd ./job_description.md

# Generic template (nothing baked in)
python scripts/create_screening_manifest.py

# Planning mode with JD and resume count for top_n sizing
python scripts/create_screening_manifest.py ./manifests/my_screening \
    --jd ./jd.md --planning --resumes-path ./resumes/

# Skills-based planning (per-skill decomposition)
python scripts/create_screening_manifest.py ./manifests/my_screening \
    --jd ./jd.md --planning --planning-prompts screening_skills_planning
```

### `run_orchestrator.py` (with discovery flags)

Runs the orchestrator. When `--documents-path` and/or `--shared-document` are
provided, documents and batch data are injected at runtime.

```bash
python scripts/run_orchestrator.py <workbook> [options]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `workbook` | Yes | — | Path to `.xlsx` workbook |
| `--documents-path` | No | — | Auto-discover documents from folder |
| `--shared-document` | No | — | Shared document file (e.g., job description) |
| `--shared-document-name` | No | — | Explicit reference name for the shared document |
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
    --documents-path ./resumes/ --shared-document ./jd.md \
    --shared-document-name job_description -c 2

# Dry run to validate before executing
python scripts/run_orchestrator.py ./screening.xlsx --dry-run

# Quiet mode (logs to file only)
python scripts/run_orchestrator.py ./screening.xlsx --quiet
```

### `manifest_run.py` (with discovery flags)

Runs the manifest orchestrator. When `--documents-path` and/or
`--shared-document` are provided, documents and batch data are injected at
runtime.

```bash
python scripts/manifest_run.py <manifest_dir> [options]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `manifest_dir` | Yes | — | Path to manifest folder |
| `--documents-path` | No | — | Auto-discover documents from folder |
| `--shared-document` | No | — | Shared document file (e.g., job description) |
| `--shared-document-name` | No | — | Explicit reference name for the shared document |
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
    --documents-path ./resumes/ --shared-document ./jd.md \
    --shared-document-name job_description -c 2

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

For both static and planning scoring modes, a `scores_pivot` sheet provides a
summary table with all criteria across all candidates (one row per
candidate-criterion pair, with normalized scores, scale bounds, and descriptions).

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
   discover_documents()   _resolve_shared_document()
        │                      │
        │  reference_name      │  reference_name (derived
        │  common_name         │    from filename stem,
        │  file_path           │    e.g. "senior_engineer")
        │                      │  file_path (absolute)
        │                      │  tags="shared"
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
    │  2. If documents_path: discover & inject docs + data   │
    │  3. If shared_document_path: inject as shared doc      │
    │  4. Merge with any source docs                        │
    │  5. Run validation + execution                        │
    └──────────────────────────────────────────────────────┘

    Shared by both ExcelOrchestrator and ManifestOrchestrator.
```

Key points:

- `--shared-document` creates a document with a `reference_name` derived
  from the filename (e.g., `senior_engineer.md` → `senior_engineer`).
  Use `--shared-document-name` to override (e.g., `--shared-document-name
  job_description` ensures the name matches prompts that reference
  `["job_description"]`).
- `--documents-path` creates one data row per discovered file. Each row
  binds its document via the `_documents` column.
- Paths are stored as absolute for runtime injection, relative for workbook
  creation.
- Discovery merges with existing workbook documents/data if present.
