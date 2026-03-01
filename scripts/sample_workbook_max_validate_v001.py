#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Validate max workbook results.

Validates workbooks created by sample_workbook_max_create_v001.py
by checking batch execution, conditional branching, multi-client usage, and RAG.

Features:
    - Batch execution verification
    - Conditional branching tracking
    - Level-by-level validation with detailed output
    - JSON output for programmatic use
    - Exit code 0 for pass, 1 for failures

Usage:
    python scripts/sample_workbook_max_validate_v001.py <workbook_path>
    python scripts/sample_workbook_max_validate_v001.py <workbook_path> --json
    python scripts/sample_workbook_max_validate_v001.py <workbook_path> --results-sheet results_20250228_123456

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import SectionDefinition, WorkbookValidator

SECTIONS = {
    "Section 1 - Input Classification": SectionDefinition(
        (1, 3),
        "Initial classification of review sentiment and urgency",
    ),
    "Section 2 - Conditional Branching": SectionDefinition(
        (4, 8),
        "Sentiment and urgency-based branching",
        features=["sentiment check", "urgency check", "conditional execution"],
    ),
    "Section 3 - Issue Resolution": SectionDefinition(
        (9, 12),
        "Issue detection and resolution paths",
        features=["issue detection", "conditional solutions"],
    ),
    "Section 4 - Response Assembly": SectionDefinition(
        (13, 16),
        "Final response construction",
        features=["conditional assembly", "internal notes"],
    ),
    "Section 5 - Final Reporting": SectionDefinition(
        (17, 20),
        "Metrics and confirmation",
    ),
    "Section 6 - RAG-Enhanced": SectionDefinition(
        (21, 27),
        "RAG semantic search with filters and reranking",
        features=["semantic_query", "semantic_filter", "query_expansion", "rerank"],
    ),
}


def main() -> int:
    validator = WorkbookValidator(
        SECTIONS,
        version="001",
        title="MAX WORKBOOK",
        track_conditions=True,
        track_batches=True,
    )
    return validator.run_cli()


if __name__ == "__main__":
    sys.exit(main())
