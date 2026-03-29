# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for manifest-based orchestration."""

import os
import sys

import polars as pl
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWorkbookManifestExporter:
    """Tests for WorkbookManifestExporter class."""

    def test_export_creates_manifest_folder(self, temp_workbook_with_data, tmp_path):
        """Test that export creates a manifest folder."""
        from src.orchestrator.manifest import WorkbookManifestExporter

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(temp_workbook_with_data)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        assert os.path.isdir(manifest_path)
        assert "manifest_" in manifest_path

    def test_export_creates_required_files(self, temp_workbook_with_data, tmp_path):
        """Test that export creates all required YAML files."""
        from src.orchestrator.manifest import WorkbookManifestExporter

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(temp_workbook_with_data)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        assert os.path.exists(os.path.join(manifest_path, "manifest.yaml"))
        assert os.path.exists(os.path.join(manifest_path, "config.yaml"))
        assert os.path.exists(os.path.join(manifest_path, "prompts.yaml"))

    def test_export_manifest_yaml_content(self, temp_workbook_with_data, tmp_path):
        """Test manifest.yaml content."""
        from src.orchestrator.manifest import WorkbookManifestExporter

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(temp_workbook_with_data)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        with open(os.path.join(manifest_path, "manifest.yaml"), encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        assert manifest["version"] == "1.0"
        assert "source_workbook" in manifest
        assert "exported_at" in manifest
        assert manifest["prompt_count"] == 3
        assert manifest["has_data"] is False
        assert manifest["has_clients"] is False
        assert manifest["has_documents"] is False

    def test_export_config_yaml_content(self, temp_workbook_with_data, tmp_path):
        """Test config.yaml content."""
        from src.orchestrator.manifest import WorkbookManifestExporter

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(temp_workbook_with_data)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        with open(os.path.join(manifest_path, "config.yaml"), encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert config["model"] == "mistral-small-2503"
        assert config["max_retries"] == 3
        assert config["temperature"] == 0.8

    def test_export_prompts_yaml_content(self, temp_workbook_with_data, tmp_path):
        """Test prompts.yaml content."""
        from src.orchestrator.manifest import WorkbookManifestExporter

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(temp_workbook_with_data)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        with open(os.path.join(manifest_path, "prompts.yaml"), encoding="utf-8") as f:
            prompts_data = yaml.safe_load(f)

        prompts = prompts_data["prompts"]
        assert len(prompts) == 3

        assert prompts[0]["sequence"] == 1
        assert prompts[0]["prompt_name"] == "greeting"
        assert prompts[0]["prompt"] == "Hello, how are you?"

        assert prompts[2]["sequence"] == 3
        assert prompts[2]["history"] == ["math", "greeting"]

    def test_export_with_batch_data(self, temp_workbook_with_batch_data, tmp_path):
        """Test export with batch data creates data.yaml."""
        from src.orchestrator.manifest import WorkbookManifestExporter

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(temp_workbook_with_batch_data)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        with open(os.path.join(manifest_path, "manifest.yaml"), encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        assert manifest["has_data"] is True

        assert os.path.exists(os.path.join(manifest_path, "data.yaml"))

        with open(os.path.join(manifest_path, "data.yaml"), encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "batches" in data
        assert len(data["batches"]) == 3


class TestManifestOrchestratorInit:
    """Tests for ManifestOrchestrator initialization."""

    def test_init_basic(self, tmp_path, mock_ffmistralsmall):
        """Test basic initialization."""
        from src.orchestrator.manifest import ManifestOrchestrator

        orchestrator = ManifestOrchestrator(
            manifest_dir=str(tmp_path),
            client=mock_ffmistralsmall,
        )

        assert orchestrator.concurrency >= 1
        assert orchestrator.client == mock_ffmistralsmall

    def test_init_with_custom_concurrency(self, tmp_path, mock_ffmistralsmall):
        """Test initialization with custom concurrency."""
        from src.orchestrator.manifest import ManifestOrchestrator

        orchestrator = ManifestOrchestrator(
            manifest_dir=str(tmp_path),
            client=mock_ffmistralsmall,
            concurrency=4,
        )

        assert orchestrator.concurrency == 4


class TestManifestOrchestratorLoad:
    """Tests for ManifestOrchestrator loading."""

    def test_load_manifest(self, temp_workbook_with_data, tmp_path, mock_ffmistralsmall):
        """Test loading manifest files."""
        from src.orchestrator.manifest import (
            ManifestOrchestrator,
            WorkbookManifestExporter,
        )

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(temp_workbook_with_data)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        orchestrator = ManifestOrchestrator(
            manifest_dir=manifest_path,
            client=mock_ffmistralsmall,
        )
        orchestrator._load_manifest()

        assert len(orchestrator.prompts) == 3
        assert orchestrator.config["model"] == "mistral-small-2503"
        assert orchestrator.is_batch_mode is False

    def test_load_manifest_with_batch_data(
        self, temp_workbook_with_batch_data, tmp_path, mock_ffmistralsmall
    ):
        """Test loading manifest with batch data."""
        from src.orchestrator.manifest import (
            ManifestOrchestrator,
            WorkbookManifestExporter,
        )

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(temp_workbook_with_batch_data)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        orchestrator = ManifestOrchestrator(
            manifest_dir=manifest_path,
            client=mock_ffmistralsmall,
        )
        orchestrator._load_manifest()

        assert orchestrator.is_batch_mode is True
        assert len(orchestrator.batch_data) == 3


class TestManifestOrchestratorOutput:
    """Tests for ManifestOrchestrator output generation."""

    def test_get_output_path_format(self, tmp_path, mock_ffmistralsmall):
        """Test output path format includes timestamp and manifest name."""
        import yaml

        from src.orchestrator.manifest import ManifestOrchestrator

        # Create manifest.yaml with name
        manifest_data = {"name": "My Prompts", "version": "1.0"}
        with open(tmp_path / "manifest.yaml", "w") as f:
            yaml.dump(manifest_data, f)

        orchestrator = ManifestOrchestrator(
            manifest_dir=str(tmp_path),
            client=mock_ffmistralsmall,
        )

        output_path = orchestrator._get_output_path()

        # Name is sanitized: "My Prompts" -> "my_prompts"
        assert "my_prompts" in str(output_path)
        assert str(output_path).endswith(".parquet")

        filename = output_path.name
        # Timestamp format: YYYYMMDDHHMMSS (14 chars)
        assert len(filename) == 14 + len(".parquet")
        assert filename.startswith("20")

    def test_write_parquet_creates_file(self, tmp_path, mock_ffmistralsmall):
        """Test that _write_parquet creates a parquet file."""
        from src.orchestrator.manifest import ManifestOrchestrator

        orchestrator = ManifestOrchestrator(
            manifest_dir=str(tmp_path),
            client=mock_ffmistralsmall,
        )
        orchestrator.source_workbook = "test_workbook.xlsx"

        results = [
            {
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello",
                "history": None,
                "client": None,
                "condition": None,
                "condition_result": None,
                "condition_error": None,
                "response": "Response text",
                "status": "success",
                "attempts": 1,
                "error": None,
                "references": None,
                "semantic_query": None,
                "semantic_filter": None,
                "query_expansion": None,
                "rerank": None,
            }
        ]

        parquet_path = orchestrator._write_parquet(results)

        assert os.path.exists(parquet_path)

    def test_write_parquet_schema(self, tmp_path, mock_ffmistralsmall):
        """Test parquet file has expected schema."""
        from src.orchestrator.manifest import ManifestOrchestrator

        orchestrator = ManifestOrchestrator(
            manifest_dir=str(tmp_path),
            client=mock_ffmistralsmall,
        )
        orchestrator.source_workbook = "test.xlsx"

        results = [
            {
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello",
                "history": ["prev"],
                "client": "writer",
                "condition": "x > 5",
                "condition_result": "True",
                "condition_error": None,
                "response": "Response",
                "status": "success",
                "attempts": 1,
                "error": None,
                "references": ["doc1"],
                "semantic_query": "query",
                "semantic_filter": None,
                "query_expansion": "true",
                "rerank": None,
            }
        ]

        parquet_path = orchestrator._write_parquet(results)
        df = pl.read_parquet(parquet_path)

        expected_columns = [
            "sequence",
            "prompt_name",
            "prompt",
            "resolved_prompt",
            "history",
            "client",
            "condition",
            "condition_result",
            "condition_error",
            "response",
            "status",
            "attempts",
            "error",
            "references",
            "semantic_query",
            "semantic_filter",
            "query_expansion",
            "rerank",
        ]

        for col in expected_columns:
            assert col in df.columns

    def test_write_parquet_metadata(self, tmp_path, mock_ffmistralsmall):
        """Test parquet file includes manifest metadata."""
        import json

        import pyarrow.parquet as pq
        import yaml

        from src.orchestrator.manifest import ManifestOrchestrator

        # Create manifest.yaml with name and output_prompts
        manifest_data = {
            "name": "Test Manifest",
            "output_prompts": ["final_post", "summary"],
        }
        with open(tmp_path / "manifest.yaml", "w") as f:
            yaml.dump(manifest_data, f)

        orchestrator = ManifestOrchestrator(
            manifest_dir=str(tmp_path),
            client=mock_ffmistralsmall,
        )
        orchestrator.source_workbook = "/path/to/test.xlsx"

        results = [
            {
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello",
                "history": None,
                "client": None,
                "condition": None,
                "condition_result": None,
                "condition_error": None,
                "response": "Response",
                "status": "success",
                "attempts": 1,
                "error": None,
                "references": None,
                "semantic_query": None,
                "semantic_filter": None,
                "query_expansion": None,
                "rerank": None,
            }
        ]

        parquet_path = orchestrator._write_parquet(results)

        # Read metadata from parquet
        pf = pq.ParquetFile(parquet_path)
        metadata = pf.schema_arrow.metadata or {}

        assert b"manifest_name" in metadata
        assert metadata[b"manifest_name"] == b"test_manifest"
        assert b"output_prompts" in metadata
        assert json.loads(metadata[b"output_prompts"]) == ["final_post", "summary"]

    def test_write_parquet_with_batch_data(self, tmp_path, mock_ffmistralsmall):
        """Test parquet file includes batch columns when in batch mode."""
        from src.orchestrator.manifest import ManifestOrchestrator

        orchestrator = ManifestOrchestrator(
            manifest_dir=str(tmp_path),
            client=mock_ffmistralsmall,
        )
        orchestrator.source_workbook = "batch_test.xlsx"

        results = [
            {
                "batch_id": 1,
                "batch_name": "batch_1",
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello",
                "history": None,
                "client": None,
                "condition": None,
                "condition_result": None,
                "condition_error": None,
                "response": "Response",
                "status": "success",
                "attempts": 1,
                "error": None,
                "references": None,
                "semantic_query": None,
                "semantic_filter": None,
                "query_expansion": None,
                "rerank": None,
            }
        ]

        parquet_path = orchestrator._write_parquet(results)
        df = pl.read_parquet(parquet_path)

        assert "batch_id" in df.columns
        assert "batch_name" in df.columns
        assert df["batch_id"][0] == 1
        assert df["batch_name"][0] == "batch_1"


class TestManifestOrchestratorSummary:
    """Tests for ManifestOrchestrator summary."""

    def test_get_summary_empty(self, tmp_path, mock_ffmistralsmall):
        """Test summary with no results."""
        from src.orchestrator.manifest import ManifestOrchestrator

        orchestrator = ManifestOrchestrator(
            manifest_dir=str(tmp_path),
            client=mock_ffmistralsmall,
        )

        summary = orchestrator.get_summary()

        assert summary["status"] == "not_run"

    def test_get_summary_with_results(self, tmp_path, mock_ffmistralsmall):
        """Test summary with results."""
        from src.orchestrator.manifest import ManifestOrchestrator

        orchestrator = ManifestOrchestrator(
            manifest_dir=str(tmp_path),
            client=mock_ffmistralsmall,
        )
        orchestrator.results = [
            {"status": "success", "attempts": 1},
            {"status": "success", "attempts": 1},
            {"status": "failed", "attempts": 3},
        ]

        summary = orchestrator.get_summary()

        assert summary["total_prompts"] == 3
        assert summary["successful"] == 2
        assert summary["failed"] == 1
        assert summary["total_attempts"] == 5


class TestManifestIntegration:
    """Integration tests for manifest workflow."""

    def test_full_workflow(self, temp_workbook_with_data, tmp_path, mock_ffmistralsmall):
        """Test full export -> run workflow without API calls."""
        from src.orchestrator.manifest import (
            ManifestOrchestrator,
            WorkbookManifestExporter,
        )

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(temp_workbook_with_data)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        orchestrator = ManifestOrchestrator(
            manifest_dir=manifest_path,
            client=mock_ffmistralsmall,
            concurrency=1,
        )
        orchestrator._load_manifest()
        orchestrator._validate()
        orchestrator._init_client()

        results = orchestrator.execute()

        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)

    def test_export_notes_in_prompts_yaml(self, tmp_path):
        """Test that notes column is preserved in manifest export."""
        from openpyxl import Workbook

        from src.orchestrator.manifest import WorkbookManifestExporter

        wb = Workbook()
        ws_config = wb.active
        ws_config.title = "config"
        ws_config["A1"] = "field"
        ws_config["B1"] = "value"
        ws_config["A2"] = "model"
        ws_config["B2"] = "mistral-small-2503"

        ws_prompts = wb.create_sheet(title="prompts")
        ws_prompts["A1"] = "sequence"
        ws_prompts["B1"] = "prompt_name"
        ws_prompts["C1"] = "prompt"
        ws_prompts["D1"] = "history"
        ws_prompts["E1"] = "notes"
        ws_prompts["A2"] = 1
        ws_prompts["B2"] = "hello"
        ws_prompts["C2"] = "Say hello"
        ws_prompts["E2"] = "This is a test note for the hello prompt"
        ws_prompts["A3"] = 2
        ws_prompts["B3"] = "goodbye"
        ws_prompts["C3"] = "Say goodbye"

        workbook_path = str(tmp_path / "notes_test.xlsx")
        wb.save(workbook_path)

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(workbook_path)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        with open(os.path.join(manifest_path, "prompts.yaml"), encoding="utf-8") as f:
            prompts_data = yaml.safe_load(f)

        prompts = prompts_data["prompts"]
        assert len(prompts) == 2
        assert prompts[0]["notes"] == "This is a test note for the hello prompt"
        assert prompts[1]["notes"] is None

    def test_export_notes_roundtrip_through_manifest_orchestrator(self, tmp_path):
        """Test that notes round-trips: workbook -> export -> load into ManifestOrchestrator."""
        from unittest.mock import MagicMock

        from openpyxl import Workbook

        from src.orchestrator.manifest import ManifestOrchestrator, WorkbookManifestExporter

        mock_client = MagicMock()

        wb = Workbook()
        ws_config = wb.active
        ws_config.title = "config"
        ws_config["A1"] = "field"
        ws_config["B1"] = "value"
        ws_config["A2"] = "model"
        ws_config["B2"] = "mistral-small-2503"

        ws_prompts = wb.create_sheet(title="prompts")
        ws_prompts["A1"] = "sequence"
        ws_prompts["B1"] = "prompt_name"
        ws_prompts["C1"] = "prompt"
        ws_prompts["D1"] = "history"
        ws_prompts["E1"] = "notes"
        ws_prompts["A2"] = 1
        ws_prompts["B2"] = "test_prompt"
        ws_prompts["C2"] = "Test"
        ws_prompts["E2"] = "Important note about this prompt"

        workbook_path = str(tmp_path / "notes_rt.xlsx")
        wb.save(workbook_path)

        manifest_dir = str(tmp_path / "manifests")
        exporter = WorkbookManifestExporter(workbook_path)
        manifest_path = exporter.export(manifest_dir=manifest_dir)

        orchestrator = ManifestOrchestrator(
            manifest_dir=manifest_path,
            client=mock_client,
        )
        orchestrator._load_source()

        assert len(orchestrator.prompts) == 1
        assert orchestrator.prompts[0]["notes"] == "Important note about this prompt"
