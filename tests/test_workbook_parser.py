# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

import os

import pytest
from openpyxl import load_workbook


class TestWorkbookParserInit:
    """Tests for WorkbookParser initialization."""

    def test_init(self, temp_workbook):
        """Test basic initialization."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        assert builder.workbook_path == temp_workbook


class TestWorkbookParserCreateTemplate:
    """Tests for template workbook creation."""

    def test_create_template_workbook(self, temp_workbook):
        """Test creating a template workbook."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        result = builder.create_template_workbook()

        assert result == temp_workbook
        assert os.path.exists(temp_workbook)

    def test_template_has_config_sheet(self, temp_workbook):
        """Test that template has config sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        builder.create_template_workbook()

        wb = load_workbook(temp_workbook)
        assert "config" in wb.sheetnames

    def test_template_has_prompts_sheet(self, temp_workbook):
        """Test that template has prompts sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        builder.create_template_workbook()

        wb = load_workbook(temp_workbook)
        assert "prompts" in wb.sheetnames

    def test_template_config_has_required_fields(self, temp_workbook):
        """Test that config sheet has required fields."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        builder.create_template_workbook()

        wb = load_workbook(temp_workbook)
        ws = wb["config"]

        fields = {row[0] for row in ws.iter_rows(min_row=2, values_only=True) if row[0]}

        assert "model" in fields
        assert "api_key_env" in fields
        assert "max_retries" in fields
        assert "temperature" in fields
        assert "max_tokens" in fields
        assert "system_instructions" in fields

    def test_template_prompts_has_required_headers(self, temp_workbook):
        """Test that prompts sheet has required headers."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        builder.create_template_workbook()

        wb = load_workbook(temp_workbook)
        ws = wb["prompts"]

        headers = [cell.value for cell in ws[1]]

        assert "sequence" in headers
        assert "prompt_name" in headers
        assert "prompt" in headers
        assert "history" in headers


class TestWorkbookParserValidate:
    """Tests for workbook validation."""

    def test_validate_workbook_success(self, temp_workbook_with_data):
        """Test validating a valid workbook."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)
        result = builder.validate_workbook()

        assert result is True

    def test_validate_workbook_not_found(self, temp_workbook):
        """Test validating non-existent workbook."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        with pytest.raises(FileNotFoundError):
            builder.validate_workbook()

    def test_validate_workbook_missing_config(self, temp_workbook):
        """Test validating workbook missing config sheet."""
        from openpyxl import Workbook

        from src.orchestrator.workbook_parser import WorkbookParser

        wb = Workbook()
        wb.create_sheet("prompts")
        del wb["Sheet"]
        wb.save(temp_workbook)

        builder = WorkbookParser(temp_workbook)

        with pytest.raises(ValueError, match="Missing required sheet: config"):
            builder.validate_workbook()

    def test_validate_workbook_missing_prompts(self, temp_workbook):
        """Test validating workbook missing prompts sheet."""
        from openpyxl import Workbook

        from src.orchestrator.workbook_parser import WorkbookParser

        wb = Workbook()
        wb.create_sheet("config")
        del wb["Sheet"]
        wb.save(temp_workbook)

        builder = WorkbookParser(temp_workbook)

        with pytest.raises(ValueError, match="Missing required sheet: prompts"):
            builder.validate_workbook()

    def test_validate_workbook_missing_columns(self, temp_workbook):
        """Test validating workbook missing required columns."""
        from openpyxl import Workbook

        from src.orchestrator.workbook_parser import WorkbookParser

        wb = Workbook()
        wb.create_sheet("config")
        wb.create_sheet("prompts")
        ws = wb["prompts"]
        ws["A1"] = "sequence"
        del wb["Sheet"]
        wb.save(temp_workbook)

        builder = WorkbookParser(temp_workbook)

        with pytest.raises(ValueError, match="Missing required columns"):
            builder.validate_workbook()


