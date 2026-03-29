#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Validate agent workbook results.

Validates workbooks created by sample_workbook_agent_create_v001.py
by checking agent-specific result fields (agent_mode, tool_calls,
total_rounds, total_llm_calls, validation_passed, validation_attempts)
alongside standard result checks.

Usage:
    python scripts/sample_workbook_agent_validate_v001.py <workbook_path>
    python scripts/sample_workbook_agent_validate_v001.py <workbook_path> --json

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import (
    VALIDATION_ATTEMPTS_COLUMN,
    VALIDATION_PASSED_COLUMN,
    SectionDefinition,
    WorkbookValidator,
)

SECTIONS = {
    "Baseline (non-agent)": SectionDefinition(
        (1, 2),
        "Non-agent prompts without tools",
    ),
    "Single tool agents": SectionDefinition(
        (3, 5),
        "Agent mode with single tools",
    ),
    "Multi-tool agents": SectionDefinition(
        (6, 7),
        "Agent mode with multiple tools",
    ),
    "Conditional agent": SectionDefinition(
        (8, 9),
        "Agent with condition on previous agent result",
    ),
    "Validated agent": SectionDefinition(
        (10, 10),
        "Agent mode with validation prompt and retry support",
        field_checks={
            10: {
                "validation_passed": {
                    "column": VALIDATION_PASSED_COLUMN,
                    "expected": True,
                },
                "validation_attempts": {
                    "column": VALIDATION_ATTEMPTS_COLUMN,
                    "greater_than": 0,
                },
            },
        },
    ),
    "Edge case": SectionDefinition(
        (11, 11),
        "Agent with max_tool_rounds=1",
    ),
}


def main() -> int:
    validator = WorkbookValidator(
        SECTIONS,
        version="001",
        title="AGENT WORKBOOK",
    )
    return validator.run_cli()


if __name__ == "__main__":
    sys.exit(main())
