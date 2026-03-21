#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Generate sample workbook for conditional execution testing with extensive functionality.

Creates 50 prompts testing:
    - String methods: startswith, endswith, lower, upper, strip, replace, split, count, etc.
    - JSON functions: json_get, json_get_default, json_has, json_keys, json_parse, json_type
    - List/dict operations: membership, subscript access, methods
    - Math functions: abs, min, max, round
    - Type functions: is_null, is_empty, bool
    - Complex combined conditions

Paired with: sample_workbook_conditional_validate_v001.py

Usage:
    python scripts/sample_workbook_conditional_create_v001.py [output_path] [--client CLIENT]

Examples:
    python scripts/sample_workbook_conditional_create_v001.py
    python scripts/sample_workbook_conditional_create_v001.py ./test.xlsx
    python scripts/sample_workbook_conditional_create_v001.py ./test.xlsx --client anthropic
    python scripts/sample_workbook_conditional_create_v001.py -c gemini

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
    """Return all prompts for the conditional workbook."""
    prompts = []

    # SECTION 1: String Method Tests (1-10)
    prompts.append(
        PromptSpec(
            1, "gen_status", "Respond with exactly: 'SUCCESS: Operation completed'", client="fast"
        )
    )
    prompts.append(
        PromptSpec(
            2,
            "check_prefix",
            "The previous response started with SUCCESS. Confirm by saying 'Prefix confirmed'.",
            history='["gen_status"]',
            client="fast",
            condition='{{gen_status.response}}.startswith("SUCCESS")',
        )
    )
    prompts.append(
        PromptSpec(
            3,
            "check_suffix",
            "The previous response ended with 'completed'. Confirm by saying 'Suffix confirmed'.",
            history='["gen_status"]',
            client="fast",
            condition='{{gen_status.response}}.endswith("completed")',
        )
    )
    prompts.append(
        PromptSpec(4, "gen_uppercase", "Respond with exactly: 'HELLO WORLD'", client="fast")
    )
    prompts.append(
        PromptSpec(
            5,
            "check_lower",
            "Convert the previous response to lowercase and confirm it says 'hello world'.",
            history='["gen_uppercase"]',
            client="fast",
            condition='{{gen_uppercase.response}}.lower() == "hello world"',
        )
    )
    prompts.append(
        PromptSpec(
            6,
            "gen_whitespace",
            "Respond with exactly: '  padded  ' (include the spaces)",
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            7,
            "check_strip",
            "The trimmed response should equal 'padded'. Confirm by saying 'Strip works'.",
            history='["gen_whitespace"]',
            client="fast",
            condition='{{gen_whitespace.response}}.strip() == "padded"',
        )
    )
    prompts.append(
        PromptSpec(8, "gen_countable", "Respond with exactly: 'error error error'", client="fast")
    )
    prompts.append(
        PromptSpec(
            9,
            "check_count",
            "The word 'error' appeared 3 times. Confirm by saying 'Count verified'.",
            history='["gen_countable"]',
            client="fast",
            condition='{{gen_countable.response}}.count("error") == 3',
        )
    )
    prompts.append(
        PromptSpec(
            10,
            "section1_summary",
            "All string method tests passed. Say 'String methods: OK'.",
            history='["check_prefix", "check_suffix", "check_lower", "check_strip", "check_count"]',
            client="default",
            condition='{{check_prefix.status}} == "success" and {{check_count.status}} == "success"',
        )
    )

    # SECTION 2: JSON Simple Access (11-18)
    prompts.append(
        PromptSpec(
            11,
            "gen_json_simple",
            'Return exactly this JSON: {"status": "active", "count": 42}',
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            12,
            "check_json_status",
            "The JSON status was 'active'. Confirm by saying 'Status is active'.",
            history='["gen_json_simple"]',
            client="fast",
            condition='json_get({{gen_json_simple.response}}, "status") == "active"',
        )
    )
    prompts.append(
        PromptSpec(
            13,
            "check_json_count",
            "The JSON count was 42. Confirm by saying 'Count is 42'.",
            history='["gen_json_simple"]',
            client="fast",
            condition='json_get({{gen_json_simple.response}}, "count") == 42',
        )
    )
    prompts.append(
        PromptSpec(
            14,
            "check_json_has_status",
            "The JSON has a 'status' key. Confirm by saying 'Key exists'.",
            history='["gen_json_simple"]',
            client="fast",
            condition='json_has({{gen_json_simple.response}}, "status") == True',
        )
    )
    prompts.append(
        PromptSpec(
            15,
            "check_json_missing_key",
            "The JSON does not have an 'error' key. Confirm by saying 'No error key'.",
            history='["gen_json_simple"]',
            client="fast",
            condition='json_has({{gen_json_simple.response}}, "error") == False',
        )
    )
    prompts.append(
        PromptSpec(
            16,
            "check_json_type_string",
            "The 'status' value is a string type. Confirm by saying 'Type is string'.",
            history='["gen_json_simple"]',
            client="fast",
            condition='json_type({{gen_json_simple.response}}, "status") == "string"',
        )
    )
    prompts.append(
        PromptSpec(
            17,
            "check_json_type_number",
            "The 'count' value is a number type. Confirm by saying 'Type is number'.",
            history='["gen_json_simple"]',
            client="fast",
            condition='json_type({{gen_json_simple.response}}, "count") == "number"',
        )
    )
    prompts.append(
        PromptSpec(
            18,
            "section2_summary",
            "JSON simple access tests completed. Say 'JSON simple: OK'.",
            history='["check_json_status", "check_json_count", "check_json_has_status"]',
            client="default",
            condition='{{check_json_status.status}} == "success"',
        )
    )

    # SECTION 3: JSON Nested Access (19-26)
    prompts.append(
        PromptSpec(
            19,
            "gen_json_nested",
            'Return exactly this JSON: {"data": {"user": {"name": "Alice", "age": 30}}}',
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            20,
            "check_nested_name",
            "The nested name was 'Alice'. Confirm by saying 'Name is Alice'.",
            history='["gen_json_nested"]',
            client="fast",
            condition='json_get({{gen_json_nested.response}}, "data.user.name") == "Alice"',
        )
    )
    prompts.append(
        PromptSpec(
            21,
            "check_nested_age",
            "The nested age was 30. Confirm by saying 'Age is 30'.",
            history='["gen_json_nested"]',
            client="fast",
            condition='json_get({{gen_json_nested.response}}, "data.user.age") == 30',
        )
    )
    prompts.append(
        PromptSpec(
            22,
            "check_deep_path_exists",
            "The deep path 'data.user.name' exists. Confirm by saying 'Path exists'.",
            history='["gen_json_nested"]',
            client="fast",
            condition='json_has({{gen_json_nested.response}}, "data.user.name") == True',
        )
    )
    prompts.append(
        PromptSpec(
            23,
            "check_deep_path_missing",
            "The path 'data.user.email' does not exist. Confirm by saying 'Email missing'.",
            history='["gen_json_nested"]',
            client="fast",
            condition='json_has({{gen_json_nested.response}}, "data.user.email") == False',
        )
    )
    prompts.append(
        PromptSpec(
            24,
            "check_json_default",
            "Using default value for missing key. Confirm 'Default works'.",
            history='["gen_json_nested"]',
            client="fast",
            condition='json_get_default({{gen_json_nested.response}}, "data.user.email", "none") == "none"',
        )
    )
    prompts.append(
        PromptSpec(
            25,
            "check_json_default_returns_value",
            "Existing key returns value not default. Confirm 'Value not default'.",
            history='["gen_json_nested"]',
            client="fast",
            condition='json_get_default({{gen_json_nested.response}}, "data.user.age", 0) == 30',
        )
    )
    prompts.append(
        PromptSpec(
            26,
            "section3_summary",
            "JSON nested access tests completed. Say 'JSON nested: OK'.",
            history='["check_nested_name", "check_nested_age", "check_json_default"]',
            client="default",
            condition='{{check_nested_name.status}} == "success"',
        )
    )

    # SECTION 4: JSON Array Access (27-34)
    prompts.append(
        PromptSpec(
            27,
            "gen_json_array",
            'Return exactly this JSON: {"items": ["apple", "banana", "cherry"]}',
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            28,
            "check_array_first",
            "The first item was 'apple'. Confirm by saying 'First is apple'.",
            history='["gen_json_array"]',
            client="fast",
            condition='json_get({{gen_json_array.response}}, "items[0]") == "apple"',
        )
    )
    prompts.append(
        PromptSpec(
            29,
            "check_array_second",
            "The second item was 'banana'. Confirm by saying 'Second is banana'.",
            history='["gen_json_array"]',
            client="fast",
            condition='json_get({{gen_json_array.response}}, "items[1]") == "banana"',
        )
    )
    prompts.append(
        PromptSpec(
            30,
            "check_array_third",
            "The third item was 'cherry'. Confirm by saying 'Third is cherry'.",
            history='["gen_json_array"]',
            client="fast",
            condition='json_get({{gen_json_array.response}}, "items[2]") == "cherry"',
        )
    )
    prompts.append(
        PromptSpec(
            31,
            "check_array_type",
            "The 'items' value is an array type. Confirm by saying 'Type is array'.",
            history='["gen_json_array"]',
            client="fast",
            condition='json_type({{gen_json_array.response}}, "items") == "array"',
        )
    )
    prompts.append(
        PromptSpec(
            32,
            "check_keys_list",
            "The JSON has an 'items' key in its keys. Confirm by saying 'Items in keys'.",
            history='["gen_json_array"]',
            client="fast",
            condition='"items" in json_keys({{gen_json_array.response}})',
        )
    )
    prompts.append(
        PromptSpec(
            33,
            "check_keys_count",
            "The JSON has exactly 1 key. Confirm by saying 'One key'.",
            history='["gen_json_array"]',
            client="fast",
            condition="len(json_keys({{gen_json_array.response}})) == 1",
        )
    )
    prompts.append(
        PromptSpec(
            34,
            "section4_summary",
            "JSON array access tests completed. Say 'JSON array: OK'.",
            history='["check_array_first", "check_array_third", "check_keys_list"]',
            client="default",
            condition='{{check_array_first.status}} == "success"',
        )
    )

    # SECTION 5: JSON Complex Nested (35-38)
    prompts.append(
        PromptSpec(
            35,
            "gen_json_complex",
            'Return exactly this JSON: {"data": {"items": [{"id": 1, "name": "first"}, {"id": 2, "name": "second"}]}}',
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            36,
            "check_complex_id",
            "The second item's id was 2. Confirm by saying 'ID is 2'.",
            history='["gen_json_complex"]',
            client="fast",
            condition='json_get({{gen_json_complex.response}}, "data.items[1].id") == 2',
        )
    )
    prompts.append(
        PromptSpec(
            37,
            "check_complex_name",
            "The first item's name was 'first'. Confirm by saying 'Name is first'.",
            history='["gen_json_complex"]',
            client="fast",
            condition='json_get({{gen_json_complex.response}}, "data.items[0].name") == "first"',
        )
    )
    prompts.append(
        PromptSpec(
            38,
            "section5_summary",
            "JSON complex nested tests completed. Say 'JSON complex: OK'.",
            history='["check_complex_id", "check_complex_name"]',
            client="default",
            condition='{{check_complex_id.status}} == "success" and {{check_complex_name.status}} == "success"',
        )
    )

    # SECTION 6: Math Functions (39-44)
    prompts.append(PromptSpec(39, "gen_negative", "Respond with exactly: '-42'", client="fast"))
    prompts.append(
        PromptSpec(
            40,
            "check_abs",
            "The absolute value is 42. Confirm by saying 'Abs is 42'.",
            history='["gen_negative"]',
            client="fast",
            condition="abs(int({{gen_negative.response}})) == 42",
        )
    )
    prompts.append(PromptSpec(41, "gen_number_5", "Respond with exactly: '5'", client="fast"))
    prompts.append(
        PromptSpec(
            42,
            "check_min",
            "The minimum of 5 and 10 is 5. Confirm by saying 'Min is 5'.",
            history='["gen_number_5"]',
            client="fast",
            condition="min(int({{gen_number_5.response}}), 10) == 5",
        )
    )
    prompts.append(
        PromptSpec(
            43,
            "check_max",
            "The maximum of 5 and 3 is 5. Confirm by saying 'Max is 5'.",
            history='["gen_number_5"]',
            client="fast",
            condition="max(int({{gen_number_5.response}}), 3) == 5",
        )
    )
    prompts.append(
        PromptSpec(
            44,
            "section6_summary",
            "Math function tests completed. Say 'Math functions: OK'.",
            history='["check_abs", "check_min", "check_max"]',
            client="default",
            condition='{{check_abs.status}} == "success"',
        )
    )

    # SECTION 7: Type Checking Functions (45-47)
    prompts.append(
        PromptSpec(
            45,
            "gen_empty_test",
            "Respond with exactly: '' (empty string, just quotes)",
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            46,
            "check_is_empty",
            "The response was empty. Confirm by saying 'Response is empty'.",
            history='["gen_empty_test"]',
            client="fast",
            condition="is_empty({{gen_empty_test.response}}) == True",
        )
    )
    prompts.append(
        PromptSpec(
            47,
            "section7_summary",
            "Type checking tests completed. Say 'Type checks: OK'.",
            history='["check_is_empty"]',
            client="default",
            condition='{{check_is_empty.status}} == "success"',
        )
    )

    # SECTION 8: Combined Complex Conditions (48-50)
    prompts.append(
        PromptSpec(
            48,
            "gen_combined_json",
            'Return exactly this JSON: {"status": "SUCCESS", "data": {"score": 85, "items": ["a", "b"]}}',
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            49,
            "check_combined_all",
            "Complex check: status starts with SUCCESS, score > 80, items array exists. Say 'All checks pass'.",
            history='["gen_combined_json"]',
            client="fast",
            condition='json_get({{gen_combined_json.response}}, "status").startswith("SUCCESS") and json_get({{gen_combined_json.response}}, "data.score") > 80 and json_has({{gen_combined_json.response}}, "data.items")',
        )
    )
    prompts.append(
        PromptSpec(
            50,
            "final_report",
            "Create a one-line summary of all 50 conditional execution tests using new features: string methods, JSON access, math functions, and combined conditions.",
            history='["section1_summary", "section2_summary", "section3_summary", "section4_summary", "section5_summary", "section6_summary", "section7_summary", "check_combined_all"]',
            client="creative",
            condition='{{section1_summary.status}} == "success" and {{section2_summary.status}} == "success" and {{check_combined_all.status}} == "success"',
        )
    )

    return prompts


