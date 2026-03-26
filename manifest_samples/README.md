# Sample Manifests

This directory contains example manifests demonstrating Plico's capabilities.

## Available Samples

### linkedin_ai_post

**Purpose:** Research trending AI news, draft authentic posts with anti-AI cliché checks, and generate image prompts.

**Workflow:**
```
Research → Validation → Multi-Draft → Selection →
Deep Research → Enrichment → AI Topic Validation → 3x Revision Cycles → Final Output
```

**Features demonstrated:**
- **Topic validation gates** (`validate_stories_ai_focus`, `validate_ai_topic`, `force_ai_rewrite`)
- **Multi-draft creation** (`draft_hook_first`, `draft_story_first`, `draft_contrarian`)
- **3 revision cycles** with conditional execution
- **URL extraction** from Perplexity search
- **Anti-AI cliché detection** (15+ patterns)
- **Source URL** included in final output
- **300-400 word posts**

**Prompt count:** 25 prompts across 11 phases

**Run:**
```bash
python scripts/manifest_run.py ./manifest_samples/linkedin_ai_post -c 2
```

**Extract results:**
```bash
python scripts/manifest_extract.py ./outputs/linkedin_ai_post/<timestamp>.parquet --save

# Export to Excel (includes resolved_prompt column)
python scripts/parquet_to_excel.py ./outputs/linkedin_ai_post/<timestamp>.parquet
```

**Revision Cycles:**

| Cycle | Threshold | Action |
|-------|-----------|--------|
| v1 | < 7.5 | First revision |
| v2 | < 8.0 | Second revision |
| v3 | < 8.5 | Third revision |

**Anti-AI Clichés Detected:**

| Pattern | Example |
|---------|---------|
| "In today's world" | Generic opener |
| "It's not X, it Y" | False dichotomy |
| "The real question is..." | Rhetorical setup |
| "Let's dive in" | Cliché transition |
| "At the end of the day" | Generic conclusion |
| "Game-changer" | Hype language |
| Rhetorical question as opener | Engagement bait |
| "This changes everything" | Overpromising |

---

## Creating New Samples

To create a new sample manifest:

```bash
mkdir -p manifest_samples/your_sample_name
```

Then create the required files:
- `manifest.yaml` - Metadata
- `config.yaml` - Configuration
- `prompts.yaml` - Prompt graph
- `clients.yaml` - (optional) Named clients
- `data.yaml` - (optional) Batch data
- `documents.yaml` - (optional) Document references
