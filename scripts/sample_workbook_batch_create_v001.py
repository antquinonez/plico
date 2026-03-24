#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Generate sample workbook for batch execution testing.

Creates 35 prompts with {{variable}} templating:
- Uses 5 data rows (batches) with different regions/products
- Tests variable resolution across all prompt types
- Tests dependency chains within batches

Uses FFLiteLLMClient with LiteLLM routing for Mistral Small.

Paired with: sample_workbook_batch_validate_v001.py

Usage:
    python scripts/sample_workbook_batch_create_v001.py [output_path] [--client CLIENT]

Examples:
    python scripts/sample_workbook_batch_create_v001.py
    python scripts/sample_workbook_batch_create_v001.py ./test.xlsx
    python scripts/sample_workbook_batch_create_v001.py ./test.xlsx --client anthropic
    python scripts/sample_workbook_batch_create_v001.py -c gemini

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


def get_data_rows() -> list[dict]:
    """Return batch data rows."""
    return [
        {
            "id": 1,
            "batch_name": "{{region}}_{{product}}",
            "region": "north",
            "product": "widget_a",
            "price": 10,
            "quantity": 100,
        },
        {
            "id": 2,
            "batch_name": "{{region}}_{{product}}",
            "region": "south",
            "product": "widget_b",
            "price": 15,
            "quantity": 75,
        },
        {
            "id": 3,
            "batch_name": "{{region}}_{{product}}",
            "region": "east",
            "product": "widget_c",
            "price": 20,
            "quantity": 50,
        },
        {
            "id": 4,
            "batch_name": "{{region}}_{{product}}",
            "region": "west",
            "product": "widget_a",
            "price": 12,
            "quantity": 80,
        },
        {
            "id": 5,
            "batch_name": "{{region}}_{{product}}",
            "region": "central",
            "product": "widget_b",
            "price": 18,
            "quantity": 60,
        },
    ]


