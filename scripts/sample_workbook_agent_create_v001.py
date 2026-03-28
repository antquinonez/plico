#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Generate sample workbook for agentic tool-call testing.

Creates 10 prompts testing agentic execution:
- Prompts 1-2: Non-agent baseline (no tools)
- Prompts 3-5: Agent mode with single tools (calculate, json_extract)
- Prompts 6-7: Agent mode with multiple tools
- Prompts 8-9: Agent mode with conditions on tool results
- Prompt 10: Agent mode with max_tool_rounds=1 (edge case)

Uses built-in tools: calculate, json_extract, http_get.
No external API keys required beyond the default client.

Paired with: sample_workbook_agent_validate_v001.py

Usage:
    python scripts/sample_workbook_agent_create_v001.py [output_path] [--client CLIENT]

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

TOOLS = [
    {
        "name": "calculate",
        "description": "Evaluate a mathematical expression safely.",
        "parameters": '{"type":"object","properties":{"expression":{"type":"string","description":"Math expression to evaluate (e.g., \\"2 + 3 * 4\\")"}},"required":["expression"]}',
        "implementation": "builtin:calculate",
        "enabled": True,
    },
    {
        "name": "json_extract",
        "description": "Extract a field from a JSON string using dot notation.",
        "parameters": '{"type":"object","properties":{"data":{"type":"string","description":"JSON string to parse."},"path":{"type":"string","description":"Dot-separated path (e.g., \\"items.0.name\\")"}},"required":["data","path"]}',
        "implementation": "builtin:json_extract",
        "enabled": True,
    },
    {
        "name": "http_get",
        "description": "Fetch text content from a URL.",
        "parameters": '{"type":"object","properties":{"url":{"type":"string","description":"The URL to fetch."},"max_length":{"type":"integer","description":"Maximum characters to return.","default":5000}},"required":["url"]}',
        "implementation": "builtin:http_get",
        "enabled": True,
    },
]


def get_prompts() -> list[PromptSpec]:
    prompts = [
        PromptSpec(1, "baseline_math", "What is 42 * 17? Just give the number.", None),
        PromptSpec(
            2,
            "baseline_json",
            'Given the JSON \'{"score": 95, "grade": "A"}\', what is the score? Just give the number.',
            None,
        ),
        PromptSpec(
            3,
            "agent_calculate",
            "Use the calculate tool to compute (144 * 23) + 789 and report the result.",
            None,
            agent_mode="true",
            tools='["calculate"]',
        ),
        PromptSpec(
            4,
            "agent_json_extract",
            'Use the json_extract tool to extract the "capital" from the JSON \'{"country":"France","capital":"Paris","population":2161000}\' and report it.',
            None,
            agent_mode="true",
            tools='["json_extract"]',
        ),
        PromptSpec(
            5,
            "agent_chained_calc",
            "Use the calculate tool: first compute 12^3, then add 500, then divide by 2. Report each intermediate result and the final answer.",
            None,
            agent_mode="true",
            tools='["calculate"]',
            max_tool_rounds=10,
        ),
        PromptSpec(
            6,
            "agent_multi_tool",
            'Use the calculate tool to compute 2^10, then use json_extract to extract the "age" from the JSON \'{"name":"Alice","age":30,"city":"NYC"}\'. Report both results.',
            None,
            agent_mode="true",
            tools='["calculate", "json_extract"]',
        ),
        PromptSpec(
            7,
            "agent_calc_with_json",
            'Use json_extract to get the "value" from \'{"value": 256, "operation": "sqrt"}\', then use calculate to compute sqrt(value). Report the final result.',
            None,
            agent_mode="true",
            tools='["json_extract", "calculate"]',
        ),
        PromptSpec(
            8,
            "agent_condition_source",
            "Compute 3 * 7 using the calculate tool and report the result.",
            None,
            agent_mode="true",
            tools='["calculate"]',
        ),
        PromptSpec(
            9,
            "agent_condition_consumer",
            "Based on the result from agent_condition_source, use calculate to multiply that result by 10.",
            '["agent_condition_source"]',
            agent_mode="true",
            tools='["calculate"]',
            condition='{{agent_condition_source.status}} == "success"',
        ),
        PromptSpec(
            10,
            "agent_max_rounds_one",
            "Use calculate to compute the square root of 2. Give the result to 5 decimal places.",
            None,
            agent_mode="true",
            tools='["calculate"]',
            max_tool_rounds=1,
        ),
    ]
    return prompts


def create_sample_workbook(output_path: str, config_overrides: dict | None = None):
    prompts = get_prompts()

    builder = WorkbookBuilder(output_path)
    builder.add_config_sheet(overrides=config_overrides)
    builder.add_tools_sheet(TOOLS)
    builder.add_prompts_sheet(prompts, include_extra_columns=True)
    builder.save()

    builder.print_summary(
        "agent",
        {
            "Total prompts": len(prompts),
            "Structure": {
                "Baseline (1-2)": "Non-agent prompts, no tools",
                "Single tool (3-5)": "Agent mode with calculate or json_extract",
                "Multi tool (6-7)": "Agent mode with multiple tools in sequence",
                "Conditional (8-9)": "Agent with condition on previous agent result",
                "Edge case (10)": "Agent with max_tool_rounds=1",
            },
            "Tools sheet": f"{len(TOOLS)} tools: calculate, json_extract, http_get",
            "Client": config_overrides.get("client_type", "default")
            if config_overrides
            else "default",
        },
        run_command=f"python scripts/run_orchestrator.py {output_path} -c 1",
    )


if __name__ == "__main__":
    config = get_config()

    args, config_overrides, _ = parse_client_args(
        script_description="Generate sample workbook for agentic tool-call testing.",
        default_output=config.sample.workbooks.agent,
    )

    create_sample_workbook(args.output, config_overrides)