class TestWorkbookParserLoadConfig:
    """Tests for loading configuration."""

    def test_load_config(self, temp_workbook_with_data, sample_config):
        """Test loading configuration from workbook."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)
        config = builder.load_config()

        assert config["model"] == sample_config["model"]
        assert config["api_key_env"] == sample_config["api_key_env"]
        assert config["max_retries"] == sample_config["max_retries"]
        assert config["temperature"] == sample_config["temperature"]

    def test_load_config_type_conversion(self, temp_workbook):
        """Test that config values are converted to correct types."""
        from openpyxl import Workbook

        from src.orchestrator.workbook_parser import WorkbookParser

        wb = Workbook()
        ws = wb.active
        ws.title = "config"
        ws["A1"] = "field"
        ws["B1"] = "value"
        ws["A2"] = "max_retries"
        ws["B2"] = "5"
        ws["A3"] = "temperature"
        ws["B3"] = "0.5"
        ws["A4"] = "max_tokens"
        ws["B4"] = "8192"
        wb.save(temp_workbook)

        builder = WorkbookParser(temp_workbook)
        config = builder.load_config()

        assert isinstance(config["max_retries"], int)
        assert isinstance(config["temperature"], float)
        assert isinstance(config["max_tokens"], int)


class TestWorkbookParserLoadPrompts:
    """Tests for loading prompts."""

    def test_load_prompts(self, temp_workbook_with_data, sample_prompts):
        """Test loading prompts from workbook."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)
        prompts = builder.load_prompts()

        assert len(prompts) == 3
        assert prompts[0]["prompt_name"] == "greeting"
        assert prompts[1]["prompt_name"] == "math"
        assert prompts[2]["prompt_name"] == "followup"

    def test_load_prompts_sorted_by_sequence(self, temp_workbook_with_data):
        """Test that prompts are sorted by sequence number."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)
        prompts = builder.load_prompts()

        sequences = [p["sequence"] for p in prompts]
        assert sequences == sorted(sequences)

    def test_load_prompts_parses_history(self, temp_workbook_with_data):
        """Test that history column is parsed correctly."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)
        prompts = builder.load_prompts()

        followup = next(p for p in prompts if p["prompt_name"] == "followup")
        assert followup["history"] == ["math", "greeting"]


class TestWorkbookParserParseHistoryString:
    """Tests for parsing history strings."""

    def test_parse_history_string_json_array(self, temp_workbook):
        """Test parsing JSON array format."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string('["a", "b", "c"]')

        assert result == ["a", "b", "c"]

    def test_parse_history_string_quoted(self, temp_workbook):
        """Test parsing quoted format."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string('["math", "greeting"]')

        assert result == ["math", "greeting"]

    def test_parse_history_string_none(self, temp_workbook):
        """Test parsing None."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string(None)

        assert result is None

    def test_parse_history_string_empty(self, temp_workbook):
        """Test parsing empty string."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string("")

        assert result is None

    def test_parse_history_string_already_list(self, temp_workbook):
        """Test parsing already-list input."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string(["a", "b"])

        assert result == ["a", "b"]

    def test_parse_history_string_comma_separated(self, temp_workbook):
        """Test parsing comma-separated format."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string("[a, b, c]")

        assert result == ["a", "b", "c"]


class TestWorkbookParserSmartQuotes:
    """Tests for smart quote normalization in history strings."""

    def test_smart_double_quotes(self, temp_workbook):
        """Test parsing history with smart double quotes."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string('["interesting_story"]')

        assert result == ["interesting_story"]

    def test_smart_single_quotes(self, temp_workbook):
        """Test parsing history with smart single quotes."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string("['test', 'value']")

        assert result == ["test", "value"]

    def test_mixed_ascii_and_smart_quotes(self, temp_workbook):
        """Test parsing history with mixed ASCII and smart quotes."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string('["ascii", "smart"]')

        assert result == ["ascii", "smart"]

    def test_backward_compatibility_ascii_quotes(self, temp_workbook):
        """Test that ASCII quotes still work (backward compatibility)."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string('["item1", "item2"]')

        assert result == ["item1", "item2"]

    def test_sample_workbook_exact_string(self, temp_workbook):
        """Test the exact string from sample_workbook.xlsx."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string('["interesting_story"]')

        assert result == ["interesting_story"]

    def test_multiple_items_smart_quotes(self, temp_workbook):
        """Test multiple items with smart quotes."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)

        result = builder.parse_history_string('["first", "second", "third"]')

        assert result == ["first", "second", "third"]


