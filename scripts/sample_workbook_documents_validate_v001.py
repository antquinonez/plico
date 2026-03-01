#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Validate documents workbook results.

Validates workbooks created by sample_workbook_documents_create_v001.py
by checking document references and RAG semantic search execution.

Features:
    - Document reference injection verification
    - RAG semantic query validation
    - Prompt type breakdown (references vs semantic_query)
    - JSON output for programmatic use
    - Exit code 0 for pass, 1 for failures

Usage:
    python scripts/sample_workbook_documents_validate_v001.py <workbook_path>
    python scripts/sample_workbook_documents_validate_v001.py <workbook_path> --json
    python scripts/sample_workbook_documents_validate_v001.py <workbook_path> --results-sheet results_20250228_123456

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import SectionDefinition, WorkbookValidator

SECTIONS = {
    "Full Document References": SectionDefinition(
        (1, 6),
        "Prompts with full document injection via references column",
    ),
    "No Reference Control": SectionDefinition(
        (7, 7),
        "Control prompt without references or semantic search",
    ),
    "RAG Semantic Search": SectionDefinition(
        (8, 20),
        "Prompts using RAG semantic search via semantic_query column",
    ),
    "Filtered RAG Search": SectionDefinition(
        (21, 21),
        "Prompts using semantic_query with semantic_filter for targeted search",
    ),
    "Enhanced RAG Search": SectionDefinition(
        (22, 23),
        "Prompts using query_expansion or rerank per-prompt overrides",
    ),
}


def main() -> int:
    validator = WorkbookValidator(
        SECTIONS,
        version="001",
        title="DOCUMENTS WORKBOOK",
    )
    return validator.run_cli()


if __name__ == "__main__":
    sys.exit(main())
