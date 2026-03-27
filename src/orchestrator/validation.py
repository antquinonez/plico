# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Validation for orchestrator prompts, config, and dependencies.

Provides a standalone OrchestratorValidator that works for both Excel and
Manifest orchestrators. Validates prompt structure, dependency DAGs, template
references, condition syntax, client assignments, config values, batch
variables, and document references.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from .condition_evaluator import ConditionEvaluator

logger = logging.getLogger(__name__)

PROMPT_REF_PATTERN = re.compile(r"\{\{(\w+)\.(\w+(?:\.\w+)*)\}\}")
BATCH_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")

REQUIRED_PROMPT_FIELDS = {"sequence", "prompt_name", "prompt"}


@dataclass
class ValidationError:
    """A single validation finding."""

    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    prompt_name: str | None = None
    prompt_sequence: int | None = None

    def __str__(self) -> str:
        loc = ""
        if self.prompt_name:
            seq_info = f" [seq {self.prompt_sequence}]" if self.prompt_sequence is not None else ""
            loc = f" [{self.prompt_name}{seq_info}]"
        return f"[{self.severity.upper()}] {self.code}{loc}: {self.message}"


@dataclass
class ValidationResult:
    """Collection of validation findings."""

    errors: list[ValidationError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(e.severity == "error" for e in self.errors)

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == "warning")

    def add_error(self, code: str, message: str, **kwargs: Any) -> None:
        self.errors.append(ValidationError(code=code, message=message, severity="error", **kwargs))

    def add_warning(self, code: str, message: str, **kwargs: Any) -> None:
        self.errors.append(
            ValidationError(code=code, message=message, severity="warning", **kwargs)
        )

    def raise_on_error(self) -> None:
        if self.has_errors:
            messages = [str(e) for e in self.errors if e.severity == "error"]
            raise ValueError("Validation failed:\n" + "\n".join(messages))

    def format_report(self) -> str:
        lines: list[str] = []
        if not self.errors:
            lines.append("All checks passed.")
            return "\n".join(lines)

        for severity in ("error", "warning"):
            filtered = [e for e in self.errors if e.severity == severity]
            if not filtered:
                continue
            label = f"{severity}s" if len(filtered) > 1 else severity
            lines.append(f"{len(filtered)} {label}:")
            for err in filtered:
                lines.append(f"  {err}")

        return "\n".join(lines)