class TestWorkbookParserWriteResults:
    """Tests for writing results."""

    def test_write_results(self, temp_workbook_with_data):
        """Test writing results to workbook."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)

        results = [
            {
                "batch_id": 0,
                "batch_name": "",
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello?",
                "history": None,
                "response": "Hi!",
                "status": "success",
                "attempts": 1,
                "error": None,
            }
        ]

        sheet_name = builder.write_results(results, "results_test")

        assert sheet_name == "results_test"

        wb = load_workbook(temp_workbook_with_data)
        assert "results_test" in wb.sheetnames

    def test_write_results_creates_new_sheet_name(self, temp_workbook_with_data):
        """Test that duplicate sheet names get timestamp suffix."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)

        builder.write_results([], "results_test")
        sheet_name = builder.write_results([], "results_test")

        assert sheet_name != "results_test"

    def test_write_results_has_all_columns(self, temp_workbook_with_data):
        """Test that results sheet has all required columns."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)

        results = [
            {
                "batch_id": 0,
                "batch_name": "",
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello?",
                "history": ["a"],
                "response": "Hi!",
                "status": "success",
                "attempts": 1,
                "error": None,
            }
        ]

        builder.write_results(results, "results_test")

        wb = load_workbook(temp_workbook_with_data)
        ws = wb["results_test"]

        headers = [cell.value for cell in ws[1]]

        assert "batch_id" in headers
        assert "batch_name" in headers
        assert "sequence" in headers
        assert "prompt_name" in headers
        assert "prompt" in headers
        assert "history" in headers
        assert "response" in headers
        assert "status" in headers
        assert "attempts" in headers
        assert "error" in headers

    def test_write_results_converts_history_to_json(self, temp_workbook_with_data):
        """Test that history is converted to JSON string."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)

        results = [
            {
                "batch_id": 0,
                "batch_name": "",
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello?",
                "history": ["a", "b"],
                "response": "Hi!",
                "status": "success",
                "attempts": 1,
                "error": None,
            }
        ]

        builder.write_results(results, "results_test")

        wb = load_workbook(temp_workbook_with_data)
        ws = wb["results_test"]

        history_cell = ws.cell(row=2, column=6).value

        assert history_cell == '["a", "b"]'


class TestWorkbookParserBatchData:
    """Tests for batch data sheet functionality."""

    def test_has_data_sheet_true(self, temp_workbook_with_batch_data):
        """Test has_data_sheet returns True when data sheet exists."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_batch_data)
        assert builder.has_data_sheet() is True

    def test_has_data_sheet_false(self, temp_workbook_with_data):
        """Test has_data_sheet returns False when no data sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)
        assert builder.has_data_sheet() is False

    def test_load_data(self, temp_workbook_with_batch_data):
        """Test loading data from data sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_batch_data)
        data = builder.load_data()

        assert len(data) == 3
        assert data[0]["region"] == "north"
        assert data[1]["region"] == "south"
        assert data[2]["region"] == "east"

    def test_load_data_columns(self, temp_workbook_with_batch_data):
        """Test that data columns are loaded correctly."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_batch_data)
        data = builder.load_data()

        assert "id" in data[0]
        assert "batch_name" in data[0]
        assert "region" in data[0]
        assert "product" in data[0]
        assert "price" in data[0]
        assert "quantity" in data[0]

    def test_load_data_empty_when_no_sheet(self, temp_workbook_with_data):
        """Test load_data returns empty list when no data sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)
        data = builder.load_data()

        assert data == []

    def test_get_data_columns(self, temp_workbook_with_batch_data):
        """Test getting data column names."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_batch_data)
        columns = builder.get_data_columns()

        assert "id" in columns
        assert "batch_name" in columns
        assert "region" in columns

    def test_create_template_with_data_sheet(self, temp_workbook):
        """Test creating template with data sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        builder.create_template_workbook(with_data_sheet=True)

        wb = load_workbook(temp_workbook)
        assert "data" in wb.sheetnames

    def test_create_template_without_data_sheet(self, temp_workbook):
        """Test creating template without data sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        builder.create_template_workbook(with_data_sheet=False)

        wb = load_workbook(temp_workbook)
        assert "data" not in wb.sheetnames


class TestWorkbookParserWriteBatchResults:
    """Tests for writing batch results to separate sheets."""

    def test_write_batch_results(self, temp_workbook_with_batch_data):
        """Test writing batch results to a separate sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_batch_data)

        results = [
            {
                "sequence": 1,
                "prompt_name": "intro",
                "prompt": "Analyze north widget_a.",
                "history": None,
                "response": "Analysis complete.",
                "status": "success",
                "attempts": 1,
                "error": None,
            }
        ]

        sheet_name = builder.write_batch_results(results, "north_widget_a")

        assert "north_widget_a" in sheet_name

        wb = load_workbook(temp_workbook_with_batch_data)
        assert sheet_name in wb.sheetnames

    def test_write_results_with_batch_info(self, temp_workbook_with_batch_data):
        """Test writing results with batch_id and batch_name columns."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_batch_data)

        results = [
            {
                "batch_id": 1,
                "batch_name": "north_widget_a",
                "sequence": 1,
                "prompt_name": "intro",
                "prompt": "Analyze north widget_a.",
                "history": None,
                "response": "Analysis complete.",
                "status": "success",
                "attempts": 1,
                "error": None,
            }
        ]

        builder.write_results(results, "results_test")

        wb = load_workbook(temp_workbook_with_batch_data)
        ws = wb["results_test"]

        headers = [cell.value for cell in ws[1]]

        assert "batch_id" in headers
        assert "batch_name" in headers


