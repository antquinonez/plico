#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Validate conditional execution workbook results.

Validates workbooks created by sample_workbook_conditional_create_v001.py
by checking condition evaluation results and execution status across all sections.

Features:
    - Section-by-section validation with detailed output
    - Condition evaluation tracking
    - JSON output for programmatic use
    - Exit code 0 for pass, 1 for failures

Usage:
    python scripts/sample_workbook_conditional_validate_v001.py <workbook_path>
    python scripts/sample_workbook_conditional_validate_v001.py <workbook_path> --json
    python scripts/sample_workbook_conditional_validate_v001.py <workbook_path> --results-sheet results_20250228_123456

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import SectionDefinition, WorkbookValidator

SECTIONS = {
    "Section 1 - String Methods": SectionDefinition(
        (1, 10),
        "String method tests",
        features=["startswith", "endswith", "lower", "strip", "count"],
    ),
    "Section 2 - JSON Simple": SectionDefinition(
        (11, 18),
        "JSON simple access tests",
        features=["json_get", "json_has", "json_type"],
    ),
    "Section 3 - JSON Nested": SectionDefinition(
        (19, 26),
        "JSON nested access tests",
        features=["nested paths", "json_get_default"],
    ),
    "Section 4 - JSON Array": SectionDefinition(
        (27, 34),
        "JSON array access tests",
        features=["array indexing", "json_keys", "in operator"],
    ),
    "Section 5 - JSON Complex": SectionDefinition(
        (35, 38),
        "JSON complex nested tests",
        features=["deep nesting", "mixed access"],
    ),
    "Section 6 - Math Functions": SectionDefinition(
        (39, 44),
        "Math function tests",
        features=["abs", "min", "max"],
    ),
    "Section 7 - Type Checking": SectionDefinition(
        (45, 47),
        "Type checking tests",
        features=["is_empty"],
    ),
    "Section 8 - Combined": SectionDefinition(
        (48, 50),
        "Combined condition tests",
        features=["chained conditions", "boolean logic"],
    ),
}


def main() -> int:
    validator = WorkbookValidator(
        SECTIONS,
        version="001",
        title="CONDITIONAL WORKBOOK",
        track_conditions=True,
    )
    return validator.run_cli()


if __name__ == "__main__":
    sys.exit(main())
