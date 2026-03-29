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
        assert "validation_passed" in headers
        assert "validation_attempts" in headers
        assert "validation_critique" in headers

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

        history_cell = ws.cell(row=2, column=7).value

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


class TestWorkbookParserAgentHeaders:
    """Tests for agent-related headers in workbook parser."""

    def test_prompts_headers_includes_agent_mode(self):
        """PROMPTS_HEADERS should include agent_mode column."""
        from src.orchestrator.workbook_parser import WorkbookParser

        assert "agent_mode" in WorkbookParser.PROMPTS_HEADERS

    def test_prompts_headers_includes_tools_columns(self):
        """PROMPTS_HEADERS should include tools and max_tool_rounds."""
        from src.orchestrator.workbook_parser import WorkbookParser

        assert "tools" in WorkbookParser.PROMPTS_HEADERS
        assert "max_tool_rounds" in WorkbookParser.PROMPTS_HEADERS

    def test_prompts_headers_include_notes_column(self):
        """PROMPTS_HEADERS should include notes for user annotations."""
        from src.orchestrator.workbook_parser import WorkbookParser

        assert "notes" in WorkbookParser.PROMPTS_HEADERS

    def test_results_headers_includes_agent_columns(self):
        """RESULTS_HEADERS should include agent metadata columns."""
        from src.orchestrator.workbook_parser import WorkbookParser

        assert "agent_mode" in WorkbookParser.RESULTS_HEADERS
        assert "tool_calls" in WorkbookParser.RESULTS_HEADERS
        assert "total_rounds" in WorkbookParser.RESULTS_HEADERS
        assert "total_llm_calls" in WorkbookParser.RESULTS_HEADERS

    def test_tools_headers_defined(self):
        """TOOLS_HEADERS should be defined."""
        from src.orchestrator.workbook_parser import WorkbookParser

        assert hasattr(WorkbookParser, "TOOLS_HEADERS")
        assert "name" in WorkbookParser.TOOLS_HEADERS
        assert "description" in WorkbookParser.TOOLS_HEADERS
        assert "parameters" in WorkbookParser.TOOLS_HEADERS
        assert "implementation" in WorkbookParser.TOOLS_HEADERS
        assert "enabled" in WorkbookParser.TOOLS_HEADERS

    def test_template_includes_agent_mode_column(self, temp_workbook):
        """Template workbook should include agent_mode column in prompts sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        builder.create_template_workbook()

        wb = load_workbook(temp_workbook)
        ws_prompts = wb["prompts"]
        headers = [ws_prompts.cell(row=1, column=col).value for col in range(1, 20)]
        assert "agent_mode" in headers

    def test_load_prompts_reads_notes_column(self, temp_workbook):
        """Prompt notes should round-trip through workbook loading."""
        from openpyxl import Workbook

        from src.orchestrator.workbook_parser import WorkbookParser

        wb = Workbook()
        ws_config = wb.active
        ws_config.title = "config"
        ws_prompts = wb.create_sheet("prompts")

        headers = WorkbookParser.PROMPTS_HEADERS
        for col, header in enumerate(headers, start=1):
            ws_prompts.cell(row=1, column=col, value=header)

        values = {
            "sequence": 1,
            "prompt_name": "annotated_prompt",
            "prompt": "Say hello",
            "history": "",
            "notes": "This prompt is for smoke testing.",
        }
        for col, header in enumerate(headers, start=1):
            ws_prompts.cell(row=2, column=col, value=values.get(header, ""))

        wb.save(temp_workbook)

        parser = WorkbookParser(temp_workbook)
        prompts = parser.load_prompts()

        assert prompts[0]["notes"] == "This prompt is for smoke testing."

    def test_create_template_with_tools_sheet(self, temp_workbook):
        """Template workbook can be created with a tools sheet."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook)
        builder.create_template_workbook(with_tools_sheet=True)

        wb = load_workbook(temp_workbook)
        assert "tools" in wb.sheetnames

    def test_load_tools_sheet(self, temp_workbook):
        """Tools sheet can be loaded from workbook."""
        from openpyxl import Workbook

        from src.orchestrator.workbook_parser import WorkbookParser

        wb = Workbook()
        wb.create_sheet("config")
        wb.create_sheet("prompts")

        ws_tools = wb.create_sheet("tools")
        tool_headers = ["name", "description", "parameters", "implementation", "enabled"]
        for col, header in enumerate(tool_headers, start=1):
            ws_tools.cell(row=1, column=col, value=header)

        ws_tools.cell(row=2, column=1, value="calculate")
        ws_tools.cell(row=2, column=2, value="Evaluate math")
        ws_tools.cell(row=2, column=3, value='{"type":"object"}')
        ws_tools.cell(row=2, column=4, value="builtin:calculate")
        ws_tools.cell(row=2, column=5, value=True)

        del wb["Sheet"]
        wb.save(temp_workbook)

        builder = WorkbookParser(temp_workbook)
        tools = builder.load_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "calculate"
        assert tools[0]["implementation"] == "builtin:calculate"


