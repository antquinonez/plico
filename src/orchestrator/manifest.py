# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Manifest-based orchestration for workbook conversion and execution.

This module provides two main classes:
- WorkbookManifestExporter: Convert Excel workbook to YAML manifest folder
- ManifestOrchestrator: Execute prompts from manifest and output to parquet

The manifest approach enables:
- Version control of prompt configurations
- Separation of workbook parsing from execution
- Efficient parquet output for analytics
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl
import yaml

from ..config import get_config
from ..FFAI import FFAI
from ..FFAIClientBase import FFAIClientBase
from .client_registry import ClientRegistry
from .condition_evaluator import ConditionEvaluator
from .document_processor import DocumentProcessor
from .document_registry import DocumentRegistry
from .workbook_parser import WorkbookParser

if TYPE_CHECKING:
    from ..RAG import FFRAGClient

logger = logging.getLogger(__name__)

MANIFEST_VERSION = "1.0"


class WorkbookManifestExporter:
    """Export Excel workbook to a YAML manifest folder structure.

    Usage:
        exporter = WorkbookManifestExporter("my_prompts.xlsx")
        manifest_path = exporter.export()
        print(f"Manifest created at: {manifest_path}")
    """

    def __init__(self, workbook_path: str) -> None:
        """Initialize the exporter.

        Args:
            workbook_path: Path to the Excel workbook file.

        """
        self.workbook_path = workbook_path
        self.builder = WorkbookParser(workbook_path)
        self._config = get_config()

    def export(self, manifest_dir: str | None = None) -> str:
        """Export workbook to manifest folder.

        Args:
            manifest_dir: Optional override for manifest directory.
                         Defaults to config paths.manifest_dir.

        Returns:
            Path to the created manifest folder.

        """
        if manifest_dir is None:
            manifest_dir = self._config.paths.manifest_dir

        workbook_name = Path(self.workbook_path).stem
        manifest_name = f"manifest_{workbook_name}"
        manifest_path = Path(manifest_dir) / manifest_name

        manifest_path.mkdir(parents=True, exist_ok=True)

        self.builder.validate_workbook()

        config = self.builder.load_config()
        prompts = self.builder.load_prompts()
        data = self.builder.load_data()
        clients = self.builder.load_clients()
        documents = self.builder.load_documents()

        self._write_manifest_yaml(
            manifest_path,
            has_data=len(data) > 0,
            has_clients=len(clients) > 0,
            has_documents=len(documents) > 0,
            prompt_count=len(prompts),
        )
        self._write_config_yaml(manifest_path, config)
        self._write_prompts_yaml(manifest_path, prompts)
        if data:
            self._write_data_yaml(manifest_path, data)
        if clients:
            self._write_clients_yaml(manifest_path, clients)
        if documents:
            self._write_documents_yaml(manifest_path, documents)

        logger.info(f"Manifest exported to: {manifest_path}")
        return str(manifest_path)

    def _write_manifest_yaml(
        self,
        manifest_path: Path,
        has_data: bool,
        has_clients: bool,
        has_documents: bool,
        prompt_count: int,
    ) -> None:
        """Write the main manifest metadata file."""
        manifest_data = {
            "version": MANIFEST_VERSION,
            "source_workbook": str(Path(self.workbook_path).resolve()),
            "exported_at": datetime.now().isoformat(),
            "has_data": has_data,
            "has_clients": has_clients,
            "has_documents": has_documents,
            "prompt_count": prompt_count,
        }

        with open(manifest_path / "manifest.yaml", "w", encoding="utf-8") as f:
            yaml.dump(manifest_data, f, default_flow_style=False, sort_keys=False)

    def _write_config_yaml(self, manifest_path: Path, config: dict[str, Any]) -> None:
        """Write configuration to YAML file."""
        with open(manifest_path / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    def _write_prompts_yaml(self, manifest_path: Path, prompts: list[dict[str, Any]]) -> None:
        """Write prompts to YAML file."""
        prompts_data = {"prompts": []}

        for prompt in prompts:
            prompt_entry = {
                "sequence": prompt.get("sequence"),
                "prompt_name": prompt.get("prompt_name"),
                "prompt": prompt.get("prompt"),
                "history": prompt.get("history") or [],
                "client": prompt.get("client"),
                "condition": prompt.get("condition"),
                "references": prompt.get("references") or [],
                "semantic_query": prompt.get("semantic_query"),
                "semantic_filter": prompt.get("semantic_filter"),
                "query_expansion": prompt.get("query_expansion"),
                "rerank": prompt.get("rerank"),
            }
            prompts_data["prompts"].append(prompt_entry)

        with open(manifest_path / "prompts.yaml", "w", encoding="utf-8") as f:
            yaml.dump(prompts_data, f, default_flow_style=False, sort_keys=False)

    def _write_data_yaml(self, manifest_path: Path, data: list[dict[str, Any]]) -> None:
        """Write batch data to YAML file."""
        batches = []
        for row in data:
            batch_entry = {k: v for k, v in row.items() if not k.startswith("_")}
            batches.append(batch_entry)

        data_yaml = {"batches": batches}
        with open(manifest_path / "data.yaml", "w", encoding="utf-8") as f:
            yaml.dump(data_yaml, f, default_flow_style=False, sort_keys=False)

    def _write_clients_yaml(self, manifest_path: Path, clients: list[dict[str, Any]]) -> None:
        """Write client configurations to YAML file."""
        clients_yaml = {"clients": clients}
        with open(manifest_path / "clients.yaml", "w", encoding="utf-8") as f:
            yaml.dump(clients_yaml, f, default_flow_style=False, sort_keys=False)

    def _write_documents_yaml(self, manifest_path: Path, documents: list[dict[str, Any]]) -> None:
        """Write document references to YAML file."""
        docs_yaml = {"documents": documents}
        with open(manifest_path / "documents.yaml", "w", encoding="utf-8") as f:
            yaml.dump(docs_yaml, f, default_flow_style=False, sort_keys=False)


class ManifestOrchestrator:
    """Execute prompts from manifest folder and output to parquet.

    Usage:
        from src.Clients.FFMistralSmall import FFMistralSmall

        client = FFMistralSmall(api_key="...")
        orchestrator = ManifestOrchestrator(
            manifest_dir="./manifests/manifest_my_prompts",
            client=client
        )
        parquet_path = orchestrator.run()
    """

    def __init__(
        self,
        manifest_dir: str,
        client: FFAIClientBase,
        config_overrides: dict[str, Any] | None = None,
        concurrency: int | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> None:
        """Initialize the ManifestOrchestrator.

        Args:
            manifest_dir: Path to the manifest folder.
            client: Default AI client for prompt execution.
            config_overrides: Optional config overrides.
            concurrency: Maximum concurrent API calls.
            progress_callback: Optional callback for progress updates.

        """
        self.manifest_dir = Path(manifest_dir)
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
        self.ffai: FFAI | None = None
        self.manifest_meta: dict[str, Any] = {}

        self.shared_prompt_attr_history: list[dict[str, Any]] = []
        self.history_lock = threading.Lock()

        self.batch_data: list[dict[str, Any]] = []
        self.is_batch_mode: bool = False
        self.client_registry: ClientRegistry | None = None
        self.has_multi_client: bool = False
        self.document_processor: DocumentProcessor | None = None
        self.document_registry: DocumentRegistry | None = None
        self.has_documents: bool = False
        self.source_workbook: str = ""

    def _load_yaml_file(self, filename: str) -> dict[str, Any]:
        """Load a YAML file from the manifest directory."""
        filepath = self.manifest_dir / filename
        if not filepath.exists():
            return {}
        with open(filepath, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_manifest(self) -> None:
        """Load all manifest files."""
        manifest_data = self._load_yaml_file("manifest.yaml")
        self.manifest_meta = manifest_data
        self.source_workbook = manifest_data.get("source_workbook", "")

        config_data = self._load_yaml_file("config.yaml")
        self.config = {**config_data, **self.config_overrides}

        prompts_data = self._load_yaml_file("prompts.yaml")
        self.prompts = prompts_data.get("prompts", [])

        if self.manifest_meta.get("has_data"):
            data_yaml = self._load_yaml_file("data.yaml")
            self.batch_data = data_yaml.get("batches", [])
            self.is_batch_mode = len(self.batch_data) > 0

        logger.info(
            f"Manifest loaded: {len(self.prompts)} prompts, batch_mode={self.is_batch_mode}"
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
        if not self.manifest_meta.get("has_clients"):
            return

        clients_yaml = self._load_yaml_file("clients.yaml")
        clients_data = clients_yaml.get("clients", [])

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
        if not self.manifest_meta.get("has_documents"):
            return

        documents_yaml = self._load_yaml_file("documents.yaml")
        documents_data = documents_yaml.get("documents", [])

        if documents_data:
            cache_dir = self.config.get(
                "document_cache_dir",
                str(self.manifest_dir / "doc_cache"),
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
                        logger.info("RAG disabled: chromadb not available")
                except Exception as e:
                    logger.warning(f"Failed to initialize RAG client: {e}")

            self.document_processor = DocumentProcessor(
                cache_dir=cache_dir,
                api_key=os.environ.get("LLAMACLOUD_TOKEN"),
                rag_client=rag_client,
            )

            workbook_dir = (
                Path(self.source_workbook).parent if self.source_workbook else self.manifest_dir
            )

            self.document_registry = DocumentRegistry(
                documents=documents_data,
                processor=self.document_processor,
                workbook_dir=str(workbook_dir),
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

    def _inject_references(self, prompt: dict[str, Any]) -> str:
        """Inject document references or semantic search results into a prompt."""
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
        """Parse a boolean override value from string."""
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
            "semantic_filter": prompt.get("semantic_filter"),
            "query_expansion": prompt.get("query_expansion"),
            "rerank": prompt.get("rerank"),
        }

    def _evaluate_condition(
        self, prompt: dict[str, Any], results_by_name: dict[str, dict[str, Any]]
    ) -> tuple[bool, str | None, str | None]:
        """Evaluate a prompt's condition.

        Returns:
            Tuple of (should_execute, condition_result, condition_error)

        """
        condition = prompt.get("condition")

        if not condition or not str(condition).strip():
            return True, None, None

        evaluator = ConditionEvaluator(results_by_name)
        result, error = evaluator.evaluate(str(condition))

        return result, str(result) if result is not None else None, error

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

    def _get_output_path(self) -> Path:
        """Generate the output parquet file path."""
        config = get_config()
        output_dir = Path(config.paths.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        workbook_name = Path(self.source_workbook).stem if self.source_workbook else "results"
        output_name = f"{timestamp}_{workbook_name}.parquet"

        return output_dir / output_name

    def _write_parquet(self, results: list[dict[str, Any]]) -> str:
        """Write results to a parquet file.

        Args:
            results: List of result dictionaries.

        Returns:
            Path to the created parquet file.

        """
        output_path = self._get_output_path()

        rows = []
        for r in results:
            row = {
                "batch_id": r.get("batch_id"),
                "batch_name": r.get("batch_name"),
                "sequence": r["sequence"],
                "prompt_name": r.get("prompt_name"),
                "prompt": r.get("prompt"),
                "history": json.dumps(r.get("history")) if r.get("history") else None,
                "client": r.get("client"),
                "condition": r.get("condition"),
                "condition_result": r.get("condition_result"),
                "condition_error": r.get("condition_error"),
                "response": r.get("response"),
                "status": r["status"],
                "attempts": r["attempts"],
                "error": r.get("error"),
                "references": json.dumps(r.get("references")) if r.get("references") else None,
                "semantic_query": r.get("semantic_query"),
                "semantic_filter": r.get("semantic_filter"),
                "query_expansion": r.get("query_expansion"),
                "rerank": r.get("rerank"),
            }
            rows.append(row)

        df = pl.DataFrame(rows)
        df.write_parquet(output_path)

        logger.info(f"Results written to parquet: {output_path}")
        return str(output_path)

    def execute(self) -> list[dict[str, Any]]:
        """Execute all prompts in sequence with dependency-aware ordering."""
        self.results = []
        results_by_name: dict[str, dict[str, Any]] = {}
        total = len(self.prompts)

        sorted_prompts = sorted(self.prompts, key=lambda p: p["sequence"])

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
        from dataclasses import dataclass, field

        @dataclass
        class PromptNode:
            sequence: int
            prompt: dict[str, Any]
            dependencies: set[int] = field(default_factory=set)
            level: int = 0

        @dataclass
        class ExecutionState:
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

        def execute_prompt_isolated(
            prompt: dict[str, Any], state: ExecutionState
        ) -> dict[str, Any]:
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

        logger.info(f"Starting parallel execution with concurrency={self.concurrency}")

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            while len(state.completed) < total:
                ready = []
                for seq, node in nodes.items():
                    if seq in state.completed or seq in state.in_progress:
                        continue
                    if node.dependencies.issubset(state.completed):
                        ready.append(node)
                ready.sort(key=lambda n: (n.level, n.sequence))

                if not ready and not state.in_progress:
                    logger.error("Deadlock detected: no ready prompts and none in progress")
                    break

                futures = {}
                for node in ready:
                    if len(state.in_progress) >= self.concurrency:
                        break
                    state.in_progress.add(node.sequence)
                    future = executor.submit(execute_prompt_isolated, node.prompt, state)
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
                                    "semantic_filter": nodes[seq].prompt.get("semantic_filter"),
                                    "query_expansion": nodes[seq].prompt.get("query_expansion"),
                                    "rerank": nodes[seq].prompt.get("rerank"),
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

    def _resolve_variables(self, text: str, data_row: dict[str, Any]) -> str:
        """Replace {{variable}} placeholders with values from data row."""
        import re

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
        import re

        if "batch_name" in data_row and data_row["batch_name"]:
            name = self._resolve_variables(str(data_row["batch_name"]), data_row)
            return re.sub(r"[^\w\-]", "_", name)[:50]
        return f"batch_{batch_id}"

    def execute_batch(self) -> list[dict[str, Any]]:
        """Execute all prompts for each batch row sequentially."""
        self.results = []
        total_batches = len(self.batch_data)
        total_prompts = len(self.prompts)
        total = total_batches * total_prompts

        for batch_idx, data_row in enumerate(self.batch_data, start=1):
            batch_name = self._resolve_batch_name(data_row, batch_idx)
            logger.info(f"Starting batch {batch_idx}/{total_batches}: {batch_name}")

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
                    "semantic_filter": resolved_prompt.get("semantic_filter"),
                    "query_expansion": resolved_prompt.get("query_expansion"),
                    "rerank": resolved_prompt.get("rerank"),
                }

                should_execute, cond_result, cond_error = self._evaluate_condition(
                    resolved_prompt, batch_results_by_name
                )
                result["condition_result"] = cond_result
                result["condition_error"] = cond_error

                if not should_execute:
                    result["status"] = "skipped"
                    result["attempts"] = 0
                    self.results.append(result)
                    if result.get("prompt_name"):
                        batch_results_by_name[result["prompt_name"]] = result
                    continue

                client_name = resolved_prompt.get("client")
                ffai = self._get_isolated_ffai(client_name)

                for attempt in range(1, max_retries + 1):
                    result["attempts"] = attempt
                    try:
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

                self.results.append(result)
                if result["status"] == "success" and result.get("prompt_name"):
                    batch_results_by_name[result["prompt_name"]] = result

                if result["status"] == "failed":
                    on_error = self.config.get("on_batch_error", "continue")
                    if on_error == "stop":
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
        """Execute batches in parallel with dependency-aware prompt execution within each batch."""
        total_batches = len(self.batch_data)
        total_prompts = len(self.prompts)
        total = total_batches * total_prompts

        results_lock = threading.Lock()
        all_results: list[dict[str, Any]] = []
        success_count = 0
        failed_count = 0

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
                    "semantic_filter": resolved_prompt.get("semantic_filter"),
                    "query_expansion": resolved_prompt.get("query_expansion"),
                    "rerank": resolved_prompt.get("rerank"),
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
                        success_count += sum(1 for r in batch_results if r["status"] == "success")
                        failed_count += sum(1 for r in batch_results if r["status"] == "failed")

                    if self.progress_callback:
                        completed = len(all_results)
                        self.progress_callback(
                            completed,
                            total,
                            success_count,
                            failed_count,
                            current_name=f"batch_{batch_idx}",
                            running=len([f for f in futures if not f.done()]),
                        )

                except Exception as e:
                    logger.error(f"Batch {batch_idx} failed with exception: {e}")

        all_results.sort(key=lambda r: (r["batch_id"], r["sequence"]))
        self.results = all_results

        logger.info(
            f"Parallel batch execution complete: {success_count} succeeded, "
            f"{failed_count} failed across {total_batches} batches"
        )

        return self.results

    def run(self) -> str:
        """Initialize, validate, execute prompts, and write results to parquet.

        Returns:
            Path to the created parquet file.

        """
        self._load_manifest()
        self._validate_dependencies()
        self._init_client()
        self._init_client_registry()
        self._init_documents()

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

        parquet_path = self._write_parquet(self.results)
        logger.info(f"Orchestration complete. Results in: {parquet_path}")
        return parquet_path

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
            "manifest_dir": str(self.manifest_dir),
            "source_workbook": self.source_workbook,
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
