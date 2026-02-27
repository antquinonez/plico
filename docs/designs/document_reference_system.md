# Document Reference System Design

**Status:** Implemented (February 2026)

## Overview

The Document Reference System allows prompts in Excel workbooks to reference external documents. Documents are parsed (OCR if needed) and stored as parquet files with checksum-based caching.

## Components

### 1. DocumentProcessor (`src/orchestrator/document_processor.py`)

**Responsibilities:**
- Compute SHA256 checksums (first 8 chars for filenames)
- Check if document needs re-parsing (checksum comparison)
- Parse documents using LlamaParse (or direct read for text files)
- Store parsed content as parquet files

**Parquet File Naming:**
```
{checksum_8_chars}|{base_name}.parquet
```

Example: `a3f2b1c8|Technical_Spec.parquet`

**Parquet Schema:**
```
reference_name: string
common_name: string
original_path: string
checksum: string (full 64-char SHA256)
content: string (markdown)
parsed_at: timestamp
file_size: int64
```

### 2. DocumentRegistry (`src/orchestrator/document_registry.py`)

**Responsibilities:**
- Load document definitions from workbook sheet
- Validate all document paths exist
- Resolve reference names to content
- Provide content lookup for prompt injection

### 3. WorkbookBuilder Updates

**New Sheet: `documents`**
| Column | Description |
|--------|-------------|
| reference_name | Unique identifier for prompts to use |
| common_name | Human-readable name |
| file_path | Path to document (relative to workbook) |
| notes | Optional description |

**New Column in `prompts`: `references`**
- Format: JSON array of reference names
- Example: `["spec_doc", "api_guide"]`

### 4. ExcelOrchestrator Updates

**New Methods:**
- `_init_documents()`: Initialize DocumentProcessor and DocumentRegistry
- `_inject_references()`: Inject document content into prompts

**Prompt Injection Format:**
```xml
<REFERENCES>
<DOC name='reference_name'>
Document content here...
</DOC>

<DOC name='another_doc'>
More content...
</DOC>
</REFERENCES>

===
Based on the documents above, please answer: [original prompt]
```

## File Storage

### Directory Structure
```
workbook.xlsx
doc_cache/
  ├── a3f2b1c8|Technical_Spec.parquet
  └── d7e8f9a2|API_Guide.parquet
library/
  ├── spec.md
  ├── api_guide.pdf
  └── details/
      └── implementation.md
```

### Config Sheet Options
| field | default | description |
|-------|---------|-------------|
| document_cache_dir | {workbook_dir}/doc_cache | Directory for parquet files |

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing file | Fail prompt immediately |
| Parse failure | Raise exception with details |
| Invalid reference | Fail validation at startup |
| Checksum mismatch | Re-parse document |

## Test Strategy

### Unit Tests
- DocumentProcessor: checksum, parquet I/O, needs_parsing logic
- DocumentRegistry: load, validate, resolve

### Integration Tests
- Full workflow with orchestrator
- Reference injection verification
- Checksum-based caching

### Test Documents
Generated programmatically in `tests/fixtures/documents/`

### Test Workbooks
- `sample_workbook_documents.xlsx` - 7 prompts with document references
- `library/` folder contains sample documents for testing

### Unit Tests
- `tests/test_document_processor.py` - 24 tests for DocumentProcessor
- `tests/test_document_registry.py` - 23 tests for DocumentRegistry

## Results Sheet

The results sheet includes a `references` column showing which documents were referenced for each prompt:

| Column | Description |
|--------|-------------|
| `references` | JSON array of document reference names (e.g., `["product_spec", "api_guide"]`) |

## API Key Configuration

LlamaParse uses `LLAMACLOUD_TOKEN` environment variable from `.env` file.

Tests requiring LlamaParse are marked with `@pytest.mark.llamaparse`.