class TestPrepareResultValue:
    """Tests for _prepare_result_value serialization helper."""

    def test_none_returns_empty_string(self):
        from src.orchestrator.workbook_parser import _prepare_result_value

        assert _prepare_result_value("status", None) == ""

    def test_string_passes_through(self):
        from src.orchestrator.workbook_parser import _prepare_result_value

        assert _prepare_result_value("status", "success") == "success"

    def test_int_passes_through(self):
        from src.orchestrator.workbook_parser import _prepare_result_value

        assert _prepare_result_value("sequence", 5) == 5

    def test_bool_false_passes_through(self):
        from src.orchestrator.workbook_parser import _prepare_result_value

        assert _prepare_result_value("agent_mode", False) is False

    def test_int_zero_passes_through(self):
        from src.orchestrator.workbook_parser import _prepare_result_value

        assert _prepare_result_value("total_rounds", 0) == 0

    def test_history_serialized_to_json(self):
        import json

        from src.orchestrator.workbook_parser import _prepare_result_value

        result = _prepare_result_value("history", ["a", "b"])
        assert json.loads(result) == ["a", "b"]

    def test_references_serialized_to_json(self):
        import json

        from src.orchestrator.workbook_parser import _prepare_result_value

        result = _prepare_result_value("references", ["doc1", "doc2"])
        assert json.loads(result) == ["doc1", "doc2"]

    def test_tool_calls_serialized_to_json(self):
        import json

        from src.orchestrator.workbook_parser import _prepare_result_value

        result = _prepare_result_value("tool_calls", [{"tool_name": "calc"}])
        assert json.loads(result) == [{"tool_name": "calc"}]

    def test_empty_list_history_serialized_to_json(self):
        from src.orchestrator.workbook_parser import _prepare_result_value

        assert _prepare_result_value("history", []) == "[]"

    def test_response_string_passes_through(self):
        from src.orchestrator.workbook_parser import _prepare_result_value

        assert _prepare_result_value("response", "Hello") == "Hello"

    def test_response_dict_serialized_to_json(self):
        import json

        from src.orchestrator.workbook_parser import _prepare_result_value

        result = _prepare_result_value("response", {"key": "value"})
        assert json.loads(result) == {"key": "value"}

    def test_response_list_serialized_to_json(self):
        import json

        from src.orchestrator.workbook_parser import _prepare_result_value

        result = _prepare_result_value("response", [1, 2, 3])
        assert json.loads(result) == [1, 2, 3]


