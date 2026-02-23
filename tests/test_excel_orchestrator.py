import pytest
from unittest.mock import MagicMock, patch
import os


class TestExcelOrchestratorInit:
    """Tests for ExcelOrchestrator initialization."""

    def test_init(self, temp_workbook, mock_ffmistralsmall):
        """Test basic initialization."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)

        assert orchestrator.workbook_path == temp_workbook
        assert orchestrator.client == mock_ffmistralsmall
        assert orchestrator.results == []

    def test_init_with_config_overrides(self, temp_workbook, mock_ffmistralsmall):
        """Test initialization with config overrides."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(
            temp_workbook, mock_ffmistralsmall, config_overrides={"temperature": 0.5}
        )

        assert orchestrator.config_overrides == {"temperature": 0.5}


class TestExcelOrchestratorWorkbookInit:
    """Tests for workbook initialization."""

    def test_init_workbook_creates_new(self, temp_workbook, mock_ffmistralsmall):
        """Test that missing workbook is created."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator._init_workbook()

        assert os.path.exists(temp_workbook)

    def test_init_workbook_validates_existing(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test that existing workbook is validated."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)

        assert orchestrator._init_workbook() is None


class TestExcelOrchestratorConfig:
    """Tests for configuration loading."""

    def test_load_config(
        self, temp_workbook_with_data, mock_ffmistralsmall, sample_config
    ):
        """Test loading configuration."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator._load_config()

        assert orchestrator.config["model"] == sample_config["model"]
        assert orchestrator.config["max_retries"] == sample_config["max_retries"]

    def test_load_config_with_overrides(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test that config overrides are applied."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data,
            mock_ffmistralsmall,
            config_overrides={"temperature": 0.1, "max_retries": 10},
        )
        orchestrator._load_config()

        assert orchestrator.config["temperature"] == 0.1
        assert orchestrator.config["max_retries"] == 10


