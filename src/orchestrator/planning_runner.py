# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Planning phase runner for orchestrator planning prompts.

Handles detection, execution, and artifact injection for planning-phase
prompts that generate scoring criteria and execution prompts before the
main batch run. Extracted from OrchestratorBase to isolate planning
concerns.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..config import get_config
from .planning import PlanningArtifactParser
from .scoring import ScoringRubric
from .validation import OrchestratorValidator

logger = logging.getLogger(__name__)


class PlanningPhaseRunner:
    """Manages the planning phase lifecycle.

    Handles three stages:
    1. detect() -- splits planning prompts from execution prompts
    2. execute() -- runs planning prompts sequentially, collects artifacts
    3. parse_artifacts() -- merges, validates, injects generated prompts/criteria

    Usage:
        runner = PlanningPhaseRunner()
        runner.detect(orchestrator)
        runner.execute(orchestrator)
    """

    def detect(self, orchestrator: Any) -> None:
        """Detect and separate planning-phase prompts from execution prompts.

        Called during _load_source() in subclasses after prompts are loaded.
        Splits orchestrator.prompts into orchestrator.planning_prompts
        (phase=planning) and orchestrator.prompts (phase=execution only).

        Args:
            orchestrator: Orchestrator instance to split prompts on.

        """
        planning = [p for p in orchestrator.prompts if p.get("phase") == "planning"]
        if planning:
            orchestrator.has_planning = True
            orchestrator.planning_prompts = sorted(planning, key=lambda x: x.get("sequence", 0))
            orchestrator.prompts = [p for p in orchestrator.prompts if p.get("phase") != "planning"]
            logger.info(
                f"Planning phase enabled: {len(orchestrator.planning_prompts)} planning prompts, "
                f"{len(orchestrator.prompts)} execution prompts"
            )
            if not orchestrator.is_batch_mode:
                logger.warning(
                    "Planning prompts detected but no batch data sheet. "
                    "Scoring and synthesis will be skipped."
                )

    def execute(self, orchestrator: Any) -> None:
        """Execute planning-phase prompts sequentially before batch execution.

        For generator prompts, parses structured JSON artifacts and injects
        scoring criteria and/or execution prompts into the pipeline.

        Args:
            orchestrator: Orchestrator instance with planning_prompts to execute.

        """
        logger.info(f"Executing planning phase with {len(orchestrator.planning_prompts)} prompts")
        results_by_name: dict[str, dict[str, Any]] = {}
        planning_config = get_config().planning

        generator_artifacts: list = []
        parser = PlanningArtifactParser()

        for prompt in orchestrator.planning_prompts:
            prompt_name = prompt.get("prompt_name", "(unnamed)")

            if orchestrator.progress_callback:
                orchestrator.progress_callback(
                    completed=len(orchestrator.planning_results),
                    total=len(orchestrator.planning_prompts),
                    success=len(
                        [r for r in orchestrator.planning_results if r.get("status") == "success"]
                    ),
                    failed=len(
                        [r for r in orchestrator.planning_results if r.get("status") == "failed"]
                    ),
                    current_name=f"[planning] {prompt_name}",
                )

            result = orchestrator._execute_prompt(prompt, results_by_name=results_by_name)

            result["result_type"] = "planning"
            result["batch_id"] = None
            result["batch_name"] = None
            orchestrator.planning_results.append(result)

            if result.get("prompt_name"):
                results_by_name[result["prompt_name"]] = result

            if prompt.get("generator") and result.get("status") == "success":
                response = result.get("response", "")
                with orchestrator.history_lock:
                    orchestrator.shared_prompt_attr_history.append(
                        {
                            "prompt": prompt.get("prompt", ""),
                            "response": response,
                            "prompt_name": prompt.get("prompt_name"),
                            "timestamp": time.time(),
                            "model": orchestrator.config.get("model"),
                            "history": prompt.get("history"),
                        }
                    )

                try:
                    artifact = parser.parse(response, prompt_name)
                    generator_artifacts.append(artifact)
                except ValueError as e:
                    logger.error(f"Planning generator '{prompt_name}' artifact parse failed: {e}")
                    if not planning_config.continue_on_parse_error:
                        raise

            logger.info(f"Planning prompt '{prompt_name}' completed: {result.get('status')}")

        if generator_artifacts:
            self.parse_and_inject(orchestrator, generator_artifacts, parser, planning_config)

        logger.info(
            f"Planning phase complete: {len(orchestrator.planning_results)} prompts executed"
        )

    def parse_and_inject(
        self,
        orchestrator: Any,
        artifacts: list,
        parser: PlanningArtifactParser,
        planning_config: Any,
    ) -> None:
        """Parse, validate, and inject generated artifacts from planning phase.

        Handles:
        - Merging artifacts from multiple generators
        - Validating and injecting generated prompts into orchestrator.prompts
        - Auto-deriving scoring rubric if no manual scoring sheet exists

        Args:
            orchestrator: Orchestrator instance to inject artifacts into.
            artifacts: List of GeneratedArtifact instances.
            parser: PlanningArtifactParser instance.
            planning_config: PlanningConfig instance.

        """
        merged_criteria, merged_prompts = parser.merge_artifacts(artifacts)

        if merged_prompts:
            existing_names = {
                p["prompt_name"] for p in orchestrator.prompts if p.get("prompt_name")
            }
            doc_refs: set[str] = set()
            if orchestrator.document_registry:
                doc_refs = set(orchestrator.document_registry.get_reference_names())
            batch_keys: set[str] = set()
            if orchestrator.is_batch_mode and orchestrator.batch_data:
                batch_keys = set(OrchestratorValidator.extract_batch_keys(orchestrator.batch_data))

            prompt_errors = parser.validate_prompts(
                merged_prompts, existing_names, doc_refs, batch_keys
            )
            if prompt_errors:
                for err in prompt_errors:
                    logger.error(f"Generated prompt validation error: {err}")
                if not planning_config.continue_on_parse_error:
                    raise ValueError(
                        f"Generated prompt validation failed with {len(prompt_errors)} errors"
                    )
                merged_prompts = [
                    p for p in merged_prompts if p.get("prompt_name") and p.get("prompt")
                ]

            existing_seqs = {p["sequence"] for p in orchestrator.prompts if p.get("sequence")}
            parser.assign_sequences(
                merged_prompts,
                existing_seqs,
                base=planning_config.generated_sequence_base,
                step=planning_config.generated_sequence_step,
            )

            for p in merged_prompts:
                p["_generated"] = True
                p["_generated_by"] = next(
                    (
                        a.source
                        for a in reversed(artifacts)
                        if any(
                            gp.get("prompt_name") == p.get("prompt_name")
                            for gp in a.generated_prompts
                        )
                    ),
                    "",
                )
                p.setdefault("phase", "execution")
                p.setdefault("generator", False)
                p.setdefault("history", None)
                p.setdefault("notes", None)
                p.setdefault("client", None)
                p.setdefault("condition", None)
                p.setdefault("agent_mode", False)
                p.setdefault("tools", None)
                p.setdefault("max_tool_rounds", None)
                p.setdefault("validation_prompt", None)
                p.setdefault("max_validation_retries", None)
                p.setdefault("semantic_query", None)
                p.setdefault("semantic_filter", None)
                p.setdefault("query_expansion", None)
                p.setdefault("rerank", None)

            orchestrator.prompts.extend(merged_prompts)
            orchestrator.prompts.sort(key=lambda x: x.get("sequence", 0))
            logger.info(f"Injected {len(merged_prompts)} generated prompts into execution pipeline")

        if merged_criteria:
            if orchestrator.has_scoring:
                logger.warning(
                    "Both scoring sheet and generated criteria present. Using scoring sheet."
                )
            else:
                all_prompt_names = {
                    p["prompt_name"] for p in orchestrator.prompts if p.get("prompt_name")
                }
                criteria_errors = parser.validate_criteria(merged_criteria, all_prompt_names)
                if criteria_errors:
                    for err in criteria_errors:
                        logger.error(f"Generated criteria validation error: {err}")

                valid_criteria = [
                    c
                    for c in merged_criteria
                    if c.get("criteria_name")
                    and (not c.get("source_prompt") or c["source_prompt"] in all_prompt_names)
                ]

                if valid_criteria:
                    scoring_criteria_objs = parser.build_scoring_criteria(valid_criteria)
                    orchestrator.scoring_rubric = ScoringRubric(scoring_criteria_objs)
                    orchestrator.has_scoring = True
                    orchestrator.evaluation_strategy = orchestrator._resolve_evaluation_strategy()
                    logger.info(
                        f"Scoring rubric auto-derived from planning phase with "
                        f"{len(valid_criteria)} criteria, "
                        f"strategy='{orchestrator.evaluation_strategy}'"
                    )
                else:
                    logger.warning(
                        "All generated scoring criteria failed validation. "
                        "Proceeding without scoring."
                    )