def get_prompts() -> list[PromptSpec]:
    """Return all prompts for the batch workbook."""
    prompts = []

    # LEVEL 0: 10 Independent Prompts (uses variables)
    prompts.append(
        PromptSpec(
            1,
            "intro",
            "You are analyzing sales data for {{region}} region, product {{product}}. Confirm by saying 'Analyzing {{region}} {{product}}'.",
        )
    )
    prompts.append(
        PromptSpec(
            2, "price_check", "The price of {{product}} is {{price}}. Just confirm the price."
        )
    )
    prompts.append(
        PromptSpec(
            3,
            "quantity_check",
            "The quantity sold of {{product}} in {{region}} is {{quantity}}. Just confirm the quantity.",
        )
    )
    prompts.append(
        PromptSpec(
            4,
            "region_fact",
            "Name one interesting fact about the {{region}} region. Keep it brief.",
        )
    )
    prompts.append(
        PromptSpec(5, "product_desc", "Describe what {{product}} might be in 10 words or less.")
    )
    prompts.append(
        PromptSpec(
            6,
            "calc_revenue",
            "Calculate total revenue: {{price}} times {{quantity}}. Just give the number.",
        )
    )
    prompts.append(
        PromptSpec(7, "calc_double", "What is {{quantity}} times 2? Just give the number.")
    )
    prompts.append(
        PromptSpec(8, "calc_half", "What is {{quantity}} divided by 2? Just give the number.")
    )
    prompts.append(
        PromptSpec(
            9,
            "calc_price_plus_tax",
            "If tax is 10%, what is the final price for {{price}}? Just give the number.",
        )
    )
    prompts.append(
        PromptSpec(10, "calc_quantity_10pct", "What is 10% of {{quantity}}? Just give the number.")
    )

    # LEVEL 1: 10 Prompts with Dependencies
    prompts.append(
        PromptSpec(
            11,
            "revenue_check",
            "Confirm: the revenue from calc_revenue should be price times quantity. Is this correct for {{region}}?",
            history='["calc_revenue", "price_check", "quantity_check"]',
        )
    )
    prompts.append(
        PromptSpec(
            12,
            "double_check",
            "If we doubled sales in {{region}}, what would the new quantity be? Answer based on calc_double.",
            history='["calc_double"]',
        )
    )
    prompts.append(
        PromptSpec(
            13,
            "half_check",
            "If we sold half as much in {{region}}, what would the quantity be? Based on calc_half.",
            history='["calc_half"]',
        )
    )
    prompts.append(
        PromptSpec(
            14,
            "tax_check",
            "Is the taxed price from calc_price_plus_tax higher than {{price}}? Answer yes or no.",
            history='["calc_price_plus_tax", "price_check"]',
        )
    )
    prompts.append(
        PromptSpec(
            15,
            "pct_check",
            "10% of our {{quantity}} units is how many? Confirm with calc_quantity_10pct.",
            history='["calc_quantity_10pct", "quantity_check"]',
        )
    )
    prompts.append(
        PromptSpec(
            16,
            "market_size",
            "Based on {{quantity}} units in {{region}}, is this a large or small market? Answer briefly.",
            history='["quantity_check"]',
        )
    )
    prompts.append(
        PromptSpec(
            17,
            "pricing_analysis",
            "At {{price}} per unit, is {{product}} premium or budget? Answer briefly.",
            history='["price_check", "product_desc"]',
        )
    )
    prompts.append(
        PromptSpec(
            18,
            "region_potential",
            "Given {{region}} region facts, what's the growth potential? Answer in one sentence.",
            history='["region_fact", "quantity_check"]',
        )
    )
    prompts.append(
        PromptSpec(
            19,
            "product_fit",
            "Does {{product}} fit well with {{region}} region? Answer yes/no with brief reason.",
            history='["product_desc", "region_fact"]',
        )
    )
    prompts.append(
        PromptSpec(
            20,
            "sales_trend",
            "If we project {{quantity}} units growing 10% (calc_quantity_10pct), what's the outlook?",
            history='["calc_quantity_10pct", "quantity_check"]',
        )
    )

    # LEVEL 2: 10 Prompts with Multiple Dependencies
    prompts.append(
        PromptSpec(
            21,
            "revenue_analysis",
            "Analyze the revenue situation for {{region}} {{product}} using revenue_check and pricing_analysis.",
            history='["revenue_check", "pricing_analysis"]',
        )
    )
    prompts.append(
        PromptSpec(
            22,
            "volume_analysis",
            "Analyze sales volume for {{region}} using double_check, half_check, and market_size.",
            history='["double_check", "half_check", "market_size"]',
        )
    )
    prompts.append(
        PromptSpec(
            23,
            "competitiveness",
            "Is {{product}} at {{price}} competitive? Use pricing_analysis and product_fit.",
            history='["pricing_analysis", "product_fit"]',
        )
    )
    prompts.append(
        PromptSpec(
            24,
            "growth_analysis",
            "Analyze growth potential using pct_check, sales_trend, and region_potential.",
            history='["pct_check", "sales_trend", "region_potential"]',
        )
    )
    prompts.append(
        PromptSpec(
            25,
            "market_position",
            "Summarize market position using market_size and competitiveness.",
            history='["market_size", "competitiveness"]',
        )
    )
    prompts.append(
        PromptSpec(
            26,
            "profit_estimate",
            "If cost is 60% of {{price}}, estimate profit for {{quantity}} units. Give just the number.",
            history='["calc_revenue", "price_check", "quantity_check"]',
        )
    )
    prompts.append(
        PromptSpec(
            27,
            "break_even",
            "If fixed costs are 1000, how many {{product}} units at {{price}} to break even? Give number.",
            history='["price_check"]',
        )
    )
    prompts.append(
        PromptSpec(
            28,
            "margin_check",
            "At price {{price}} with estimated profit, what's the profit margin percentage?",
            history='["profit_estimate", "price_check"]',
        )
    )
    prompts.append(
        PromptSpec(
            29,
            "volume_impact",
            "If quantity doubles (calc_double), what's the new revenue? Use calc_revenue as base.",
            history='["calc_revenue", "calc_double"]',
        )
    )
    prompts.append(
        PromptSpec(
            30,
            "scenario_compare",
            "Compare current revenue (calc_revenue) vs doubled quantity (volume_impact). Which is higher?",
            history='["calc_revenue", "volume_impact"]',
        )
    )

    # LEVEL 3: 5 Final Synthesis Prompts
    prompts.append(
        PromptSpec(
            31,
            "executive_summary",
            "Provide a 2-sentence executive summary for {{region}} {{product}} using revenue_analysis and market_position.",
            history='["revenue_analysis", "market_position"]',
        )
    )
    prompts.append(
        PromptSpec(
            32,
            "recommendations",
            "Based on growth_analysis and competitiveness, give 2 recommendations for {{region}}.",
            history='["growth_analysis", "competitiveness"]',
        )
    )
    prompts.append(
        PromptSpec(
            33,
            "risk_assessment",
            "Assess risks for {{product}} in {{region}} using market_position and scenario_compare.",
            history='["market_position", "scenario_compare"]',
        )
    )
    prompts.append(
        PromptSpec(
            34,
            "action_plan",
            "Create a 3-step action plan for {{region}} using all previous analyses.",
            history='["executive_summary", "recommendations", "risk_assessment"]',
        )
    )
    prompts.append(
        PromptSpec(
            35,
            "final_score",
            "On a scale of 1-10, score the {{region}} {{product}} business potential. Just give the number.",
            history='["executive_summary", "market_position", "growth_analysis"]',
        )
    )

    return prompts


