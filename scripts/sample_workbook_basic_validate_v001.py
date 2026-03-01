#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Validate basic workbook results.

Validates workbooks created by sample_workbook_basic_create_v001.py
by checking execution status and dependency chain resolution.

Features:
    - Level-by-level validation with detailed output
    - Dependency chain verification
    - JSON output for programmatic use
    - Exit code 0 for pass, 1 for failures

Usage:
    python scripts/sample_workbook_basic_validate_v001.py <workbook_path>
    python scripts/sample_workbook_basic_validate_v001.py <workbook_path> --json
    python scripts/sample_workbook_basic_validate_v001.py <workbook_path> --results-sheet results_20250228_123456

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import SectionDefinition, WorkbookValidator

SECTIONS = {
    "Level 0 - Independent Prompts": SectionDefinition(
        (1, 12),
        "12 fully parallel independent prompts",
    ),
    "Level 1 - Single Dependencies": SectionDefinition(
        (13, 22),
        "10 prompts with 1-2 dependencies",
    ),
    "Level 2 - Multiple Dependencies": SectionDefinition(
        (23, 27),
        "5 prompts with 2-4 dependencies",
    ),
    "Level 3 - Final Prompts": SectionDefinition(
        (28, 31),
        "4 final synthesis prompts",
    ),
}


def main() -> int:
    validator = WorkbookValidator(
        SECTIONS,
        version="001",
        title="BASIC WORKBOOK",
    )
    return validator.run_cli()


if __name__ == "__main__":
    sys.exit(main())
