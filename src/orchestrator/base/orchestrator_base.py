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
from ...core.client_base import FFAIClientBase
from ...core.response_context import ResponseContext
from ...FFAI import FFAI
from ...observability import get_telemetry_manager
from ..agent_executor import AgentExecutor
from ..client_registry import ClientRegistry
from ..document_processor import DocumentProcessor
from ..document_registry import DocumentRegistry
from ..executor import Executor
from ..graph import build_execution_graph, evaluate_condition, get_ready_prompts
from ..models import ConfigSpec, DocumentSpec, Interaction, PromptSpec
from ..planning_runner import PlanningPhaseRunner
from ..results import ResultBuilder, ResultsFrame
from ..scoring import ScoringRubric
from ..state import ExecutionState, PromptNode
from ..synthesis_runner import SynthesisRunner
from ..templating import resolve_batch_name, resolve_prompt_variables, resolve_variables
from ..tool_registry import ToolDefinition, ToolRegistry
from ..validation_manager import ValidationManager

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

        self.config: ConfigSpec = {}
        self.prompts: list[PromptSpec] = []
        self.results: list[dict[str, Any]] = []

        # FFAI wrapper around the default client. Created by _init_client() and
        # used as the template for cloning isolated instances. Individual prompt
        # execution always uses _get_isolated_ffai() so that each call gets its
        # own client state.
        self.ffai: FFAI | None = None

        self.shared_prompt_attr_history: list[Interaction] = []
        self.history_lock = threading.Lock()
        self._response_context = ResponseContext(
            shared_prompt_attr_history=self.shared_prompt_attr_history,
            history_lock=self.history_lock,
        )

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
        self._validation_manager = ValidationManager()
        self._synthesis_runner = SynthesisRunner()
        self._planning_runner = PlanningPhaseRunner()

        # Planning phase state
        self.planning_results: list[dict[str, Any]] = []
        self.has_planning: bool = False
        self.planning_prompts: list[PromptSpec] = []

        self._results_frame: ResultsFrame | None = None

    @property
    def results_frame(self) -> ResultsFrame:
        """Lazily-built ResultsFrame wrapping self.results.

        Invalidated whenever self.results is reassigned.
        """
        if self._results_frame is None:
            all_results = list(self.planning_results) + list(self.results)
            self._results_frame = ResultsFrame(all_results)
        return self._results_frame

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
        documents_data: list[DocumentSpec],
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

    def _get_isolated_ffai(
        self,
        client_name: str | None = None,
        batch_history: list[Interaction] | None = None,
        batch_history_lock: threading.Lock | None = None,
    ) -> FFAI:
        """Create an FFAI instance with isolated client and scoped history.

        Args:
            client_name: Optional name of client from registry.
            batch_history: Optional per-batch history list (isolates from shared history).
            batch_history_lock: Optional lock for the per-batch history.

        Returns:
            FFAI instance with isolated client.

        """
        if client_name and self.client_registry:
            client = self.client_registry.clone(client_name)
        else:
            client = self.client.clone()
        history = (
            batch_history
            if batch_history is not None
            else self._response_context.prompt_attr_history
        )
        lock = batch_history_lock if batch_history_lock is not None else self.history_lock
        return FFAI(
            client,
            shared_prompt_attr_history=history,
            history_lock=lock,
        )

    def _record_to_history(
        self,
        history: list[Interaction],
        lock: threading.Lock | None,
        prompt: PromptSpec,
        response: str | None,
    ) -> None:
        """Record an interaction to a specific history list.

        Args:
            history: The history list to append to.
            lock: Optional lock for thread-safe access.
            prompt: Prompt dictionary.
            response: The response text.

        """
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

        if lock:
            with lock:
                history.append(interaction)
        else:
            history.append(interaction)

    def _validate(self) -> None:
        """Run comprehensive validation on prompts, config, and dependencies.

        Uses OrchestratorValidator to check prompt structure, dependency DAGs,
        template references, condition syntax, client assignments, config values,
        and more. Raises ValueError if any errors are found.
        """
        self._validation_manager.validate(self)

    def _inject_references(self, prompt: PromptSpec) -> str:
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
        self, prompt: PromptSpec, results_by_name: dict[str, dict[str, Any]]
    ) -> tuple[bool, str | None, str | None]:
        """Evaluate a prompt's condition.

        Kept for ManifestOrchestrator backward compatibility.
        New code should use _evaluate_condition_with_trace instead.
        """
        return evaluate_condition(prompt, results_by_name)

    def _evaluate_condition_with_trace(
        self, prompt: PromptSpec, results_by_name: dict[str, dict[str, Any]]
    ) -> tuple[bool, str | None, str | None, str | None]:
        """Evaluate a prompt's condition and return the resolved trace."""
        from ..graph import evaluate_condition_with_trace

        return evaluate_condition_with_trace(prompt, results_by_name)

    def _execute_agent_mode(
        self,
        prompt: PromptSpec,
        ffai: FFAI,
        builder: Any,
        seq_label: str,
        batch_history: list[Interaction] | None = None,
        batch_history_lock: threading.Lock | None = None,
    ) -> dict[str, Any]:
        """Execute a prompt using the agentic tool-call loop.

        Delegates to AgentExecutor with callbacks for orchestrator-specific
        operations (history recording, reference injection, client isolation).

        Args:
            prompt: Prompt dictionary with agent_mode=True.
            ffai: FFAI instance for the execution.
            builder: ResultBuilder already configured with prompt metadata.
            seq_label: Label for logging (e.g. "Sequence 10").
            batch_history: Optional per-batch history list.
            batch_history_lock: Optional lock for the per-batch history.

        Returns:
            Result dictionary with tool call records, or None for fallback.

        """
        history = batch_history if batch_history is not None else self.shared_prompt_attr_history
        lock = batch_history_lock if batch_history_lock is not None else self.history_lock

        def _record_to_batch_history(prompt_dict: dict[str, Any], response: str | None) -> None:
            self._record_to_history(history, lock, prompt_dict, response)

        agent_executor = AgentExecutor(
            tool_registry=self.tool_registry,
            config=self.config,
            record_history_fn=_record_to_batch_history,
        )
        return agent_executor.execute(
            prompt=prompt,
            ffai=ffai,
            builder=builder,
            seq_label=seq_label,
            inject_references_fn=self._inject_references,
            get_isolated_ffai_fn=lambda client_name=None: self._get_isolated_ffai(
                client_name,
                batch_history=batch_history,
                batch_history_lock=batch_history_lock,
            ),
        )

    def _execute_with_retry(
        self,
        prompt: PromptSpec,
        results_by_name: dict[str, dict[str, Any]],
        results_lock: threading.Lock | None = None,
        batch_id: int | None = None,
        batch_name: str | None = None,
        batch_history: list[Interaction] | None = None,
        batch_history_lock: threading.Lock | None = None,
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
            batch_history: Optional per-batch history list (isolates from shared history).
            batch_history_lock: Optional lock for the per-batch history.

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
                should_execute, cond_result, cond_error, cond_trace = (
                    self._evaluate_condition_with_trace(prompt, results_by_name)
                )
        else:
            should_execute, cond_result, cond_error, cond_trace = (
                self._evaluate_condition_with_trace(prompt, results_by_name)
            )

        builder.with_condition_result(cond_result, cond_error)
        builder.with_condition_trace(cond_trace)

        if not should_execute:
            builder.as_skipped(cond_result, cond_error)
            logger.info(f"{seq_label} skipped: condition evaluated to False")
            return builder.build_dict()

        ffai = self._get_isolated_ffai(
            client_name,
            batch_history=batch_history,
            batch_history_lock=batch_history_lock,
        )

        if prompt.get("agent_mode") and self.tool_registry:
            agent_result = self._execute_agent_mode(
                prompt,
                ffai,
                builder,
                seq_label,
                batch_history=batch_history,
                batch_history_lock=batch_history_lock,
            )
            if agent_result is not None:
                return agent_result

        if prompt.get("agent_mode") and not self.tool_registry:
            logger.warning(
                f"{seq_label} has agent_mode=true but no tool registry initialized; "
                "falling back to single-shot execution. Add a 'tools' sheet or "
                "tools.yaml to the workbook/manifest."
            )

        telemetry = get_telemetry_manager()
        prompt_span_name = "orchestrator.prompt"

        with telemetry.span(prompt_span_name) as prompt_span:
            prompt_span.set_attribute("prompt.name", prompt.get("prompt_name", ""))
            prompt_span.set_attribute("prompt.sequence", prompt["sequence"])
            if batch_id is not None:
                prompt_span.set_attribute("prompt.batch_id", batch_id)

            for attempt in range(1, max_retries + 1):
                builder.with_attempts(attempt)

                try:
                    logger.info(
                        f"Executing {seq_label} (attempt {attempt})"
                        + (f" with client '{client_name}'" if client_name else "")
                    )

                    injected_prompt = self._inject_references(prompt)

                    call_start = time.monotonic()
                    result = ffai.generate_response(
                        prompt=injected_prompt,
                        prompt_name=prompt.get("prompt_name"),
                        history=prompt.get("history"),
                        model=self.config.get("model"),
                        temperature=self.config.get("temperature"),
                        max_tokens=self.config.get("max_tokens"),
                    )
                    call_duration_ms = (time.monotonic() - call_start) * 1000

                    builder.with_resolved_prompt(result.resolved_prompt or injected_prompt)
                    builder.with_response(result.response)
                    builder.with_duration(call_duration_ms)

                    if result.usage:
                        builder.with_usage(
                            result.usage.input_tokens,
                            result.usage.output_tokens,
                            result.usage.total_tokens,
                        )
                        prompt_span.set_attribute("prompt.input_tokens", result.usage.input_tokens)
                        prompt_span.set_attribute(
                            "prompt.output_tokens", result.usage.output_tokens
                        )
                        prompt_span.set_attribute("prompt.total_tokens", result.usage.total_tokens)
                    builder.with_cost(result.cost_usd)
                    prompt_span.set_attribute("prompt.cost_usd", result.cost_usd)
                    prompt_span.set_attribute("prompt.duration_ms", call_duration_ms)
                    prompt_span.set_attribute("prompt.status", "success")
                    prompt_span.set_attribute("prompt.attempts", attempt)

                    logger.info(f"{seq_label} succeeded")
                    break

                except Exception as e:
                    builder.with_error(str(e), attempt)
                    logger.warning(f"{seq_label} failed (attempt {attempt}): {e}")

                    if attempt == max_retries:
                        logger.error(f"{seq_label} failed after {max_retries} attempts")
                        prompt_span.set_attribute("prompt.status", "failed")
                        prompt_span.set_attribute("prompt.error", str(e)[:500])
                    else:
                        delay = retry_base_delay * (2 ** (attempt - 1))
                        logger.info(f"Retrying {seq_label} in {delay:.1f}s")
                        time.sleep(delay)

        return builder.build_dict()

    def _execute_prompt_core(
        self,
        prompt: PromptSpec,
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

    def _execute_prompt_isolated(self, prompt: PromptSpec, state: ExecutionState) -> dict[str, Any]:
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
        prompt: PromptSpec,
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

    def _resolve_variables(self, text: str | None, data_row: dict[str, Any]) -> str | None:
        """Replace {{variable}} placeholders with values from data row."""
        return resolve_variables(text, data_row)

    def _resolve_prompt_variables(self, prompt: PromptSpec, data_row: dict[str, Any]) -> PromptSpec:
        """Resolve all {{variable}} placeholders in a prompt."""
        return resolve_prompt_variables(prompt, data_row)

    def _resolve_batch_name(self, data_row: dict[str, Any], batch_id: int) -> str:
        """Generate batch name from data row or default."""
        return resolve_batch_name(data_row, batch_id)

    def _execute_single_batch(
        self,
        batch_id: int,
        data_row: dict[str, Any],
        batch_name: str,
        batch_history: list[Interaction] | None = None,
        batch_history_lock: threading.Lock | None = None,
    ) -> list[dict[str, Any]]:
        """Execute all prompts for a single batch with resolved variables.

        Args:
            batch_id: Batch ID number.
            data_row: Variable values for this batch.
            batch_name: Name for this batch.
            batch_history: Optional per-batch history list.
            batch_history_lock: Optional lock for the per-batch history.

        Returns:
            List of result dictionaries.

        """
        results: list[dict[str, Any]] = []
        results_by_name: dict[str, dict[str, Any]] = {}

        for prompt in self.prompts:
            resolved_prompt = self._resolve_prompt_variables(prompt, data_row)

            result = self._execute_prompt_with_batch(
                resolved_prompt,
                batch_id,
                batch_name,
                results_by_name,
                batch_history=batch_history,
                batch_history_lock=batch_history_lock,
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
        prompt: PromptSpec,
        batch_id: int,
        batch_name: str,
        results_by_name: dict[str, dict[str, Any]] | None = None,
        batch_history: list[Interaction] | None = None,
        batch_history_lock: threading.Lock | None = None,
    ) -> dict[str, Any]:
        """Execute a single prompt and tag with batch info.

        Args:
            prompt: Prompt dictionary.
            batch_id: Batch ID number.
            batch_name: Batch name.
            results_by_name: Optional results indexed by prompt_name.
            batch_history: Optional per-batch history list.
            batch_history_lock: Optional lock for the per-batch history.

        Returns:
            Result dictionary with batch info.

        """
        return self._execute_with_retry(
            prompt,
            results_by_name or {},
            batch_id=batch_id,
            batch_name=batch_name,
            batch_history=batch_history,
            batch_history_lock=batch_history_lock,
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
        return self._synthesis_runner.resolve_evaluation_strategy(self)

    def _aggregate_scores(self) -> None:
        """Extract scores from batch results and compute composites."""
        self._synthesis_runner.aggregate_scores(self)

    def _execute_synthesis(self) -> None:
        """Execute synthesis prompts with cross-row batch context."""
        self._synthesis_runner.execute_synthesis(self)

    def _detect_planning_prompts(self) -> None:
        """Detect and separate planning-phase prompts from execution prompts.

        Called during _load_source() in subclasses after prompts are loaded.
        Splits self.prompts into self.planning_prompts (phase=planning) and
        self.prompts (phase=execution only).
        """
        self._planning_runner.detect(self)

    @staticmethod
    def _resolve_shared_document(
        document_path: str,
        reference_name: str | None = None,
    ) -> DocumentSpec:
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

        discovered_docs: list[DocumentSpec] = []

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
        self._planning_runner.execute(self)

    def _parse_generated_artifacts(
        self,
        artifacts: list,
        parser: Any,
        planning_config: Any,
    ) -> None:
        """Parse, validate, and inject generated artifacts from planning phase."""
        self._planning_runner.parse_and_inject(self, artifacts, parser, planning_config)

    def _validate_pre_planning(self) -> None:
        """Run validation checks that can be performed before planning phase.

        Skips scoring source_prompt checks and synthesis source_prompts checks
        since generated prompts don't exist yet.
        """
        self._validation_manager.validate_pre_planning(self)

    def _validate_post_planning(self) -> None:
        """Run validation checks after planning phase, including generated artifacts.

        Validates scoring source_prompt mappings and synthesis source_prompts
        now that generated prompts are available.
        """
        self._validation_manager.validate_post_planning(self)

    def run(self) -> str:
        """Initialize, validate, execute prompts, and write results.

        Returns:
            Output identifier (sheet name or parquet path).

        """
        telemetry = get_telemetry_manager()
        run_span_name = "orchestrator.run"

        with telemetry.span(run_span_name) as run_span:
            run_span.set_attribute("orchestrator.name", self.config.get("name", ""))
            run_span.set_attribute("orchestrator.client_type", self.config.get("client_type", ""))
            run_span.set_attribute("orchestrator.batch_mode", self.is_batch_mode)

            self._load_source()

            if self.has_planning:
                with telemetry.span("orchestrator.planning") as planning_span:
                    planning_span.set_attribute(
                        "planning.prompt_count",
                        len([p for p in self.prompts if p.get("phase") == "planning"]),
                    )
                    self._validate_pre_planning()
                    self._init_client()
                    self._execute_planning_phase()
                    self._validate_post_planning()
            else:
                self._validate()
                self._init_client()

            with telemetry.span("orchestrator.execution") as exec_span:
                mode = "sequential"
                if self.is_batch_mode:
                    mode = "batch_parallel" if self.concurrency > 1 else "batch"
                elif self.concurrency > 1:
                    mode = "parallel"
                exec_span.set_attribute("execution.mode", mode)

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
                self._results_frame = None

            if self.has_scoring:
                self._aggregate_scores()

            if self.has_synthesis:
                with telemetry.span("orchestrator.synthesis") as synth_span:
                    synth_count = len(list(getattr(self, "synthesis_prompts", []) or []))
                    synth_span.set_attribute("synthesis.prompt_count", synth_count)
                    self._execute_synthesis()

            try:
                output = self._write_results(self.results)
            except Exception:
                logger.error("Failed to write results", exc_info=True)
                run_span.set_attribute("run.write_error", True)
                raise

            summary = self.get_summary()
            if "total_prompts" in summary:
                run_span.set_attribute("run.total_prompts", summary["total_prompts"])
                run_span.set_attribute("run.successful", summary["successful"])
                run_span.set_attribute("run.failed", summary["failed"])
            if "tokens" in summary:
                run_span.set_attribute("run.total_tokens", summary["tokens"]["total"])
            if "cost_usd" in summary:
                run_span.set_attribute("run.cost_usd", summary["cost_usd"])

            logger.info(f"Orchestration complete. Results in: {output}")
            return output

    def get_summary(self) -> dict[str, Any]:
        """Get execution summary.

        Returns:
            Dictionary with execution statistics.

        """
        if not self.results:
            return {"status": "not_run"}

        return ResultsFrame(self.results).summary(
            is_batch_mode=self.is_batch_mode,
            evaluation_strategy=self.evaluation_strategy,
            has_scoring=self.has_scoring,
            has_synthesis=self.has_synthesis,
        )
