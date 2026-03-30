# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Excel-based AI prompt orchestration engine.

This module provides the ExcelOrchestrator class for executing AI prompt
workflows defined in Excel workbooks with support for:
- Sequential and parallel execution
- Batch execution with variable templating
- Multi-client support
- Document reference injection
- Semantic search via RAG (semantic_query)
- Conditional execution
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

from ..FFAIClientBase import FFAIClientBase
from .base import OrchestratorBase
from .scoring import ScoringCriteria, ScoringRubric
from .workbook_parser import WorkbookParser

logger = logging.getLogger(__name__)


class ExcelOrchestrator(OrchestratorBase):
    """Orchestrates AI prompt execution via Excel workbook.

    Usage:
        from src.Clients.FFMistralSmall import FFMistralSmall
        from src.orchestrator import ExcelOrchestrator

        client = FFMistralSmall(api_key="...")
        orchestrator = ExcelOrchestrator("prompts.xlsx", client=client)
        orchestrator.run()
    """

    def __init__(
        self,
        workbook_path: str,
        client: FFAIClientBase,
        config_overrides: dict[str, Any] | None = None,
        concurrency: int | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> None:
        """Initialize the ExcelOrchestrator.

        Args:
            workbook_path: Path to the Excel workbook.
            client: Default AI client for prompt execution.
            config_overrides: Optional config overrides from workbook.
            concurrency: Maximum concurrent API calls (1-max). Uses config default if None.
            progress_callback: Optional callback for progress updates.

        """
        super().__init__(
            client=client,
            config_overrides=config_overrides,
            concurrency=concurrency,
            progress_callback=progress_callback,
        )
        self._workbook_path = workbook_path
        self.builder = WorkbookParser(workbook_path)

    @property
    def source_path(self) -> str:
        """Return the workbook path."""
        return self._workbook_path

    @property
    def workbook_path(self) -> str:
        """Return the workbook path (backward compatibility)."""
        return self._workbook_path

    def _get_cache_dir(self) -> str:
        """Get directory for document caching."""
        return self.config.get(
            "document_cache_dir",
            os.path.join(os.path.dirname(self._workbook_path), "doc_cache"),
        )

    def _init_workbook(self) -> None:
        """Initialize workbook - create if not exists, validate if exists."""
        if not os.path.exists(self._workbook_path):
            logger.info(f"Workbook not found, creating template: {self._workbook_path}")
            self.builder.create_template_workbook()
        else:
            logger.info(f"Workbook found, validating: {self._workbook_path}")
            self.builder.validate_workbook()

    def _load_source(self) -> None:
        """Load prompts and config from Excel workbook."""
        self._init_workbook()
        self._load_config()

        clients_data = self.builder.load_clients()
        if clients_data:
            self._init_client_registry(clients_data)

        documents_data = self.builder.load_documents()
        if documents_data:
            self._init_documents(documents_data, os.path.dirname(self._workbook_path))

        tools_data = self.builder.load_tools()
        if tools_data:
            self._init_tools(tools_data)

        scoring_data = self.builder.load_scoring()
        if scoring_data:
            criteria = [
                ScoringCriteria(
                    criteria_name=c["criteria_name"],
                    description=c["description"],
                    scale_min=c["scale_min"],
                    scale_max=c["scale_max"],
                    weight=c["weight"],
                    source_prompt=c["source_prompt"],
                )
                for c in scoring_data
            ]
            self.scoring_rubric = ScoringRubric(criteria)
            self.has_scoring = True
            self.evaluation_strategy = self._resolve_evaluation_strategy()
            logger.info(
                f"Scoring enabled with {len(criteria)} criteria, "
                f"strategy='{self.evaluation_strategy}'"
            )

        self.batch_data = self.builder.load_data()
        self.is_batch_mode = len(self.batch_data) > 0

    def _load_config(self) -> None:
        """Load config from workbook builder (backward compatibility)."""
        self.config = self.builder.load_config()
        self.config.update(self.config_overrides)

        validation_errors = self.builder.validate_config(self.config)
        if validation_errors:
            error_msg = "; ".join(validation_errors)
            raise ValueError(f"Config validation failed: {error_msg}")

        logger.info(
            f"Configuration loaded: name={self.config.get('name', 'unnamed')}, "
            f"model={self.config.get('model')}, "
            f"max_retries={self.config.get('max_retries')}"
        )

        self.prompts = self.builder.load_prompts()

    def _init_client_registry(self, clients_data: list[dict[str, Any]] | None = None) -> None:
        """Initialize client registry from workbook (backward compatibility wrapper).

        Args:
            clients_data: Optional clients data (loaded from workbook if not provided).

        """
        if clients_data is None:
            clients_data = self.builder.load_clients()
        super()._init_client_registry(clients_data)

    def _init_documents(
        self,
        documents_data: list[dict[str, Any]] | None = None,
        workbook_dir: str | None = None,
    ) -> None:
        """Initialize documents from workbook (backward compatibility wrapper).

        Args:
            documents_data: Optional documents data (loaded from workbook if not provided).
            workbook_dir: Optional workbook directory (derived from workbook_path if not provided).

        """
        if documents_data is None:
            documents_data = self.builder.load_documents()
        if workbook_dir is None:
            workbook_dir = os.path.dirname(self._workbook_path)
        super()._init_documents(documents_data, workbook_dir)

    def _write_results(self, results: list[dict[str, Any]]) -> str:
        """Write results to Excel sheet.

        Args:
            results: List of result dictionaries.

        Returns:
            Name of the results sheet created.

        """
        batch_output = self.config.get("batch_output", "combined")

        if self.is_batch_mode and batch_output == "separate_sheets":
            return self._write_separate_batch_results()
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_sheet = f"results_{timestamp}"
            self.builder.write_results(results, results_sheet)
            logger.info(f"Orchestration complete. Results in sheet: {results_sheet}")
            return results_sheet

    def _write_separate_batch_results(self) -> str:
        """Write results to separate sheets per batch.

        Returns:
            Comma-separated list of sheet names.

        """
        batches: dict[int, list[dict[str, Any]]] = {}
        for result in self.results:
            batch_id = result.get("batch_id", 0)
            if batch_id not in batches:
                batches[batch_id] = []
            batches[batch_id].append(result)

        sheet_names: list[str] = []
        for batch_id in sorted(batches.keys()):
            batch_results = batches[batch_id]
            batch_name = batch_results[0].get("batch_name", f"batch_{batch_id}")
            sheet_name = self.builder.write_batch_results(batch_results, batch_name)
            sheet_names.append(sheet_name)

        logger.info(f"Wrote {len(sheet_names)} batch result sheets")
        return ", ".join(sheet_names)

    def run(self) -> str:
        """Initialize, validate, execute prompts, and write results.

        Returns:
            Name of the results sheet created.

        """
        return super().run()

    def get_summary(self) -> dict[str, Any]:
        """Get execution summary.

        Returns:
            Dictionary with execution statistics.

        """
        summary = super().get_summary()
        if summary.get("status") != "not_run":
            summary["workbook"] = self._workbook_path
        return summary
