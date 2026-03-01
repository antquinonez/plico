# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Excel workbook parser for prompt orchestration.

Provides utilities for validating, reading, and writing orchestrator workbooks
with config, prompts, data, clients, and documents sheets.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from ..config import get_config

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
        self._config = get_config()

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
    def CONFIG_FIELDS(self) -> list[tuple[str, str]]:
        defaults = self._config.workbook.defaults
        return [
            ("client_type", ""),
            ("model", defaults.model),
            ("api_key_env", defaults.api_key_env),
            ("max_retries", str(defaults.max_retries)),
            ("temperature", str(defaults.temperature)),
            ("max_tokens", str(defaults.max_tokens)),
            ("system_instructions", defaults.system_instructions),
            ("created_at", ""),
        ]

    @property
    def BATCH_CONFIG_FIELDS(self) -> list[tuple[str, str]]:
        batch = self._config.workbook.batch
        return [
            ("batch_mode", batch.mode),
            ("batch_output", batch.output),
            ("on_batch_error", batch.on_error),
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
    ]
    REQUIRED_PROMPTS_HEADERS = ["sequence", "prompt_name", "prompt", "history"]
    DOCUMENTS_HEADERS = [
        "reference_name",
        "common_name",
        "file_path",
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

    def create_template_workbook(
        self,
        with_data_sheet: bool = False,
        with_clients_sheet: bool = False,
        with_documents_sheet: bool = False,
    ) -> str:
        """Create a new workbook with template structure."""
        logger.info(f"Creating template workbook: {self.workbook_path}")

        wb = Workbook()

        ws_config = wb.active
        ws_config.title = self.CONFIG_SHEET
        ws_config["A1"] = "field"
        ws_config["B1"] = "value"

        all_config = list(self.CONFIG_FIELDS)
        if with_data_sheet:
            all_config.extend(self.BATCH_CONFIG_FIELDS)

        for idx, (field, default) in enumerate(all_config, start=2):
            ws_config[f"A{idx}"] = field
            if field == "created_at":
                ws_config[f"B{idx}"] = datetime.now().isoformat()
            else:
                ws_config[f"B{idx}"] = default

        ws_config.column_dimensions["A"].width = 20
        ws_config.column_dimensions["B"].width = 60

        ws_prompts = wb.create_sheet(title=self.PROMPTS_SHEET)
        for col_idx, header in enumerate(self.PROMPTS_HEADERS, start=1):
            ws_prompts.cell(row=1, column=col_idx, value=header)
            ws_prompts.column_dimensions[get_column_letter(col_idx)].width = max(
                15, len(header) + 5
            )

        ws_prompts.column_dimensions["C"].width = 50
        ws_prompts.column_dimensions["D"].width = 30
        ws_prompts.column_dimensions["E"].width = 15
        ws_prompts.column_dimensions["F"].width = 40
        ws_prompts.column_dimensions["G"].width = 30
        ws_prompts.column_dimensions["H"].width = 30

        if with_data_sheet:
            ws_data = wb.create_sheet(title=self.DATA_SHEET)
            ws_data["A1"] = "id"
            ws_data["B1"] = "batch_name"
            ws_data.column_dimensions["A"].width = 10
            ws_data.column_dimensions["B"].width = 30

        if with_clients_sheet:
            ws_clients = wb.create_sheet(title=self.CLIENTS_SHEET)
            for col_idx, header in enumerate(self.CLIENTS_HEADERS, start=1):
                ws_clients.cell(row=1, column=col_idx, value=header)
                ws_clients.column_dimensions[get_column_letter(col_idx)].width = max(
                    15, len(header) + 5
                )

        if with_documents_sheet:
            ws_documents = wb.create_sheet(title=self.DOCUMENTS_SHEET)
            for col_idx, header in enumerate(self.DOCUMENTS_HEADERS, start=1):
                ws_documents.cell(row=1, column=col_idx, value=header)
                ws_documents.column_dimensions[get_column_letter(col_idx)].width = max(
                    15, len(header) + 5
                )
            ws_documents.column_dimensions["C"].width = 50
            ws_documents.column_dimensions["D"].width = 40

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
        """Load configuration from config sheet."""
        wb = load_workbook(self.workbook_path)
        ws = wb[self.CONFIG_SHEET]

        config = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] and row[1] is not None:
                key = str(row[0]).strip()
                value = row[1]

                if key == "max_retries":
                    value = int(value)
                elif key == "temperature":
                    value = float(value)
                elif key == "max_tokens":
                    value = int(value)

                config[key] = value

        logger.debug(f"Loaded config: {config}")
        return config

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
            - notes: optional description

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
                documents.append(
                    {
                        "reference_name": str(row_data.get("reference_name", "")).strip(),
                        "common_name": str(row_data.get("common_name", "")).strip()
                        if row_data.get("common_name")
                        else row_data.get("reference_name", ""),
                        "file_path": str(row_data.get("file_path", "")).strip(),
                        "notes": str(row_data.get("notes", "")).strip()
                        if row_data.get("notes")
                        else None,
                    }
                )

        logger.info(f"Loaded {len(documents)} document configurations")
        return documents

    def parse_history_string(self, history_str: Any) -> list[str] | None:  # noqa: ANN401
        """Parse history string like '["a", "b"]' into list."""
        if not history_str:
            return None

        if isinstance(history_str, list):
            return history_str

        s = str(history_str).strip()

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

            history = result.get("history")
            history_str = json.dumps(history) if history else ""
            ws.cell(row=row_idx, column=6, value=history_str)

            ws.cell(row=row_idx, column=7, value=result.get("client"))
            ws.cell(row=row_idx, column=8, value=result.get("condition"))
            ws.cell(row=row_idx, column=9, value=result.get("condition_result"))
            ws.cell(row=row_idx, column=10, value=result.get("condition_error"))
            response = result.get("response")
            if isinstance(response, list | dict):
                response = json.dumps(response)
            ws.cell(row=row_idx, column=11, value=response)
            ws.cell(row=row_idx, column=12, value=result.get("status"))
            ws.cell(row=row_idx, column=13, value=result.get("attempts"))
            ws.cell(row=row_idx, column=14, value=result.get("error"))

            references = result.get("references")
            references_str = json.dumps(references) if references else ""
            ws.cell(row=row_idx, column=15, value=references_str)

            semantic_query = result.get("semantic_query")
            ws.cell(row=row_idx, column=16, value=semantic_query if semantic_query else "")

            semantic_filter = result.get("semantic_filter")
            ws.cell(row=row_idx, column=17, value=semantic_filter if semantic_filter else "")

            query_expansion = result.get("query_expansion")
            ws.cell(row=row_idx, column=18, value=query_expansion if query_expansion else "")

            rerank = result.get("rerank")
            ws.cell(row=row_idx, column=19, value=rerank if rerank else "")

        ws.column_dimensions["A"].width = 10
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 18
        ws.column_dimensions["E"].width = 50
        ws.column_dimensions["F"].width = 30
        ws.column_dimensions["G"].width = 15
        ws.column_dimensions["H"].width = 40
        ws.column_dimensions["I"].width = 15
        ws.column_dimensions["J"].width = 25
        ws.column_dimensions["K"].width = 60
        ws.column_dimensions["L"].width = 10
        ws.column_dimensions["M"].width = 10
        ws.column_dimensions["N"].width = 40
        ws.column_dimensions["O"].width = 30
        ws.column_dimensions["P"].width = 30
        ws.column_dimensions["Q"].width = 15
        ws.column_dimensions["R"].width = 18
        ws.column_dimensions["S"].width = 10

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

            history = result.get("history")
            history_str = json.dumps(history) if history else ""
            ws.cell(row=row_idx, column=6, value=history_str)

            ws.cell(row=row_idx, column=7, value=result.get("client"))
            ws.cell(row=row_idx, column=8, value=result.get("condition"))
            ws.cell(row=row_idx, column=9, value=result.get("condition_result"))
            ws.cell(row=row_idx, column=10, value=result.get("condition_error"))
            response = result.get("response")
            if isinstance(response, list | dict):
                response = json.dumps(response)
            ws.cell(row=row_idx, column=11, value=response)
            ws.cell(row=row_idx, column=12, value=result.get("status"))
            ws.cell(row=row_idx, column=13, value=result.get("attempts"))
            ws.cell(row=row_idx, column=14, value=result.get("error"))

            references = result.get("references")
            references_str = json.dumps(references) if references else ""
            ws.cell(row=row_idx, column=15, value=references_str)

            semantic_query = result.get("semantic_query")
            ws.cell(row=row_idx, column=16, value=semantic_query if semantic_query else "")

            semantic_filter = result.get("semantic_filter")
            ws.cell(row=row_idx, column=17, value=semantic_filter if semantic_filter else "")

            query_expansion = result.get("query_expansion")
            ws.cell(row=row_idx, column=18, value=query_expansion if query_expansion else "")

            rerank = result.get("rerank")
            ws.cell(row=row_idx, column=19, value=rerank if rerank else "")

        ws.column_dimensions["A"].width = 10
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 18
        ws.column_dimensions["E"].width = 50
        ws.column_dimensions["F"].width = 30
        ws.column_dimensions["G"].width = 15
        ws.column_dimensions["H"].width = 40
        ws.column_dimensions["I"].width = 15
        ws.column_dimensions["J"].width = 25
        ws.column_dimensions["K"].width = 60
        ws.column_dimensions["L"].width = 10
        ws.column_dimensions["M"].width = 10
        ws.column_dimensions["N"].width = 40
        ws.column_dimensions["O"].width = 30
        ws.column_dimensions["P"].width = 30
        ws.column_dimensions["Q"].width = 15
        ws.column_dimensions["R"].width = 18
        ws.column_dimensions["S"].width = 10

        wb.save(self.workbook_path)
        logger.info(f"Batch results written to sheet: {sheet_name}")
        return sheet_name
