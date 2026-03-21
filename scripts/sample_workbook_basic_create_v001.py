#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Generate sample workbook for parallel execution testing.

Creates 31 prompts with various dependency patterns:
- Level 0: 12 independent prompts (fully parallel)
- Level 1: 10 prompts with 1-2 dependencies each
- Level 2: 5 prompts with 2-4 dependencies each
- Level 3: 4 final synthesis prompts

Uses FFLiteLLMClient with LiteLLM routing for Mistral Small.

Paired with: sample_workbook_basic_validate_v001.py

Usage:
    python scripts/sample_workbook_basic_create_v001.py [output_path] [--client CLIENT]

Examples:
    python scripts/sample_workbook_basic_create_v001.py
    python scripts/sample_workbook_basic_create_v001.py ./test.xlsx
    python scripts/sample_workbook_basic_create_v001.py ./test.xlsx --client anthropic
    python scripts/sample_workbook_basic_create_v001.py -c gemini

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import (
    PromptSpec,
    WorkbookBuilder,
    parse_client_args,
)

from src.config import get_config


def get_prompts() -> list[PromptSpec]:
    """Return all prompts for the basic workbook."""
    prompts = []

    # Level 0: 12 Independent Prompts (Parallel)
    for i in range(1, 7):
        prompts.append(
            PromptSpec(i, f"math_{i}", f"What is {i} + {i}? Just give the number.", None)
        )

    words = ["apple", "banana", "cherry", "dog", "elephant", "flower"]
    for i, word in enumerate(words, 7):
        prompts.append(
            PromptSpec(
                i,
                f"word_{i}",
                f"How many letters are in the word '{word}'? Just give the number.",
                None,
            )
        )

    # Level 1: 10 Prompts with Dependencies
    for i in range(1, 7):
        prompts.append(
            PromptSpec(
                12 + i,
                f"double_{i}",
                f"Take the result from math_{i} and multiply it by 2. Just give the number.",
                f'["math_{i}"]',
            )
        )

    for i in range(7, 11):
        prompts.append(
            PromptSpec(
                12 + i,
                f"compare_{i}",
                f"Is the word length from word_{i} greater than word_{i + 1}? Answer yes or no.",
                f'["word_{i}", "word_{i + 1}"]',
            )
        )

    # Level 2: 5 Prompts with Multiple Dependencies
    prompts.append(
        PromptSpec(
            23,
            "sum_1",
            "Add the results from double_1 and double_2. Just give the number.",
            '["double_1", "double_2"]',
        )
    )
    prompts.append(
        PromptSpec(
            24,
            "sum_2",
            "Add the results from double_3 and double_4. Just give the number.",
            '["double_3", "double_4"]',
        )
    )
    prompts.append(
        PromptSpec(
            25,
            "sum_3",
            "Add the results from double_5 and double_6. Just give the number.",
            '["double_5", "double_6"]',
        )
    )
    prompts.append(
        PromptSpec(
            26,
            "triple_check",
            "Add results from sum_1, sum_2, and sum_3. Just give the number.",
            '["sum_1", "sum_2", "sum_3"]',
        )
    )
    prompts.append(
        PromptSpec(
            27,
            "word_analysis",
            "Based on compare_7, compare_8, compare_9, and compare_10, are most answers yes or no?",
            '["compare_7", "compare_8", "compare_9", "compare_10"]',
        )
    )

    # Level 3: 4 Final Prompts
    prompts.append(
        PromptSpec(
            28,
            "final_math",
            "What is the final number from triple_check divided by 3? Just give the number.",
            '["triple_check"]',
        )
    )
    prompts.append(
        PromptSpec(
            29,
            "final_words",
            "Summarize: Are longer words typically before or after shorter words alphabetically? Based on word_analysis.",
            '["word_analysis"]',
        )
    )
    prompts.append(
        PromptSpec(30, "bonus_math", "What is 100 divided by 4? Just give the number.", None)
    )
    prompts.append(
        PromptSpec(31, "bonus_fact", "Name one interesting fact about the number 42.", None)
    )

    return prompts


def create_sample_workbook(output_path: str, config_overrides: dict | None = None):
    """Create the basic sample workbook.

    Args:
        output_path: Path where the workbook will be saved.
        config_overrides: Optional overrides for the config sheet (client_type, model).

    """
    prompts = get_prompts()

    builder = WorkbookBuilder(output_path)
    builder.add_config_sheet(overrides=config_overrides)
    builder.add_prompts_sheet(prompts, include_extra_columns=False)
    builder.save()

    builder.print_summary(
        "basic",
        {
            "Total prompts": len(prompts),
            "Dependency Structure": {
                "Level 0": "12 independent prompts (sequences 1-12)",
                "Level 1": "10 prompts with 1-2 dependencies (sequences 13-22)",
                "Level 2": "5 prompts with 2-4 dependencies (sequences 23-27)",
                "Level 3": "4 final prompts (sequences 28-31)",
            },
            "Client": config_overrides.get("client_type", "default")
            if config_overrides
            else "default",
        },
        run_command=f"python scripts/run_orchestrator.py {output_path} -c 3",
    )


if __name__ == "__main__":
    config = get_config()

    args, config_overrides, _ = parse_client_args(
        script_description="Generate sample workbook for parallel execution testing.",
        default_output=config.sample.workbooks.basic,
    )

    create_sample_workbook(args.output, config_overrides)
