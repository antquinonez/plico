#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Sample workbook creation and validation utilities.

This package provides reusable components for creating and validating
Excel workbooks used in orchestrator testing.

Main components:
    - PromptSpec: Dataclass for prompt specifications
    - SectionDefinition: Dataclass for validation section definitions
    - WorkbookBuilder: Class for creating test workbooks
    - WorkbookValidator: Class for validating workbook results

Example usage - Creating a workbook:
    from sample_workbooks import WorkbookBuilder, PromptSpec

    prompts = [
        PromptSpec(1, "greeting", "Say hello", None),
        PromptSpec(2, "question", "Ask a question", '["greeting"]'),
    ]

    builder = WorkbookBuilder("output.xlsx")
    builder.add_config_sheet().add_prompts_sheet(prompts).save()

Example usage - Validating results:
    from sample_workbooks import WorkbookValidator, SectionDefinition

    sections = {
        "Level 0": SectionDefinition((1, 10), "Independent prompts"),
        "Level 1": SectionDefinition((11, 20), "With dependencies"),
    }

    validator = WorkbookValidator(sections, version="001")
    results = validator.validate_workbook(Path("workbook.xlsx"))
    validator.print_report(results, "My Workbook")
"""

from .base import (
    DEFAULT_BATCH_CONFIG_FIELDS,
    DEFAULT_CLIENTS_COLUMN_WIDTHS,
    DEFAULT_CLIENTS_HEADERS,
    DEFAULT_CONFIG_COLUMN_WIDTHS,
    DEFAULT_CONFIG_FIELDS,
    DEFAULT_DOCUMENTS_COLUMN_WIDTHS,
    DEFAULT_DOCUMENTS_HEADERS,
    DEFAULT_PROMPT_COLUMN_WIDTHS,
    DEFAULT_PROMPT_HEADERS,
    DEFAULT_TOOLS_COLUMN_WIDTHS,
    DEFAULT_TOOLS_HEADERS,
    PromptSpec,
    SectionDefinition,
)
from .builders import WorkbookBuilder
from .utils import (
    build_config_overrides,
    build_sample_clients_overrides,
    create_client_argument_parser,
    get_available_clients,
    get_client_config,
    parse_client_args,
)
from .validators import WorkbookValidator, create_validator

__all__ = [
    "WorkbookBuilder",
    "WorkbookValidator",
    "PromptSpec",
    "SectionDefinition",
    "create_validator",
    "DEFAULT_CONFIG_FIELDS",
    "DEFAULT_CONFIG_COLUMN_WIDTHS",
    "DEFAULT_BATCH_CONFIG_FIELDS",
    "DEFAULT_PROMPT_HEADERS",
    "DEFAULT_PROMPT_COLUMN_WIDTHS",
    "DEFAULT_CLIENTS_HEADERS",
    "DEFAULT_CLIENTS_COLUMN_WIDTHS",
    "DEFAULT_DOCUMENTS_HEADERS",
    "DEFAULT_DOCUMENTS_COLUMN_WIDTHS",
    "DEFAULT_TOOLS_HEADERS",
    "DEFAULT_TOOLS_COLUMN_WIDTHS",
    "get_available_clients",
    "get_client_config",
    "build_config_overrides",
    "build_sample_clients_overrides",
    "create_client_argument_parser",
    "parse_client_args",
]
