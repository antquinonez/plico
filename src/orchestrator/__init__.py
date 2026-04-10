# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Orchestrator package for Excel-based AI prompt execution."""

from .client_registry import ClientRegistry
from .condition_evaluator import ConditionEvaluator
from .discovery import (
    create_data_rows_from_documents,
    create_evaluation_workbook,
    discover_documents,
)
from .excel_orchestrator import ExcelOrchestrator
from .manifest import ManifestOrchestrator, WorkbookManifestExporter
from .validation import OrchestratorValidator, ValidationError, ValidationResult
from .workbook_parser import WorkbookParser

__all__ = [
    "ClientRegistry",
    "ConditionEvaluator",
    "ExcelOrchestrator",
    "ManifestOrchestrator",
    "OrchestratorValidator",
    "ValidationError",
    "ValidationResult",
    "WorkbookManifestExporter",
    "WorkbookParser",
    "create_data_rows_from_documents",
    "create_evaluation_workbook",
    "discover_documents",
]
