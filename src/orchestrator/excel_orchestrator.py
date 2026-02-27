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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..config import get_config
from ..FFAI import FFAI
from ..FFAIClientBase import FFAIClientBase
from .client_registry import ClientRegistry
from .condition_evaluator import ConditionEvaluator
from .document_processor import DocumentProcessor
from .document_registry import DocumentRegistry
from .workbook_builder import WorkbookBuilder

if TYPE_CHECKING:
    from ..RAG import FFRAGClient

logger = logging.getLogger(__name__)


@dataclass
class PromptNode:
    """Represents a prompt in the execution dependency graph.

    Attributes:
        sequence: The prompt's sequence number.
        prompt: The prompt dictionary.
        dependencies: Set of sequence numbers this prompt depends on.
        level: The execution level (0 = no dependencies).

    """

    sequence: int
    prompt: dict[str, Any]
    dependencies: set[int] = field(default_factory=set)
    level: int = 0


@dataclass
class ExecutionState:
    """Tracks state during parallel execution.

    Attributes:
        completed: Set of completed sequence numbers.
        in_progress: Set of currently executing sequence numbers.
        pending: Dict of pending PromptNodes by sequence number.
        results: List of execution results.
        results_lock: Thread lock for result access.
        success_count: Number of successful executions.
        failed_count: Number of failed executions.
        skipped_count: Number of skipped executions.
        results_by_name: Results indexed by prompt name.
        current_name: Name of currently executing prompt.
        running_count: Number of currently running tasks.

    """

    completed: set[int] = field(default_factory=set)
    in_progress: set[int] = field(default_factory=set)
    pending: dict[int, PromptNode] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)
    results_lock: threading.Lock = field(default_factory=threading.Lock)
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    results_by_name: dict[str, dict[str, Any]] = field(default_factory=dict)
    current_name: str = ""
    running_count: int = 0


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
        self.builder = WorkbookBuilder(workbook_path)

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

    def _inject_references(self, prompt: dict[str, Any]) -> str:
        """Inject document references or semantic search results into a prompt.

        Args:
            prompt: Prompt dictionary with optional 'references' and/or 'semantic_query' fields

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
                return self.document_registry.inject_semantic_query(prompt_text, semantic_query)
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

    def _create_result_dict(self, prompt: dict[str, Any]) -> dict[str, Any]:
        """Create a result dictionary for a prompt."""
        return {
            "sequence": prompt["sequence"],
            "prompt_name": prompt.get("prompt_name"),
            "prompt": prompt["prompt"],
            "history": prompt.get("history"),
            "client": prompt.get("client"),
            "condition": prompt.get("condition"),
            "condition_result": None,
            "condition_error": None,
            "response": None,
            "status": "pending",
            "attempts": 0,
            "error": None,
            "references": prompt.get("references"),
            "semantic_query": prompt.get("semantic_query"),
        }

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

        result = {
            "batch_id": batch_id,
            "batch_name": batch_name,
            "sequence": prompt["sequence"],
            "prompt_name": prompt.get("prompt_name"),
            "prompt": prompt["prompt"],
            "history": prompt.get("history"),
            "client": prompt.get("client"),
            "condition": prompt.get("condition"),
            "condition_result": None,
            "condition_error": None,
            "response": None,
            "status": "pending",
            "attempts": 0,
            "error": None,
            "references": prompt.get("references"),
            "semantic_query": prompt.get("semantic_query"),
        }

        results_by_name = results_by_name or {}

        should_execute, cond_result, cond_error = self._evaluate_condition(prompt, results_by_name)
        result["condition_result"] = cond_result
        result["condition_error"] = cond_error

        if not should_execute:
            result["status"] = "skipped"
            result["attempts"] = 0
            logger.info(
                f"Batch {batch_id}, sequence {prompt['sequence']} skipped: condition evaluated to False"
            )
            return result

        client_name = prompt.get("client")
        ffai = self._get_isolated_ffai(client_name)

        for attempt in range(1, max_retries + 1):
            result["attempts"] = attempt

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

                result["response"] = response
                result["status"] = "success"
                logger.info(f"Batch {batch_id}, sequence {prompt['sequence']} succeeded")
                break

            except Exception as e:
                result["error"] = str(e)
                logger.warning(
                    f"Batch {batch_id}, sequence {prompt['sequence']} failed (attempt {attempt}): {e}"
                )

                if attempt == max_retries:
                    result["status"] = "failed"
                    logger.error(
                        f"Batch {batch_id}, sequence {prompt['sequence']} failed after {max_retries} attempts"
                    )

        return result

    def execute(self) -> list[dict[str, Any]]:
        """Execute all prompts in sequence with dependency-aware ordering."""
        self.results = []
        results_by_name: dict[str, dict[str, Any]] = {}
        total = len(self.prompts)

        nodes = self._build_execution_graph()
        sorted_prompts = sorted(
            self.prompts, key=lambda p: (nodes[p["sequence"]].level, p["sequence"])
        )

        for prompt in sorted_prompts:
            if self.progress_callback:
                self.progress_callback(
                    len(self.results),
                    total,
                    sum(1 for r in self.results if r["status"] == "success"),
                    sum(1 for r in self.results if r["status"] == "failed"),
                    current_name=prompt.get("prompt_name"),
                    running=1,
                )
            result = self._execute_prompt(prompt, results_by_name)
            self.results.append(result)

            if result.get("prompt_name"):
                results_by_name[result["prompt_name"]] = result

        successful = sum(1 for r in self.results if r["status"] == "success")
        failed = sum(1 for r in self.results if r["status"] == "failed")
        skipped = sum(1 for r in self.results if r["status"] == "skipped")

        if self.progress_callback:
            self.progress_callback(
                total,
                total,
                successful,
                failed,
                current_name=None,
                running=0,
            )

        logger.info(
            f"Execution complete: {successful} succeeded, {failed} failed, {skipped} skipped"
        )
        return self.results

    def execute_parallel(self) -> list[dict[str, Any]]:
        """Execute prompts in parallel with dependency-aware scheduling."""
        nodes = self._build_execution_graph()
        state = ExecutionState(pending=dict(nodes))

        total = len(nodes)

        def update_progress() -> None:
            if self.progress_callback:
                self.progress_callback(
                    len(state.completed),
                    total,
                    state.success_count,
                    state.failed_count,
                    current_name=state.current_name,
                    running=len(state.in_progress),
                )

        logger.info(f"Starting parallel execution with concurrency={self.concurrency}")

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            while len(state.completed) < total:
                ready = self._get_ready_prompts(state, nodes)

                if not ready and not state.in_progress:
                    logger.error("Deadlock detected: no ready prompts and none in progress")
                    break

                futures = {}
                for node in ready:
                    if len(state.in_progress) >= self.concurrency:
                        break
                    state.in_progress.add(node.sequence)
                    future = executor.submit(self._execute_prompt_isolated, node.prompt, state)
                    futures[future] = node.sequence

                for future in as_completed(futures):
                    seq = futures[future]
                    try:
                        result = future.result()
                        with state.results_lock:
                            state.results.append(result)
                            state.completed.add(seq)
                            state.current_name = result.get("prompt_name") or f"seq_{seq}"
                            if result["status"] == "success":
                                state.success_count += 1
                            elif result["status"] == "skipped":
                                state.skipped_count += 1
                            else:
                                state.failed_count += 1
                            if result.get("prompt_name"):
                                state.results_by_name[result["prompt_name"]] = result
                    except Exception as e:
                        logger.error(f"Unexpected error for sequence {seq}: {e}")
                        with state.results_lock:
                            state.completed.add(seq)
                            state.failed_count += 1
                            state.current_name = (
                                nodes[seq].prompt.get("prompt_name") or f"seq_{seq}"
                            )
                            state.results.append(
                                {
                                    "sequence": seq,
                                    "prompt_name": nodes[seq].prompt.get("prompt_name"),
                                    "prompt": nodes[seq].prompt["prompt"],
                                    "history": nodes[seq].prompt.get("history"),
                                    "client": nodes[seq].prompt.get("client"),
                                    "condition": nodes[seq].prompt.get("condition"),
                                    "condition_result": None,
                                    "condition_error": None,
                                    "response": None,
                                    "status": "failed",
                                    "attempts": 1,
                                    "error": str(e),
                                    "references": nodes[seq].prompt.get("references"),
                                    "semantic_query": nodes[seq].prompt.get("semantic_query"),
                                }
                            )
                    finally:
                        state.in_progress.discard(seq)
                        update_progress()

        state.results.sort(key=lambda r: r["sequence"])
        self.results = state.results

        logger.info(
            f"Parallel execution complete: {state.success_count} succeeded, "
            f"{state.failed_count} failed, {state.skipped_count} skipped"
        )
        return self.results

    def execute_batch(self) -> list[dict[str, Any]]:
        """Execute all prompts for each batch row sequentially."""
        self.results = []
        total_batches = len(self.batch_data)
        total_prompts = len(self.prompts)
        total = total_batches * total_prompts

        for batch_idx, data_row in enumerate(self.batch_data, start=1):
            batch_name = self._resolve_batch_name(data_row, batch_idx)
            logger.info(f"Starting batch {batch_idx}/{total_batches}: {batch_name}")

            batch_results = self._execute_single_batch(batch_idx, data_row, batch_name)
            self.results.extend(batch_results)

            batch_failed = sum(1 for r in batch_results if r["status"] == "failed")
            if batch_failed > 0:
                on_error = self.config.get("on_batch_error", "continue")
                if on_error == "stop":
                    logger.error(f"Stopping at batch {batch_idx} due to {batch_failed} failures")
                    break

            if self.progress_callback:
                completed = len(self.results)
                success = sum(1 for r in self.results if r["status"] == "success")
                failed = sum(1 for r in self.results if r["status"] == "failed")
                self.progress_callback(
                    completed,
                    total,
                    success,
                    failed,
                    current_name=f"batch_{batch_idx}",
                    running=1,
                )

        successful = sum(1 for r in self.results if r["status"] == "success")
        failed = sum(1 for r in self.results if r["status"] == "failed")
        skipped = sum(1 for r in self.results if r["status"] == "skipped")
        logger.info(
            f"Batch execution complete: {successful} succeeded, {failed} failed, {skipped} skipped"
        )
        return self.results

    def execute_batch_parallel(self) -> list[dict[str, Any]]:
        """Execute batches in parallel, with dependency-aware prompt execution within each batch."""
        total_batches = len(self.batch_data)
        total_prompts = len(self.prompts)
        total = total_batches * total_prompts

        state = ExecutionState()
        results_lock = threading.Lock()

        def execute_single_batch_isolated(
            batch_idx: int, data_row: dict[str, Any]
        ) -> list[dict[str, Any]]:
            batch_name = self._resolve_batch_name(data_row, batch_idx)
            batch_results = []
            batch_results_by_name: dict[str, dict[str, Any]] = {}

            for prompt in self.prompts:
                resolved_prompt = self._resolve_prompt_variables(prompt, data_row)

                max_retries = self.config.get("max_retries", 3)
                result = {
                    "batch_id": batch_idx,
                    "batch_name": batch_name,
                    "sequence": resolved_prompt["sequence"],
                    "prompt_name": resolved_prompt.get("prompt_name"),
                    "prompt": resolved_prompt["prompt"],
                    "history": resolved_prompt.get("history"),
                    "client": resolved_prompt.get("client"),
                    "condition": resolved_prompt.get("condition"),
                    "condition_result": None,
                    "condition_error": None,
                    "response": None,
                    "status": "pending",
                    "attempts": 0,
                    "error": None,
                    "references": resolved_prompt.get("references"),
                    "semantic_query": resolved_prompt.get("semantic_query"),
                }

                evaluator = ConditionEvaluator(batch_results_by_name)
                should_execute, cond_error = evaluator.evaluate(
                    resolved_prompt.get("condition") or ""
                )
                result["condition_result"] = should_execute
                result["condition_error"] = cond_error

                if not should_execute:
                    result["status"] = "skipped"
                    result["attempts"] = 0
                    batch_results.append(result)
                    if result.get("prompt_name"):
                        batch_results_by_name[result["prompt_name"]] = result
                    continue

                client_name = resolved_prompt.get("client")

                for attempt in range(1, max_retries + 1):
                    result["attempts"] = attempt
                    try:
                        ffai = self._get_isolated_ffai(client_name)

                        injected_prompt = self._inject_references(resolved_prompt)

                        response = ffai.generate_response(
                            prompt=injected_prompt,
                            prompt_name=resolved_prompt.get("prompt_name"),
                            history=resolved_prompt.get("history"),
                            model=self.config.get("model"),
                            temperature=self.config.get("temperature"),
                            max_tokens=self.config.get("max_tokens"),
                        )

                        result["response"] = response
                        result["status"] = "success"
                        break

                    except Exception as e:
                        result["error"] = str(e)
                        if attempt == max_retries:
                            result["status"] = "failed"

                batch_results.append(result)
                if result["status"] == "success" and result.get("prompt_name"):
                    batch_results_by_name[result["prompt_name"]] = result

                if result["status"] == "failed":
                    on_error = self.config.get("on_batch_error", "continue")
                    if on_error == "stop":
                        break

            return batch_results

        all_results = []
        failed_batches = []

        logger.info(f"Starting parallel batch execution with concurrency={self.concurrency}")

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {}
            for batch_idx, data_row in enumerate(self.batch_data, start=1):
                future = executor.submit(execute_single_batch_isolated, batch_idx, data_row)
                futures[future] = batch_idx

            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    batch_results = future.result()
                    with results_lock:
                        all_results.extend(batch_results)
                        state.success_count += sum(
                            1 for r in batch_results if r["status"] == "success"
                        )
                        state.failed_count += sum(
                            1 for r in batch_results if r["status"] == "failed"
                        )

                    if self.progress_callback:
                        completed = len(all_results)
                        self.progress_callback(
                            completed,
                            total,
                            state.success_count,
                            state.failed_count,
                            current_name=f"batch_{batch_idx}",
                            running=len([f for f in futures if not f.done()]),
                        )

                    batch_failed = sum(1 for r in batch_results if r["status"] == "failed")
                    if batch_failed > 0:
                        failed_batches.append(batch_idx)

                except Exception as e:
                    logger.error(f"Batch {batch_idx} failed with exception: {e}")
                    failed_batches.append(batch_idx)

        all_results.sort(key=lambda r: (r["batch_id"], r["sequence"]))
        self.results = all_results

        logger.info(
            f"Parallel batch execution complete: {state.success_count} succeeded, "
            f"{state.failed_count} failed across {total_batches} batches"
        )
        if failed_batches:
            logger.warning(f"Failed batches: {failed_batches}")

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

        if self.is_batch_mode:
            logger.info(f"Running in batch mode with {len(self.batch_data)} batches")
            if self.concurrency > 1:
                self.execute_batch_parallel()
            else:
                self.execute_batch()
        else:
            if self.concurrency > 1:
                self.execute_parallel()
            else:
                self.execute()

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

            batch_failures = {}
            for r in self.results:
                if r["status"] == "failed":
                    batch_id = r.get("batch_id", 0)
                    batch_failures[batch_id] = batch_failures.get(batch_id, 0) + 1
            if batch_failures:
                summary["batches_with_failures"] = batch_failures

        return summary
