#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Generate sample workbook for document reference and RAG semantic search testing.

Creates a workbook with:
    - config sheet
    - prompts sheet with references and semantic_query columns
    - documents sheet
    - data sheet (optional batch data)

Demonstrates:
    - Full document injection via references column
    - Semantic search via semantic_query column (RAG)

Uses FFLiteLLMClient with LiteLLM routing for Mistral Small.

Paired with: sample_workbook_documents_validate_v001.py

Usage:
    python scripts/sample_workbook_documents_create_v001.py [output_path]

Version: 001
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sample_workbooks import PromptSpec, WorkbookBuilder

from src.config import get_config


def get_documents() -> list[dict]:
    """Return document references for the documents sheet."""
    config = get_config()
    library = config.paths.library

    return [
        {
            "reference_name": "product_spec",
            "common_name": "Product Specification",
            "file_path": f"{library}/product_spec.md",
            "notes": "Main product documentation",
        },
        {
            "reference_name": "api_ref",
            "common_name": "API Reference",
            "file_path": f"{library}/api_reference.txt",
            "notes": "API documentation",
        },
        {
            "reference_name": "config",
            "common_name": "Configuration File",
            "file_path": f"{library}/config.json",
            "notes": "App configuration",
        },
        {
            "reference_name": "troubleshoot",
            "common_name": "Troubleshooting Guide",
            "file_path": f"{library}/troubleshooting.txt",
            "notes": "Common issues and solutions",
        },
        {
            "reference_name": "architecture",
            "common_name": "System Architecture",
            "file_path": f"{library}/ARCHITECTURE.md",
            "notes": "Overall system architecture documentation",
        },
        {
            "reference_name": "client_api_guide",
            "common_name": "Client API User Guide",
            "file_path": f"{library}/CLIENT API USER GUIDE.md",
            "notes": "User guide for client API usage",
        },
        {
            "reference_name": "clients_arch",
            "common_name": "Clients Architecture",
            "file_path": f"{library}/CLIENTS_ARCHITECTURE.md",
            "notes": "Architecture for AI client implementations",
        },
        {
            "reference_name": "conditional_guide",
            "common_name": "Conditional Expressions Guide",
            "file_path": f"{library}/CONDITIONAL EXPRESSIONS USER GUIDE.md",
            "notes": "Guide for conditional expressions in prompts",
        },
        {
            "reference_name": "configuration_doc",
            "common_name": "Configuration Documentation",
            "file_path": f"{library}/CONFIGURATION.md",
            "notes": "Configuration management documentation",
        },
        {
            "reference_name": "orchestrator_arch",
            "common_name": "Orchestrator Architecture",
            "file_path": f"{library}/ORCHESTRATOR_ARCHITECTURE.md",
            "notes": "Excel orchestrator architecture documentation",
        },
        {
            "reference_name": "orchestrator_readme",
            "common_name": "Orchestrator README",
            "file_path": f"{library}/ORCHESTRATOR README.md",
            "notes": "Orchestrator usage and examples",
        },
        {
            "reference_name": "rag_architecture",
            "common_name": "RAG Architecture",
            "file_path": f"{library}/RAG_ARCHITECTURE.md",
            "notes": "Retrieval-Augmented Generation architecture",
        },
        {
            "reference_name": "shared_history",
            "common_name": "Shared History Design",
            "file_path": f"{library}/SHARED_HISTORY_DESIGN.md",
            "notes": "Conversation history sharing design",
        },
    ]