class OrchestratorValidator:
    """Validates orchestrator prompts, config, and dependencies.

    Works for both Excel and Manifest orchestrators. Manifest-specific
    checks (has_* flags, prompt_count, output_prompts) are only performed
    when ``manifest_meta`` is provided.

    Usage::

        validator = OrchestratorValidator(prompts, config, manifest_meta=meta)
        result = validator.validate()
        if result.has_errors:
            result.raise_on_error()
    """

    def __init__(
        self,
        prompts: list[dict[str, Any]],
        config: dict[str, Any],
        *,
        manifest_meta: dict[str, Any] | None = None,
        client_names: list[str] | None = None,
        batch_data_keys: list[str] | None = None,
        doc_ref_names: list[str] | None = None,
        available_client_types: list[str] | None = None,
    ) -> None:
        self.prompts = prompts
        self.config = config
        self.manifest_meta = manifest_meta
        self.client_names = client_names or []
        self.batch_data_keys = batch_data_keys or []
        self.doc_ref_names = doc_ref_names or []
        self.available_client_types = available_client_types or []

    def validate(self) -> ValidationResult:
        """Run all validation checks and return results."""
        result = ValidationResult()
        self._validate_prompt_fields(result)
        self._validate_unique_prompt_names(result)
        self._validate_sequences(result)
        self._validate_history_dependencies(result)
        self._validate_template_references(result)
        self._validate_condition_syntax(result)
        self._validate_client_assignments(result)
        self._validate_config_values(result)
        self._validate_document_references(result)
        self._validate_batch_variables(result)
        if self.manifest_meta is not None:
            self._validate_manifest_metadata(result)
        return result

    def _validate_prompt_fields(self, result: ValidationResult) -> None:
        for prompt in self.prompts:
            name = prompt.get("prompt_name", "(unnamed)")
            seq = prompt.get("sequence")
            for field_name in REQUIRED_PROMPT_FIELDS:
                if prompt.get(field_name) is None:
                    result.add_error(
                        "MISSING_FIELD",
                        f"Required field '{field_name}' is missing or null",
                        prompt_name=name,
                        prompt_sequence=seq,
                    )

    def _validate_unique_prompt_names(self, result: ValidationResult) -> None:
        seen: dict[str, int] = {}
        for prompt in self.prompts:
            name = prompt.get("prompt_name")
            if not name:
                continue
            if name in seen:
                result.add_error(
                    "DUPLICATE_PROMPT_NAME",
                    f"Prompt name '{name}' used at sequence {seen[name]} and {prompt.get('sequence')}",
                    prompt_name=name,
                    prompt_sequence=prompt.get("sequence"),
                )
            else:
                seen[name] = prompt.get("sequence")

    def _validate_sequences(self, result: ValidationResult) -> None:
        for prompt in self.prompts:
            seq = prompt.get("sequence")
            if seq is None:
                continue
            if not isinstance(seq, int) or seq < 1:
                result.add_error(
                    "INVALID_SEQUENCE",
                    f"Sequence must be a positive integer, got '{seq}'",
                    prompt_name=prompt.get("prompt_name"),
                    prompt_sequence=seq,
                )

    def _validate_history_dependencies(self, result: ValidationResult) -> None:
        prompt_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}
        name_to_seq = {
            p["prompt_name"]: p["sequence"]
            for p in self.prompts
            if p.get("prompt_name") and p.get("sequence")
        }

        for prompt in self.prompts:
            seq = prompt.get("sequence")
            name = prompt.get("prompt_name")
            history = prompt.get("history") or []

            for dep_name in history:
                if dep_name not in prompt_names:
                    result.add_error(
                        "UNKNOWN_DEPENDENCY",
                        f"History dependency '{dep_name}' not found in any prompt_name",
                        prompt_name=name,
                        prompt_sequence=seq,
                    )
                else:
                    dep_seq = name_to_seq.get(dep_name)
                    if dep_seq is not None and dep_seq >= seq:
                        result.add_error(
                            "FORWARD_DEPENDENCY",
                            f"Dependency '{dep_name}' (seq {dep_seq}) must come before sequence {seq}",
                            prompt_name=name,
                            prompt_sequence=seq,
                        )

    def _validate_template_references(self, result: ValidationResult) -> None:
        prompt_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}
        history_sets: dict[str, set[str]] = {}
        for prompt in self.prompts:
            name = prompt.get("prompt_name")
            if name:
                history_sets[name] = set(prompt.get("history") or [])

        for prompt in self.prompts:
            name = prompt.get("prompt_name")
            seq = prompt.get("sequence")
            prompt_text = prompt.get("prompt", "")
            condition = prompt.get("condition") or ""

            for text, text_label in [(prompt_text, "prompt"), (condition, "condition")]:
                if not text or not isinstance(text, str):
                    continue
                for ref_name, _prop in PROMPT_REF_PATTERN.findall(text):
                    if ref_name not in prompt_names:
                        result.add_error(
                            "UNKNOWN_TEMPLATE_REF",
                            f"Template reference '{{{{{ref_name}.property}}}}' in {text_label} references unknown prompt",
                            prompt_name=name,
                            prompt_sequence=seq,
                        )
                    elif ref_name != name and ref_name not in history_sets.get(name, set()):
                        result.add_warning(
                            "UNDECLARED_HISTORY_REF",
                            f"'{ref_name}' referenced in {text_label} via {{{{{ref_name}.property}}}} "
                            f"but not listed in history -- dependency not tracked by DAG",
                            prompt_name=name,
                            prompt_sequence=seq,
                        )

    def _validate_condition_syntax(self, result: ValidationResult) -> None:
        for prompt in self.prompts:
            condition = prompt.get("condition")
            if not condition or not condition.strip():
                continue
            is_valid, error_msg = ConditionEvaluator.validate_syntax(condition)
            if not is_valid:
                result.add_error(
                    "INVALID_CONDITION",
                    f"Condition syntax error: {error_msg}",
                    prompt_name=prompt.get("prompt_name"),
                    prompt_sequence=prompt.get("sequence"),
                )

    def _validate_client_assignments(self, result: ValidationResult) -> None:
        for prompt in self.prompts:
            client = prompt.get("client")
            if not client:
                continue
            if self.client_names and client not in self.client_names:
                result.add_error(
                    "UNKNOWN_CLIENT",
                    f"Client '{client}' not found in clients registry. "
                    f"Available: {self.client_names}",
                    prompt_name=prompt.get("prompt_name"),
                    prompt_sequence=prompt.get("sequence"),
                )

    def _validate_config_values(self, result: ValidationResult) -> None:
        temperature = self.config.get("temperature")
        if temperature is not None:
            try:
                t = float(temperature)
                if not (0.0 <= t <= 2.0):
                    result.add_error(
                        "INVALID_CONFIG", f"temperature {temperature} out of range [0.0, 2.0]"
                    )
            except (TypeError, ValueError):
                result.add_error(
                    "INVALID_CONFIG", f"temperature '{temperature}' is not a valid number"
                )

        max_retries = self.config.get("max_retries")
        if max_retries is not None:
            try:
                r = int(max_retries)
                if not (1 <= r <= 10):
                    result.add_error(
                        "INVALID_CONFIG", f"max_retries {max_retries} out of range [1, 10]"
                    )
            except (TypeError, ValueError):
                result.add_error(
                    "INVALID_CONFIG", f"max_retries '{max_retries}' is not a valid integer"
                )

        client_type = self.config.get("client_type")
        if (
            client_type
            and self.available_client_types
            and client_type not in self.available_client_types
        ):
            result.add_error(
                "UNKNOWN_CLIENT_TYPE",
                f"client_type '{client_type}' not recognized. "
                f"Available: {', '.join(sorted(self.available_client_types))}",
            )

    def _validate_document_references(self, result: ValidationResult) -> None:
        if not self.doc_ref_names:
            return
        doc_set = set(self.doc_ref_names)
        for prompt in self.prompts:
            references = prompt.get("references") or []
            for ref_name in references:
                if ref_name not in doc_set:
                    result.add_error(
                        "UNKNOWN_DOCUMENT_REF",
                        f"Document reference '{ref_name}' not found in documents",
                        prompt_name=prompt.get("prompt_name"),
                        prompt_sequence=prompt.get("sequence"),
                    )

    def _validate_batch_variables(self, result: ValidationResult) -> None:
        if not self.batch_data_keys:
            return
        prompt_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}
        batch_set = set(self.batch_data_keys)

        for prompt in self.prompts:
            prompt_text = prompt.get("prompt", "")
            if not prompt_text or not isinstance(prompt_text, str):
                continue
            for var_name in BATCH_VAR_PATTERN.findall(prompt_text):
                if var_name in prompt_names:
                    continue
                if var_name not in batch_set:
                    result.add_warning(
                        "UNKNOWN_BATCH_VARIABLE",
                        f"Template variable '{{{{{var_name}}}}}' not found in batch data keys",
                        prompt_name=prompt.get("prompt_name"),
                        prompt_sequence=prompt.get("sequence"),
                    )

    def _validate_manifest_metadata(self, result: ValidationResult) -> None:
        if not self.manifest_meta:
            return

        prompt_count = self.manifest_meta.get("prompt_count")
        if prompt_count is not None:
            actual = len(self.prompts)
            try:
                declared = int(prompt_count)
                if declared != actual:
                    result.add_warning(
                        "PROMPT_COUNT_MISMATCH",
                        f"manifest.yaml declares {declared} prompts, found {actual}",
                    )
            except (TypeError, ValueError):
                result.add_warning(
                    "PROMPT_COUNT_MISMATCH",
                    f"manifest.yaml prompt_count '{prompt_count}' is not a valid integer",
                )

        output_prompts = self.manifest_meta.get("output_prompts") or []
        if output_prompts:
            prompt_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}
            missing = set(output_prompts) - prompt_names
            if missing:
                result.add_error(
                    "UNKNOWN_OUTPUT_PROMPT",
                    f"output_prompts references non-existent prompts: {missing}",
                )

        has_data = self.manifest_meta.get("has_data", False)
        if has_data and not self.batch_data_keys:
            result.add_warning(
                "HAS_DATA_NO_BATCH",
                "manifest.yaml has has_data=true but no batch data keys provided for validation",
            )

        has_clients = self.manifest_meta.get("has_clients", False)
        if has_clients and not self.client_names:
            result.add_warning(
                "HAS_CLIENTS_NO_REGISTRY",
                "manifest.yaml has has_clients=true but no client names provided for validation",
            )

        has_documents = self.manifest_meta.get("has_documents", False)
        if has_documents and not self.doc_ref_names:
            result.add_warning(
                "HAS_DOCS_NO_REGISTRY",
                "manifest.yaml has has_documents=true but no document references provided for validation",
            )
