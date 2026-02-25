#!/usr/bin/env python
"""
Generate test workbook for document reference testing.

Creates a workbook with:
    - config sheet
    - prompts sheet with references column
    - documents sheet
    - data sheet (optional batch data)

Usage:
    python scripts/create_test_workbook_documents.py [output_path]
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openpyxl import Workbook


def create_test_workbook(output_path: str):
    wb = Workbook()

    ws_config = wb.active
    ws_config.title = "config"
    ws_config["A1"] = "field"
    ws_config["B1"] = "value"

    config_data = [
        ("model", "mistral-small-2503"),
        ("api_key_env", "MISTRALSMALL_KEY"),
        ("max_retries", "2"),
        ("temperature", "0.7"),
        ("max_tokens", "1000"),
        (
            "system_instructions",
            "You are a helpful assistant. Analyze documents and answer questions based on their content.",
        ),
        ("created_at", datetime.now().isoformat()),
    ]

    for idx, (field, value) in enumerate(config_data, start=2):
        ws_config[f"A{idx}"] = field
        ws_config[f"B{idx}"] = value

    ws_config.column_dimensions["A"].width = 20
    ws_config.column_dimensions["B"].width = 70

    ws_documents = wb.create_sheet(title="documents")
    doc_headers = ["reference_name", "common_name", "file_path", "notes"]
    for col_idx, header in enumerate(doc_headers, start=1):
        ws_documents.cell(row=1, column=col_idx, value=header)

    library_dir = Path(__file__).parent.parent / "library"

    documents = [
        (
            "product_spec",
            "Product Specification",
            "library/product_spec.md",
            "Main product documentation",
        ),
        ("api_ref", "API Reference", "library/api_reference.txt", "API documentation"),
        ("config", "Configuration File", "library/config.json", "App configuration"),
        (
            "troubleshoot",
            "Troubleshooting Guide",
            "library/troubleshooting.txt",
            "Common issues and solutions",
        ),
    ]

    for row_idx, (ref_name, common_name, file_path, notes) in enumerate(
        documents, start=2
    ):
        ws_documents.cell(row=row_idx, column=1, value=ref_name)
        ws_documents.cell(row=row_idx, column=2, value=common_name)
        ws_documents.cell(row=row_idx, column=3, value=file_path)
        ws_documents.cell(row=row_idx, column=4, value=notes)

    ws_documents.column_dimensions["A"].width = 18
    ws_documents.column_dimensions["B"].width = 25
    ws_documents.column_dimensions["C"].width = 50
    ws_documents.column_dimensions["D"].width = 30

    ws_prompts = wb.create_sheet(title="prompts")
    prompt_headers = [
        "sequence",
        "prompt_name",
        "prompt",
        "history",
        "client",
        "condition",
        "references",
    ]
    for col_idx, header in enumerate(prompt_headers, start=1):
        ws_prompts.cell(row=1, column=col_idx, value=header)

    prompts = [
        (
            1,
            "spec_summary",
            "Summarize the key features of the product specification.",
            None,
            None,
            None,
            '["product_spec"]',
        ),
        (
            2,
            "api_overview",
            "List the available client types and their purposes.",
            None,
            None,
            None,
            '["api_ref"]',
        ),
        (
            3,
            "config_analysis",
            "What features are enabled in the configuration?",
            None,
            None,
            None,
            '["config"]',
        ),
        (
            4,
            "combined_analysis",
            "Based on the product spec and API reference, describe the system architecture.",
            None,
            None,
            None,
            '["product_spec", "api_ref"]',
        ),
        (
            5,
            "troubleshoot_summary",
            "Summarize the common issues and their solutions.",
            None,
            None,
            None,
            '["troubleshoot"]',
        ),
        (
            6,
            "full_context",
            "Using all documents, provide a comprehensive overview of the FFClients system.",
            None,
            None,
            None,
            '["product_spec", "api_ref", "config", "troubleshoot"]',
        ),
        (
            7,
            "no_ref_prompt",
            "What is 2 + 2? Just give the number.",
            None,
            None,
            None,
            "",
        ),
    ]

    for row_idx, (seq, name, prompt, history, client, condition, refs) in enumerate(
        prompts, start=2
    ):
        ws_prompts.cell(row=row_idx, column=1, value=seq)
        ws_prompts.cell(row=row_idx, column=2, value=name)
        ws_prompts.cell(row=row_idx, column=3, value=prompt)
        ws_prompts.cell(row=row_idx, column=4, value=history if history else "")
        ws_prompts.cell(row=row_idx, column=5, value=client if client else "")
        ws_prompts.cell(row=row_idx, column=6, value=condition if condition else "")
        ws_prompts.cell(row=row_idx, column=7, value=refs if refs else "")

    ws_prompts.column_dimensions["A"].width = 10
    ws_prompts.column_dimensions["B"].width = 20
    ws_prompts.column_dimensions["C"].width = 60
    ws_prompts.column_dimensions["D"].width = 15
    ws_prompts.column_dimensions["E"].width = 12
    ws_prompts.column_dimensions["F"].width = 15
    ws_prompts.column_dimensions["G"].width = 30

    wb.save(output_path)

    print(f"\n{'=' * 60}")
    print(f"Created document reference test workbook: {output_path}")
    print(f"{'=' * 60}")
    print(f"\nDocuments defined: {len(documents)}")
    for ref_name, common_name, _, _ in documents:
        print(f"  - {ref_name}: {common_name}")
    print(f"\nPrompts defined: {len(prompts)}")
    print(f"  - 6 prompts with document references")
    print(f"  - 1 prompt without references")
    print(f"\n{'=' * 60}")
    print(f"Run with: python scripts/run_orchestrator.py {output_path}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "test_workbook_documents.xlsx"
    create_test_workbook(output)
