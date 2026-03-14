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
import re
import threading
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..config import get_config
from ..FFAI import FFAI
from ..FFAIClientBase import FFAIClientBase
from .client_registry import ClientRegistry
from .condition_evaluator import ConditionEvaluator
from .document_processor import DocumentProcessor
from .document_registry import DocumentRegistry
from .execution import (
    BatchParallelStrategy,
    BatchSequentialStrategy,
    ParallelStrategy,
    SequentialStrategy,
    get_execution_strategy,
)
from .results import ResultBuilder
from .state import ExecutionState, PromptNode
from .workbook_parser import WorkbookParser

if TYPE_CHECKING:
    from ..RAG import FFRAGClient

logger = logging.getLogger(__name__)


class ExcelOrchestrator:
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
        self.workbook_path = workbook_path
        self.client = client
        self.config_overrides = config_overrides or {}

        config = get_config()
        default_concurrency = config.orchestrator.default_concurrency
        max_concurrency = config.orchestrator.max_concurrency

        if concurrency is None:
            concurrency = default_concurrency
        self.concurrency = min(max(1, concurrency), max_concurrency)

        self.progress_callback = progress_callback
        self.builder = WorkbookParser(workbook_path)

        self.config: dict[str, Any] = {}
        self.prompts: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []
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

    def _get_isolated_ffai(self, client_name: str | None = None) -> FFAI:
        """Create an FFAI instance with isolated client but shared history."""
        if client_name and self.client_registry:
            client = self.client_registry.clone(client_name)
        else:
            client = self.client.clone()
        return FFAI(
            client,
            shared_prompt_attr_history=self.shared_prompt_attr_history,
            history_lock=self.history_lock,
        )

    def _get_isolated_client(self, client_name: str | None = None) -> FFAIClientBase:
        """Get an isolated client (fresh clone) for execution."""
        if client_name and self.client_registry:
            return self.client_registry.clone(client_name)
        return self.client.clone()

    def _init_workbook(self) -> None:
        """Initialize workbook - create if not exists, validate if exists."""
        if not os.path.exists(self.workbook_path):
            logger.info(f"Workbook not found, creating template: {self.workbook_path}")
            self.builder.create_template_workbook()
        else:
            logger.info(f"Workbook found, validating: {self.workbook_path}")
            self.builder.validate_workbook()

    def _load_config(self) -> None:
        """Load configuration, apply overrides."""
        self.config = self.builder.load_config()
        self.config.update(self.config_overrides)
        logger.info(
            f"Configuration loaded: model={self.config.get('model')}, "
            f"max_retries={self.config.get('max_retries')}"
        )

    def _init_client(self) -> None:
        """Initialize FFAI wrapper with configured client."""
        self.ffai = FFAI(
            self.client,
            shared_prompt_attr_history=self.shared_prompt_attr_history,
            history_lock=self.history_lock,
        )
        logger.info("FFAI wrapper initialized")

    def _init_client_registry(self) -> None:
        """Initialize client registry for multi-client support."""
        clients_data = self.builder.load_clients()
        if clients_data:
            self.client_registry = ClientRegistry(default_client=self.client)
            self.has_multi_client = True
            for client_def in clients_data:
                self.client_registry.register(
                    name=client_def["name"],
                    client_type=client_def.get("client_type", "mistral-small"),
                    config=client_def,
                )
            logger.info(f"Client registry initialized with {len(clients_data)} clients")

    def _init_documents(self) -> None:
        """Initialize document processor and registry for document references."""
        documents_data = self.builder.load_documents()
        if documents_data:
            cache_dir = self.config.get(
                "document_cache_dir",
                os.path.join(os.path.dirname(self.workbook_path), "doc_cache"),
            )

            config = get_config()
            rag_client: FFRAGClient | None = None
            if config.rag.enabled:
                try:
                    from ..RAG import CHROMADB_AVAILABLE, FFRAGClient

                    if CHROMADB_AVAILABLE:
                        rag_client = FFRAGClient()
                        if hasattr(self.client, "generate_response"):
                            rag_client.set_llm_generate_fn(self.client.generate_response)
                        logger.info("RAG client initialized for semantic search")
                    else:
                        logger.info(
                            "RAG disabled: chromadb not available (requires Python 3.11-3.13)"
                        )
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
                workbook_dir=os.path.dirname(self.workbook_path),
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

    def _inject_references(self, prompt: dict[str, Any]) -> str:
        """Inject document references or semantic search results into a prompt.

        Args:
            prompt: Prompt dictionary with optional 'references', 'semantic_query',
                    'semantic_filter', 'query_expansion', and/or 'rerank' fields

        Returns:
            Prompt text with references injected, or original prompt if no references

        Raises:
            ValueError: If referenced document is not found

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
                    import json

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
            value: Value from prompt (string, bool, or None).

        Returns:
            True, False, or None if not specified.

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

    def _create_result_dict(self, prompt: dict[str, Any]) -> dict[str, Any]:
        """Create a result dictionary for a prompt."""
        return ResultBuilder(prompt).build_dict()

    def _validate_dependencies(self) -> None:
        """Validate all history dependencies reference existing prompt_names."""
        prompt_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}
        prompt_names_by_sequence = {}

        for p in self.prompts:
            seq = p["sequence"]
            name = p.get("prompt_name")
            if name:
                prompt_names_by_sequence[seq] = name

        errors = []
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
                    dep_sequence = next(
                        (p["sequence"] for p in self.prompts if p.get("prompt_name") == dep_name),
                        None,
                    )
                    if dep_sequence and dep_sequence >= seq:
                        errors.append(
                            f"Sequence {seq}: dependency '{dep_name}' (seq {dep_sequence}) "
                            f"must be defined before sequence {seq}"
                        )

        if errors:
            raise ValueError("Dependency validation failed:\n" + "\n".join(errors))

        logger.info("Dependency validation passed")

    def _build_execution_graph(self) -> dict[int, PromptNode]:
        """Build dependency graph for parallel execution."""
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

        def assign_levels(seq: int, visited: set[int]) -> int:
            if seq in visited:
                return 0
            visited.add(seq)
            if not nodes[seq].dependencies:
                nodes[seq].level = 0
                return 0
            max_dep_level = max(assign_levels(dep, visited) for dep in nodes[seq].dependencies)
            nodes[seq].level = max_dep_level + 1
            return nodes[seq].level

        for seq in nodes:
            assign_levels(seq, set())

        return nodes

    def _get_ready_prompts(
        self, state: ExecutionState, nodes: dict[int, PromptNode]
    ) -> list[PromptNode]:
        """Get prompts ready for execution (all dependencies completed)."""
        ready = []
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

        Returns:
            Tuple of (should_execute, condition_result, condition_error)

        """
        condition = prompt.get("condition")

        if not condition or not condition.strip():
            return True, None, None

        evaluator = ConditionEvaluator(results_by_name)
        result, error = evaluator.evaluate(condition)

        return result, result, error

    def _execute_prompt_isolated(
        self, prompt: dict[str, Any], state: ExecutionState
    ) -> dict[str, Any]:
        """Execute a single prompt with completely isolated client clone."""
        max_retries = self.config.get("max_retries", 3)

        result = self._create_result_dict(prompt)

        client_name = prompt.get("client")

        with state.results_lock:
            should_execute, cond_result, cond_error = self._evaluate_condition(
                prompt, state.results_by_name
            )
            result["condition_result"] = cond_result
            result["condition_error"] = cond_error

        if not should_execute:
            result["status"] = "skipped"
            result["attempts"] = 0
            logger.info(f"Sequence {prompt['sequence']} skipped: condition evaluated to False")
            return result

        for attempt in range(1, max_retries + 1):
            result["attempts"] = attempt

            try:
                logger.debug(
                    f"Executing sequence {prompt['sequence']} (attempt {attempt})"
                    + (f" with client '{client_name}'" if client_name else "")
                )

                ffai = self._get_isolated_ffai(client_name)

                injected_prompt = self._inject_references(prompt)

                response = ffai.generate_response(
                    prompt=injected_prompt,
                    prompt_name=prompt.get("prompt_name"),
                    history=prompt.get("history"),
                    model=self.config.get("model"),
                    temperature=self.config.get("temperature"),
                    max_tokens=self.config.get("max_tokens"),
                )

                result["response"] = response
                result["status"] = "success"
                logger.debug(f"Sequence {prompt['sequence']} succeeded")
                break

            except Exception as e:
                result["error"] = str(e)
                logger.warning(f"Sequence {prompt['sequence']} failed (attempt {attempt}): {e}")

                if attempt == max_retries:
                    result["status"] = "failed"
                    logger.error(
                        f"Sequence {prompt['sequence']} failed after {max_retries} attempts"
                    )

        return result

    def _execute_prompt(
        self,
        prompt: dict[str, Any],
        results_by_name: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute a single prompt with retry logic."""
        max_retries = self.config.get("max_retries", 3)

        result = self._create_result_dict(prompt)

        results_by_name = results_by_name or {}

        should_execute, cond_result, cond_error = self._evaluate_condition(prompt, results_by_name)
        result["condition_result"] = cond_result
        result["condition_error"] = cond_error

        if not should_execute:
            result["status"] = "skipped"
            result["attempts"] = 0
            logger.info(f"Sequence {prompt['sequence']} skipped: condition evaluated to False")
            return result

        client_name = prompt.get("client")
        ffai = self._get_isolated_ffai(client_name)

        for attempt in range(1, max_retries + 1):
            result["attempts"] = attempt

            try:
                logger.info(
                    f"Executing sequence {prompt['sequence']} (attempt {attempt})"
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

                result["response"] = response
                result["status"] = "success"
                logger.info(f"Sequence {prompt['sequence']} succeeded")
                break

            except Exception as e:
                result["error"] = str(e)
                logger.warning(f"Sequence {prompt['sequence']} failed (attempt {attempt}): {e}")

                if attempt == max_retries:
                    result["status"] = "failed"
                    logger.error(
                        f"Sequence {prompt['sequence']} failed after {max_retries} attempts"
                    )

        return result

    def _resolve_variables(self, text: str, data_row: dict[str, Any]) -> str:
        """Replace {{variable}} placeholders with values from data row."""
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
        """Resolve all {{variable}} placeholders in a prompt."""
        resolved = dict(prompt)
        resolved["prompt"] = self._resolve_variables(prompt.get("prompt", ""), data_row)
        if prompt.get("prompt_name"):
            resolved["prompt_name"] = self._resolve_variables(prompt["prompt_name"], data_row)
        return resolved

    def _resolve_batch_name(self, data_row: dict[str, Any], batch_id: int) -> str:
        """Generate batch name from data row or default."""
        if "batch_name" in data_row and data_row["batch_name"]:
            name = self._resolve_variables(str(data_row["batch_name"]), data_row)
            return re.sub(r"[^\w\-]", "_", name)[:50]
        return f"batch_{batch_id}"

    def _execute_single_batch(
        self, batch_id: int, data_row: dict[str, Any], batch_name: str
    ) -> list[dict[str, Any]]:
        """Execute all prompts for a single batch with resolved variables."""
        results = []
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
        """Execute a single prompt and tag with batch info."""
        max_retries = self.config.get("max_retries", 3)

        builder = ResultBuilder(prompt).with_batch(batch_id, batch_name)
        results_by_name = results_by_name or {}

        should_execute, cond_result, cond_error = self._evaluate_condition(prompt, results_by_name)
        builder.with_condition_result(cond_result, cond_error)

        if not should_execute:
            builder.as_skipped(cond_result, cond_error)
            logger.info(
                f"Batch {batch_id}, sequence {prompt['sequence']} skipped: condition evaluated to False"
            )
            return builder.build_dict()

        client_name = prompt.get("client")
        ffai = self._get_isolated_ffai(client_name)

        for attempt in range(1, max_retries + 1):
            builder.with_attempts(attempt)

            try:
                logger.info(
                    f"Executing batch {batch_id}, sequence {prompt['sequence']} (attempt {attempt})"
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

                builder.with_response(response)
                logger.info(f"Batch {batch_id}, sequence {prompt['sequence']} succeeded")
                break

            except Exception as e:
                builder.with_error(str(e), attempt)
                logger.warning(
                    f"Batch {batch_id}, sequence {prompt['sequence']} failed (attempt {attempt}): {e}"
                )

                if attempt == max_retries:
                    logger.error(
                        f"Batch {batch_id}, sequence {prompt['sequence']} failed after {max_retries} attempts"
                    )

        return builder.build_dict()

    def execute(self) -> list[dict[str, Any]]:
        """Execute all prompts in sequence with dependency-aware ordering."""
        strategy = SequentialStrategy()
        self.results = strategy.execute(self)
        return self.results

    def execute_parallel(self) -> list[dict[str, Any]]:
        """Execute prompts in parallel with dependency-aware scheduling."""
        strategy = ParallelStrategy()
        self.results = strategy.execute(self)
        return self.results

    def execute_batch(self) -> list[dict[str, Any]]:
        """Execute all prompts for each batch row sequentially."""
        strategy = BatchSequentialStrategy()
        self.results = strategy.execute(self)
        return self.results

    def execute_batch_parallel(self) -> list[dict[str, Any]]:
        """Execute batches in parallel, with dependency-aware prompt execution within each batch."""
        strategy = BatchParallelStrategy()
        self.results = strategy.execute(self)
        return self.results

    def run(self) -> str:
        """Initialize, validate, execute prompts, and write results.

        Returns:
            Name of the results sheet created.

        """
        self._init_workbook()
        self._load_config()
        self.prompts = self.builder.load_prompts()
        self._validate_dependencies()
        self._init_client()
        self._init_client_registry()
        self._init_documents()

        self.batch_data = self.builder.load_data()
        self.is_batch_mode = len(self.batch_data) > 0

        strategy = get_execution_strategy(self.is_batch_mode, self.concurrency)
        logger.info(f"Using {strategy.name} execution strategy")

        if self.is_batch_mode:
            logger.info(f"Running in batch mode with {len(self.batch_data)} batches")

        self.results = strategy.execute(self)

        batch_output = self.config.get("batch_output", "combined")

        if self.is_batch_mode and batch_output == "separate_sheets":
            return self._write_separate_batch_results()
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_sheet = f"results_{timestamp}"
            self.builder.write_results(self.results, results_sheet)
            logger.info(f"Orchestration complete. Results in sheet: {results_sheet}")
            return results_sheet

    def _write_separate_batch_results(self) -> str:
        """Write results to separate sheets per batch."""
        batches: dict[int, list[dict[str, Any]]] = {}
        for result in self.results:
            batch_id = result.get("batch_id", 0)
            if batch_id not in batches:
                batches[batch_id] = []
            batches[batch_id].append(result)

        sheet_names = []
        for batch_id in sorted(batches.keys()):
            batch_results = batches[batch_id]
            batch_name = batch_results[0].get("batch_name", f"batch_{batch_id}")
            sheet_name = self.builder.write_batch_results(batch_results, batch_name)
            sheet_names.append(sheet_name)

        logger.info(f"Wrote {len(sheet_names)} batch result sheets")
        return ", ".join(sheet_names)

    def get_summary(self) -> dict[str, Any]:
        """Get execution summary."""
        if not self.results:
            return {"status": "not_run"}

        summary = {
            "total_prompts": len(self.results),
            "successful": sum(1 for r in self.results if r["status"] == "success"),
            "failed": sum(1 for r in self.results if r["status"] == "failed"),
            "skipped": sum(1 for r in self.results if r["status"] == "skipped"),
            "total_attempts": sum(r["attempts"] for r in self.results),
            "workbook": self.workbook_path,
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
