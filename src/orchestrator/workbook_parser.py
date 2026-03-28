# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Excel workbook parser for prompt orchestration.

Provides utilities for validating, reading, and writing orchestrator workbooks
with config, prompts, data, clients, and documents sheets.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any

from openpyxl import Workbook, load_workbook

from ..config import get_config
from .workbook_formatter import WorkbookFormatter

logger = logging.getLogger(__name__)


class WorkbookParser:
    """Parses and validates Excel workbooks for prompt orchestration."""

    def __init__(self, workbook_path: str) -> None:
        """Initialize the WorkbookParser.

        Args:
            workbook_path: Path to the Excel workbook file.

        """
        self.workbook_path = workbook_path
        self._has_data_sheet: bool | None = None
        self._has_clients_sheet: bool | None = None
        self._has_documents_sheet: bool | None = None
        self._has_tools_sheet: bool | None = None
        self._config = get_config()
        self.formatter = WorkbookFormatter(self._config)

    @property
    def CONFIG_SHEET(self) -> str:
        return self._config.workbook.sheet_names.config

    @property
    def PROMPTS_SHEET(self) -> str:
        return self._config.workbook.sheet_names.prompts

    @property
    def DATA_SHEET(self) -> str:
        return self._config.workbook.sheet_names.data

    @property
    def CLIENTS_SHEET(self) -> str:
        return self._config.workbook.sheet_names.clients

    @property
    def DOCUMENTS_SHEET(self) -> str:
        return self._config.workbook.sheet_names.documents

    @property
    def TOOLS_SHEET(self) -> str:
        return self._config.workbook.sheet_names.tools

    @property
    def CONFIG_FIELDS(self) -> list[tuple[str, str, str]]:
        defaults = self._config.workbook.defaults
        return [
            ("name", "", "Human-readable name for this process/workbook"),
            ("description", "", "Brief description of what this process does"),
            ("client_type", "", "AI client type from config/clients.yaml client_types"),
            ("model", defaults.model, "Model identifier (e.g., mistral-small-latest)"),
            ("api_key_env", defaults.api_key_env, "Environment variable name for API key"),
            ("max_retries", str(defaults.max_retries), "Maximum retry attempts (1-10)"),
            ("temperature", str(defaults.temperature), "Sampling temperature (0.0-2.0)"),
            ("max_tokens", str(defaults.max_tokens), "Maximum response tokens"),
            ("system_instructions", defaults.system_instructions, "System prompt for AI"),
            ("created_at", "", "ISO timestamp when created"),
        ]

    @property
    def BATCH_CONFIG_FIELDS(self) -> list[tuple[str, str, str]]:
        batch = self._config.workbook.batch
        return [
            (
                "batch_mode",
                batch.mode,
                "Batch execution mode: 'per_row' (execute for each data row)",
            ),
            (
                "batch_output",
                batch.output,
                "Output format: 'combined' (single sheet) or 'separate_sheets'",
            ),
            (
                "on_batch_error",
                batch.on_error,
                "Error handling: 'continue' (skip failed) or 'stop' (halt on error)",
            ),
        ]

    PROMPTS_HEADERS = [
        "sequence",
        "prompt_name",
        "prompt",
        "history",
        "client",
        "condition",
        "references",
        "semantic_query",
        "semantic_filter",
        "query_expansion",
        "rerank",
        "agent_mode",
        "tools",
        "max_tool_rounds",
    ]
    REQUIRED_PROMPTS_HEADERS = ["sequence", "prompt_name", "prompt", "history"]
    DOCUMENTS_HEADERS = [
        "reference_name",
        "common_name",
        "file_path",
        "tags",
        "chunking_strategy",
        "notes",
    ]
    CLIENTS_HEADERS = [
        "name",
        "client_type",
        "api_key_env",
        "model",
        "temperature",
        "max_tokens",
        "system_instructions",
    ]
    RESULTS_HEADERS = [
        "batch_id",
        "batch_name",
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
        "agent_mode",
        "tool_calls",
        "total_rounds",
        "total_llm_calls",
    ]
    TOOLS_HEADERS = [
        "name",
        "description",
        "parameters",
        "implementation",
        "enabled",
    ]

    def has_data_sheet(self) -> bool:
        """Check if workbook has a data sheet for batch execution."""
        if self._has_data_sheet is not None:
            return self._has_data_sheet

        if not os.path.exists(self.workbook_path):
            self._has_data_sheet = False
            return False

        wb = load_workbook(self.workbook_path)
        self._has_data_sheet = self.DATA_SHEET in wb.sheetnames
        return self._has_data_sheet

    def has_clients_sheet(self) -> bool:
        """Check if workbook has a clients sheet for multi-client execution."""
        if self._has_clients_sheet is not None:
            return self._has_clients_sheet

        if not os.path.exists(self.workbook_path):
            self._has_clients_sheet = False
            return False

        wb = load_workbook(self.workbook_path)
        self._has_clients_sheet = self.CLIENTS_SHEET in wb.sheetnames
        return self._has_clients_sheet

    def has_documents_sheet(self) -> bool:
        """Check if workbook has a documents sheet for document references."""
        if self._has_documents_sheet is not None:
            return self._has_documents_sheet

        if not os.path.exists(self.workbook_path):
            self._has_documents_sheet = False
            return False

        wb = load_workbook(self.workbook_path)
        self._has_documents_sheet = self.DOCUMENTS_SHEET in wb.sheetnames
        return self._has_documents_sheet

    def has_tools_sheet(self) -> bool:
        """Check if workbook has a tools sheet for agentic execution."""
        if self._has_tools_sheet is not None:
            return self._has_tools_sheet

        if not os.path.exists(self.workbook_path):
            self._has_tools_sheet = False
            return False

        wb = load_workbook(self.workbook_path)
        self._has_tools_sheet = self.TOOLS_SHEET in wb.sheetnames
        return self._has_tools_sheet

    def create_template_workbook(
        self,
        with_data_sheet: bool = False,
        with_clients_sheet: bool = False,
        with_documents_sheet: bool = False,
        with_tools_sheet: bool = False,
    ) -> str:
        """Create a new workbook with template structure."""
        logger.info(f"Creating template workbook: {self.workbook_path}")

        wb = Workbook()

        ws_config = wb.active
        ws_config.title = self.CONFIG_SHEET
        ws_config["A1"] = "field"
        ws_config["B1"] = "value"
        ws_config["C1"] = "notes"

        all_config = list(self.CONFIG_FIELDS)
        if with_data_sheet:
            all_config.extend(self.BATCH_CONFIG_FIELDS)

        for idx, (field, default, notes) in enumerate(all_config, start=2):
            ws_config[f"A{idx}"] = field
            if field == "created_at":
                ws_config[f"B{idx}"] = datetime.now().isoformat()
            else:
                ws_config[f"B{idx}"] = default
            ws_config[f"C{idx}"] = notes

        self.formatter.apply_formatting(ws_config, "config")

        ws_prompts = wb.create_sheet(title=self.PROMPTS_SHEET)
        for col_idx, header in enumerate(self.PROMPTS_HEADERS, start=1):
            ws_prompts.cell(row=1, column=col_idx, value=header)

        self.formatter.apply_formatting(ws_prompts, "prompts")

        if with_data_sheet:
            ws_data = wb.create_sheet(title=self.DATA_SHEET)
            ws_data["A1"] = "id"
            ws_data["B1"] = "batch_name"
            self.formatter.apply_formatting(ws_data, "data")

        if with_clients_sheet:
            ws_clients = wb.create_sheet(title=self.CLIENTS_SHEET)
            for col_idx, header in enumerate(self.CLIENTS_HEADERS, start=1):
                ws_clients.cell(row=1, column=col_idx, value=header)
            self.formatter.apply_formatting(ws_clients, "clients")

        if with_documents_sheet:
            ws_documents = wb.create_sheet(title=self.DOCUMENTS_SHEET)
            for col_idx, header in enumerate(self.DOCUMENTS_HEADERS, start=1):
                ws_documents.cell(row=1, column=col_idx, value=header)
            self.formatter.apply_formatting(ws_documents, "documents")

        if with_tools_sheet:
            ws_tools = wb.create_sheet(title=self.TOOLS_SHEET)
            for col_idx, header in enumerate(self.TOOLS_HEADERS, start=1):
                ws_tools.cell(row=1, column=col_idx, value=header)
            self.formatter.apply_formatting(ws_tools, "tools")

        wb.save(self.workbook_path)
        logger.info(f"Template workbook created: {self.workbook_path}")
        return self.workbook_path

    def validate_workbook(self) -> bool:
        """Validate workbook has required structure."""
        if not os.path.exists(self.workbook_path):
            raise FileNotFoundError(f"Workbook not found: {self.workbook_path}")

        wb = load_workbook(self.workbook_path)

        if self.CONFIG_SHEET not in wb.sheetnames:
            raise ValueError(f"Missing required sheet: {self.CONFIG_SHEET}")

        if self.PROMPTS_SHEET not in wb.sheetnames:
            raise ValueError(f"Missing required sheet: {self.PROMPTS_SHEET}")

        ws_prompts = wb[self.PROMPTS_SHEET]

        actual_headers = []
        for col in range(1, ws_prompts.max_column + 1):
            header = ws_prompts.cell(row=1, column=col).value
            if header:
                actual_headers.append(str(header).strip().lower())

        normalized_required = [h.lower() for h in self.REQUIRED_PROMPTS_HEADERS]
        missing = set(normalized_required) - set(actual_headers)
        if missing:
            raise ValueError(f"Missing required columns in prompts sheet: {missing}")

        logger.info(f"Workbook validated: {self.workbook_path}")
        return True

    def load_config(self) -> dict[str, Any]:
        """Load configuration from config sheet.

        Handles both 2-column format (field, value) and 3-column format
        (field, value, notes). The notes column is ignored if present.

        Returns:
            Dict of config field -> value pairs.

        """
        wb = load_workbook(self.workbook_path)
        ws = wb[self.CONFIG_SHEET]

        config = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue

            key = str(row[0]).strip()
            value = row[1] if len(row) > 1 else None

            if value is None:
                continue

            if key == "max_retries" or key == "max_tokens":
                value = int(value)
            elif key == "temperature":
                value = float(value)

            config[key] = value

        logger.debug(f"Loaded config: {config}")
        return config

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """Validate config values and return list of error messages.

        Args:
            config: Configuration dictionary from load_config().

        Returns:
            List of error message strings. Empty list if valid.

        """
        errors: list[str] = []

        client_type = config.get("client_type")
        if client_type:
            available = self._config.get_available_client_types()
            if client_type not in available:
                errors.append(
                    f"Unknown client_type '{client_type}'. Available: {', '.join(sorted(available))}"
                )

        temperature = config.get("temperature")
        if temperature is not None:
            try:
                temp_float = float(temperature)
                if not (0.0 <= temp_float <= 2.0):
                    errors.append(f"temperature {temperature} out of range [0.0, 2.0]")
            except (TypeError, ValueError):
                errors.append(f"temperature '{temperature}' is not a valid number")

        max_retries = config.get("max_retries")
        if max_retries is not None:
            try:
                retries_int = int(max_retries)
                if not (1 <= retries_int <= 10):
                    errors.append(f"max_retries {max_retries} out of range [1, 10]")
            except (TypeError, ValueError):
                errors.append(f"max_retries '{max_retries}' is not a valid integer")

        batch_mode = config.get("batch_mode")
        if batch_mode and batch_mode not in ["per_row"]:
            errors.append(f"batch_mode '{batch_mode}' not supported. Use: per_row")

        batch_output = config.get("batch_output")
        if batch_output and batch_output not in ["combined", "separate_sheets"]:
            errors.append("batch_output must be 'combined' or 'separate_sheets'")

        on_batch_error = config.get("on_batch_error")
        if on_batch_error and on_batch_error not in ["continue", "stop"]:
            errors.append("on_batch_error must be 'continue' or 'stop'")

        return errors

    def load_prompts(self) -> list[dict[str, Any]]:
        """Load prompts from prompts sheet."""
        wb = load_workbook(self.workbook_path)
        ws = wb[self.PROMPTS_SHEET]

        headers = []
        for col in range(1, ws.max_column + 1):
            header = ws.cell(row=1, column=col).value
            headers.append(str(header).strip().lower() if header else f"col_{col}")

        prompts = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue

            row_dict = {}
            for col_idx, header in enumerate(headers):
                if col_idx < len(row):
                    row_dict[header] = row[col_idx]

            prompt_data = {
                "sequence": int(row_dict.get("sequence")) if row_dict.get("sequence") else None,
                "prompt_name": str(row_dict.get("prompt_name", "")).strip()
                if row_dict.get("prompt_name")
                else None,
                "prompt": str(row_dict.get("prompt", "")).strip()
                if row_dict.get("prompt")
                else None,
                "history": self.parse_history_string(row_dict.get("history"))
                if row_dict.get("history")
                else None,
                "client": str(row_dict.get("client", "")).strip()
                if row_dict.get("client")
                else None,
                "condition": str(row_dict.get("condition", "")).strip()
                if row_dict.get("condition")
                else None,
                "references": self.parse_history_string(row_dict.get("references"))
                if row_dict.get("references")
                else None,
                "semantic_query": str(row_dict.get("semantic_query", "")).strip()
                if row_dict.get("semantic_query")
                else None,
                "semantic_filter": str(row_dict.get("semantic_filter", "")).strip()
                if row_dict.get("semantic_filter")
                else None,
                "query_expansion": str(row_dict.get("query_expansion", "")).strip().lower()
                if row_dict.get("query_expansion")
                else None,
                "rerank": str(row_dict.get("rerank", "")).strip().lower()
                if row_dict.get("rerank")
                else None,
                "agent_mode": str(row_dict.get("agent_mode", "")).strip().lower()
                in ("true", "1", "yes")
                if row_dict.get("agent_mode")
                else False,
                "tools": self.parse_history_string(row_dict.get("tools"))
                if row_dict.get("tools")
                else None,
                "max_tool_rounds": int(row_dict["max_tool_rounds"])
                if row_dict.get("max_tool_rounds")
                else None,
            }

            if prompt_data["sequence"] and prompt_data["prompt"]:
                prompts.append(prompt_data)

        prompts.sort(key=lambda x: x["sequence"])
        logger.info(f"Loaded {len(prompts)} prompts")
        return prompts

    def load_data(self) -> list[dict[str, Any]]:
        """Load batch data from data sheet."""
        if not self.has_data_sheet():
            return []

        wb = load_workbook(self.workbook_path)
        ws = wb[self.DATA_SHEET]

        headers = []
        for col in range(1, ws.max_column + 1):
            header = ws.cell(row=1, column=col).value
            headers.append(str(header).strip() if header else f"col_{col}")

        data_rows = []
        for row_idx in range(2, ws.max_row + 1):
            row_data = {}
            has_content = False
            for col_idx, header in enumerate(headers, start=1):
                value = ws.cell(row=row_idx, column=col_idx).value
                row_data[header] = value
                if value is not None:
                    has_content = True

            if has_content:
                row_data["_row_idx"] = row_idx
                data_rows.append(row_data)

        logger.info(f"Loaded {len(data_rows)} data rows for batch execution")
        return data_rows

    def get_data_columns(self) -> list[str]:
        """Get column names from data sheet."""
        if not self.has_data_sheet():
            return []

        wb = load_workbook(self.workbook_path)
        ws = wb[self.DATA_SHEET]

        headers = []
        for col in range(1, ws.max_column + 1):
            header = ws.cell(row=1, column=col).value
            if header:
                headers.append(str(header).strip())

        return headers

    def load_clients(self) -> list[dict[str, Any]]:
        """Load client configurations from clients sheet.

        Returns:
            List of client config dictionaries with keys:
            - name: unique identifier for this client
            - client_type: type of client (e.g., "mistral-small", "anthropic")
            - api_key_env: environment variable for API key (optional)
            - model: model override (optional)
            - temperature: temperature override (optional)
            - max_tokens: max tokens override (optional)
            - system_instructions: system prompt override (optional)

        """
        if not self.has_clients_sheet():
            return []

        wb = load_workbook(self.workbook_path)
        ws = wb[self.CLIENTS_SHEET]

        headers = []
        for col in range(1, ws.max_column + 1):
            header = ws.cell(row=1, column=col).value
            headers.append(str(header).strip() if header else f"col_{col}")

        clients = []
        for row_idx in range(2, ws.max_row + 1):
            row_data = {}
            has_content = False
            for col_idx, header in enumerate(headers, start=1):
                value = ws.cell(row=row_idx, column=col_idx).value
                row_data[header] = value
                if value is not None:
                    has_content = True

            if has_content and row_data.get("name") and row_data.get("client_type"):
                clients.append(row_data)

        logger.info(f"Loaded {len(clients)} client configurations")
        return clients

    def load_documents(self) -> list[dict[str, Any]]:
        """Load document definitions from documents sheet.

        Returns:
            List of document config dictionaries with keys:
            - reference_name: unique identifier for referencing in prompts
            - common_name: human-readable name
            - file_path: path to document (relative to workbook)
            - tags: comma-separated tags for filtering (optional)
            - notes: optional description
            - chunking_strategy: inferred from file extension

        """
        if not self.has_documents_sheet():
            return []

        wb = load_workbook(self.workbook_path)
        ws = wb[self.DOCUMENTS_SHEET]

        headers = []
        for col in range(1, ws.max_column + 1):
            header = ws.cell(row=1, column=col).value
            headers.append(str(header).strip() if header else f"col_{col}")

        documents = []
        for row_idx in range(2, ws.max_row + 1):
            row_data = {}
            has_content = False
            for col_idx, header in enumerate(headers, start=1):
                value = ws.cell(row=row_idx, column=col_idx).value
                row_data[header] = value
                if value is not None:
                    has_content = True

            if has_content and row_data.get("reference_name") and row_data.get("file_path"):
                file_path = str(row_data.get("file_path", "")).strip()
                tags_raw = row_data.get("tags")
                tags_list = None
                if tags_raw:
                    tags_str = str(tags_raw).strip()
                    tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]

                documents.append(
                    {
                        "reference_name": str(row_data.get("reference_name", "")).strip(),
                        "common_name": str(row_data.get("common_name", "")).strip()
                        if row_data.get("common_name")
                        else row_data.get("reference_name", ""),
                        "file_path": file_path,
                        "tags": tags_list,
                        "notes": str(row_data.get("notes", "")).strip()
                        if row_data.get("notes")
                        else None,
                        "chunking_strategy": self._infer_chunking_strategy(file_path),
                    }
                )

        logger.info(f"Loaded {len(documents)} document configurations")
        return documents

    def load_tools(self) -> list[dict[str, Any]]:
        """Load tool definitions from tools sheet.

        Returns:
            List of tool config dictionaries with keys:
            - name: unique identifier for the tool
            - description: human-readable description sent to LLM
            - parameters: JSON Schema for tool parameters
            - implementation: implementation reference (builtin:<name> or python:<module.func>)
            - enabled: whether the tool is available (default True)

        """
        if not self.has_tools_sheet():
            return []

        wb = load_workbook(self.workbook_path)
        ws = wb[self.TOOLS_SHEET]

        headers = []
        for col in range(1, ws.max_column + 1):
            header = ws.cell(row=1, column=col).value
            headers.append(str(header).strip() if header else f"col_{col}")

        tools = []
        for row_idx in range(2, ws.max_row + 1):
            row_data = {}
            has_content = False
            for col_idx, header in enumerate(headers, start=1):
                value = ws.cell(row=row_idx, column=col_idx).value
                row_data[header] = value
                if value is not None:
                    has_content = True

            if has_content and row_data.get("name"):
                enabled = row_data.get("enabled", True)
                if isinstance(enabled, str):
                    enabled = enabled.strip().lower() not in ("false", "0", "no")
                tools.append(
                    {
                        "name": str(row_data["name"]).strip(),
                        "description": str(row_data.get("description", "")).strip(),
                        "parameters": row_data.get("parameters", {}),
                        "implementation": str(row_data.get("implementation", "")).strip(),
                        "enabled": bool(enabled),
                    }
                )

        logger.info(f"Loaded {len(tools)} tool definitions")
        return tools

    def _infer_chunking_strategy(self, file_path: str) -> str:
        """Infer chunking strategy from file extension.

        Args:
            file_path: Path to the document file.

        Returns:
            Chunking strategy name: 'markdown', 'code', or 'recursive' (default).

        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".md":
            return "markdown"
        elif ext in {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".c",
            ".cpp",
            ".h",
            ".rb",
            ".php",
            ".swift",
            ".kt",
        }:
            return "code"
        else:
            return "recursive"

    def parse_history_string(self, history_str: Any) -> list[str] | None:  # noqa: ANN401
        """Parse history string like '["a", "b"]' into list.

        Handles smart quotes (curly quotes) by normalizing them to ASCII quotes
        before parsing. This allows users to copy/paste from Word, Google Docs, etc.
        """
        if not history_str:
            return None

        if isinstance(history_str, list):
            return history_str

        s = str(history_str).strip()

        quote_map = {
            0x201C: 0x22,
            0x201D: 0x22,
            0x2018: 0x27,
            0x2019: 0x27,
            0x201E: 0x22,
            0x201F: 0x22,
        }
        s = s.translate(quote_map)

        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(item).strip().strip("\"'") for item in parsed]
            except json.JSONDecodeError:
                pass

            inner = s[1:-1]
            items = re.findall(r'["\']([^"\']+)["\']', inner)
            if items:
                return items

            items = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
            if items:
                return items

        return [s.strip().strip("\"'")]

    def write_results(self, results: list[dict[str, Any]], sheet_name: str) -> str:
        """Write execution results to a new sheet."""
        wb = load_workbook(self.workbook_path)

        if sheet_name in wb.sheetnames:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            sheet_name = f"results_{timestamp}"

        ws = wb.create_sheet(title=sheet_name)

        for col_idx, header in enumerate(self.RESULTS_HEADERS, start=1):
            ws.cell(row=1, column=col_idx, value=header)

        for row_idx, result in enumerate(results, start=2):
            ws.cell(row=row_idx, column=1, value=result.get("batch_id"))
            ws.cell(row=row_idx, column=2, value=result.get("batch_name"))
            ws.cell(row=row_idx, column=3, value=result.get("sequence"))
            ws.cell(row=row_idx, column=4, value=result.get("prompt_name"))
            ws.cell(row=row_idx, column=5, value=result.get("prompt"))
            ws.cell(row=row_idx, column=6, value=result.get("resolved_prompt"))

            history = result.get("history")
            history_str = json.dumps(history) if history else ""
            ws.cell(row=row_idx, column=7, value=history_str)

            ws.cell(row=row_idx, column=8, value=result.get("client"))
            ws.cell(row=row_idx, column=9, value=result.get("condition"))
            ws.cell(row=row_idx, column=10, value=result.get("condition_result"))
            ws.cell(row=row_idx, column=11, value=result.get("condition_error"))
            response = result.get("response")
            if isinstance(response, list | dict):
                response = json.dumps(response)
            ws.cell(row=row_idx, column=12, value=response)
            ws.cell(row=row_idx, column=13, value=result.get("status"))
            ws.cell(row=row_idx, column=14, value=result.get("attempts"))
            ws.cell(row=row_idx, column=15, value=result.get("error"))

            references = result.get("references")
            references_str = json.dumps(references) if references else ""
            ws.cell(row=row_idx, column=16, value=references_str)

            semantic_query = result.get("semantic_query")
            ws.cell(row=row_idx, column=17, value=semantic_query if semantic_query else "")

            semantic_filter = result.get("semantic_filter")
            ws.cell(row=row_idx, column=18, value=semantic_filter if semantic_filter else "")

            query_expansion = result.get("query_expansion")
            ws.cell(row=row_idx, column=19, value=query_expansion if query_expansion else "")

            rerank = result.get("rerank")
            ws.cell(row=row_idx, column=20, value=rerank if rerank else "")

            agent_mode = result.get("agent_mode")
            ws.cell(row=row_idx, column=21, value=agent_mode if agent_mode else "")

            tool_calls = result.get("tool_calls")
            tool_calls_str = json.dumps(tool_calls) if tool_calls else ""
            ws.cell(row=row_idx, column=22, value=tool_calls_str)

            total_rounds = result.get("total_rounds")
            ws.cell(row=row_idx, column=23, value=total_rounds if total_rounds else "")

            total_llm_calls = result.get("total_llm_calls")
            ws.cell(row=row_idx, column=24, value=total_llm_calls if total_llm_calls else "")

        self.formatter.apply_formatting(ws, "results")

        wb.save(self.workbook_path)
        logger.info(f"Results written to sheet: {sheet_name}")
        return sheet_name

    def write_batch_results(
        self,
        results: list[dict[str, Any]],
        batch_name: str,
        base_sheet_name: str = "results",
    ) -> str:
        """Write results for a single batch to a separate sheet."""
        wb = load_workbook(self.workbook_path)

        sheet_name = f"{base_sheet_name}_{batch_name}"
        original_name = sheet_name
        counter = 1
        while sheet_name in wb.sheetnames:
            sheet_name = f"{original_name}_{counter}"
            counter += 1

        ws = wb.create_sheet(title=sheet_name)

        for col_idx, header in enumerate(self.RESULTS_HEADERS, start=1):
            ws.cell(row=1, column=col_idx, value=header)

        for row_idx, result in enumerate(results, start=2):
            ws.cell(row=row_idx, column=1, value=result.get("batch_id"))
            ws.cell(row=row_idx, column=2, value=result.get("batch_name"))
            ws.cell(row=row_idx, column=3, value=result.get("sequence"))
            ws.cell(row=row_idx, column=4, value=result.get("prompt_name"))
            ws.cell(row=row_idx, column=5, value=result.get("prompt"))
            ws.cell(row=row_idx, column=6, value=result.get("resolved_prompt"))

            history = result.get("history")
            history_str = json.dumps(history) if history else ""
            ws.cell(row=row_idx, column=7, value=history_str)

            ws.cell(row=row_idx, column=8, value=result.get("client"))
            ws.cell(row=row_idx, column=9, value=result.get("condition"))
            ws.cell(row=row_idx, column=10, value=result.get("condition_result"))
            ws.cell(row=row_idx, column=11, value=result.get("condition_error"))
            response = result.get("response")
            if isinstance(response, list | dict):
                response = json.dumps(response)
            ws.cell(row=row_idx, column=12, value=response)
            ws.cell(row=row_idx, column=13, value=result.get("status"))
            ws.cell(row=row_idx, column=14, value=result.get("attempts"))
            ws.cell(row=row_idx, column=15, value=result.get("error"))

            references = result.get("references")
            references_str = json.dumps(references) if references else ""
            ws.cell(row=row_idx, column=16, value=references_str)

            semantic_query = result.get("semantic_query")
            ws.cell(row=row_idx, column=17, value=semantic_query if semantic_query else "")

            semantic_filter = result.get("semantic_filter")
            ws.cell(row=row_idx, column=18, value=semantic_filter if semantic_filter else "")

            query_expansion = result.get("query_expansion")
            ws.cell(row=row_idx, column=19, value=query_expansion if query_expansion else "")

            rerank = result.get("rerank")
            ws.cell(row=row_idx, column=20, value=rerank if rerank else "")

            agent_mode = result.get("agent_mode")
            ws.cell(row=row_idx, column=21, value=agent_mode if agent_mode else "")

            tool_calls = result.get("tool_calls")
            tool_calls_str = json.dumps(tool_calls) if tool_calls else ""
            ws.cell(row=row_idx, column=22, value=tool_calls_str)

            total_rounds = result.get("total_rounds")
            ws.cell(row=row_idx, column=23, value=total_rounds if total_rounds else "")

            total_llm_calls = result.get("total_llm_calls")
            ws.cell(row=row_idx, column=24, value=total_llm_calls if total_llm_calls else "")

        ws.column_dimensions["A"].width = 10
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 18
        ws.column_dimensions["E"].width = 50
        ws.column_dimensions["F"].width = 60
        ws.column_dimensions["G"].width = 30
        ws.column_dimensions["H"].width = 15
        ws.column_dimensions["I"].width = 40
        ws.column_dimensions["J"].width = 15
        ws.column_dimensions["K"].width = 25
        ws.column_dimensions["L"].width = 60
        ws.column_dimensions["M"].width = 10
        ws.column_dimensions["N"].width = 10
        ws.column_dimensions["O"].width = 40
        ws.column_dimensions["P"].width = 30
        ws.column_dimensions["Q"].width = 30
        ws.column_dimensions["R"].width = 15
        ws.column_dimensions["S"].width = 18
        ws.column_dimensions["T"].width = 10
        ws.column_dimensions["U"].width = 12
        ws.column_dimensions["V"].width = 50
        ws.column_dimensions["W"].width = 14
        ws.column_dimensions["X"].width = 16

        wb.save(self.workbook_path)
        logger.info(f"Batch results written to sheet: {sheet_name}")
        return sheet_name
