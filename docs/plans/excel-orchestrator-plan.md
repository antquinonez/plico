# Excel Orchestrator Implementation Plan

## Tasks

### Phase 1: Core Classes

#### 1.1 Create orchestrator module structure
- [x] Create `src/orchestrator/` directory
- [x] Create `src/orchestrator/__init__.py`

#### 1.2 WorkbookBuilder class
- [x] Create `src/orchestrator/workbook_builder.py`
- [x] Implement `create_template_workbook()` - creates workbook with config and prompts sheets
- [x] Implement `validate_workbook()` - checks required sheets/columns exist
- [x] Implement `parse_history_string()` - converts `["a", "b"]` string to list

#### 1.3 ExcelOrchestrator class
- [x] Create `src/orchestrator/excel_orchestrator.py`
- [x] Implement `__init__()` - accept path, client, config overrides
- [x] Implement `load_config()` - read from config sheet
- [x] Implement `load_prompts()` - read from prompts sheet, parse history
- [x] Implement `validate_dependencies()` - ensure all history refs exist
- [x] Implement `execute_prompt()` - single prompt execution with retry
- [x] Implement `execute()` - run all prompts in sequence
- [x] Implement `write_results()` - create timestamped results sheet
- [x] Implement `run()` - main entry point

### Phase 2: Client Script

#### 2.1 CLI script
- [x] Create `scripts/run_orchestrator.py`
- [x] Parse command line args (workbook path, optional config)
- [x] Initialize client from config
- [x] Instantiate orchestrator and run
- [x] Print summary to console

### Phase 3: Testing

#### 3.1 Manual testing
- [x] Test workbook creation (no file provided)
- [x] Test workbook validation
- [x] Test prompt execution with dependencies
- [x] Test retry logic (logic implemented, not explicitly tested)
- [x] Test results sheet creation

### Phase 4: Documentation

#### 4.1 Usage docs
- [ ] Document workbook format in README or docs
- [x] Add example workbook

## Dependencies

- `openpyxl` (already in requirements.txt)
- Existing `src/FFAI.py` and `src/Clients/` classes

## Estimated Effort

| Phase | Time |
|-------|------|
| 1.1-1.2 | 30 min |
| 1.3 | 1 hour |
| 2.1 | 20 min |
| 3.1 | 30 min |
| 4.1 | 15 min |
| **Total** | ~2.5 hours |

## Order of Implementation

1. `src/orchestrator/__init__.py`
2. `src/orchestrator/workbook_builder.py`
3. `src/orchestrator/excel_orchestrator.py`
4. `scripts/run_orchestrator.py`
5. Test and iterate