def get_prompts() -> list[PromptSpec]:
    """Return all prompts for the documents workbook."""
    prompts = []

    # Full document references (1-6)
    prompts.append(
        PromptSpec(
            1,
            "spec_summary",
            "Summarize the key features of the product specification.",
            references='["product_spec"]',
        )
    )
    prompts.append(
        PromptSpec(
            2,
            "api_overview",
            "List the available client types and their purposes.",
            references='["api_ref"]',
        )
    )
    prompts.append(
        PromptSpec(
            3,
            "config_analysis",
            "What features are enabled in the configuration?",
            references='["config"]',
        )
    )
    prompts.append(
        PromptSpec(
            4,
            "combined_analysis",
            "Based on the product spec and API reference, describe the system architecture.",
            references='["product_spec", "api_ref"]',
        )
    )
    prompts.append(
        PromptSpec(
            5,
            "troubleshoot_summary",
            "Summarize the common issues and their solutions.",
            references='["troubleshoot"]',
        )
    )
    prompts.append(
        PromptSpec(
            6,
            "full_context",
            "Using all documents, provide a comprehensive overview of the FFClients system.",
            references='["product_spec", "api_ref", "config", "troubleshoot"]',
        )
    )

    # No reference control (7)
    prompts.append(PromptSpec(7, "no_ref_prompt", "What is 2 + 2? Just give the number."))

    # RAG semantic search (8-20)
    prompts.append(
        PromptSpec(
            8,
            "rag_authentication",
            "How do I authenticate with the API?",
            semantic_query="authentication API key token",
        )
    )
    prompts.append(
        PromptSpec(
            9,
            "rag_errors",
            "What are common errors and how do I fix them?",
            semantic_query="troubleshooting error import dependency",
        )
    )
    prompts.append(
        PromptSpec(
            10,
            "rag_performance",
            "What are the performance tips for this system?",
            semantic_query="performance batch concurrency tokens",
        )
    )
    prompts.append(
        PromptSpec(
            11,
            "rag_chunking",
            "What chunking strategies are available for document processing?",
            semantic_query="chunking strategy recursive markdown hierarchical",
        )
    )
    prompts.append(
        PromptSpec(
            12,
            "rag_hybrid_search",
            "How does hybrid search work in the RAG system?",
            semantic_query="hybrid search BM25 vector fusion",
        )
    )
    prompts.append(
        PromptSpec(
            13,
            "rag_indexing",
            "What indexing strategies does the RAG module support?",
            semantic_query="indexing BM25 hierarchical contextual embeddings",
        )
    )
    prompts.append(
        PromptSpec(
            14,
            "orchestrator_usage",
            "How do I use the Excel orchestrator to run prompts?",
            semantic_query="orchestrator workbook prompts sheet execution",
        )
    )
    prompts.append(
        PromptSpec(
            15,
            "conditional_prompts",
            "How can I use conditional expressions in prompts?",
            semantic_query="conditional expression if equals contains",
        )
    )
    prompts.append(
        PromptSpec(
            16,
            "client_types",
            "What AI client types are supported and how do they differ?",
            semantic_query="client mistral anthropic openai azure",
        )
    )
    prompts.append(
        PromptSpec(
            17,
            "configuration_yaml",
            "How is configuration managed in FFClients?",
            semantic_query="configuration yaml pydantic settings",
        )
    )
    prompts.append(
        PromptSpec(
            18,
            "shared_history",
            "How does conversation history sharing work between prompts?",
            semantic_query="history conversation shared previous response",
        )
    )
    prompts.append(
        PromptSpec(
            19,
            "document_references",
            "How do document references work in the orchestrator?",
            semantic_query="document reference injection full text",
        )
    )
    prompts.append(
        PromptSpec(
            20,
            "reranking_strategies",
            "What reranking strategies are available for search results?",
            semantic_query="rerank cross-encoder diversity re-ranking",
        )
    )

    # Filtered RAG search (21)
    prompts.append(
        PromptSpec(
            21,
            "rag_filtered_auth",
            "Find authentication information ONLY in the API reference document.",
            semantic_query="authentication API key",
            semantic_filter='{"reference_name": "api_ref"}',
        )
    )

    # Enhanced RAG search (22-23)
    prompts.append(
        PromptSpec(
            22,
            "rag_expanded_search",
            "Find comprehensive information about error handling and troubleshooting.",
            semantic_query="error handling exception troubleshooting",
            query_expansion="true",
        )
    )
    prompts.append(
        PromptSpec(
            23,
            "rag_reranked_search",
            "What are the best practices for document chunking strategies?",
            semantic_query="chunking strategy best practices",
            rerank="true",
        )
    )

    return prompts


def create_sample_workbook(output_path: str):
    """Create the documents sample workbook."""
    prompts = get_prompts()
    documents = get_documents()

    builder = WorkbookBuilder(output_path)
    builder.add_config_sheet(
        overrides={
            "max_tokens": "1000",
            "system_instructions": "You are a helpful assistant. Analyze documents and answer questions based on their content. Be concise and accurate.",
        }
    )
    builder.add_documents_sheet(documents)
    builder.add_prompts_sheet(prompts, include_extra_columns=True)
    builder.save()

    builder.print_summary(
        "document reference",
        {
            "Documents defined": len(documents),
            "Prompts defined": len(prompts),
            "Prompt types": [
                "6 prompts with document references (full injection)",
                "13 prompts with semantic_query (RAG search)",
                "2 prompts with semantic_filter (filtered RAG search)",
                "1 prompt with query_expansion enabled",
                "1 prompt with rerank enabled",
                "1 prompt without references or semantic search",
            ],
        },
    )


if __name__ == "__main__":
    config = get_config()
    output = sys.argv[1] if len(sys.argv) > 1 else config.sample.workbooks.documents
    create_sample_workbook(output)
