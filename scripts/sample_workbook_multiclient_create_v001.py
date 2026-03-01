#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Generate sample workbook for multi-client execution testing.

Creates a workbook with:
- config sheet
- prompts sheet with client column
- clients sheet with named client configurations using FFLiteLLMClient

Paired with: sample_workbook_multiclient_validate_v001.py

Usage:
    python scripts/sample_workbook_multiclient_create_v001.py [output_path]

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import PromptSpec, WorkbookBuilder

from src.config import get_config


def get_prompts() -> list[PromptSpec]:
    """Return all prompts for the multiclient workbook."""
    prompts = []

    # Level 0: Independent prompts using different clients
    prompts.append(
        PromptSpec(
            1,
            "classify",
            "Classify this sentiment: 'I love this product!'. Answer: positive, negative, or neutral.",
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            2,
            "analyze",
            "Analyze the sentence 'The weather is nice today' for linguistic features.",
        )
    )
    prompts.append(
        PromptSpec(3, "creative", "Write a one-line poem about clouds.", client="creative")
    )
    prompts.append(
        PromptSpec(
            4,
            "summarize",
            "Summarize: 'AI is transforming many industries including healthcare and finance.'",
            client="fast",
        )
    )
    prompts.append(PromptSpec(5, "expand", "Expand on this topic: 'Machine learning basics'"))

    # Level 1: Prompts with dependencies
    prompts.append(
        PromptSpec(
            6,
            "classify_context",
            "Based on the classification, explain why it was classified that way.",
            history='["classify"]',
        )
    )
    prompts.append(
        PromptSpec(
            7,
            "analyze_deep",
            "Provide a deeper linguistic analysis based on the initial analysis.",
            history='["analyze"]',
            client="creative",
        )
    )
    prompts.append(
        PromptSpec(
            8,
            "poem_explain",
            "Explain the imagery in the poem.",
            history='["creative"]',
        )
    )
    prompts.append(
        PromptSpec(
            9,
            "summary_validate",
            "Is this summary accurate and complete? Answer yes or no with reason.",
            history='["summarize"]',
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            10,
            "expand_outline",
            "Create an outline based on the expansion.",
            history='["expand"]',
        )
    )

    # Level 2: Synthesis prompts
    prompts.append(
        PromptSpec(
            11,
            "compare",
            "Compare the classification and analysis approaches used.",
            history='["classify", "analyze"]',
        )
    )
    prompts.append(
        PromptSpec(
            12,
            "creative_summary",
            "Summarize both the poem and its explanation creatively.",
            history='["creative", "poem_explain"]',
            client="creative",
        )
    )
    prompts.append(
        PromptSpec(
            13,
            "final_report",
            "Create a brief report summarizing all findings.",
            history='["classify_context", "analyze_deep", "summary_validate"]',
        )
    )

    return prompts


def create_multiclient_sample_workbook(output_path: str):
    """Create the multiclient sample workbook."""
    prompts = get_prompts()

    builder = WorkbookBuilder(output_path)
    builder.add_config_sheet(
        overrides={
            "system_instructions": "You are a helpful assistant. Give brief, concise answers.",
        }
    )
    builder.add_clients_sheet()
    builder.add_prompts_sheet(prompts, include_extra_columns=False)
    builder.save()

    client_assignments = {}
    for p in prompts:
        c = p.client or "(default)"
        client_assignments[f"Seq {p.sequence:2d} ({p.name})"] = c

    builder.print_summary(
        "MULTI-CLIENT",
        {
            "Total prompts": len(prompts),
            "Prompt client assignments": client_assignments,
            "Prompt Structure": {
                "Level 0": "5 independent prompts (sequences 1-5)",
                "Level 1": "5 prompts with 1 dependency (sequences 6-10)",
                "Level 2": "3 synthesis prompts (sequences 11-13)",
            },
        },
        run_command=f"python scripts/run_orchestrator.py {output_path} -c 2",
    )


if __name__ == "__main__":
    config = get_config()
    output = sys.argv[1] if len(sys.argv) > 1 else config.sample.workbooks.multiclient
    create_multiclient_sample_workbook(output)