def create_conditional_sample_workbook(
    output_path: str,
    config_overrides: dict | None = None,
    sample_clients_overrides: dict | None = None,
):
    """Create the conditional sample workbook.

    Args:
        output_path: Path where the workbook will be saved.
        config_overrides: Optional overrides for the config sheet (client_type, model).
        sample_clients_overrides: Optional overrides for sample_clients in the clients sheet.

    """
    prompts = get_prompts()

    builder = WorkbookBuilder(output_path)
    builder.add_config_sheet(
        overrides={
            "system_instructions": (
                "You are a helpful assistant. For JSON questions, return valid JSON. "
                "For classification, respond with just the category. "
                "For yes/no questions, respond with just 'yes' or 'no'. "
                "Keep responses concise."
            ),
            **(config_overrides or {}),
        }
    )
    builder.add_clients_sheet(sample_clients_overrides=sample_clients_overrides)
    builder.add_prompts_sheet(prompts, include_extra_columns=False)
    builder.save()

    builder.print_summary(
        "conditional execution",
        {
            "Total prompts": len(prompts),
            "Client": config_overrides.get("client_type", "default")
            if config_overrides
            else "default",
            "Conditional Patterns Tested": [
                "SECTION 1 - String Methods (1-10): .startswith(), .endswith(), .lower(), .strip(), .count()",
                "SECTION 2 - JSON Simple Access (11-18): json_get(), json_has(), json_type()",
                "SECTION 3 - JSON Nested Access (19-26): Nested path, json_get_default()",
                "SECTION 4 - JSON Array Access (27-34): Array indexing, json_keys(), 'in' operator",
                "SECTION 5 - JSON Complex Nested (35-38): Deep nesting",
                "SECTION 6 - Math Functions (39-44): abs(), min(), max()",
                "SECTION 7 - Type Checking (45-47): is_empty()",
                "SECTION 8 - Combined Conditions (48-50): Chained conditions",
            ],
        },
    )


if __name__ == "__main__":
    config = get_config()

    args, config_overrides, sample_clients_overrides = parse_client_args(
        script_description="Generate sample workbook for conditional execution testing.",
        default_output=config.sample.workbooks.conditional,
    )

    create_conditional_sample_workbook(args.output, config_overrides, sample_clients_overrides)
