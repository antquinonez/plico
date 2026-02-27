# FFClients Makefile
# ===============
# Commands for running test workbooks and validation.

.PHONY: help create clean run validate spot-check all

# Configuration
PYTHON ?= python3
VENV ?= .venv
SCRIPTS_DIR := scripts
VALIDATION_DIR := $(SCRIPTS_DIR)/validation

# Workbook paths (from config)
BASIC_WB := ./test_workbook_30.xlsx
MULTICLIENT_WB := ./test_workbook_multiclient.xlsx
CONDITIONAL_WB := ./test_workbook_conditional.xlsx
DOCUMENTS_WB := ./test_workbook_documents.xlsx
BATCH_WB := ./test_workbook_batch.xlsx
MAX_WB := ./test_workbook_max.xlsx

ALL_WORKBOOKS := $(BASIC_WB) $(MULTICLIENT_WB) $(CONDITIONAL_WB) $(DOCUMENTS_WB) $(BATCH_WB) $(MAX_WB)

# Concurrency settings
CONCURRENCY ?= 3

# Default target
help:
	@echo "FFClients Makefile Commands:"
	@echo ""
	@echo "  make create      - Create all test workbooks"
	@echo "  make clean        - Remove all test workbooks"
	@echo "  make run          - Run orchestrator on all workbooks"
	@echo "  make validate     - Validate all workbook results"
	@echo "  make spot-check   - Spot check responses"
	@echo "  make all           - Create, run, and validate all workbooks"
	@echo ""
	@echo "Individual workbooks:"
	@echo "  make basic         - Create and run basic workbook"
	@echo "  make multiclient   - Create and run multiclient workbook"
	@echo "  make conditional   - Create and run conditional workbook"
	@echo "  make documents     - Create and run documents workbook"
	@echo "  make batch         - Create and run batch workbook"
	@echo "  make max           - Create and run max workbook"
	@echo ""
	@echo "Options:"
	@echo "  CONCURRENCY=N    - Set parallel execution concurrency (default: 3)"

# Activate virtual environment and run command
run-in-venv = source .venv/bin/activate && POLARS_SKIP_CPU_CHECK=1

# Create all test workbooks
create:
	@echo "Creating test workbooks..."
	$(run-in-venv) python $(SCRIPTS_DIR)/create_test_workbook.py
	$(run-in-venv) python $(SCRIPTS_DIR)/create_test_workbook_multiclient.py
	$(run-in-venv) python $(SCRIPTS_DIR)/create_test_workbook_max.py
	$(run-in-venv) python $(SCRIPTS_DIR)/create_test_workbook_documents.py
	$(run-in-venv) python $(SCRIPTS_DIR)/create_test_workbook_conditional.py
	$(run-in-venv) python $(SCRIPTS_DIR)/create_test_workbook_batch.py
	@echo "All workbooks created."

# Clean all test workbooks
clean:
	@echo "Removing test workbooks..."
	rm -f $(ALL_WORKBOOKS)
	@echo "All workbooks removed."

# Run orchestrator on all workbooks
run: create
	@echo "Running orchestrator on all workbooks..."
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(BASIC_WB) -c $(CONCURRENCY)
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(MULTICLIENT_WB) -c 2
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(CONDITIONAL_WB) -c $(CONCURRENCY)
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(DOCUMENTS_WB)
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(BATCH_WB) -c $(CONCURRENCY)
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(MAX_WB) -c $(CONCURRENCY)
	@echo "All workbooks processed."

# Validate all workbooks
validate:
	@echo "Validating all workbooks..."
	$(run-in-venv) python $(VALIDATION_DIR)/validate_all.py

# Spot check responses
spot-check:
	@echo "Spot checking responses..."
	$(run-in-venv) python $(VALIDATION_DIR)/spot_check.py

# Full pipeline: create, run, and validate
all: clean create run validate
	@echo "Full pipeline complete!"

# Individual workbook targets
basic: create
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(BASIC_WB) -c $(CONCURRENCY)

multiclient: create
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(MULTICLIENT_WB) -c 2

conditional: create
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(CONDITIONAL_WB) -c $(CONCURRENCY)

documents: create
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(DOCUMENTS_WB)

batch: create
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(BATCH_WB) -c $(CONCURRENCY)

max: create
	$(run-in-venv) python $(SCRIPTS_DIR)/run_orchestrator.py $(MAX_WB) -c $(CONCURRENCY)
