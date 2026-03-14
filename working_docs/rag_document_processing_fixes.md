# RAG Document Processing Fixes

## Status: COMPLETED (2026-03-09)

## Issues Fixed

### 1. Orphaned Parquet Cache Files ✓
**File:** `src/orchestrator/document_processor.py`

**Fix:** Added `_cleanup_old_parquet_files()` method that removes old parquet files with different checksums for the same reference_name. Called from `store_document()` before writing new parquet.

### 2. Double Checksum Computation ✓
**File:** `src/orchestrator/document_processor.py`

**Fix:** Added optional `checksum` parameter to `needs_parsing()`. Updated `get_document_content()` to pass pre-computed checksum.

### 3. Missing Template Columns ✓
**File:** `src/orchestrator/workbook_parser.py`

**Fix:** Added `tags` and `chunking_strategy` to `DOCUMENTS_HEADERS` constant.

---

## Files Modified

1. `src/orchestrator/document_processor.py`
   - Added `_cleanup_old_parquet_files()` method (lines 128-153)
   - Modified `needs_parsing()` to accept optional `checksum` parameter
   - Modified `store_document()` to call cleanup before writing
   - Modified `get_document_content()` to pass pre-computed checksum

2. `src/orchestrator/workbook_parser.py`
   - Added `tags` and `chunking_strategy` to `DOCUMENTS_HEADERS` (lines 101-107)

3. `tests/test_document_processor.py`
   - Added `TestCleanupOldParquetFiles` test class with 4 tests
   - Added 2 new tests to `TestNeedsParsing` for pre-computed checksum

---

## Test Results

```
tests/test_document_processor.py: 29 passed, 1 skipped
```

## Verification

```bash
inv documents    # Ran successfully with 23 prompts, 236 chunks indexed
inv index-status # Shows 10 markdown docs + 3 recursive docs
```

---

## Summary

All three issues were fixed with minimal changes:

1. **Orphan cleanup** - New `_cleanup_old_parquet_files()` method removes stale cache files
2. **Checksum optimization** - `needs_parsing()` now accepts pre-computed checksum
3. **Template columns** - `DOCUMENTS_HEADERS` now includes `tags` and `chunking_strategy`

No breaking changes. All existing tests pass. The documents workflow runs correctly.

**Impact:** Performance overhead (SHA256 on every file read).

**Solution:** Refactor `needs_parsing()` to accept an optional pre-computed checksum parameter.

### 3. Missing Template Columns
**File:** `src/orchestrator/workbook_parser.py`
**Location:** `DOCUMENTS_HEADERS` constant (lines 101-106)

**Problem:** The constant only includes `reference_name`, `common_name`, `file_path`, `notes`. But `load_documents()` also parses `tags` and `chunking_strategy` columns.

**Impact:** Users won't see `tags` and `chunking_strategy` columns in template workbooks. The columns still work if manually added.

**Solution:** Add `tags` and `chunking_strategy` to `DOCUMENTS_HEADERS`.

---

## Implementation Plan

### Step 1: Fix orphaned cache files
- [ ] Modify `DocumentProcessor.store_document()` to find and delete old parquet files for the same reference_name
- [ ] Add test case for orphan cleanup

### Step 2: Fix double checksum computation
- [ ] Add optional `checksum` parameter to `needs_parsing()`
- [ ] Update `get_document_content()` to pass pre-computed checksum
- [ ] Add test case for checksum parameter usage

### Step 3: Fix missing template columns
- [ ] Update `DOCUMENTS_HEADERS` to include `tags` and `chunking_strategy`
- [ ] Update template creation to handle new columns properly
- [ ] Verify documents workbook creates with all columns

### Step 4: Test and Validate
- [ ] Run existing tests to ensure no regressions
- [ ] Run `inv documents` to test the documents workbook workflow
- [ ] Verify RAG indexing works correctly

---

## Files to Modify

1. `src/orchestrator/document_processor.py` - Fix issues #1 and #2
2. `src/orchestrator/workbook_parser.py` - Fix issue #3
3. `tests/test_document_processor.py` - Add new tests

---

## Test Cases to Add

### TestDocumentProcessorCleanOrphans
- Test that storing a document with a new checksum removes the old parquet file
- Test that multiple old versions are all removed
- Test that other documents' parquet files are not affected

### TestNeedsParsingWithChecksum
- Test that `needs_parsing()` accepts optional checksum parameter
- Test that pre-computed checksum is used when provided
- Test that checksum is computed when not provided (backward compatibility)

---

## Verification

After implementing fixes:

```bash
# Clear any existing indexes
inv index-clear

# Run the documents workflow
inv documents

# Check index status
inv index-status

# Run tests
inv test tests/test_document_processor.py
inv test tests/test_document_registry.py
```
