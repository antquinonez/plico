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

import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...config import get_config
from ...FFAI import FFAI
from ...FFAIClientBase import FFAIClientBase
from ..agent_executor import AgentExecutor
from ..client_registry import ClientRegistry
from ..document_processor import DocumentProcessor
from ..document_registry import DocumentRegistry
from ..executor import Executor
from ..graph import build_execution_graph, evaluate_condition, get_ready_prompts
from ..planning import PlanningArtifactParser
from ..results import ResultBuilder
from ..scoring import ScoreAggregator, ScoringRubric
from ..state import ExecutionState, PromptNode
from ..synthesis import SynthesisExecutor, build_entry_results_map
from ..templating import resolve_batch_name, resolve_prompt_variables, resolve_variables
from ..tool_registry import ToolDefinition, ToolRegistry
from ..validation import OrchestratorValidator
from ..workbook_parser import parse_history_string

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
        documents_path: str | None = None,
        shared_document_path: str | None = None,
        shared_document_name: str | None = None,
    ) -> None:
        """Initialize the orchestrator base.

        Args:
            client: Default AI client for prompt execution.
            config_overrides: Optional config overrides.
            concurrency: Maximum concurrent API calls (1-max). Uses config default if None.
            progress_callback: Optional callback for progress updates.
            documents_path: Optional folder path to auto-discover documents.
                Discovered documents populate the documents registry and batch
                data at runtime without modifying the source.
            shared_document_path: Optional path to a shared document file (e.g.,
                a job description, rubric, or reference document) added to the
                documents registry.
            shared_document_name: Optional reference name for the shared document.
                When provided, this is used as the ``reference_name`` in the
                documents registry (e.g., ``"job_description"``). When omitted,
                the name is derived from the filename stem using snake_case
                sanitization.

        """
        self.client = client
        self._documents_path = documents_path
        self._shared_document_path = shared_document_path
        self._shared_document_name = shared_document_name
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
        self.tool_registry: ToolRegistry | None = None
        self.has_tools: bool = False
        self.has_scoring: bool = False
        self.scoring_rubric: ScoringRubric | None = None
        self.evaluation_strategy: str = "balanced"
        self.has_synthesis: bool = False
        self.synthesis_prompts: list[dict[str, Any]] = []
        self._rag_client: FFRAGClient | None = None
        self._executor = Executor()

        # Planning phase state
        self.planning_results: list[dict[str, Any]] = []
        self.has_planning: bool = False
        self.planning_prompts: list[dict[str, Any]] = []

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

        self._rag_client = rag_client

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

    def _init_tools(self, tools_data: list[dict[str, Any]]) -> None:
        """Initialize tool registry from tool definitions.

        Registers all built-in tools with context-bound executors, then
        overlays any custom tool definitions from the workbook or manifest.

        Built-in tools are registered but disabled by default. A tool becomes
        enabled when it appears in the tools sheet (with enabled=true) or
        when a prompt references it via agent_mode.

        Args:
            tools_data: List of tool definition dictionaries.

        """
        if not tools_data:
            return

        from ..builtin_tools import BUILTIN_TOOL_DEFINITIONS, create_context_tools

        self.tool_registry = ToolRegistry()

        context_tools = create_context_tools(
            rag_client=getattr(self, "_rag_client", None),
            document_registry=self.document_registry,
        )

        for name, builtin_def in BUILTIN_TOOL_DEFINITIONS.items():
            definition = ToolDefinition(
                name=name,
                description=builtin_def["description"],
                parameters=builtin_def["parameters"],
                implementation=f"builtin:{name}",
                enabled=False,
            )
            self.tool_registry.register(definition)
            if name in context_tools:
                self.tool_registry.register_executor(name, context_tools[name])

        for tool_def in tools_data:
            definition = ToolDefinition.from_dict(tool_def)
            if definition.name in self.tool_registry.get_registered_names():
                existing = self.tool_registry.get_tool(definition.name)
                existing.enabled = definition.enabled
                if definition.implementation and definition.implementation.startswith("python:"):
                    callable_path = definition.implementation[len("python:") :]
                    executor = self.tool_registry.load_python_callable(callable_path)
                    if executor is not None:
                        self.tool_registry.register_executor(definition.name, executor)
            else:
                self.tool_registry.register(definition)

        self.has_tools = True
        enabled_names = self.tool_registry.get_enabled_names()
        logger.info(
            f"Tool registry initialized: {len(enabled_names)} enabled "
            f"({', '.join(enabled_names) if enabled_names else 'none'})"
        )

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

    def _record_agent_result_in_shared_history(
        self,
        prompt: dict[str, Any],
        response: str | None,
    ) -> None:
        """Record successful agent responses for downstream interpolation."""
        if response is None:
            return

        interaction = {
            "prompt": prompt.get("prompt", ""),
            "response": response,
            "prompt_name": prompt.get("prompt_name"),
            "timestamp": time.time(),
            "model": self.config.get("model"),
            "history": prompt.get("history"),
        }

        if self.history_lock:
            with self.history_lock:
                self.shared_prompt_attr_history.append(interaction)
        else:
            self.shared_prompt_attr_history.append(interaction)

    def _build_validator_params(self) -> dict[str, Any]:
        """Build common parameters for OrchestratorValidator.

        Returns:
            Dict of keyword arguments for OrchestratorValidator.__init__().

        """
        client_names = self.client_registry.get_registered_names() if self.client_registry else []

        batch_keys: list[str] = []
        row_docs: dict[int, list[str]] = {}
        if self.is_batch_mode and self.batch_data:
            batch_keys = OrchestratorValidator.extract_batch_keys(self.batch_data)
            for idx, row in enumerate(self.batch_data):
                raw = row.get("_documents")
                if raw:
                    parsed = parse_history_string(raw)
                    if parsed:
                        row_docs[idx] = parsed

        doc_refs: list[str] = []
        if self.document_registry:
            doc_refs = list(self.document_registry.get_reference_names())

        tool_names: list[str] = []
        if self.tool_registry:
            tool_names = self.tool_registry.get_registered_names()

        available_types: list[str] = []
        try:
            available_types = get_config().get_available_client_types()
        except Exception:
            logger.debug("Could not load available client types for validation", exc_info=True)

        scoring_criteria: list[dict[str, Any]] = []
        available_strategies: list[str] = []
        if self.has_scoring and self.scoring_rubric:
            from dataclasses import asdict

            scoring_criteria = [asdict(c) for c in self.scoring_rubric.criteria]
        try:
            eval_config = get_config().evaluation
            available_strategies = list(eval_config.strategies.keys()) if eval_config else []
        except Exception:
            pass

        return {
            "prompts": self.prompts,
            "config": self.config,
            "manifest_meta": getattr(self, "_manifest_meta", None),
            "client_names": client_names,
            "batch_data_keys": batch_keys,
            "doc_ref_names": doc_refs,
            "available_client_types": available_types,
            "tool_names": tool_names,
            "row_doc_refs": row_docs,
            "scoring_criteria": scoring_criteria,
            "available_strategies": available_strategies,
            "synthesis_prompts": self.synthesis_prompts if self.has_synthesis else None,
        }

    def _run_validator(
        self,
        label: str,
        **overrides: Any,
    ) -> None:
        """Build validator, run checks, and handle results.

        Args:
            label: Human-readable label for log messages (e.g., "Validation").
            **overrides: Extra keyword arguments passed to OrchestratorValidator,
                         overriding values from _build_validator_params().

        Raises:
            ValueError: If validation finds errors.

        """
        params = self._build_validator_params()
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

    def _validate(self) -> None:
        """Run comprehensive validation on prompts, config, and dependencies.

        Uses OrchestratorValidator to check prompt structure, dependency DAGs,
        template references, condition syntax, client assignments, config values,
        and more. Raises ValueError if any errors are found.
        """
        self._run_validator("Validation")

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
        return build_execution_graph(self.prompts)

    def _get_ready_prompts(
        self, state: ExecutionState, nodes: dict[int, PromptNode]
    ) -> list[PromptNode]:
        """Get prompts ready for execution (all dependencies completed)."""
        return get_ready_prompts(state, nodes)

    def _evaluate_condition(
        self, prompt: dict[str, Any], results_by_name: dict[str, dict[str, Any]]
    ) -> tuple[bool, str | None, str | None]:
        """Evaluate a prompt's condition."""
        return evaluate_condition(prompt, results_by_name)

    def _execute_agent_mode(
        self,
        prompt: dict[str, Any],
        ffai: FFAI,
        builder: Any,
        seq_label: str,
    ) -> dict[str, Any]:
        """Execute a prompt using the agentic tool-call loop.

        Delegates to AgentExecutor with callbacks for orchestrator-specific
        operations (history recording, reference injection, client isolation).

        Args:
            prompt: Prompt dictionary with agent_mode=True.
            ffai: FFAI instance for the execution.
            builder: ResultBuilder already configured with prompt metadata.
            seq_label: Label for logging (e.g. "Sequence 10").

        Returns:
            Result dictionary with tool call records, or None for fallback.

        """
        agent_executor = AgentExecutor(
            tool_registry=self.tool_registry,
            config=self.config,
            record_history_fn=self._record_agent_result_in_shared_history,
        )
        return agent_executor.execute(
            prompt=prompt,
            ffai=ffai,
            builder=builder,
            seq_label=seq_label,
            inject_references_fn=self._inject_references,
            get_isolated_ffai_fn=self._get_isolated_ffai,
        )

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

        if prompt.get("agent_mode") and self.tool_registry:
            agent_result = self._execute_agent_mode(prompt, ffai, builder, seq_label)
            if agent_result is not None:
                return agent_result

        if prompt.get("agent_mode") and not self.tool_registry:
            logger.warning(
                f"{seq_label} has agent_mode=true but no tool registry initialized; "
                "falling back to single-shot execution. Add a 'tools' sheet or "
                "tools.yaml to the workbook/manifest."
            )

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
        """Replace {{variable}} placeholders with values from data row."""
        return resolve_variables(text, data_row)

    def _resolve_prompt_variables(
        self, prompt: dict[str, Any], data_row: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve all {{variable}} placeholders in a prompt."""
        return resolve_prompt_variables(prompt, data_row)

    def _resolve_batch_name(self, data_row: dict[str, Any], batch_id: int) -> str:
        """Generate batch name from data row or default."""
        return resolve_batch_name(data_row, batch_id)

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

    def _resolve_evaluation_strategy(self) -> str:
        """Resolve the effective evaluation strategy.

        Resolution order:
        1. Workbook config sheet evaluation_strategy (if present and valid)
        2. config/main.yaml evaluation.default_strategy
        3. Hardcoded fallback: 'balanced'

        """
        config_strategy = self.config.get("evaluation_strategy", "").strip()
        try:
            eval_config = get_config().evaluation
            available = eval_config.strategies if eval_config else {}
            if config_strategy and config_strategy in available:
                return config_strategy
            if eval_config and eval_config.default_strategy:
                return eval_config.default_strategy
        except Exception:
            logger.debug("Could not load evaluation config", exc_info=True)
        return "balanced"

    def _aggregate_scores(self) -> None:
        """Extract scores from batch results and compute composites."""
        if not self.scoring_rubric or not self.is_batch_mode:
            return

        try:
            eval_config = get_config().evaluation
            failure_threshold = eval_config.scoring_failure_threshold if eval_config else 0.5
            strategy_overrides = {}
            if eval_config and self.evaluation_strategy in eval_config.strategies:
                strategy_overrides = eval_config.strategies[
                    self.evaluation_strategy
                ].criteria_overrides
        except Exception:
            failure_threshold = 0.5
            strategy_overrides = {}
            logger.debug("Could not load evaluation config for scoring", exc_info=True)

        aggregator = ScoreAggregator(
            rubric=self.scoring_rubric,
            strategy=self.evaluation_strategy,
            strategy_overrides=strategy_overrides,
            failure_threshold=failure_threshold,
        )

        grouped: dict[int, list[dict[str, Any]]] = {}
        for r in self.results:
            batch_id = r.get("batch_id")
            if batch_id is None:
                continue  # Skip planning results (batch_id=None)
            if batch_id not in grouped:
                grouped[batch_id] = []
            grouped[batch_id].append(r)

        for batch_id, batch_results in grouped.items():
            results_by_name = {r["prompt_name"]: r for r in batch_results}
            batch_name = (
                batch_results[0].get("batch_name", f"batch_{batch_id}") if batch_results else ""
            )
            scoring_result = aggregator.aggregate_entry(results_by_name, batch_name)

            for r in batch_results:
                r["scores"] = scoring_result["scores"]
                r["composite_score"] = scoring_result["composite_score"]
                r["scoring_status"] = scoring_result["scoring_status"]
                r["strategy"] = scoring_result["strategy"]
                r["result_type"] = "batch"

    def _execute_synthesis(self) -> None:
        """Execute synthesis prompts with cross-row batch context."""
        if not self.synthesis_prompts or not self.is_batch_mode:
            return

        try:
            eval_config = get_config().evaluation
            max_context = eval_config.max_synthesis_context_chars if eval_config else 30000
        except Exception:
            max_context = 30000
            logger.debug("Could not load evaluation config for synthesis", exc_info=True)

        executor = SynthesisExecutor(max_context_chars=max_context)

        grouped: dict[int, list[dict[str, Any]]] = {}
        for r in self.results:
            batch_id = r.get("batch_id", 0)
            if batch_id not in grouped:
                grouped[batch_id] = []
            grouped[batch_id].append(r)

        sorted_batch_ids = sorted(grouped.keys())
        batch_results_list = [grouped[bid] for bid in sorted_batch_ids]

        entry_results_map = build_entry_results_map(batch_results_list)

        criteria_list: list[dict[str, Any]] = []
        if self.scoring_rubric:
            criteria_list = [
                {"criteria_name": c.criteria_name} for c in self.scoring_rubric.criteria
            ]

        sorted_entries = executor.sort_entries(
            batch_results_list,
            scoring_criteria=criteria_list,
            has_scoring=self.has_scoring,
        )

        for entry in sorted_entries:
            bid = entry.get("batch_id", 0)
            entry["_all_results"] = entry_results_map.get(bid, {})

        self.shared_prompt_attr_history = []
        synthesis_results: list[dict[str, Any]] = []
        results_by_name: dict[str, dict[str, Any]] = {}

        for synth_prompt in self.synthesis_prompts:
            try:
                source_scope = synth_prompt.get("source_scope", "all")
                source_prompts = synth_prompt.get("source_prompts", [])
                include_scores = synth_prompt.get("include_scores", True)

                entries = executor.resolve_source_scope(source_scope, sorted_entries)

                scale_max = 10
                if self.scoring_rubric and self.scoring_rubric.criteria:
                    scale_max = self.scoring_rubric.criteria[0].scale_max

                context = executor.format_entry_context(
                    entries,
                    source_prompts,
                    include_scores,
                    strategy=self.evaluation_strategy if self.has_scoring else "",
                    scale_max=scale_max,
                )

                resolved_history = ""
                history_deps = synth_prompt.get("history") or []
                for dep_name in history_deps:
                    dep_result = results_by_name.get(dep_name)
                    if dep_result and dep_result.get("status") == "failed":
                        logger.warning(
                            f"Synthesis prompt '{synth_prompt.get('prompt_name')}' "
                            f"references failed prompt '{dep_name}', "
                            f"which returned empty response"
                        )
                    dep_response = dep_result.get("response", "") if dep_result else ""
                    resolved_history += f"--- {dep_name} ---\n{dep_response}\n\n"
                    if dep_result:
                        self.shared_prompt_attr_history.append(dep_result)

                prompt_parts = [context]
                if resolved_history.strip():
                    prompt_parts.append(resolved_history.strip())
                prompt_parts.append(synth_prompt["prompt"])
                full_prompt = "\n\n===\n\n".join(prompt_parts)

                ffai = self._get_isolated_ffai(synth_prompt.get("client"))
                response = ffai.generate_response(
                    prompt=full_prompt,
                    prompt_name=synth_prompt.get("prompt_name"),
                )

                result = {
                    "sequence": synth_prompt["sequence"],
                    "prompt_name": synth_prompt.get("prompt_name"),
                    "prompt": synth_prompt["prompt"],
                    "resolved_prompt": full_prompt,
                    "response": response,
                    "status": "success",
                    "attempts": 1,
                    "batch_id": -1,
                    "batch_name": "",
                    "history": synth_prompt.get("history"),
                    "condition": synth_prompt.get("condition"),
                    "condition_result": None,
                    "condition_error": None,
                    "error": None,
                    "references": None,
                    "result_type": "synthesis",
                    "scores": None,
                    "composite_score": None,
                    "scoring_status": "",
                    "strategy": self.evaluation_strategy if self.has_scoring else None,
                    "client": synth_prompt.get("client"),
                    "agent_mode": False,
                    "tool_calls": None,
                    "total_rounds": None,
                    "total_llm_calls": None,
                    "validation_passed": None,
                    "validation_attempts": None,
                    "validation_critique": None,
                    "semantic_query": None,
                    "semantic_filter": None,
                    "query_expansion": None,
                    "rerank": None,
                }

            except Exception as e:
                logger.error(
                    f"Synthesis prompt '{synth_prompt.get('prompt_name')}' failed: {e}",
                    exc_info=True,
                )
                result = {
                    "sequence": synth_prompt["sequence"],
                    "prompt_name": synth_prompt.get("prompt_name"),
                    "prompt": synth_prompt["prompt"],
                    "resolved_prompt": "",
                    "response": "",
                    "status": "failed",
                    "attempts": 1,
                    "error": str(e),
                    "batch_id": -1,
                    "batch_name": "",
                    "history": synth_prompt.get("history"),
                    "condition": synth_prompt.get("condition"),
                    "condition_result": None,
                    "condition_error": None,
                    "references": None,
                    "result_type": "synthesis",
                    "scores": None,
                    "composite_score": None,
                    "scoring_status": "",
                    "strategy": self.evaluation_strategy if self.has_scoring else None,
                    "client": synth_prompt.get("client"),
                    "agent_mode": False,
                    "tool_calls": None,
                    "total_rounds": None,
                    "total_llm_calls": None,
                    "validation_passed": None,
                    "validation_attempts": None,
                    "validation_critique": None,
                    "semantic_query": None,
                    "semantic_filter": None,
                    "query_expansion": None,
                    "rerank": None,
                }

            synthesis_results.append(result)
            if result.get("prompt_name"):
                results_by_name[result["prompt_name"]] = result

        self.results.extend(synthesis_results)
        logger.info(f"Synthesis complete: {len(synthesis_results)} prompts executed")

    def _detect_planning_prompts(self) -> None:
        """Detect and separate planning-phase prompts from execution prompts.

        Called during _load_source() in subclasses after prompts are loaded.
        Splits self.prompts into self.planning_prompts (phase=planning) and
        self.prompts (phase=execution only).
        """
        planning = [p for p in self.prompts if p.get("phase") == "planning"]
        if planning:
            self.has_planning = True
            self.planning_prompts = sorted(planning, key=lambda x: x.get("sequence", 0))
            self.prompts = [p for p in self.prompts if p.get("phase") != "planning"]
            logger.info(
                f"Planning phase enabled: {len(self.planning_prompts)} planning prompts, "
                f"{len(self.prompts)} execution prompts"
            )
            if not self.is_batch_mode:
                logger.warning(
                    "Planning prompts detected but no batch data sheet. "
                    "Scoring and synthesis will be skipped."
                )

    @staticmethod
    def _resolve_shared_document(
        document_path: str,
        reference_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a document definition for a shared document file.

        Args:
            document_path: Path to the shared document file.
            reference_name: Optional reference name. If not provided, derived
                from the filename stem using snake_case sanitization.

        Returns:
            Document definition dict suitable for the documents registry.

        """
        from pathlib import Path

        path = Path(document_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Shared document file not found: {document_path}")

        if reference_name is None:
            import re

            reference_name = re.sub(r"[^a-z0-9_]+", "_", path.stem.lower()).strip("_")

        return {
            "reference_name": reference_name,
            "common_name": path.stem,
            "file_path": str(path),
            "tags": "shared",
            "chunking_strategy": "",
            "notes": f"Shared document: {path.name}",
        }

    def _inject_discovery_overrides(self, source_dir: str) -> None:
        """Inject documents and batch data from documents_path and shared_document_path.

        Called by subclasses during _load_source() after loading their own
        documents and batch data. Discovered documents merge with any
        existing documents; discovered batch rows append to existing data.

        Args:
            source_dir: Base directory for resolving document paths
                (workbook dir for Excel, manifest dir for Manifest).

        """
        from ..discovery import create_data_rows_from_documents, discover_documents

        discovered_docs: list[dict[str, Any]] = []

        if self._shared_document_path:
            shared_doc = self._resolve_shared_document(
                self._shared_document_path,
                reference_name=self._shared_document_name,
            )
            discovered_docs.append(shared_doc)
            logger.info(
                f"Injected shared document '{shared_doc['reference_name']}': "
                f"{shared_doc['file_path']}"
            )

        if self._documents_path:
            folder_docs = discover_documents(
                self._documents_path,
                absolute_paths=True,
            )
            if not folder_docs:
                logger.warning(f"No documents discovered in documents_path: {self._documents_path}")
            else:
                discovered_docs.extend(folder_docs)
                logger.info(
                    f"Discovered {len(folder_docs)} documents from documents_path: "
                    f"{self._documents_path}"
                )

                folder_data = create_data_rows_from_documents(folder_docs)
                if self.batch_data:
                    self.batch_data.extend(folder_data)
                    logger.info(
                        f"Appended {len(folder_data)} batch rows to existing "
                        f"{len(self.batch_data) - len(folder_data)} source rows"
                    )
                else:
                    self.batch_data = folder_data
                    logger.info(f"Created {len(folder_data)} batch rows from discovered documents")

                self.is_batch_mode = len(self.batch_data) > 0

        if discovered_docs:
            all_docs = discovered_docs
            if self.has_documents and self.document_registry:
                existing = list(self.document_registry.documents.values())
                all_docs = existing + discovered_docs
                logger.info(
                    f"Merged {len(discovered_docs)} discovered docs with "
                    f"{len(existing)} source docs"
                )

            self._init_documents(all_docs, source_dir)

    def _execute_planning_phase(self) -> None:
        """Execute planning-phase prompts sequentially before batch execution.

        For generator prompts, parses structured JSON artifacts and injects
        scoring criteria and/or execution prompts into the pipeline.
        """
        logger.info(f"Executing planning phase with {len(self.planning_prompts)} prompts")
        results_by_name: dict[str, dict[str, Any]] = {}
        planning_config = get_config().planning

        generator_artifacts: list = []
        parser = PlanningArtifactParser()

        for prompt in self.planning_prompts:
            prompt_name = prompt.get("prompt_name", "(unnamed)")

            if self.progress_callback:
                self.progress_callback(
                    completed=len(self.planning_results),
                    total=len(self.planning_prompts),
                    success=len([r for r in self.planning_results if r.get("status") == "success"]),
                    failed=len([r for r in self.planning_results if r.get("status") == "failed"]),
                    current_name=f"[planning] {prompt_name}",
                )

            result = self._execute_prompt(prompt, results_by_name=results_by_name)

            # Tag as planning result
            result["result_type"] = "planning"
            result["batch_id"] = None
            result["batch_name"] = None
            self.planning_results.append(result)

            if result.get("prompt_name"):
                results_by_name[result["prompt_name"]] = result

            # For generator prompts: manually record in shared history with original
            # prompt_name (FFAI flattens dict responses by key, losing the original name)
            if prompt.get("generator") and result.get("status") == "success":
                response = result.get("response", "")
                with self.history_lock:
                    self.shared_prompt_attr_history.append(
                        {
                            "prompt": prompt.get("prompt", ""),
                            "response": response,
                            "prompt_name": prompt.get("prompt_name"),
                            "timestamp": time.time(),
                            "model": self.config.get("model"),
                            "history": prompt.get("history"),
                        }
                    )

                # Parse generator artifacts
                try:
                    artifact = parser.parse(response, prompt_name)
                    generator_artifacts.append(artifact)
                except ValueError as e:
                    logger.error(f"Planning generator '{prompt_name}' artifact parse failed: {e}")
                    if not planning_config.continue_on_parse_error:
                        raise

            logger.info(f"Planning prompt '{prompt_name}' completed: {result.get('status')}")

        # Parse and inject generated artifacts
        if generator_artifacts:
            self._parse_generated_artifacts(generator_artifacts, parser, planning_config)

        logger.info(f"Planning phase complete: {len(self.planning_results)} prompts executed")

    def _parse_generated_artifacts(
        self,
        artifacts: list,
        parser: PlanningArtifactParser,
        planning_config: Any,
    ) -> None:
        """Parse, validate, and inject generated artifacts from planning phase.

        Handles:
        - Merging artifacts from multiple generators
        - Validating and injecting generated prompts into self.prompts
        - Auto-deriving scoring rubric if no manual scoring sheet exists

        Args:
            artifacts: List of GeneratedArtifact instances.
            parser: PlanningArtifactParser instance.
            planning_config: PlanningConfig instance.

        """
        merged_criteria, merged_prompts = parser.merge_artifacts(artifacts)

        # Validate and inject generated prompts
        if merged_prompts:
            existing_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}
            doc_refs: set[str] = set()
            if self.document_registry:
                doc_refs = set(self.document_registry.get_reference_names())
            batch_keys: set[str] = set()
            if self.is_batch_mode and self.batch_data:
                batch_keys = set(OrchestratorValidator.extract_batch_keys(self.batch_data))

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
                # Filter out prompts with missing required fields
                merged_prompts = [
                    p for p in merged_prompts if p.get("prompt_name") and p.get("prompt")
                ]

            # Assign sequence numbers
            existing_seqs = {p["sequence"] for p in self.prompts if p.get("sequence")}
            parser.assign_sequences(
                merged_prompts,
                existing_seqs,
                base=planning_config.generated_sequence_base,
                step=planning_config.generated_sequence_step,
            )

            # Tag and inject generated prompts
            for p in merged_prompts:
                p["_generated"] = True
                # Use reversed() so the last generator wins (refinement pattern)
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

            self.prompts.extend(merged_prompts)
            self.prompts.sort(key=lambda x: x.get("sequence", 0))
            logger.info(f"Injected {len(merged_prompts)} generated prompts into execution pipeline")

        # Auto-derive scoring rubric
        if merged_criteria:
            if self.has_scoring:
                logger.warning(
                    "Both scoring sheet and generated criteria present. Using scoring sheet."
                )
            else:
                # Validate source_prompt mapping against final prompt list
                all_prompt_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}
                criteria_errors = parser.validate_criteria(merged_criteria, all_prompt_names)
                if criteria_errors:
                    for err in criteria_errors:
                        logger.error(f"Generated criteria validation error: {err}")

                # Filter to valid criteria only
                valid_criteria = [
                    c
                    for c in merged_criteria
                    if c.get("criteria_name")
                    and (not c.get("source_prompt") or c["source_prompt"] in all_prompt_names)
                ]

                if valid_criteria:
                    scoring_criteria_objs = parser.build_scoring_criteria(valid_criteria)
                    self.scoring_rubric = ScoringRubric(scoring_criteria_objs)
                    self.has_scoring = True
                    self.evaluation_strategy = self._resolve_evaluation_strategy()
                    logger.info(
                        f"Scoring rubric auto-derived from planning phase with "
                        f"{len(valid_criteria)} criteria, "
                        f"strategy='{self.evaluation_strategy}'"
                    )
                else:
                    logger.warning(
                        "All generated scoring criteria failed validation. "
                        "Proceeding without scoring."
                    )

    def _validate_pre_planning(self) -> None:
        """Run validation checks that can be performed before planning phase.

        Skips scoring source_prompt checks and synthesis source_prompts checks
        since generated prompts don't exist yet.
        """
        self._run_validator(
            "Pre-planning validation",
            skip_scoring_source_check=True,
            skip_synthesis_source_check=True,
            planning_prompts=self.planning_prompts,
        )

    def _validate_post_planning(self) -> None:
        """Run validation checks after planning phase, including generated artifacts.

        Validates scoring source_prompt mappings and synthesis source_prompts
        now that generated prompts are available.
        """
        self._run_validator(
            "Post-planning validation",
            skip_scoring_source_check=False,
            skip_synthesis_source_check=False,
        )

    def run(self) -> str:
        """Initialize, validate, execute prompts, and write results.

        Returns:
            Output identifier (sheet name or parquet path).

        """
        self._load_source()

        if self.has_planning:
            self._validate_pre_planning()
            self._init_client()
            self._execute_planning_phase()
            self._validate_post_planning()
        else:
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

        if self.has_scoring:
            self._aggregate_scores()

        if self.has_synthesis:
            self._execute_synthesis()

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

        if self.has_scoring:
            scored = [r for r in self.results if r.get("scoring_status")]
            scoring_block: dict[str, Any] = {
                "total_scored": len(scored),
                "ok": sum(1 for r in scored if r["scoring_status"] == "ok"),
                "partial": sum(1 for r in scored if r["scoring_status"] == "partial"),
                "failed": sum(1 for r in scored if r["scoring_status"] == "failed"),
                "skipped": sum(1 for r in scored if r["scoring_status"] == "skipped"),
                "strategy": self.evaluation_strategy,
            }
            composites = [
                r["composite_score"] for r in scored if r.get("composite_score") is not None
            ]
            if composites:
                scoring_block["avg_composite"] = round(sum(composites) / len(composites), 2)
                scoring_block["max_composite"] = max(composites)
                scoring_block["min_composite"] = min(composites)
            summary["scoring"] = scoring_block

        if self.has_synthesis:
            synth = [r for r in self.results if r.get("result_type") == "synthesis"]
            summary["synthesis"] = {
                "count": len(synth),
                "successful": sum(1 for r in synth if r["status"] == "success"),
                "failed": sum(1 for r in synth if r["status"] == "failed"),
            }

        return summary
