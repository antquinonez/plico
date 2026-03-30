#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Validate screening workbook results.

Validates workbooks created by sample_workbook_screening_create_v001.py
by checking execution status, scoring extraction, and synthesis output.

Features:
    - Prompt execution validation across all levels
    - Scoring status verification (ok/partial/failed/skipped)
    - Synthesis prompt validation
    - JSON output for programmatic use
    - Exit code 0 for pass, 1 for failures

Usage:
    python scripts/sample_workbook_screening_validate_v001.py <workbook_path>
    python scripts/sample_workbook_screening_validate_v001.py <workbook_path> --json
    python scripts/sample_workbook_screening_validate_v001.py <workbook_path> --results-sheet results_20250228_123456

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import SectionDefinition, WorkbookValidator

SECTIONS = {
    "Profile Extraction": SectionDefinition(
        (10, 10),
        "Extract candidate profile from resume (per-row documents)",
    ),
    "Skill Evaluation": SectionDefinition(
        (20, 20),
        "Evaluate technical skills against JD (score: skills_match)",
    ),
    "Education Evaluation": SectionDefinition(
        (30, 30),
        "Evaluate education quality (score: education)",
    ),
    "Experience Evaluation": SectionDefinition(
        (40, 40),
        "Evaluate work experience depth (score: experience_depth)",
    ),
    "Growth Assessment": SectionDefinition(
        (50, 50),
        "Assess career growth trajectory (score: growth_trajectory)",
    ),
    "Employer Evaluation": SectionDefinition(
        (60, 60),
        "Evaluate employer prestige (score: employer_prestige)",
    ),
    "Overall Assessment": SectionDefinition(
        (70, 70),
        "Narrative assessment combining all evaluations",
    ),
}

EXPECTED_BATCHES = 5


def main() -> int:
    validator = WorkbookValidator(
        SECTIONS,
        version="001",
        title="SCREENING WORKBOOK",
        track_batches=True,
    )
    return validator.run_cli()


if __name__ == "__main__":
    sys.exit(main())
