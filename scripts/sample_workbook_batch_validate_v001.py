#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Validate batch workbook results.

Validates workbooks created by sample_workbook_batch_create_v001.py
by checking batch execution and variable resolution across all levels.

Features:
    - Batch data execution verification
    - Variable resolution tracking
    - Level-by-level validation with detailed output
    - JSON output for programmatic use
    - Exit code 0 for pass, 1 for failures

Usage:
    python scripts/sample_workbook_batch_validate_v001.py <workbook_path>
    python scripts/sample_workbook_batch_validate_v001.py <workbook_path> --json
    python scripts/sample_workbook_batch_validate_v001.py <workbook_path> --results-sheet results_20250228_123456

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import SectionDefinition, WorkbookValidator

SECTIONS = {
    "Level 0 - Independent Prompts": SectionDefinition(
        (1, 10),
        "10 independent prompts using {{variable}} templating",
    ),
    "Level 1 - Single Dependencies": SectionDefinition(
        (11, 20),
        "10 prompts with 1-3 dependencies",
    ),
    "Level 2 - Multiple Dependencies": SectionDefinition(
        (21, 30),
        "10 prompts with 2-3 dependencies",
    ),
    "Level 3 - Final Synthesis": SectionDefinition(
        (31, 35),
        "5 final synthesis prompts",
    ),
}

EXPECTED_BATCHES = 5


def main() -> int:
    validator = WorkbookValidator(
        SECTIONS,
        version="001",
        title="BATCH WORKBOOK",
        track_batches=True,
    )
    return validator.run_cli()


if __name__ == "__main__":
    sys.exit(main())