class TestWorkbookParserClientsSheet:
    """Tests for clients sheet functionality."""

    def test_has_clients_sheet_true(self, temp_workbook):
        """Test has_clients_sheet returns True when clients sheet exists."""
        from openpyxl import Workbook

        from src.orchestrator.workbook_parser import WorkbookParser

        wb = Workbook()
        wb.create_sheet("config")
        wb.create_sheet("prompts")
        wb.create_sheet("clients")
        del wb["Sheet"]
        wb.save(temp_workbook)

        builder = WorkbookParser(temp_workbook)
        assert builder.has_clients_sheet() is True

    def test_has_clients_sheet_false(self, temp_workbook_with_data):
        """Test has_clients_sheet returns False when no clients sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)
        assert builder.has_clients_sheet() is False

    def test_load_clients(self, temp_workbook):
        """Test loading clients from clients sheet."""
        from openpyxl import Workbook

        from src.orchestrator.workbook_parser import WorkbookParser

        wb = Workbook()
        wb.create_sheet("config")
        wb.create_sheet("prompts")

        ws_clients = wb.create_sheet("clients")
        headers = ["name", "client_type", "api_key_env", "model", "temperature"]
        for col, header in enumerate(headers, start=1):
            ws_clients.cell(row=1, column=col, value=header)

        ws_clients.cell(row=2, column=1, value="fast")
        ws_clients.cell(row=2, column=2, value="mistral-small")
        ws_clients.cell(row=2, column=3, value="MISTRALSMALL_KEY")
        ws_clients.cell(row=2, column=4, value="mistral-small-2503")
        ws_clients.cell(row=2, column=5, value=0.3)

        ws_clients.cell(row=3, column=1, value="smart")
        ws_clients.cell(row=3, column=2, value="anthropic")
        ws_clients.cell(row=3, column=3, value="ANTHROPIC_API_KEY")

        del wb["Sheet"]
        wb.save(temp_workbook)

        builder = WorkbookParser(temp_workbook)
        clients = builder.load_clients()

        assert len(clients) == 2
        assert clients[0]["name"] == "fast"
        assert clients[0]["client_type"] == "mistral-small"
        assert clients[1]["name"] == "smart"

    def test_load_clients_empty_when_no_sheet(self, temp_workbook_with_data):
        """Test load_clients returns empty list when no clients sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)
        clients = builder.load_clients()

        assert clients == []

    def test_create_template_with_clients_sheet(self, temp_workbook):
        """Test creating template with clients sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        builder.create_template_workbook(with_clients_sheet=True)

        wb = load_workbook(temp_workbook)
        assert "clients" in wb.sheetnames

    def test_load_prompts_with_client_column(self, temp_workbook):
        """Test loading prompts that include client column."""
        from openpyxl import Workbook

        from src.orchestrator.workbook_parser import WorkbookParser

        wb = Workbook()
        wb.create_sheet("config")

        ws_prompts = wb.create_sheet("prompts")
        headers = ["sequence", "prompt_name", "prompt", "history", "client"]
        for col, header in enumerate(headers, start=1):
            ws_prompts.cell(row=1, column=col, value=header)

        ws_prompts.cell(row=2, column=1, value=1)
        ws_prompts.cell(row=2, column=2, value="classify")
        ws_prompts.cell(row=2, column=3, value="Classify this text")
        ws_prompts.cell(row=2, column=4, value="")
        ws_prompts.cell(row=2, column=5, value="fast")

        ws_prompts.cell(row=3, column=1, value=2)
        ws_prompts.cell(row=3, column=2, value="analyze")
        ws_prompts.cell(row=3, column=3, value="Analyze deeply")
        ws_prompts.cell(row=3, column=4, value="")
        ws_prompts.cell(row=3, column=5, value="smart")

        del wb["Sheet"]
        wb.save(temp_workbook)

        builder = WorkbookParser(temp_workbook)
        prompts = builder.load_prompts()

        assert len(prompts) == 2
        assert prompts[0]["client"] == "fast"
        assert prompts[1]["client"] == "smart"