def create_batch_sample_workbook(
    output_path: str,
    config_overrides: dict | None = None,
):
    """Create the batch sample workbook.

    Args:
        output_path: Path where the workbook will be saved.
        config_overrides: Optional overrides for the config sheet (client_type, model).

    """
    prompts = get_prompts()
    data_rows = get_data_rows()
    config = get_config()
    batch_config = config.workbook.batch

    builder = WorkbookBuilder(output_path)
    builder.add_config_sheet(
        overrides=config_overrides,
        extra_fields=[
            (
                "batch_mode",
                batch_config.mode,
                "Batch execution mode: 'per_row' (execute for each data row)",
            ),
            (
                "batch_output",
                batch_config.output,
                "Output format: 'combined' (single sheet) or 'separate_sheets'",
            ),
            (
                "on_batch_error",
                batch_config.on_error,
                "Error handling: 'continue' (skip failed) or 'stop' (halt on error)",
            ),
        ],
    )
    builder.add_data_sheet(data_rows)
    builder.add_prompts_sheet(prompts, include_extra_columns=False)
    builder.save()

    builder.print_summary(
        "BATCH",
        {
            "Total prompts": len(prompts),
            "Total batches": len(data_rows),
            "Client": config_overrides.get("client_type", "default")
            if config_overrides
            else "default",
            "Data Variables": [
                "region: north, south, east, west, central",
                "product: widget_a, widget_b, widget_c",
                "price: 10, 12, 15, 18, 20",
                "quantity: 50, 60, 75, 80, 100",
            ],
            "Prompt Structure": {
                "Level 0": "10 independent prompts (sequences 1-10)",
                "Level 1": "10 prompts with 1-3 dependencies (sequences 11-20)",
                "Level 2": "10 prompts with 2-3 dependencies (sequences 21-30)",
                "Level 3": "5 synthesis prompts (sequences 31-35)",
            },
            "Total executions": f"{len(prompts)} prompts x {len(data_rows)} batches = {len(prompts) * len(data_rows)} total",
        },
    )


if __name__ == "__main__":
    config = get_config()

    args, config_overrides, _ = parse_client_args(
        script_description="Generate sample workbook for batch execution testing.",
        default_output=config.sample.workbooks.batch,
    )

    create_batch_sample_workbook(args.output, config_overrides)
