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
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from ..config import get_config
from ..FFAIClientBase import FFAIClientBase
from .base import OrchestratorBase
from .workbook_parser import WorkbookParser

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
        tools = self.builder.load_tools()

        manifest_name_value = config.get("name", workbook_name)
        manifest_description = config.get("description", "")

        self._write_manifest_yaml(
            manifest_path,
            name=manifest_name_value,
            description=manifest_description,
            has_data=len(data) > 0,
            has_clients=len(clients) > 0,
            has_documents=len(documents) > 0,
            has_tools=len(tools) > 0,
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
        if tools:
            self._write_tools_yaml(manifest_path, tools)

        logger.info(f"Manifest exported to: {manifest_path}")
        return str(manifest_path)

    def _write_manifest_yaml(
        self,
        manifest_path: Path,
        name: str,
        description: str,
        has_data: bool,
        has_clients: bool,
        has_documents: bool,
        has_tools: bool = False,
        prompt_count: int = 0,
    ) -> None:
        """Write the main manifest metadata file."""
        manifest_data = {
            "name": name,
            "description": description,
            "version": MANIFEST_VERSION,
            "source_workbook": str(Path(self.workbook_path).resolve()),
            "exported_at": datetime.now().isoformat(),
            "has_data": has_data,
            "has_clients": has_clients,
            "has_documents": has_documents,
            "has_tools": has_tools,
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
                "notes": prompt.get("notes"),
                "client": prompt.get("client"),
                "condition": prompt.get("condition"),
                "references": prompt.get("references") or [],
                "semantic_query": prompt.get("semantic_query"),
                "semantic_filter": prompt.get("semantic_filter"),
                "query_expansion": prompt.get("query_expansion"),
                "rerank": prompt.get("rerank"),
            }
            if prompt.get("agent_mode"):
                prompt_entry["agent_mode"] = True
                prompt_entry["tools"] = prompt.get("tools") or []
                if prompt.get("max_tool_rounds"):
                    prompt_entry["max_tool_rounds"] = prompt.get("max_tool_rounds")
                if prompt.get("validation_prompt"):
                    prompt_entry["validation_prompt"] = prompt.get("validation_prompt")
                if prompt.get("max_validation_retries"):
                    prompt_entry["max_validation_retries"] = prompt.get("max_validation_retries")
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

    def _write_tools_yaml(self, manifest_path: Path, tools: list[dict[str, Any]]) -> None:
        """Write tool definitions to YAML file."""
        tools_yaml = {"tools": tools}
        with open(manifest_path / "tools.yaml", "w", encoding="utf-8") as f:
            yaml.dump(tools_yaml, f, default_flow_style=False, sort_keys=False)


class ManifestOrchestrator(OrchestratorBase):
    """Execute prompts from manifest folder and output to parquet.

    Usage:
        from src.Clients.FFMistralSmall import FFMistralSmall

        from src.orchestrator import ManifestOrchestrator

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
        super().__init__(
            client=client,
            config_overrides=config_overrides,
            concurrency=concurrency,
            progress_callback=progress_callback,
        )
        self._manifest_dir = Path(manifest_dir)
        self._manifest_meta: dict[str, Any] = {}
        self._source_workbook: str = ""

    @property
    def source_path(self) -> str:
        """Return the manifest directory path."""
        return str(self._manifest_dir)

    @property
    def manifest_meta(self) -> dict[str, Any]:
        """Return manifest metadata (backward compatibility)."""
        return self._manifest_meta

    @manifest_meta.setter
    def manifest_meta(self, value: dict[str, Any]) -> None:
        """Set manifest metadata (backward compatibility)."""
        self._manifest_meta = value

    @property
    def source_workbook(self) -> str:
        """Return the source workbook path (backward compatibility)."""
        return self._source_workbook

    @source_workbook.setter
    def source_workbook(self, value: str) -> None:
        """Set the source workbook path (backward compatibility)."""
        self._source_workbook = value

    def _get_cache_dir(self) -> str:
        """Get directory for document caching."""
        return self.config.get(
            "document_cache_dir",
            str(self._manifest_dir / "doc_cache"),
        )

    def _evaluate_condition(
        self, prompt: dict[str, Any], results_by_name: dict[str, dict[str, Any]]
    ) -> tuple[bool, str | None, str | None]:
        """Evaluate a prompt's condition (override to return string result for backward compatibility).

        Returns:
            Tuple of (should_execute, condition_result_string, condition_error)

        """
        should_execute, result, error = super()._evaluate_condition(prompt, results_by_name)
        return should_execute, str(result) if result is not None else None, error

    def _init_client_registry(self, clients_data: list[dict[str, Any]] | None = None) -> None:
        """Initialize client registry from manifest (backward compatibility wrapper).

        Args:
            clients_data: Optional clients data (loaded from YAML if not provided).

        """
        if clients_data is None and self._manifest_meta.get("has_clients"):
            clients_yaml = self._load_yaml_file("clients.yaml")
            clients_data = clients_yaml.get("clients", [])
        if clients_data:
            super()._init_client_registry(clients_data)

    def _init_documents(
        self,
        documents_data: list[dict[str, Any]] | None = None,
        workbook_dir: str | None = None,
    ) -> None:
        """Initialize documents from manifest (backward compatibility wrapper).

        Args:
            documents_data: Optional documents data (loaded from YAML if not provided).
            workbook_dir: Optional workbook directory.

        """
        if documents_data is None and self._manifest_meta.get("has_documents"):
            documents_yaml = self._load_yaml_file("documents.yaml")
            documents_data = documents_yaml.get("documents", [])
        if documents_data:
            if workbook_dir is None:
                workbook_dir = str(
                    Path(self._source_workbook).parent
                    if self._source_workbook
                    else Path(self._manifest_dir)
                )
            super()._init_documents(documents_data, workbook_dir)

    def _load_source(self) -> None:
        """Load prompts and config from manifest YAML files."""
        manifest_data = self._load_yaml_file("manifest.yaml")
        self._manifest_meta = manifest_data
        self._source_workbook = manifest_data.get("source_workbook", "")

        config_data = self._load_yaml_file("config.yaml")
        self.config = {**config_data, **self.config_overrides}

        self.prompts = self._load_yaml_file("prompts.yaml").get("prompts", [])

        if self._manifest_meta.get("has_data"):
            data_yaml = self._load_yaml_file("data.yaml")
            self.batch_data = data_yaml.get("batches", [])
            self.is_batch_mode = len(self.batch_data) > 0

        if self._manifest_meta.get("has_clients"):
            clients_yaml = self._load_yaml_file("clients.yaml")
            clients_data = clients_yaml.get("clients", [])
            if clients_data:
                self._init_client_registry(clients_data)

        if self._manifest_meta.get("has_documents"):
            documents_yaml = self._load_yaml_file("documents.yaml")
            documents_data = documents_yaml.get("documents", [])
            if documents_data:
                workbook_dir = str(
                    Path(self._source_workbook).parent
                    if self._source_workbook
                    else Path(self._manifest_dir)
                )
                self._init_documents(documents_data, workbook_dir)

        if self._manifest_meta.get("has_tools"):
            tools_yaml = self._load_yaml_file("tools.yaml")
            tools_data = tools_yaml.get("tools", [])
            if tools_data:
                self._init_tools(tools_data)

        logger.info(
            f"Manifest loaded: {len(self.prompts)} prompts, batch_mode={self.is_batch_mode}"
        )

    def _load_manifest(self) -> None:
        """Load manifest files (backward compatibility alias for _load_source)."""
        self._load_source()

    def _load_yaml_file(self, filename: str) -> dict[str, Any]:
        """Load a YAML file from the manifest directory.

        Args:
            filename: Name of the YAML file to load.

        Returns:
            Parsed YAML data or empty dict.

        """
        filepath = self._manifest_dir / filename
        if not filepath.exists():
            return {}
        with open(filepath, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _get_manifest_name(self) -> str:
        """Get manifest name from manifest.yaml or directory name.

        Returns:
            Manifest name for use in output paths.

        """
        manifest_data = self._load_yaml_file("manifest.yaml")
        if manifest_data.get("name"):
            name = manifest_data["name"]
            # Sanitize for filesystem
            return name.lower().replace(" ", "_").replace("-", "_")

        # Fall back to directory name (remove manifest_ prefix if present)
        dir_name = self._manifest_dir.name
        if dir_name.startswith("manifest_"):
            return dir_name[9:]
        return dir_name

    def _get_output_path(self) -> Path:
        """Generate output path: outputs/<manifest_name>/<timestamp>.parquet"""
        config = get_config()
        base_output_dir = Path(config.paths.output_dir)

        manifest_name = self._get_manifest_name()
        output_dir = base_output_dir / manifest_name
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return output_dir / f"{timestamp}.parquet"

    def _get_output_prompts(self) -> list[str]:
        """Get list of prompts to extract from manifest.yaml.

        Returns:
            List of prompt names to extract, or empty list for auto-detection.

        """
        manifest_data = self._load_yaml_file("manifest.yaml")
        return manifest_data.get("output_prompts", [])

    def _write_results(self, results: list[dict[str, Any]]) -> str:
        """Write results to a parquet file.

        Args:
            results: List of result dictionaries.

        Returns:
            Path to the created parquet file.

        """
        output_path = self._get_output_path()
        manifest_name = self._get_manifest_name()
        output_prompts = self._get_output_prompts()

        rows = []
        for r in results:
            row = {
                "batch_id": r.get("batch_id"),
                "batch_name": r.get("batch_name"),
                "sequence": r["sequence"],
                "prompt_name": r.get("prompt_name"),
                "prompt": r.get("prompt"),
                "resolved_prompt": r.get("resolved_prompt"),
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
                "agent_mode": r.get("agent_mode"),
                "tool_calls": json.dumps(r.get("tool_calls")) if r.get("tool_calls") else None,
                "total_rounds": r.get("total_rounds"),
                "total_llm_calls": r.get("total_llm_calls"),
                "validation_passed": r.get("validation_passed"),
                "validation_attempts": r.get("validation_attempts"),
                "validation_critique": r.get("validation_critique"),
            }
            rows.append(row)

        df = pl.DataFrame(rows)

        import pyarrow.parquet as pq

        # Add manifest metadata as parquet key-value metadata
        manifest_meta = {
            b"manifest_name": manifest_name.encode("utf-8"),
            b"output_prompts": json.dumps(output_prompts).encode("utf-8"),
            b"source_workbook": (self._source_workbook or "").encode("utf-8"),
        }

        # Convert to Arrow table and add metadata
        table = df.to_arrow()
        existing_meta = dict(table.schema.metadata or {})
        existing_meta.update(manifest_meta)
        table = table.replace_schema_metadata(existing_meta)

        pq.write_table(table, output_path)

        logger.info(f"Results written to parquet: {output_path}")
        return str(output_path)

    def _write_parquet(self, results: list[dict[str, Any]]) -> str:
        """Write results to a parquet file (backward compatibility wrapper).

        Args:
            results: List of result dictionaries.

        Returns:
            Path to the created parquet file.

        """
        return self._write_results(results)

    def get_summary(self) -> dict[str, Any]:
        """Get execution summary.

        Returns:
            Dictionary with execution statistics.

        """
        summary = super().get_summary()
        if summary.get("status") != "not_run":
            summary["manifest_dir"] = str(self._manifest_dir)
            summary["manifest_name"] = self._get_manifest_name()
            summary["source_workbook"] = self._source_workbook
            summary["output_prompts"] = self._get_output_prompts()
        return summary

    @staticmethod
    def get_manifest_metadata(parquet_path: str) -> dict[str, Any]:
        """Extract manifest metadata from a parquet file.

        Args:
            parquet_path: Path to the parquet file.

        Returns:
            Dictionary with manifest metadata (manifest_name, output_prompts, etc.)

        """
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(parquet_path)
        metadata = parquet_file.schema_arrow.metadata or {}

        return {
            "manifest_name": metadata.get(b"manifest_name", b"").decode("utf-8"),
            "output_prompts": json.loads(metadata.get(b"output_prompts", b"[]")),
            "source_workbook": metadata.get(b"source_workbook", b"").decode("utf-8"),
        }
