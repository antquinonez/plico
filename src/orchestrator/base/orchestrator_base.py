# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Abstract base class for prompt orchestrators.

This module provides OrchestratorBase, which contains all shared functionality
between ExcelOrchestrator and ManifestOrchestrator, including:
- Client and registry management
- Document processing and reference injection
- Prompt execution with retry logic
- Dependency resolution and graph building
- Batch execution with variable templating
- Condition evaluation
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...config import get_config
from ...FFAI import FFAI
from ...FFAIClientBase import FFAIClientBase
from ..client_registry import ClientRegistry
from ..condition_evaluator import ConditionEvaluator
from ..document_processor import DocumentProcessor
from ..document_registry import DocumentRegistry
from ..executor import Executor
from ..results import ResultBuilder
from ..state import ExecutionState, PromptNode
from ..validation import OrchestratorValidator

if TYPE_CHECKING:
    from ...RAG import FFRAGClient

logger = logging.getLogger(__name__)


class OrchestratorBase(ABC):
    """Abstract base class for prompt orchestrators.

    Provides shared functionality for:
    - Client and registry management
    - Document processing
    - Prompt execution with retries
    - Dependency resolution
    - Batch execution
    - Condition evaluation

    Subclasses must implement:
    - _load_source(): Load prompts and config from source
    - _get_cache_dir(): Return directory for document caching
    - _write_results(): Write results to output format
    - source_path property: Return the source path identifier
    """

    def __init__(
        self,
        client: FFAIClientBase,
        config_overrides: dict[str, Any] | None = None,
        concurrency: int | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> None:
        """Initialize the orchestrator base.

        Args:
            client: Default AI client for prompt execution.
            config_overrides: Optional config overrides.
            concurrency: Maximum concurrent API calls (1-max). Uses config default if None.
            progress_callback: Optional callback for progress updates.

        """
        self.client = client
        self.config_overrides = config_overrides or {}

        config = get_config()
        default_concurrency = config.orchestrator.default_concurrency
        max_concurrency = config.orchestrator.max_concurrency

        if concurrency is None:
            concurrency = default_concurrency
        self.concurrency = min(max(1, concurrency), max_concurrency)

        self.progress_callback = progress_callback

        self.config: dict[str, Any] = {}
        self.prompts: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []

        # FFAI wrapper around the default client. Created by _init_client() and
        # used as the template for cloning isolated instances. Individual prompt
        # execution always uses _get_isolated_ffai() so that each call gets its
        # own client state.
        self.ffai: FFAI | None = None

        self.shared_prompt_attr_history: list[dict[str, Any]] = []
        self.history_lock = threading.Lock()

        self.batch_data: list[dict[str, Any]] = []
        self.is_batch_mode: bool = False
        self.client_registry: ClientRegistry | None = None
        self.has_multi_client: bool = False
        self.document_processor: DocumentProcessor | None = None
        self.document_registry: DocumentRegistry | None = None
        self.has_documents: bool = False
        self._executor = Executor()

    @property
    @abstractmethod
    def source_path(self) -> str:
        """Return the source path (workbook or manifest dir)."""
        ...

    @abstractmethod
    def _load_source(self) -> None:
        """Load prompts and config from source (Excel or YAML)."""
        ...

    @abstractmethod
    def _get_cache_dir(self) -> str:
        """Get directory for document caching."""
        ...

    @abstractmethod
    def _write_results(self, results: list[dict[str, Any]]) -> str:
        """Write results to output format. Returns output identifier."""
        ...

    def _init_client(self) -> None:
        """Initialize FFAI wrapper with configured client."""
        self.ffai = FFAI(
            self.client,
            shared_prompt_attr_history=self.shared_prompt_attr_history,
            history_lock=self.history_lock,
        )
        logger.info("FFAI wrapper initialized")

    def _init_client_registry(self, clients_data: list[dict[str, Any]]) -> None:
        """Initialize client registry for multi-client support.

        Args:
            clients_data: List of client definitions with name, client_type, config.

        """
        if not clients_data:
            return

        self.client_registry = ClientRegistry(default_client=self.client)
        self.has_multi_client = True
        for client_def in clients_data:
            self.client_registry.register(
                name=client_def["name"],
                client_type=client_def.get("client_type", "mistral-small"),
                config=client_def,
            )
        logger.info(f"Client registry initialized with {len(clients_data)} clients")

    def _init_documents(
        self,
        documents_data: list[dict[str, Any]],
        workbook_dir: str,
    ) -> None:
        """Initialize document processor and registry for document references.

        Args:
            documents_data: List of document definitions.
            workbook_dir: Directory containing the source workbook/manifest.

        """
        if not documents_data:
            return

        cache_dir = self._get_cache_dir()

        config = get_config()
        rag_client: FFRAGClient | None = None
        if config.rag.enabled:
            try:
                from ...RAG import CHROMADB_AVAILABLE, FFRAGClient

                if CHROMADB_AVAILABLE:
                    rag_client = FFRAGClient()
                    if hasattr(self.client, "generate_response"):
                        rag_client.set_llm_generate_fn(self.client.generate_response)
                    logger.info("RAG client initialized for semantic search")
                else:
                    logger.info("RAG disabled: chromadb not available (requires Python 3.11-3.13)")
            except Exception as e:
                logger.warning(f"Failed to initialize RAG client: {e}")

        self.document_processor = DocumentProcessor(
            cache_dir=cache_dir,
            api_key=os.environ.get("LLAMACLOUD_TOKEN"),
            rag_client=rag_client,
        )

        self.document_registry = DocumentRegistry(
            documents=documents_data,
            processor=self.document_processor,
            workbook_dir=workbook_dir,
            rag_client=rag_client,
        )

        self.has_documents = True
        self.document_registry.validate_documents()
        logger.info(f"Document registry initialized with {len(documents_data)} documents")

        if rag_client:
            logger.info("Pre-indexing all documents for RAG search")
            indexing_results = self.document_registry.index_all_documents()
            indexed_count = sum(1 for v in indexing_results.values() if v > 0)
            logger.info(f"Indexed {indexed_count} documents for semantic search")

    def _get_isolated_ffai(self, client_name: str | None = None) -> FFAI:
        """Create an FFAI instance with isolated client but shared history.

        Args:
            client_name: Optional name of client from registry.

        Returns:
            FFAI instance with isolated client.

        """
        if client_name and self.client_registry:
            client = self.client_registry.clone(client_name)
        else:
            client = self.client.clone()
        return FFAI(
            client,
            shared_prompt_attr_history=self.shared_prompt_attr_history,
            history_lock=self.history_lock,
        )

    def _validate_dependencies(self) -> None:
        """Validate all history dependencies reference existing prompt_names."""
        prompt_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}
        name_to_sequence: dict[str, int] = {
            p["prompt_name"]: p["sequence"] for p in self.prompts if p.get("prompt_name")
        }

        errors: list[str] = []
        for prompt in self.prompts:
            seq = prompt["sequence"]
            history = prompt.get("history")

            if not history:
                continue

            for dep_name in history:
                if dep_name not in prompt_names:
                    errors.append(
                        f"Sequence {seq}: dependency '{dep_name}' not found in any prompt_name"
                    )
                else:
                    dep_sequence = name_to_sequence.get(dep_name)
                    if dep_sequence and dep_sequence >= seq:
                        errors.append(
                            f"Sequence {seq}: dependency '{dep_name}' (seq {dep_sequence}) "
                            f"must be defined before sequence {seq}"
                        )

        if errors:
            raise ValueError("Dependency validation failed:\n" + "\n".join(errors))

        logger.info("Dependency validation passed")

    def _validate(self) -> None:
        """Run comprehensive validation on prompts, config, and dependencies.

        Replaces the basic _validate_dependencies() check with a full
        validation suite. Raises ValueError if any errors are found.
        """
        client_names = self.client_registry.get_registered_names() if self.client_registry else []

        batch_keys: list[str] = []
        if self.is_batch_mode and self.batch_data:
            skip = {"id", "batch_name"}
            for row in self.batch_data:
                batch_keys.extend(k for k in row if k not in skip and k not in batch_keys)

        doc_refs: list[str] = []
        if self.document_registry:
            doc_refs = list(self.document_registry.get_reference_names())

        available_types: list[str] = []
        with contextlib.suppress(Exception):
            available_types = get_config().get_available_client_types()

        validator = OrchestratorValidator(
            prompts=self.prompts,
            config=self.config,
            manifest_meta=getattr(self, "_manifest_meta", None),
            client_names=client_names,
            batch_data_keys=batch_keys,
            doc_ref_names=doc_refs,
            available_client_types=available_types,
        )

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
            logger.info(f"Validation passed with {result.warning_count} warning(s)")
        else:
            logger.info("Validation passed")

    def _inject_references(self, prompt: dict[str, Any]) -> str:
        """Inject document references or semantic search results into a prompt.

        Args:
            prompt: Prompt dictionary with optional references or semantic_query.

        Returns:
            Prompt text with injected content.

        """
        prompt_text = prompt.get("prompt", "")
        semantic_query = prompt.get("semantic_query")

        if (
            semantic_query
            and self.has_documents
            and self.document_registry
            and self.document_registry.rag_client
        ):
            try:
                semantic_filter = None
                semantic_filter_str = prompt.get("semantic_filter")
                if semantic_filter_str:
                    semantic_filter = json.loads(semantic_filter_str)

                query_expansion = self._parse_bool_override(prompt.get("query_expansion"))
                rerank = self._parse_bool_override(prompt.get("rerank"))

                return self.document_registry.inject_semantic_query(
                    prompt_text,
                    semantic_query,
                    semantic_filter=semantic_filter,
                    query_expansion=query_expansion,
                    rerank=rerank,
                )
            except Exception as e:
                logger.warning(f"Semantic search failed: {e}, falling back to references")

        references = prompt.get("references")

        if not references or not self.has_documents:
            return prompt_text

        if not self.document_registry:
            raise ValueError("Document registry not initialized")

        ref_names = references if isinstance(references, list) else []

        if not ref_names:
            return prompt_text

        missing = [r for r in ref_names if r not in self.document_registry.get_reference_names()]
        if missing:
            raise ValueError(f"Referenced documents not found: {missing}")

        return self.document_registry.inject_references_into_prompt(prompt_text, ref_names)

    def _parse_bool_override(self, value: Any) -> bool | None:
        """Parse a boolean override value from string.

        Args:
            value: Value to parse (bool, str, or other).

        Returns:
            Parsed boolean or None if invalid.

        """
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "yes", "1"):
                return True
            if v in ("false", "no", "0"):
                return False
        return None

    def _build_execution_graph(self) -> dict[int, PromptNode]:
        """Build dependency graph for parallel execution.

        Returns:
            Dictionary mapping sequence numbers to PromptNodes.

        Raises:
            ValueError: If a dependency cycle is detected.

        """
        nodes: dict[int, PromptNode] = {}
        prompt_by_name: dict[str, int] = {}

        for prompt in self.prompts:
            seq = prompt["sequence"]
            nodes[seq] = PromptNode(sequence=seq, prompt=prompt)
            name = prompt.get("prompt_name")
            if name:
                prompt_by_name[name] = seq

        for prompt in self.prompts:
            seq = prompt["sequence"]
            history = prompt.get("history") or []
            for dep_name in history:
                if dep_name in prompt_by_name:
                    nodes[seq].dependencies.add(prompt_by_name[dep_name])

            condition = prompt.get("condition") or ""
            for dep_name, _ in ConditionEvaluator.extract_referenced_names(condition):
                if dep_name in prompt_by_name:
                    nodes[seq].dependencies.add(prompt_by_name[dep_name])

        # Memoization cache for computed levels
        level_cache: dict[int, int] = {}

        def assign_levels(seq: int, path: set[int]) -> int:
            if seq in level_cache:
                return level_cache[seq]
            if seq in path:
                cycle_seqs = sorted(path | {seq})
                raise ValueError(f"Dependency cycle detected involving sequences: {cycle_seqs}")
            path.add(seq)
            if not nodes[seq].dependencies:
                nodes[seq].level = 0
                level_cache[seq] = 0
                return 0
            max_dep_level = max(assign_levels(dep, path) for dep in nodes[seq].dependencies)
            nodes[seq].level = max_dep_level + 1
            level_cache[seq] = nodes[seq].level
            path.discard(seq)
            return nodes[seq].level

        for seq in nodes:
            assign_levels(seq, set())

        return nodes

    def _get_ready_prompts(
        self, state: ExecutionState, nodes: dict[int, PromptNode]
    ) -> list[PromptNode]:
        """Get prompts ready for execution (all dependencies completed).

        Args:
            state: Current execution state.
            nodes: Execution graph nodes.

        Returns:
            List of PromptNodes ready for execution, sorted by level and sequence.

        """
        ready: list[PromptNode] = []
        for seq, node in nodes.items():
            if seq in state.completed or seq in state.in_progress:
                continue
            if node.dependencies.issubset(state.completed):
                ready.append(node)
        ready.sort(key=lambda n: (n.level, n.sequence))
        return ready

    def _evaluate_condition(
        self, prompt: dict[str, Any], results_by_name: dict[str, dict[str, Any]]
    ) -> tuple[bool, str | None, str | None]:
        """Evaluate a prompt's condition.

        Args:
            prompt: Prompt dictionary with optional condition.
            results_by_name: Results indexed by prompt_name.

        Returns:
            Tuple of (should_execute, condition_result, condition_error).

        """
        condition = prompt.get("condition")

        if not condition or not str(condition).strip():
            return True, None, None

        evaluator = ConditionEvaluator(results_by_name)
        result, error = evaluator.evaluate(str(condition))

        return result, result, error

    def _execute_with_retry(
        self,
        prompt: dict[str, Any],
        results_by_name: dict[str, dict[str, Any]],
        results_lock: threading.Lock | None = None,
        batch_id: int | None = None,
        batch_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute a prompt with retry logic, supporting both regular and batch execution.

        Unified execution path for all modes (sequential, parallel, batch, batch_parallel).
        Uses ResultBuilder for consistent result construction.

        Args:
            prompt: Prompt dictionary.
            results_by_name: Results indexed by prompt_name for condition evaluation.
            results_lock: Optional lock for thread-safe condition evaluation (parallel mode).
            batch_id: Optional batch identifier.
            batch_name: Optional batch name.

        Returns:
            Result dictionary.

        """
        max_retries = self.config.get("max_retries", 3)
        retry_base_delay = self.config.get("retry_base_delay", 1.0)

        builder = ResultBuilder(prompt)
        if batch_id is not None and batch_name is not None:
            builder = builder.with_batch(batch_id, batch_name)

        seq_label = (
            f"Batch {batch_id}, sequence {prompt['sequence']}"
            if batch_id is not None
            else f"Sequence {prompt['sequence']}"
        )
        client_name = prompt.get("client")

        if results_lock:
            with results_lock:
                should_execute, cond_result, cond_error = self._evaluate_condition(
                    prompt, results_by_name
                )
        else:
            should_execute, cond_result, cond_error = self._evaluate_condition(
                prompt, results_by_name
            )

        builder.with_condition_result(cond_result, cond_error)

        if not should_execute:
            builder.as_skipped(cond_result, cond_error)
            logger.info(f"{seq_label} skipped: condition evaluated to False")
            return builder.build_dict()

        ffai = self._get_isolated_ffai(client_name)

        for attempt in range(1, max_retries + 1):
            builder.with_attempts(attempt)

            try:
                logger.info(
                    f"Executing {seq_label} (attempt {attempt})"
                    + (f" with client '{client_name}'" if client_name else "")
                )

                injected_prompt = self._inject_references(prompt)

                response = ffai.generate_response(
                    prompt=injected_prompt,
                    prompt_name=prompt.get("prompt_name"),
                    history=prompt.get("history"),
                    model=self.config.get("model"),
                    temperature=self.config.get("temperature"),
                    max_tokens=self.config.get("max_tokens"),
                )

                builder.with_resolved_prompt(ffai.last_resolved_prompt or injected_prompt)
                builder.with_response(response)
                logger.info(f"{seq_label} succeeded")
                break

            except Exception as e:
                builder.with_error(str(e), attempt)
                logger.warning(f"{seq_label} failed (attempt {attempt}): {e}")

                if attempt == max_retries:
                    logger.error(f"{seq_label} failed after {max_retries} attempts")
                else:
                    delay = retry_base_delay * (2 ** (attempt - 1))
                    logger.info(f"Retrying {seq_label} in {delay:.1f}s")
                    time.sleep(delay)

        return builder.build_dict()

    def _execute_prompt_core(
        self,
        prompt: dict[str, Any],
        results_by_name: dict[str, dict[str, Any]],
        results_lock: threading.Lock | None = None,
    ) -> dict[str, Any]:
        """Execute a single prompt with retry logic and optional thread-safe condition evaluation.

        This is the unified execution path for both sequential and parallel modes.

        Args:
            prompt: Prompt dictionary.
            results_by_name: Results indexed by prompt_name for condition evaluation.
            results_lock: Optional lock for thread-safe condition evaluation (parallel mode).

        Returns:
            Result dictionary.

        """
        return self._execute_with_retry(prompt, results_by_name, results_lock)

    def _execute_prompt_isolated(
        self, prompt: dict[str, Any], state: ExecutionState
    ) -> dict[str, Any]:
        """Execute a single prompt with completely isolated client clone.

        Used by the parallel executor. Delegates to _execute_prompt_core with
        a results lock for thread-safe condition evaluation.

        Args:
            prompt: Prompt dictionary.
            state: Execution state for tracking.

        Returns:
            Result dictionary.

        """
        return self._execute_prompt_core(
            prompt,
            results_by_name=state.results_by_name,
            results_lock=state.results_lock,
        )

    def _execute_prompt(
        self,
        prompt: dict[str, Any],
        results_by_name: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute a single prompt with retry logic.

        Used by the sequential executor.

        Args:
            prompt: Prompt dictionary.
            results_by_name: Optional results indexed by prompt_name.

        Returns:
            Result dictionary.

        """
        return self._execute_prompt_core(
            prompt,
            results_by_name=results_by_name or {},
        )

    def _resolve_variables(self, text: str, data_row: dict[str, Any]) -> str:
        """Replace {{variable}} placeholders with values from data row.

        Args:
            text: Text with {{variable}} placeholders.
            data_row: Dictionary of variable values.

        Returns:
            Text with placeholders replaced.

        """
        if not text:
            return text

        pattern = r"\{\{(\w+)\}\}"

        def replacer(match: re.Match[str]) -> str:
            var_name = match.group(1)
            if var_name in data_row and data_row[var_name] is not None:
                return str(data_row[var_name])
            logger.warning(f"Variable '{var_name}' not found in data row")
            return match.group(0)

        return re.sub(pattern, replacer, text)

    def _resolve_prompt_variables(
        self, prompt: dict[str, Any], data_row: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve all {{variable}} placeholders in a prompt.

        Args:
            prompt: Prompt dictionary.
            data_row: Dictionary of variable values.

        Returns:
            Prompt dictionary with resolved placeholders.

        """
        resolved = dict(prompt)
        resolved["prompt"] = self._resolve_variables(prompt.get("prompt", ""), data_row)
        if prompt.get("prompt_name"):
            resolved["prompt_name"] = self._resolve_variables(prompt["prompt_name"], data_row)
        return resolved

    def _resolve_batch_name(self, data_row: dict[str, Any], batch_id: int) -> str:
        """Generate batch name from data row or default.

        Args:
            data_row: Dictionary with optional batch_name field.
            batch_id: Default batch ID number.

        Returns:
            Batch name string.

        """
        if "batch_name" in data_row and data_row["batch_name"]:
            name = self._resolve_variables(str(data_row["batch_name"]), data_row)
            return re.sub(r"[^\w\-]", "_", name)[:50]
        return f"batch_{batch_id}"

    def _execute_single_batch(
        self, batch_id: int, data_row: dict[str, Any], batch_name: str
    ) -> list[dict[str, Any]]:
        """Execute all prompts for a single batch with resolved variables.

        Args:
            batch_id: Batch ID number.
            data_row: Variable values for this batch.
            batch_name: Name for this batch.

        Returns:
            List of result dictionaries.

        """
        results: list[dict[str, Any]] = []
        results_by_name: dict[str, dict[str, Any]] = {}

        for prompt in self.prompts:
            resolved_prompt = self._resolve_prompt_variables(prompt, data_row)

            result = self._execute_prompt_with_batch(
                resolved_prompt, batch_id, batch_name, results_by_name
            )
            results.append(result)

            if result.get("prompt_name"):
                results_by_name[result["prompt_name"]] = result

            if result["status"] == "failed":
                on_error = self.config.get("on_batch_error", "continue")
                if on_error == "stop":
                    logger.error(f"Stopping batch execution due to failure at batch {batch_id}")
                    break

        return results

    def _execute_prompt_with_batch(
        self,
        prompt: dict[str, Any],
        batch_id: int,
        batch_name: str,
        results_by_name: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute a single prompt and tag with batch info.

        Args:
            prompt: Prompt dictionary.
            batch_id: Batch ID number.
            batch_name: Batch name.
            results_by_name: Optional results indexed by prompt_name.

        Returns:
            Result dictionary with batch info.

        """
        return self._execute_with_retry(
            prompt, results_by_name or {}, batch_id=batch_id, batch_name=batch_name
        )

    def execute(self) -> list[dict[str, Any]]:
        """Execute all prompts in sequence with dependency-aware ordering.

        Returns:
            List of result dictionaries.

        """
        return self._executor.execute_sequential(self)

    def execute_parallel(self) -> list[dict[str, Any]]:
        """Execute prompts in parallel with dependency-aware scheduling.

        Returns:
            List of result dictionaries sorted by sequence.

        """
        return self._executor.execute_parallel(self)

    def execute_batch(self) -> list[dict[str, Any]]:
        """Execute all prompts for each batch row sequentially.

        Returns:
            List of result dictionaries for all batches.

        """
        return self._executor.execute_batch(self)

    def execute_batch_parallel(self) -> list[dict[str, Any]]:
        """Execute batches in parallel with dependency-aware prompt execution within each batch.

        Returns:
            List of result dictionaries sorted by (batch_id, sequence).

        """
        return self._executor.execute_batch_parallel(self)

    def run(self) -> str:
        """Initialize, validate, execute prompts, and write results.

        Returns:
            Output identifier (sheet name or parquet path).

        """
        self._load_source()
        self._validate()
        self._init_client()

        if self.is_batch_mode:
            logger.info(f"Running in batch mode with {len(self.batch_data)} batches")
            if self.concurrency > 1:
                logger.info("Using parallel batch execution")
                self.results = self.execute_batch_parallel()
            else:
                self.results = self.execute_batch()
        else:
            if self.concurrency > 1:
                logger.info("Using parallel execution")
                self.results = self.execute_parallel()
            else:
                self.results = self.execute()

        output = self._write_results(self.results)
        logger.info(f"Orchestration complete. Results in: {output}")
        return output

    def get_summary(self) -> dict[str, Any]:
        """Get execution summary.

        Returns:
            Dictionary with execution statistics.

        """
        if not self.results:
            return {"status": "not_run"}

        summary: dict[str, Any] = {
            "total_prompts": len(self.results),
            "successful": sum(1 for r in self.results if r["status"] == "success"),
            "failed": sum(1 for r in self.results if r["status"] == "failed"),
            "skipped": sum(1 for r in self.results if r["status"] == "skipped"),
            "total_attempts": sum(r["attempts"] for r in self.results),
        }

        condition_count = sum(1 for r in self.results if r.get("condition"))
        if condition_count > 0:
            summary["prompts_with_conditions"] = condition_count

        if self.is_batch_mode:
            batch_ids = {r.get("batch_id", 0) for r in self.results}
            summary["total_batches"] = len(batch_ids)
            summary["batch_mode"] = True

            batch_failures: dict[int, int] = {}
            for r in self.results:
                if r["status"] == "failed":
                    batch_id = r.get("batch_id", 0)
                    batch_failures[batch_id] = batch_failures.get(batch_id, 0) + 1
            if batch_failures:
                summary["batches_with_failures"] = batch_failures

        return summary