class TestWriteResultsRoundTrip:
    """Tests that verify header-to-data alignment after writing results."""

    def test_header_data_alignment(self, temp_workbook_with_data):
        """Each header should map to the correct data column."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)

        results = [
            {
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello?",
                "resolved_prompt": "Hello? resolved",
                "history": ["a"],
                "response": "Hi!",
                "status": "success",
                "attempts": 2,
            }
        ]

        builder.write_results(results, "results_test")

        wb = load_workbook(temp_workbook_with_data)
        ws = wb["results_test"]

        for col_idx, header in enumerate(builder.RESULTS_HEADERS, start=1):
            header_cell = ws.cell(row=1, column=col_idx).value
            assert header_cell == header, (
                f"Column {col_idx}: expected '{header}', got '{header_cell}'"
            )

        assert ws.cell(row=2, column=3).value == 1
        assert ws.cell(row=2, column=4).value == "test"
        assert ws.cell(row=2, column=5).value == "Hello?"
        assert ws.cell(row=2, column=6).value == "Hello? resolved"
        assert ws.cell(row=2, column=7).value == '["a"]'
        assert ws.cell(row=2, column=12).value == "Hi!"
        assert ws.cell(row=2, column=13).value == "success"
        assert ws.cell(row=2, column=14).value == 2

    def test_falsy_values_written_correctly(self, temp_workbook_with_data):
        """agent_mode=False, total_rounds=0, total_llm_calls=0 should not become empty string."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)

        results = [
            {
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello?",
                "agent_mode": False,
                "total_rounds": 0,
                "total_llm_calls": 0,
                "status": "success",
                "attempts": 1,
            }
        ]

        builder.write_results(results, "results_test")

        wb = load_workbook(temp_workbook_with_data)
        ws = wb["results_test"]

        agent_mode_col = builder.RESULTS_HEADERS.index("agent_mode") + 1
        total_rounds_col = builder.RESULTS_HEADERS.index("total_rounds") + 1
        total_llm_calls_col = builder.RESULTS_HEADERS.index("total_llm_calls") + 1

        assert ws.cell(row=2, column=agent_mode_col).value is False
        assert ws.cell(row=2, column=total_rounds_col).value == 0
        assert ws.cell(row=2, column=total_llm_calls_col).value == 0

    def test_validation_fields_written_correctly(self, temp_workbook_with_data):
        """validation_passed, validation_attempts, validation_critique round-trip correctly."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)

        results = [
            {
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello?",
                "status": "success",
                "attempts": 1,
                "validation_passed": False,
                "validation_attempts": 3,
                "validation_critique": "Response too short",
            }
        ]

        builder.write_results(results, "results_test")

        wb = load_workbook(temp_workbook_with_data)
        ws = wb["results_test"]

        vp_col = builder.RESULTS_HEADERS.index("validation_passed") + 1
        va_col = builder.RESULTS_HEADERS.index("validation_attempts") + 1
        vc_col = builder.RESULTS_HEADERS.index("validation_critique") + 1

        assert ws.cell(row=2, column=vp_col).value is False
        assert ws.cell(row=2, column=va_col).value == 3
        assert ws.cell(row=2, column=vc_col).value == "Response too short"

    def test_none_values_written_as_empty_string(self, temp_workbook_with_data):
        """None values should become empty string in Excel (openpyxl reads back as None)."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)

        results = [
            {
                "sequence": 1,
                "prompt": "Hello?",
                "status": "success",
                "attempts": 1,
                "error": None,
                "response": None,
            }
        ]

        builder.write_results(results, "results_test")

        wb = load_workbook(temp_workbook_with_data)
        ws = wb["results_test"]

        error_col = builder.RESULTS_HEADERS.index("error") + 1
        response_col = builder.RESULTS_HEADERS.index("response") + 1

        assert ws.cell(row=2, column=error_col).value in ("", None)
        assert ws.cell(row=2, column=response_col).value in ("", None)

    def test_batch_results_same_alignment_as_write_results(self, temp_workbook_with_data):
        """write_batch_results should produce identical column layout to write_results."""
        from src.orchestrator.workbook_parser import WorkbookParser

        builder = WorkbookParser(temp_workbook_with_data)

        results = [
            {
                "batch_id": 1,
                "batch_name": "test_batch",
                "sequence": 1,
                "prompt_name": "test",
                "prompt": "Hello?",
                "response": "Hi!",
                "status": "success",
                "attempts": 1,
            }
        ]

        builder.write_results(results, "results_test")
        builder.write_batch_results(results, "batch1")

        wb = load_workbook(temp_workbook_with_data)
        ws_main = wb["results_test"]

        batch_sheet_name = None
        for name in wb.sheetnames:
            if name.startswith("results_batch1"):
                batch_sheet_name = name
                break
        assert batch_sheet_name is not None

        ws_batch = wb[batch_sheet_name]

        for col_idx, header in enumerate(builder.RESULTS_HEADERS, start=1):
            main_header = ws_main.cell(row=1, column=col_idx).value
            batch_header = ws_batch.cell(row=1, column=col_idx).value
            assert main_header == batch_header == header

        for col_idx in range(1, len(builder.RESULTS_HEADERS) + 1):
            main_val = ws_main.cell(row=2, column=col_idx).value
            batch_val = ws_batch.cell(row=2, column=col_idx).value
            assert main_val == batch_val, (
                f"Column {col_idx} ({builder.RESULTS_HEADERS[col_idx - 1]}): "
                f"write_results={main_val!r}, write_batch_results={batch_val!r}"
            )
