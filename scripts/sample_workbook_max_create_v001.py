#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Generate comprehensive sample workbook combining batch, conditional, multi-client, and RAG features.

This workbook demonstrates the full power of FFClients orchestrator:
- BATCH: Multiple data rows processed through the same prompt chain
- CONDITIONAL: Prompts execute/skip based on runtime conditions
- MULTI-CLIENT: Different model configurations for different task types
- RAG: Semantic search with query expansion, filtering, and reranking

Uses FFLiteLLMClient with LiteLLM routing for Mistral Small.

Creates 27 prompts across 6 sections with 5 batch data rows and 13 documents for RAG.

Paired with: sample_workbook_max_validate_v001.py

Usage:
    python scripts/sample_workbook_max_create_v001.py [output_path]

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import PromptSpec, WorkbookBuilder

from src.config import get_config


def get_documents() -> list[dict]:
    """Return document references for RAG."""
    config = get_config()
    library = config.paths.library

    return [
        {
            "reference_name": "product_spec",
            "common_name": "Product Specification",
            "file_path": f"{library}/product_spec.md",
            "tags": "product,specification,overview",
            "notes": "Main product documentation",
        },
        {
            "reference_name": "api_ref",
            "common_name": "API Reference",
            "file_path": f"{library}/api_reference.txt",
            "tags": "api,reference,clients,authentication",
            "notes": "API documentation",
        },
        {
            "reference_name": "config",
            "common_name": "Configuration File",
            "file_path": f"{library}/config.json",
            "tags": "config,json,settings",
            "notes": "App configuration",
        },
        {
            "reference_name": "troubleshoot",
            "common_name": "Troubleshooting Guide",
            "file_path": f"{library}/troubleshooting.txt",
            "tags": "troubleshooting,errors,issues,support",
            "notes": "Common issues and solutions",
        },
        {
            "reference_name": "architecture",
            "common_name": "System Architecture",
            "file_path": f"{library}/ARCHITECTURE.md",
            "tags": "architecture,system,design",
            "notes": "Overall system architecture documentation",
        },
        {
            "reference_name": "client_api_guide",
            "common_name": "Client API User Guide",
            "file_path": f"{library}/CLIENT API USER GUIDE.md",
            "tags": "client,api,guide,user",
            "notes": "User guide for client API usage",
        },
        {
            "reference_name": "clients_arch",
            "common_name": "Clients Architecture",
            "file_path": f"{library}/CLIENTS_ARCHITECTURE.md",
            "tags": "clients,architecture,design,ai",
            "notes": "Architecture for AI client implementations",
        },
        {
            "reference_name": "conditional_guide",
            "common_name": "Conditional Expressions Guide",
            "file_path": f"{library}/CONDITIONAL EXPRESSIONS USER GUIDE.md",
            "tags": "conditional,expressions,logic,prompts",
            "notes": "Guide for conditional expressions in prompts",
        },
        {
            "reference_name": "configuration_doc",
            "common_name": "Configuration Documentation",
            "file_path": f"{library}/CONFIGURATION.md",
            "tags": "configuration,yaml,pydantic,settings",
            "notes": "Configuration management documentation",
        },
        {
            "reference_name": "orchestrator_arch",
            "common_name": "Orchestrator Architecture",
            "file_path": f"{library}/ORCHESTRATOR_ARCHITECTURE.md",
            "tags": "orchestrator,architecture,excel,workbook",
            "notes": "Excel orchestrator architecture documentation",
        },
        {
            "reference_name": "orchestrator_readme",
            "common_name": "Orchestrator README",
            "file_path": f"{library}/ORCHESTRATOR README.md",
            "tags": "orchestrator,readme,usage,examples",
            "notes": "Orchestrator usage and examples",
        },
        {
            "reference_name": "rag_architecture",
            "common_name": "RAG Architecture",
            "file_path": f"{library}/RAG_ARCHITECTURE.md",
            "tags": "rag,embeddings,vectordb,search,chunking",
            "notes": "Retrieval-Augmented Generation architecture",
        },
        {
            "reference_name": "shared_history",
            "common_name": "Shared History Design",
            "file_path": f"{library}/SHARED_HISTORY_DESIGN.md",
            "tags": "history,conversation,sharing,context",
            "notes": "Conversation history sharing design",
        },
    ]


