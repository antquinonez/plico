# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""Integration tests for agent execution (requires API key)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.sample_workbooks import PromptSpec, WorkbookBuilder

from src.Clients.FFLiteLLMClient import FFLiteLLMClient
from src.orchestrator import ExcelOrchestrator


@pytest.fixture(scope="module")
def agent_workbook(tmp_path_factory):
    tools = [
        {
            "name": "calculate",
            "description": "Evaluate a mathematical expression safely.",
            "parameters": '{"type":"object","properties":{"expression":{"type":"string"}},"required":["expression"]}',
            "implementation": "builtin:calculate",
            "enabled": True,
        },
    ]

    prompts = [
        PromptSpec(1, "baseline", "What is 2+2?"),
        PromptSpec(
            2,
            "agent_calc",
            "Use the calculate tool to compute 12 * 8. Report the result.",
            agent_mode="true",
            tools='["calculate"]',
        ),
        PromptSpec(
            3,
            "agent_chain",
            "Use calculate to compute 10^2, then use it again to add 500 to that result.",
            agent_mode="true",
            tools='["calculate"]',
            max_tool_rounds=10,
        ),
    ]

    path = str(tmp_path_factory.mktemp("agent_test") / "test_agent.xlsx")
    builder = WorkbookBuilder(path)
    builder.add_config_sheet()
    builder.add_tools_sheet(tools)
    builder.add_prompts_sheet(prompts, include_extra_columns=True)
    builder.save()
    return path


@pytest.fixture(scope="module")
def client():
    api_key = os.environ.get("MISTRALSMALL_KEY") or os.environ.get("MISTRAL_KEY")
    if not api_key:
        pytest.skip("No Mistral API key available")
    return FFLiteLLMClient(model_string="mistral/mistral-small-latest", api_key=api_key)


@pytest.mark.integration
class TestAgentIntegration:
    def test_baseline_no_agent_mode(self, agent_workbook, client):
        orchestrator = ExcelOrchestrator(agent_workbook, client=client)
        orchestrator.run()
        assert len(orchestrator.results) >= 1
        baseline = [r for r in orchestrator.results if r.get("prompt_name") == "baseline"]
        assert len(baseline) == 1
        assert baseline[0]["status"] == "success"
        assert baseline[0].get("agent_mode") is not True

    def test_agent_single_tool(self, agent_workbook, client):
        orchestrator = ExcelOrchestrator(agent_workbook, client=client)
        orchestrator.run()
        agent_results = [r for r in orchestrator.results if r.get("prompt_name") == "agent_calc"]
        assert len(agent_results) == 1
        result = agent_results[0]
        assert result["status"] == "success"
        assert result.get("agent_mode") is True
        assert result.get("tool_calls") is not None
        assert len(result["tool_calls"]) >= 1
        assert result["tool_calls"][0]["tool_name"] == "calculate"
        assert result["total_rounds"] >= 2
        assert result["total_llm_calls"] >= 2

    def test_agent_multi_round(self, agent_workbook, client):
        orchestrator = ExcelOrchestrator(agent_workbook, client=client)
        orchestrator.run()
        chain_results = [r for r in orchestrator.results if r.get("prompt_name") == "agent_chain"]
        assert len(chain_results) == 1
        result = chain_results[0]
        assert result["status"] == "success"
        assert result.get("agent_mode") is True
        assert result.get("total_rounds") is not None
        assert result["total_rounds"] >= 2