class TestExcelOrchestratorDependencyValidation:
    """Tests for dependency validation."""

    def test_validate_dependencies_success(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test successful dependency validation."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator._init_workbook()
        orchestrator.prompts = orchestrator.builder.load_prompts()

        assert orchestrator._validate_dependencies() is None

    def test_validate_dependencies_missing_reference(
        self, temp_workbook, mock_ffmistralsmall
    ):
        """Test validation fails for missing dependency reference."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "config"
        ws["A1"] = "field"
        ws["B1"] = "value"
        ws["A2"] = "model"
        ws["B2"] = "test-model"

        ws = wb.create_sheet("prompts")
        ws["A1"] = "sequence"
        ws["B1"] = "prompt_name"
        ws["C1"] = "prompt"
        ws["D1"] = "history"
        ws["A2"] = 1
        ws["B2"] = "test"
        ws["C2"] = "Hello"
        ws["D2"] = '["nonexistent"]'
        wb.save(temp_workbook)

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator._init_workbook()
        orchestrator.prompts = orchestrator.builder.load_prompts()

        with pytest.raises(ValueError, match="Dependency validation failed"):
            orchestrator._validate_dependencies()

    def test_validate_dependencies_wrong_order(
        self, temp_workbook, mock_ffmistralsmall
    ):
        """Test validation fails when dependency defined after use."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "config"
        ws["A1"] = "field"
        ws["B1"] = "value"
        ws["A2"] = "model"
        ws["B2"] = "test-model"

        ws = wb.create_sheet("prompts")
        ws["A1"] = "sequence"
        ws["B1"] = "prompt_name"
        ws["C1"] = "prompt"
        ws["D1"] = "history"
        ws["A2"] = 1
        ws["B2"] = "first"
        ws["C2"] = "Hello"
        ws["D2"] = '["second"]'
        ws["A3"] = 2
        ws["B3"] = "second"
        ws["C3"] = "World"
        ws["D3"] = ""
        wb.save(temp_workbook)

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        orchestrator._init_workbook()
        orchestrator.prompts = orchestrator.builder.load_prompts()

        with pytest.raises(ValueError, match="must be defined before"):
            orchestrator._validate_dependencies()


class TestExcelOrchestratorExecute:
    """Tests for prompt execution."""

    def test_execute_single_prompt(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test executing a single prompt."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        results = orchestrator.execute()

        assert len(results) == 1
        assert results[0]["status"] == "success"

    def test_execute_all_prompts(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test executing all prompts."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()
        orchestrator._init_client()

        results = orchestrator.execute()

        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)

    def test_execute_with_history(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test executing prompt with history dependencies."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()
        orchestrator._init_client()

        results = orchestrator.execute()

        followup = next(r for r in results if r["prompt_name"] == "followup")
        assert followup["history"] == ["math", "greeting"]

    def test_execute_handles_failure(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test that execution handles failures gracefully."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        mock_ffmistralsmall.generate_response = MagicMock(
            side_effect=Exception("API Error")
        )

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        results = orchestrator.execute()

        assert results[0]["status"] == "failed"
        assert "API Error" in results[0]["error"]

    def test_execute_retries_on_failure(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test that execution retries on failure."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        call_count = [0]

        def flaky_generate(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Temporary error")
            return "Success!"

        mock_ffmistralsmall.generate_response = flaky_generate

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()[:1]
        orchestrator._init_client()

        results = orchestrator.execute()

        assert results[0]["status"] == "success"
        assert results[0]["attempts"] == 3


class TestExcelOrchestratorRun:
    """Tests for the main run method."""

    def test_run_creates_results_sheet(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test that run creates a results sheet."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator
        from openpyxl import load_workbook

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        results_sheet = orchestrator.run()

        assert results_sheet.startswith("results_")

        wb = load_workbook(temp_workbook_with_data)
        assert results_sheet in wb.sheetnames

    def test_run_returns_sheet_name(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test that run returns the results sheet name."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        results_sheet = orchestrator.run()

        assert isinstance(results_sheet, str)
        assert results_sheet.startswith("results_")


class TestExcelOrchestratorSummary:
    """Tests for execution summary."""

    def test_get_summary_before_run(self, temp_workbook, mock_ffmistralsmall):
        """Test getting summary before execution."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook, mock_ffmistralsmall)
        summary = orchestrator.get_summary()

        assert summary["status"] == "not_run"

    def test_get_summary_after_run(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test getting summary after execution."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator.run()
        summary = orchestrator.get_summary()

        assert summary["total_prompts"] == 3
        assert summary["successful"] == 3
        assert summary["failed"] == 0
        assert "workbook" in summary

    def test_get_summary_with_failures(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test getting summary with failures."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        mock_ffmistralsmall.generate_response = MagicMock(
            side_effect=Exception("Error")
        )
        mock_ffmistralsmall.clone = MagicMock(return_value=mock_ffmistralsmall)

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator.run()
        summary = orchestrator.get_summary()

        assert summary["successful"] == 0
        assert summary["failed"] == 3


class TestExcelOrchestratorParallelExecution:
    """Tests for parallel execution."""

    def test_build_execution_graph(self, temp_workbook_with_data, mock_ffmistralsmall):
        """Test building execution graph with dependency levels."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(temp_workbook_with_data, mock_ffmistralsmall)
        orchestrator._init_workbook()
        orchestrator.prompts = orchestrator.builder.load_prompts()

        nodes = orchestrator._build_execution_graph()

        assert len(nodes) == 3

    def test_parallel_execution_basic(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test parallel execution with mock client."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data, mock_ffmistralsmall, concurrency=2
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()
        orchestrator._init_client()

        results = orchestrator.execute_parallel()

        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)

    def test_parallel_execution_respects_dependencies(
        self, temp_workbook, mock_ffmistralsmall
    ):
        """Test that parallel execution respects dependencies via execution graph."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "config"
        ws["A1"] = "field"
        ws["B1"] = "value"
        ws["A2"] = "model"
        ws["B2"] = "test-model"
        ws["A3"] = "max_retries"
        ws["B3"] = 1

        ws = wb.create_sheet("prompts")
        ws["A1"] = "sequence"
        ws["B1"] = "prompt_name"
        ws["C1"] = "prompt"
        ws["D1"] = "history"

        ws["A2"] = 1
        ws["B2"] = "first"
        ws["C2"] = "Task A"

        ws["A3"] = 2
        ws["B3"] = "second"
        ws["C3"] = "Task B"

        ws["A4"] = 3
        ws["B4"] = "third"
        ws["C4"] = "Task C depends on first"
        ws["D4"] = '["first"]'

        wb.save(temp_workbook)

        orchestrator = ExcelOrchestrator(
            temp_workbook, mock_ffmistralsmall, concurrency=2
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()

        nodes = orchestrator._build_execution_graph()

        assert nodes[1].level == 0
        assert nodes[2].level == 0
        assert nodes[3].level == 1

        assert nodes[1].dependencies == set()
        assert nodes[2].dependencies == set()
        assert nodes[3].dependencies == {1}

    def test_concurrency_parameter_clamping(self, temp_workbook, mock_ffmistralsmall):
        """Test that concurrency is clamped to valid range."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(
            temp_workbook, mock_ffmistralsmall, concurrency=0
        )
        assert orchestrator.concurrency == 1

        orchestrator = ExcelOrchestrator(
            temp_workbook, mock_ffmistralsmall, concurrency=15
        )
        assert orchestrator.concurrency == 10

    def test_sequential_when_concurrency_is_one(
        self, temp_workbook_with_data, mock_ffmistralsmall
    ):
        """Test that concurrency=1 uses sequential execution."""
        from src.orchestrator.excel_orchestrator import ExcelOrchestrator

        orchestrator = ExcelOrchestrator(
            temp_workbook_with_data, mock_ffmistralsmall, concurrency=1
        )
        orchestrator._init_workbook()
        orchestrator._load_config()
        orchestrator.prompts = orchestrator.builder.load_prompts()
        orchestrator._init_client()

        results = orchestrator.execute()

        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)
