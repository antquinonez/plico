# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Planning phase artifact parsing and validation.

Handles parsing of generator prompt JSON responses into scoring criteria
and execution prompts, merging artifacts from multiple generators, and
validating generated artifacts before injection into the orchestrator pipeline.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

from json_repair import loads as json_repair_loads

from .scoring import ScoringCriteria

logger = logging.getLogger(__name__)

# Matches {{word}} but NOT {{word.prop}}
_BATCH_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")

EXPECTED_ARTIFACT_KEYS = {"scoring_criteria", "prompts"}
REQUIRED_PROMPT_FIELDS = {"prompt_name", "prompt"}
REQUIRED_CRITERIA_FIELDS = {"criteria_name", "description"}


@dataclass
class GeneratedArtifact:
    """Parsed output from a single generator prompt."""

    scoring_criteria: list[dict[str, Any]] = field(default_factory=list)
    generated_prompts: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""


class PlanningArtifactParser:
    """Parses and validates generator prompt responses.

    Handles:
    - JSON parsing with fault-tolerance (json_repair)
    - Merging artifacts from multiple generators (refinement pattern)
    - Validation of scoring criteria and generated prompts
    - Sequence number assignment for generated prompts
    """

    def parse(self, response: str, source_name: str) -> GeneratedArtifact:
        """Parse a generator prompt's JSON response.

        Uses json_repair_loads for fault-tolerant parsing.
        Returns empty lists for missing arrays.
        Logs warnings for unexpected keys.

        Args:
            response: Raw LLM response string.
            source_name: prompt_name of the generator that produced this.

        Returns:
            Parsed GeneratedArtifact with criteria and prompts.

        Raises:
            ValueError: If the response cannot be parsed as JSON at all.

        """
        if not response or not response.strip():
            logger.warning(f"Generator '{source_name}' returned empty response")
            raise ValueError(f"Generator '{source_name}' returned empty response")

        try:
            data = json_repair_loads(response)
        except Exception as e:
            logger.error(f"Generator '{source_name}' response is not valid JSON: {e}")
            raise ValueError(f"Generator '{source_name}' response is not valid JSON: {e}") from e

        if not isinstance(data, dict):
            logger.error(
                f"Generator '{source_name}' response is not a JSON object "
                f"(got {type(data).__name__})"
            )
            raise ValueError(
                f"Generator '{source_name}' response is not a JSON object "
                f"(got {type(data).__name__})"
            )

        unexpected_keys = set(data.keys()) - EXPECTED_ARTIFACT_KEYS
        if unexpected_keys:
            logger.warning(
                f"Generator '{source_name}' response has unexpected keys: "
                f"{sorted(unexpected_keys)}. Expected: {sorted(EXPECTED_ARTIFACT_KEYS)}"
            )

        scoring_criteria = data.get("scoring_criteria", [])
        if not isinstance(scoring_criteria, list):
            logger.warning(f"Generator '{source_name}' scoring_criteria is not a list, ignoring")
            scoring_criteria = []
        else:
            before = len(scoring_criteria)
            scoring_criteria = [c for c in scoring_criteria if isinstance(c, dict)]
            if len(scoring_criteria) < before:
                logger.warning(
                    f"Generator '{source_name}' dropped {before - len(scoring_criteria)} "
                    f"non-dict scoring_criteria entries"
                )

        generated_prompts = data.get("prompts", [])
        if not isinstance(generated_prompts, list):
            logger.warning(f"Generator '{source_name}' prompts is not a list, ignoring")
            generated_prompts = []
        else:
            before = len(generated_prompts)
            generated_prompts = [p for p in generated_prompts if isinstance(p, dict)]
            if len(generated_prompts) < before:
                logger.warning(
                    f"Generator '{source_name}' dropped {before - len(generated_prompts)} "
                    f"non-dict prompts entries"
                )

        logger.info(
            f"Generator '{source_name}' produced "
            f"{len(scoring_criteria)} criteria, {len(generated_prompts)} prompts"
        )

        return GeneratedArtifact(
            scoring_criteria=scoring_criteria,
            generated_prompts=generated_prompts,
            source=source_name,
        )

    def merge_artifacts(
        self,
        artifacts: list[GeneratedArtifact],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Merge artifacts from multiple generators (refinement pattern).

        Later artifacts overwrite earlier ones on key collisions.
        Logs warnings for criteria_name and prompt_name collisions.

        Args:
            artifacts: List of GeneratedArtifacts in sequence order.

        Returns:
            Tuple of (merged_criteria, merged_prompts).

        """
        criteria_by_name: dict[str, dict[str, Any]] = {}
        prompts_by_name: dict[str, dict[str, Any]] = {}

        for artifact in artifacts:
            for criteria in artifact.scoring_criteria:
                if not isinstance(criteria, dict):
                    continue
                name = criteria.get("criteria_name", "")
                if name in criteria_by_name:
                    logger.warning(
                        f"Criteria '{name}' from generator '{artifact.source}' "
                        f"overwrites previous definition"
                    )
                criteria_by_name[name] = criteria

            for prompt in artifact.generated_prompts:
                if not isinstance(prompt, dict):
                    continue
                name = prompt.get("prompt_name", "")
                if name in prompts_by_name:
                    logger.warning(
                        f"Prompt '{name}' from generator '{artifact.source}' "
                        f"overwrites previous definition"
                    )
                prompts_by_name[name] = prompt

        return list(criteria_by_name.values()), list(prompts_by_name.values())

    def validate_criteria(
        self,
        criteria: list[dict[str, Any]],
        available_prompt_names: set[str],
    ) -> list[str]:
        """Validate scoring criteria. Return list of error messages.

        Checks: required fields, source_prompt exists in prompt_names,
        positive weights, consistent scale_min/scale_max.

        Args:
            criteria: List of criteria dicts from generator.
            available_prompt_names: Set of known execution prompt names.

        Returns:
            List of error message strings. Empty if all valid.

        """
        errors: list[str] = []

        if not criteria:
            return errors

        scale_min: int | None = None
        scale_max: int | None = None

        for idx, c in enumerate(criteria):
            name = c.get("criteria_name", "")
            label = f"criteria[{idx}] ('{name}')" if name else f"criteria[{idx}]"

            # Required fields
            for req_field in REQUIRED_CRITERIA_FIELDS:
                if not c.get(req_field):
                    errors.append(f"{label}: missing required field '{req_field}'")

            if not name:
                continue

            # source_prompt mapping
            source = c.get("source_prompt", "")
            if source and source not in available_prompt_names:
                errors.append(
                    f"{label}: source_prompt '{source}' does not match any known execution prompt"
                )

            # Weight validation
            weight = c.get("weight")
            if weight is not None:
                try:
                    w = float(weight)
                    if w <= 0:
                        errors.append(f"{label}: weight must be > 0, got {w}")
                except (TypeError, ValueError):
                    errors.append(f"{label}: weight is not a number: '{weight}'")

            # Scale consistency
            c_min = c.get("scale_min")
            c_max = c.get("scale_max")
            if c_min is not None and c_max is not None:
                try:
                    c_min_val = int(c_min)
                    c_max_val = int(c_max)
                    if scale_min is None:
                        scale_min = c_min_val
                        scale_max = c_max_val
                    elif scale_min != c_min_val or scale_max != c_max_val:
                        errors.append(
                            f"{label}: scale [{c_min_val}, {c_max_val}] inconsistent "
                            f"with [{scale_min}, {scale_max}] (uniform scale required)"
                        )
                except (TypeError, ValueError):
                    errors.append(f"{label}: scale_min/scale_max must be integers")

        return errors

    def validate_prompts(
        self,
        prompts: list[dict[str, Any]],
        existing_names: set[str],
        doc_refs: set[str],
        batch_keys: set[str],
    ) -> list[str]:
        """Validate generated prompts. Return list of error messages.

        Checks: required fields (prompt_name, prompt), no name collisions,
        valid document references, valid history dependencies,
        valid {{variable}} references against batch keys.

        Args:
            prompts: List of generated prompt dicts.
            existing_names: Set of existing (static) prompt names.
            doc_refs: Set of valid document reference names.
            batch_keys: Set of valid batch variable keys.

        Returns:
            List of error message strings. Empty if all valid.

        """
        errors: list[str] = []
        generated_names: set[str] = set()

        for idx, p in enumerate(prompts):
            name = p.get("prompt_name", "")
            label = f"prompt[{idx}] ('{name}')" if name else f"prompt[{idx}]"

            # Required fields
            for req_field in REQUIRED_PROMPT_FIELDS:
                if not p.get(req_field):
                    errors.append(f"{label}: missing required field '{req_field}'")

            if not name:
                continue

            # Name collision with existing prompts
            if name in existing_names:
                errors.append(f"{label}: name collides with existing prompt '{name}'")

            # Name collision within generated prompts
            if name in generated_names:
                errors.append(f"{label}: duplicate generated prompt name '{name}'")
            generated_names.add(name)

            # Document references validation
            refs = p.get("references") or []
            if isinstance(refs, str):
                refs = [refs]
            for ref in refs:
                if ref and doc_refs and ref not in doc_refs:
                    errors.append(f"{label}: references unknown document '{ref}'")

            # History dependencies — validate against all known names
            all_known = existing_names | generated_names
            history = p.get("history") or []
            if isinstance(history, str):
                history = [history]
            for dep in history:
                if dep and dep not in all_known:
                    errors.append(f"{label}: history references unknown prompt '{dep}'")

            # {{variable}} references
            prompt_text = p.get("prompt", "")
            if batch_keys and prompt_text:
                for match in _BATCH_VAR_PATTERN.finditer(prompt_text):
                    var_name = match.group(1)
                    # Skip prompt attribute references (handled by {{name.attr}} pattern)
                    if var_name not in batch_keys and var_name not in all_known:
                        errors.append(
                            f"{label}: template variable '{{{{{var_name}}}}}' "
                            f"not found in batch data keys"
                        )

        return errors

    def assign_sequences(
        self,
        prompts: list[dict[str, Any]],
        existing_sequences: set[int],
        base: str | int = "auto",
        step: int = 10,
    ) -> list[dict[str, Any]]:
        """Assign sequence numbers to generated prompts.

        When base="auto": uses max(existing_sequences) rounded up to
        nearest 100. When base is int: uses that directly.

        Args:
            prompts: List of generated prompt dicts (modified in place).
            existing_sequences: Set of existing sequence numbers.
            base: "auto" or explicit int for starting sequence.
            step: Increment between generated prompts.

        Returns:
            The prompts list with sequence numbers assigned.

        """
        if not prompts:
            return prompts

        if base == "auto":
            if existing_sequences:
                max_seq = max(existing_sequences)
                # Round up to nearest 100
                base_seq = int(math.ceil((max_seq + 1) / 100.0) * 100)
            else:
                base_seq = 1000
        else:
            base_seq = int(base)

        for idx, prompt in enumerate(prompts):
            seq = base_seq + (idx * step)
            # Avoid collisions
            while seq in existing_sequences:
                seq += 1
            prompt["sequence"] = seq
            existing_sequences.add(seq)

        return prompts

    def build_scoring_criteria(
        self,
        criteria_dicts: list[dict[str, Any]],
    ) -> list[ScoringCriteria]:
        """Convert validated criteria dicts to ScoringCriteria dataclass instances.

        Auto-derived criteria default to score_type="normalized_score" so they
        appear in the scores_pivot sheet (which filters on this value).

        Args:
            criteria_dicts: List of validated criteria dictionaries.

        Returns:
            List of ScoringCriteria instances.

        """
        result: list[ScoringCriteria] = []
        for c in criteria_dicts:
            raw_weight = c.get("weight", 1.0)
            raw_min = c.get("scale_min", 1)
            raw_max = c.get("scale_max", 10)
            try:
                weight = float(raw_weight) if raw_weight not in (None, "") else 1.0
            except (ValueError, TypeError):
                weight = 1.0
            try:
                scale_min = int(raw_min) if raw_min not in (None, "") else 1
            except (ValueError, TypeError):
                scale_min = 1
            try:
                scale_max = int(raw_max) if raw_max not in (None, "") else 10
            except (ValueError, TypeError):
                scale_max = 10
            result.append(
                ScoringCriteria(
                    criteria_name=c["criteria_name"],
                    description=c.get("description", ""),
                    scale_min=scale_min,
                    scale_max=scale_max,
                    weight=weight,
                    source_prompt=c.get("source_prompt", ""),
                    score_type=c.get("score_type", "normalized_score"),
                )
            )
        return result
