#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Validate multiclient workbook results.

Validates workbooks created by sample_workbook_multiclient_create_v001.py
by checking client assignments and execution status across all levels.

Features:
    - Client assignment verification
    - Level-by-level validation with detailed output
    - Dependency chain verification
    - JSON output for programmatic use
    - Exit code 0 for pass, 1 for failures

Usage:
    python scripts/sample_workbook_multiclient_validate_v001.py <workbook_path>
    python scripts/sample_workbook_multiclient_validate_v001.py <workbook_path> --json
    python scripts/sample_workbook_multiclient_validate_v001.py <workbook_path> --results-sheet results_20250228_123456

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import SectionDefinition, WorkbookValidator

SECTIONS = {
    "Level 0 - Independent Prompts": SectionDefinition(
        (1, 5),
        "5 independent prompts using different clients",
    ),
    "Level 1 - Single Dependencies": SectionDefinition(
        (6, 10),
        "5 prompts with 1 dependency",
    ),
    "Level 2 - Synthesis Prompts": SectionDefinition(
        (11, 13),
        "3 synthesis prompts combining earlier results",
    ),
}


def main() -> int:
    validator = WorkbookValidator(
        SECTIONS,
        version="001",
        title="MULTICLIENT WORKBOOK",
    )
    return validator.run_cli()


if __name__ == "__main__":
    sys.exit(main())
