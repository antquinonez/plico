# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Validation manager for orchestrator validation lifecycle.

Handles building validator parameters from orchestrator state, running
OrchestratorValidator checks, and reporting results. Extracted from
OrchestratorBase to isolate validation orchestration concerns.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from ..config import get_config
from .validation import OrchestratorValidator
from .workbook_parser import parse_history_string

logger = logging.getLogger(__name__)


class ValidationManager:
    """Manages orchestrator validation lifecycle.

    Receives an orchestrator reference and builds validator parameters
    from its state, then runs checks via OrchestratorValidator.

    Usage:
        manager = ValidationManager()
        manager.validate(orchestrator)
        manager.validate_pre_planning(orchestrator)
        manager.validate_post_planning(orchestrator)
    """

    def _build_params(self, orchestrator: Any) -> dict[str, Any]:
        """Build parameters for OrchestratorValidator from orchestrator state.

        Args:
            orchestrator: Orchestrator instance to gather state from.

        Returns:
            Dict of keyword arguments for OrchestratorValidator.__init__().

        """
        client_names = (
            orchestrator.client_registry.get_registered_names()
            if orchestrator.client_registry
            else []
        )

        batch_keys: list[str] = []
        row_docs: dict[int, list[str]] = {}
        if orchestrator.is_batch_mode and orchestrator.batch_data:
            batch_keys = OrchestratorValidator.extract_batch_keys(orchestrator.batch_data)
            for idx, row in enumerate(orchestrator.batch_data):
                raw = row.get("_documents")
                if raw:
                    parsed = parse_history_string(raw)
                    if parsed:
                        row_docs[idx] = parsed

        doc_refs: list[str] = []
        if orchestrator.document_registry:
            doc_refs = list(orchestrator.document_registry.get_reference_names())

        tool_names: list[str] = []
        if orchestrator.tool_registry:
            tool_names = orchestrator.tool_registry.get_registered_names()

        available_types: list[str] = []
        try:
            available_types = get_config().get_available_client_types()
        except Exception:
            logger.debug("Could not load available client types for validation", exc_info=True)

        scoring_criteria: list[dict[str, Any]] = []
        available_strategies: list[str] = []
        if orchestrator.has_scoring and orchestrator.scoring_rubric:
            scoring_criteria = [asdict(c) for c in orchestrator.scoring_rubric.criteria]
        try:
            eval_config = get_config().evaluation
            available_strategies = list(eval_config.strategies.keys()) if eval_config else []
        except Exception:
            pass

        return {
            "prompts": orchestrator.prompts,
            "config": orchestrator.config,
            "manifest_meta": getattr(orchestrator, "_manifest_meta", None),
            "client_names": client_names,
            "batch_data_keys": batch_keys,
            "doc_ref_names": doc_refs,
            "available_client_types": available_types,
            "tool_names": tool_names,
            "row_doc_refs": row_docs,
            "scoring_criteria": scoring_criteria,
            "available_strategies": available_strategies,
            "synthesis_prompts": (
                orchestrator.synthesis_prompts if orchestrator.has_synthesis else None
            ),
        }

    def _run(
        self,
        orchestrator: Any,
        label: str,
        **overrides: Any,
    ) -> None:
        """Build validator, run checks, and handle results.

        Args:
            orchestrator: Orchestrator instance to validate.
            label: Human-readable label for log messages (e.g., "Validation").
            **overrides: Extra keyword arguments passed to OrchestratorValidator,
                         overriding values from _build_params().

        Raises:
            ValueError: If validation finds errors.

        """
        params = self._build_params(orchestrator)
        params.update(overrides)
        validator = OrchestratorValidator(**params)
        result = validator.validate()

        for warning in result.errors:
            if warning.severity == "warning":
                logger.warning(str(warning))

        if result.has_errors:
            for error in result.errors:
                if error.severity == "error":
                    logger.error(str(error))
            result.raise_on_error()
        elif result.warning_count > 0:
            logger.info(f"{label} passed with {result.warning_count} warning(s)")
        else:
            logger.info(f"{label} passed")

    def validate(self, orchestrator: Any) -> None:
        """Run comprehensive validation on prompts, config, and dependencies.

        Uses OrchestratorValidator to check prompt structure, dependency DAGs,
        template references, condition syntax, client assignments, config values,
        and more. Raises ValueError if any errors are found.

        Args:
            orchestrator: Orchestrator instance to validate.

        """
        self._run(orchestrator, "Validation")

    def validate_pre_planning(self, orchestrator: Any) -> None:
        """Run validation checks that can be performed before planning phase.

        Skips scoring source_prompt checks and synthesis source_prompts checks
        since generated prompts don't exist yet.

        Args:
            orchestrator: Orchestrator instance to validate.

        """
        self._run(
            orchestrator,
            "Pre-planning validation",
            skip_scoring_source_check=True,
            skip_synthesis_source_check=True,
            planning_prompts=orchestrator.planning_prompts,
        )

    def validate_post_planning(self, orchestrator: Any) -> None:
        """Run validation checks after planning phase, including generated artifacts.

        Validates scoring source_prompt mappings and synthesis source_prompts
        now that generated prompts are available.

        Args:
            orchestrator: Orchestrator instance to validate.

        """
        self._run(
            orchestrator,
            "Post-planning validation",
            skip_scoring_source_check=False,
            skip_synthesis_source_check=False,
        )