def get_batch_data() -> list[dict]:
    """Return batch data rows."""
    return [
        {
            "batch_name": "product_a",
            "product_name": "Wireless Headphones",
            "review_text": "The sound quality is amazing but the battery life could be better.",
            "priority": "high",
        },
        {
            "batch_name": "product_b",
            "product_name": "Coffee Maker",
            "review_text": "Works perfectly every morning. Love the auto-brew feature!",
            "priority": "medium",
        },
        {
            "batch_name": "product_c",
            "product_name": "Running Shoes",
            "review_text": "Uncomfortable after long runs. Disappointed with the fit.",
            "priority": "high",
        },
        {
            "batch_name": "product_d",
            "product_name": "Desk Lamp",
            "review_text": "Good brightness levels. The adjustable arm is very useful.",
            "priority": "low",
        },
        {
            "batch_name": "product_e",
            "product_name": "Water Bottle",
            "review_text": "Leaks when placed sideways. Cannot recommend.",
            "priority": "high",
        },
    ]


def get_prompts() -> list[PromptSpec]:
    """Return all prompts for the max workbook."""
    prompts = []

    # SECTION 1: Input Classification (1-3)
    prompts.append(
        PromptSpec(
            1,
            "classify_sentiment",
            "Classify this product review as positive, negative, or neutral. Just respond with the category name.\n\nProduct: {{product_name}}\nReview: {{review_text}}",
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            2,
            "rate_urgency",
            "Rate the urgency of this review on a scale of 1-5 (1=low, 5=critical). Consider the priority level: {{priority}}. Just respond with the number.\n\nReview: {{review_text}}",
            client="fast",
        )
    )
    prompts.append(
        PromptSpec(
            3,
            "detect_issues",
            "Analyze this review for any specific issues mentioned. If issues found, list them briefly. If no issues, say 'none'.\n\nReview: {{review_text}}",
            client="analytical",
        )
    )

    # SECTION 2: Conditional Branching (4-8)
    prompts.append(
        PromptSpec(
            4,
            "positive_response",
            "Write a warm thank-you response for this positive review. One sentence.\n\nProduct: {{product_name}}",
            history='["classify_sentiment"]',
            client="creative",
            condition='"positive" in lower({{classify_sentiment.response}})',
        )
    )
    prompts.append(
        PromptSpec(
            5,
            "negative_response",
            "Write a professional apology and resolution offer for this negative review. One sentence.\n\nProduct: {{product_name}}",
            history='["classify_sentiment"]',
            condition='"negative" in lower({{classify_sentiment.response}})',
        )
    )
    prompts.append(
        PromptSpec(
            6,
            "neutral_response",
            "Write a polite acknowledgment for this neutral review. One sentence.\n\nProduct: {{product_name}}",
            history='["classify_sentiment"]',
            condition='"neutral" in lower({{classify_sentiment.response}})',
        )
    )
    prompts.append(
        PromptSpec(
            7,
            "escalate_high",
            "Flag this as HIGH PRIORITY for immediate attention. Confirm with 'ESCALATED'.",
            history='["rate_urgency"]',
            client="analytical",
            condition='{{rate_urgency.response}} == "5" or {{rate_urgency.response}} == "4"',
        )
    )
    prompts.append(
        PromptSpec(
            8,
            "normal_priority",
            "Note: Standard response time applies. Confirm with 'QUEUED'.",
            history='["rate_urgency"]',
            condition='{{rate_urgency.response}} != "5" and {{rate_urgency.response}} != "4"',
        )
    )

    # SECTION 3: Issue Resolution (9-12)
    prompts.append(
        PromptSpec(
            9,
            "generate_solution",
            "Based on the issues detected, suggest a brief resolution or workaround. Keep it practical and concise.\n\nIssues: {{detect_issues.response}}",
            history='["detect_issues"]',
            client="creative",
            condition='lower({{detect_issues.response}}) != "none" and len({{detect_issues.response}}) > 4',
        )
    )
    prompts.append(
        PromptSpec(
            10,
            "no_issues_note",
            "No action needed - customer had no specific issues. Say 'No issues to address.'",
            history='["detect_issues"]',
            client="fast",
            condition='lower({{detect_issues.response}}) == "none" or len({{detect_issues.response}}) <= 4',
        )
    )
    prompts.append(
        PromptSpec(
            11,
            "detailed_analysis",
            "Provide a detailed analysis of why this review needs attention. Consider sentiment, urgency, and issues. Be thorough but concise.",
            history='["classify_sentiment", "rate_urgency", "detect_issues"]',
            client="analytical",
            condition='{{rate_urgency.response}} == "5" or {{rate_urgency.response}} == "4"',
        )
    )
    prompts.append(
        PromptSpec(
            12,
            "brief_summary",
            "Summarize the customer feedback in one sentence.",
            history='["classify_sentiment", "detect_issues"]',
            condition='{{rate_urgency.response}} != "5" and {{rate_urgency.response}} != "4"',
        )
    )

    # SECTION 4: Response Assembly (13-16)
    prompts.append(
        PromptSpec(
            13,
            "assemble_response",
            "Create the final customer response email. Include the appropriate sentiment response and any solutions if applicable.\n\nUse the sentiment response from previous steps.",
            history='["positive_response", "negative_response", "neutral_response", "generate_solution"]',
            client="creative",
            condition='{{positive_response.status}} == "success" or {{negative_response.status}} == "success" or {{neutral_response.status}} == "success"',
        )
    )
    prompts.append(
        PromptSpec(
            14,
            "priority_note",
            "Add the priority handling status to the response context.",
            history='["escalate_high", "normal_priority"]',
            condition='{{escalate_high.status}} == "success" or {{normal_priority.status}} == "success"',
        )
    )
    prompts.append(
        PromptSpec(
            15,
            "internal_notes",
            "Create internal notes for the support team about this review. Include analysis if available.",
            history='["detailed_analysis", "brief_summary"]',
            client="analytical",
            condition='{{detailed_analysis.status}} == "success" or {{brief_summary.status}} == "success"',
        )
    )
    prompts.append(
        PromptSpec(
            16,
            "skip_reason",
            "Note: Some steps were skipped due to conditional logic. Say 'Partial processing completed.'",
            history='["assemble_response"]',
            client="fast",
            condition='{{assemble_response.status}} != "success"',
        )
    )

    # SECTION 5: Final Reporting (17-20)
    prompts.append(
        PromptSpec(
            17,
            "metrics",
            "Based on this review processing, provide: sentiment category, urgency level (1-5), and whether issues were detected. Format: 'Sentiment: X, Urgency: Y, Issues: Z'",
            history='["classify_sentiment", "rate_urgency", "detect_issues"]',
            client="analytical",
        )
    )
    prompts.append(
        PromptSpec(
            18,
            "quality_check",
            "Quality check: Was a complete response generated? Answer yes or no.",
            history='["assemble_response"]',
            client="fast",
            condition='{{assemble_response.status}} == "success"',
        )
    )
    prompts.append(
        PromptSpec(
            19,
            "batch_item_summary",
            "Create a one-line summary for this batch item: {{batch_name}} - {{product_name}}.",
            history='["metrics", "quality_check"]',
            client="creative",
        )
    )
    prompts.append(
        PromptSpec(
            20,
            "final_confirmation",
            "Processing complete for {{product_name}}. Confirm with 'DONE' and include the sentiment classification result.",
            history='["batch_item_summary"]',
        )
    )

    # SECTION 6: RAG-Enhanced Analysis (21-27)
    prompts.append(
        PromptSpec(
            21,
            "rag_product_context",
            "Search documentation for best practices related to: {{product_name}}. Summarize any relevant guidance for handling this product category.",
            client="analytical",
            semantic_query="{{product_name}} product handling guidance",
        )
    )
    prompts.append(
        PromptSpec(
            22,
            "rag_sentiment_guidance",
            "Find guidance for handling negative customer feedback. Product: {{product_name}}",
            history='["classify_sentiment"]',
            condition='"negative" in lower({{classify_sentiment.response}})',
            semantic_query="negative feedback customer complaint handling",
        )
    )
    prompts.append(
        PromptSpec(
            23,
            "rag_troubleshooting_search",
            "Search troubleshooting documentation for solutions to: {{detect_issues.response}}",
            history='["detect_issues"]',
            condition='lower({{detect_issues.response}}) != "none"',
            semantic_query="troubleshooting error solution fix",
        )
    )
    prompts.append(
        PromptSpec(
            24,
            "rag_filtered_search",
            "Find escalation procedures from API documentation. Product: {{product_name}}, Urgency: {{rate_urgency.response}}",
            history='["rate_urgency"]',
            client="fast",
            condition='{{rate_urgency.response}} == "5" or {{rate_urgency.response}} == "4"',
            semantic_query="escalation priority urgent handling",
            semantic_filter='{"reference_name": "api_ref"}',
        )
    )
    prompts.append(
        PromptSpec(
            25,
            "rag_expanded_search",
            "Research comprehensive approaches for: {{product_name}} customer satisfaction. Review context: {{review_text}}",
            client="creative",
            semantic_query="customer satisfaction improvement quality",
            query_expansion="true",
        )
    )
    prompts.append(
        PromptSpec(
            26,
            "rag_reranked_search",
            "Find the most relevant solutions for reported issues: {{detect_issues.response}}",
            history='["classify_sentiment", "detect_issues"]',
            client="analytical",
            condition='"negative" in lower({{classify_sentiment.response}}) and lower({{detect_issues.response}}) != "none"',
            semantic_query="error fix solution troubleshooting",
            rerank="true",
        )
    )
    prompts.append(
        PromptSpec(
            27,
            "rag_comprehensive",
            "Based on the full API reference and semantic search results, provide a final recommendation for {{product_name}}.",
            history='["rag_reranked_search"]',
            client="creative",
            references='["api_ref"]',
            semantic_query="{{product_name}} recommendation guidance",
        )
    )

    return prompts


