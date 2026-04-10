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
- Auto-discovery of documents from a folder (resumes_path)
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from ..FFAIClientBase import FFAIClientBase
from .base import OrchestratorBase
from .discovery import create_data_rows_from_documents, discover_documents
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
        resumes_path: str | None = None,
        jd_path: str | None = None,
    ) -> None:
        """Initialize the ExcelOrchestrator.

        Args:
            workbook_path: Path to the Excel workbook.
            client: Default AI client for prompt execution.
            config_overrides: Optional config overrides from workbook.
            concurrency: Maximum concurrent API calls (1-max). Uses config default if None.
            progress_callback: Optional callback for progress updates.
            resumes_path: Optional folder path to auto-discover documents (e.g., resumes).
                Discovered documents populate the documents registry and batch data
                at runtime without modifying the workbook.
            jd_path: Optional path to a job description file. Added as a shared
                document with ``reference_name="job_description"`` available to all
                prompts via ``references: '["job_description"]'``.

        """
        super().__init__(
            client=client,
            config_overrides=config_overrides,
            concurrency=concurrency,
            progress_callback=progress_callback,
        )
        self._workbook_path = workbook_path
        self.builder = WorkbookParser(workbook_path)
        self._resumes_path = resumes_path
        self._jd_path = jd_path

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
                    score_type=c.get("score_type", ""),
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

        synthesis_data = self.builder.load_synthesis()
        if synthesis_data:
            self.synthesis_prompts = synthesis_data
            self.has_synthesis = True
            logger.info(f"Synthesis enabled with {len(synthesis_data)} prompts")

        self.batch_data = self.builder.load_data()
        self.is_batch_mode = len(self.batch_data) > 0

        self._inject_discovery_overrides()

        self._detect_planning_prompts()

    def _inject_discovery_overrides(self) -> None:
        """Inject documents and batch data from resumes_path and jd_path."""
        discovered_docs: list[dict[str, Any]] = []

        if self._jd_path:
            jd_doc = self._resolve_jd_document(self._jd_path)
            discovered_docs.append(jd_doc)
            logger.info(f"Injected JD as shared document: {jd_doc['file_path']}")

        if self._resumes_path:
            resume_docs = discover_documents(
                self._resumes_path,
                absolute_paths=True,
                tags=["resume"],
            )
            if not resume_docs:
                logger.warning(f"No documents discovered in resumes_path: {self._resumes_path}")
            else:
                discovered_docs.extend(resume_docs)
                logger.info(
                    f"Discovered {len(resume_docs)} documents from resumes_path: "
                    f"{self._resumes_path}"
                )

                resume_data = create_data_rows_from_documents(resume_docs)
                if self.batch_data:
                    self.batch_data.extend(resume_data)
                    logger.info(
                        f"Appended {len(resume_data)} batch rows to existing "
                        f"{len(self.batch_data) - len(resume_data)} workbook rows"
                    )
                else:
                    self.batch_data = resume_data
                    logger.info(f"Created {len(resume_data)} batch rows from discovered documents")

                self.is_batch_mode = len(self.batch_data) > 0

        if discovered_docs:
            all_docs = discovered_docs
            if self.has_documents and self.document_registry:
                existing = list(self.document_registry.documents.values())
                all_docs = existing + discovered_docs
                logger.info(
                    f"Merged {len(discovered_docs)} discovered docs with "
                    f"{len(existing)} workbook docs"
                )

            workbook_dir = os.path.dirname(self._workbook_path)
            self._init_documents(all_docs, workbook_dir)

    @staticmethod
    def _resolve_jd_document(jd_path: str) -> dict[str, Any]:
        """Create a document definition for a job description file.

        Args:
            jd_path: Path to the job description file.

        Returns:
            Document definition dict with reference_name="job_description".

        """
        path = Path(jd_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Job description file not found: {jd_path}")

        return {
            "reference_name": "job_description",
            "common_name": "Job Description",
            "file_path": str(path),
            "tags": "jd",
            "chunking_strategy": "",
            "notes": f"Shared job description: {path.name}",
        }

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

        # Include planning results in the combined results list
        all_results = list(self.planning_results) + list(results)

        if self.is_batch_mode and batch_output == "separate_sheets":
            main_sheet = self._write_separate_batch_results()
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_sheet = f"results_{timestamp}"
            self.builder.write_results(all_results, results_sheet)
            main_sheet = results_sheet
            logger.info(f"Orchestration complete. Results in sheet: {results_sheet}")

        if self.has_scoring and self.scoring_rubric:
            scoring_criteria = [
                {
                    "criteria_name": c.criteria_name,
                    "description": c.description,
                    "scale_min": c.scale_min,
                    "scale_max": c.scale_max,
                    "weight": c.weight,
                    "source_prompt": c.source_prompt,
                    "score_type": c.score_type,
                }
                for c in self.scoring_rubric.criteria
            ]
            pivot_sheet = self.builder.write_scores_pivot(results, scoring_criteria)
            if pivot_sheet:
                logger.info(f"Scores pivot sheet created: {pivot_sheet}")

        return main_sheet

    def _write_separate_batch_results(self) -> str:
        """Write results to separate sheets per batch.

        Planning results (batch_id=None) are written to a dedicated sheet
        to avoid creating a spurious None-keyed batch group.

        Returns:
            Comma-separated list of sheet names.

        """
        sheet_names: list[str] = []

        # Write planning results to a separate sheet if present
        if self.planning_results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            planning_sheet = f"planning_{timestamp}"
            self.builder.write_results(self.planning_results, planning_sheet)
            sheet_names.append(planning_sheet)

        # Filter out planning results from batch grouping
        batches: dict[int, list[dict[str, Any]]] = {}
        for result in self.results:
            if result.get("result_type") == "planning":
                continue
            batch_id = result.get("batch_id", 0)
            if batch_id is None:
                continue
            if batch_id not in batches:
                batches[batch_id] = []
            batches[batch_id].append(result)

        for batch_id in sorted(batches.keys()):
            batch_results = batches[batch_id]
            batch_name = batch_results[0].get("batch_name", f"batch_{batch_id}")
            sheet_name = self.builder.write_batch_results(batch_results, batch_name)
            sheet_names.append(sheet_name)

        logger.info(f"Wrote {len(sheet_names)} result sheets")
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