def create_max_sample_workbook(output_path: str):
    """Create the max sample workbook."""
    prompts = get_prompts()
    documents = get_documents()
    batch_data = get_batch_data()
    config = get_config()
    batch_config = config.workbook.batch

    builder = WorkbookBuilder(output_path)
    builder.add_config_sheet(
        overrides={
            "system_instructions": (
                "You are a helpful assistant. Give brief, concise answers. "
                "For classification, respond with just the category. "
                "For ratings, respond with just the number. "
                "For yes/no, respond with just 'yes' or 'no'."
            ),
        },
        extra_fields=[
            ("batch_mode", batch_config.mode),
            ("batch_output", batch_config.output),
            ("on_batch_error", batch_config.on_error),
        ],
    )
    builder.add_clients_sheet(client_names=["default", "fast", "creative", "analytical"])
    builder.add_data_sheet(batch_data)
    builder.add_documents_sheet(documents)
    builder.add_prompts_sheet(prompts, include_extra_columns=True)
    builder.save()

    rag_prompts = [p for p in prompts if p.semantic_query]
    filtered_rag = [p for p in prompts if p.semantic_filter]
    expanded_rag = [p for p in prompts if p.query_expansion]
    reranked_rag = [p for p in prompts if p.rerank]
    cond_count = sum(1 for p in prompts if p.condition)

    builder.print_summary(
        "MAX",
        {
            "FEATURES COMBINED": {
                "BATCH MODE": f"{len(batch_data)} data rows x {len(prompts)} prompts = {len(batch_data) * len(prompts)} total executions",
                "CONDITIONAL EXECUTION": f"{cond_count} prompts with conditions",
                "RAG SEMANTIC SEARCH": f"{len(rag_prompts)} semantic_query, {len(filtered_rag)} filtered, {len(expanded_rag)} expanded, {len(reranked_rag)} reranked",
            },
            "Documents defined": len(documents),
            "Prompt Structure": {
                "Section 1 (Seq 1-3)": "Input Classification",
                "Section 2 (Seq 4-8)": "Conditional Branching (sentiment + urgency)",
                "Section 3 (Seq 9-12)": "Issue Resolution",
                "Section 4 (Seq 13-16)": "Response Assembly",
                "Section 5 (Seq 17-20)": "Final Reporting",
                "Section 6 (Seq 21-27)": "RAG-Enhanced Analysis",
            },
        },
        run_command=f"python scripts/run_orchestrator.py {output_path} -c 3",
    )


if __name__ == "__main__":
    config = get_config()
    output = sys.argv[1] if len(sys.argv) > 1 else config.sample.workbooks.max
    create_max_sample_workbook(output)
