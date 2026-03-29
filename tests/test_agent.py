# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT

"""Tests for agent module: agent_result, tool_registry, agent_loop."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.agent.agent_loop import AgentLoop
from src.agent.agent_result import AgentResult, ToolCallRecord
from src.FFAIClientBase import FFAIClientBase
from src.orchestrator.tool_registry import ToolDefinition, ToolRegistry


class TestToolCallRecord:
    def test_to_dict(self):
        record = ToolCallRecord(
            round=1,
            tool_name="rag_search",
            tool_call_id="tc_123",
            arguments={"query": "test"},
            result="found 3 docs",
            duration_ms=150.5,
        )
        d = record.to_dict()
        assert d["round"] == 1
        assert d["tool_name"] == "rag_search"
        assert d["tool_call_id"] == "tc_123"
        assert d["arguments"] == {"query": "test"}
        assert d["error"] is None

    def test_from_dict(self):
        data = {
            "round": 2,
            "tool_name": "calculate",
            "tool_call_id": "tc_456",
            "arguments": {"expression": "2+2"},
            "result": "4",
            "duration_ms": 10.0,
            "error": None,
        }
        record = ToolCallRecord.from_dict(data)
        assert record.round == 2
        assert record.tool_name == "calculate"

    def test_roundtrip(self):
        original = ToolCallRecord(
            round=3,
            tool_name="http_get",
            tool_call_id="tc_789",
            arguments={"url": "https://example.com"},
            result="<html>...</html>",
            duration_ms=500.0,
            error="timeout",
        )
        restored = ToolCallRecord.from_dict(original.to_dict())
        assert restored.round == original.round
        assert restored.error == original.error

    def test_defaults(self):
        record = ToolCallRecord(round=1, tool_name="test")
        assert record.tool_call_id == ""
        assert record.arguments == {}
        assert record.result == ""
        assert record.duration_ms == 0.0
        assert record.error is None


class TestAgentResult:
    def test_basic_properties(self):
        result = AgentResult(
            response="final answer",
            tool_calls=[ToolCallRecord(round=1, tool_name="rag_search")],
            total_rounds=2,
            total_llm_calls=3,
            status="success",
        )
        assert result.tool_calls_count == 1
        assert result.last_tool_name == "rag_search"
        assert len(result.failed_tool_calls) == 0

    def test_failed_tool_calls(self):
        result = AgentResult(
            response="",
            tool_calls=[
                ToolCallRecord(round=1, tool_name="rag_search", error=None),
                ToolCallRecord(round=2, tool_name="calculate", error="division by zero"),
            ],
        )
        assert result.tool_calls_count == 2
        assert len(result.failed_tool_calls) == 1

    def test_empty_tool_calls(self):
        result = AgentResult(response="direct answer")
        assert result.tool_calls_count == 0
        assert result.last_tool_name == ""

    def test_to_dict_from_dict_roundtrip(self):
        original = AgentResult(
            response="test",
            tool_calls=[ToolCallRecord(round=1, tool_name="calculate")],
            total_rounds=1,
            total_llm_calls=2,
            status="success",
        )
        restored = AgentResult.from_dict(original.to_dict())
        assert restored.response == original.response
        assert len(restored.tool_calls) == 1

    def test_defaults(self):
        result = AgentResult()
        assert result.response == ""
        assert result.tool_calls == []
        assert result.status == "success"
        assert result.tool_calls_count == 0
        assert result.last_tool_name == ""

    def test_valid_statuses(self):
        assert "success" in AgentResult.VALID_STATUSES
        assert "failed" in AgentResult.VALID_STATUSES
        assert "max_rounds_exceeded" in AgentResult.VALID_STATUSES


class TestToolDefinition:
    def test_to_openai_tool(self):
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {"input": {"type": "string"}}},
        )
        schema = tool.to_openai_tool()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"

    def test_from_dict_json_string_parameters(self):
        tool = ToolDefinition.from_dict(
            {
                "name": "calc",
                "description": "Calculator",
                "parameters": '{"type": "object", "properties": {"expr": {"type": "string"}}}',
            }
        )
        assert tool.parameters["type"] == "object"

    def test_from_dict_invalid_parameters(self):
        tool = ToolDefinition.from_dict(
            {
                "name": "broken",
                "description": "Broken params",
                "parameters": "not json",
            }
        )
        assert tool.parameters == {"type": "object", "properties": {}}

    def test_from_dict_none_parameters(self):
        tool = ToolDefinition.from_dict(
            {
                "name": "no_params",
                "description": "No params",
                "parameters": None,
            }
        )
        assert tool.parameters == {}

    def test_from_dict_missing_parameters(self):
        tool = ToolDefinition.from_dict(
            {
                "name": "missing_params",
                "description": "Missing params",
            }
        )
        assert tool.parameters == {}

    def test_roundtrip(self):
        original = ToolDefinition(
            name="test",
            description="Test",
            parameters={"type": "object", "properties": {}},
            implementation="builtin:rag_search",
            enabled=False,
        )
        restored = ToolDefinition.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.implementation == original.implementation
        assert restored.enabled == original.enabled


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = ToolDefinition(name="my_tool", description="Test tool")
        registry.register(tool)
        assert registry.has_tool("my_tool")
        assert registry.get_tool("my_tool") == tool

    def test_register_duplicate_raises(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="dup", description="First"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(ToolDefinition(name="dup", description="Second"))

    def test_get_missing_tool_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="not found"):
            registry.get_tool("missing")

    def test_get_tools_schema_filters(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="a", description="A"))
        registry.register(ToolDefinition(name="b", description="B"))
        schemas = registry.get_tools_schema(["a", "c"])
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "a"

    def test_get_tools_schema_respects_enabled(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="on", description="On", enabled=True))
        registry.register(ToolDefinition(name="off", description="Off", enabled=False))
        schemas = registry.get_tools_schema(["on", "off"])
        assert len(schemas) == 1

    def test_execute_with_registered_executor(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="echo", description="Echo"))
        registry.register_executor("echo", lambda args: json.dumps(args))
        result = registry.execute_tool("echo", {"msg": "hello"})
        assert json.loads(result)["msg"] == "hello"

    def test_execute_missing_tool_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.execute_tool("missing", {})

    def test_execute_disabled_tool_raises(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="off", description="Off", enabled=False))
        with pytest.raises(RuntimeError, match="disabled"):
            registry.execute_tool("off", {})

    def test_executor_not_found_raises(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="noimpl", description="No impl"))
        with pytest.raises(RuntimeError, match="No executor found"):
            registry.execute_tool("noimpl", {})

    def test_register_executor_for_unknown_tool_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="unknown tool"):
            registry.register_executor("ghost", lambda args: "ghost")

    def test_get_enabled_names(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="z", description="Z", enabled=True))
        registry.register(ToolDefinition(name="a", description="A", enabled=False))
        assert registry.get_enabled_names() == ["z"]

    def test_executor_replacement(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="test", description="Test"))
        registry.register_executor("test", lambda args: "first")
        registry.register_executor("test", lambda args: "second")
        assert registry.execute_tool("test", {}) == "second"

    def test_execute_non_string_result(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="dict", description="Dict"))
        registry.register_executor("dict", lambda args: {"key": "value"})
        result = registry.execute_tool("dict", {})
        assert isinstance(result, str)

    def test_execute_tool_error_propagates(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="err", description="Err"))
        registry.register_executor("err", lambda args: (_ for _ in ()).throw(ValueError("boom")))
        with pytest.raises(RuntimeError, match="boom"):
            registry.execute_tool("err", {})

    def test_empty_implementation(self):
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="noimpl", description="N", implementation=""))
        with pytest.raises(RuntimeError, match="No executor found"):
            registry.execute_tool("noimpl", {})

    def test_register_executor_none_does_not_break_builtin_resolution(self):
        """Registering a custom executor should override builtin, but builtin still works if not registered."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="calculate", description="Calc", implementation="builtin:calculate")
        )
        registry.register_executor("calculate", lambda args: "builtin result")
        result = registry.execute_tool("calculate", {"expression": "2+2"})
        assert result == "builtin result"

    def test_builtin_resolution_works_without_explicit_executor(self):
        """Builtin tools should work via implementation field without register_executor."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="calculate",
                description="Calc",
                implementation="builtin:calculate",
                enabled=True,
            )
        )
        result = registry.execute_tool("calculate", {"expression": "2+2"})
        assert "4" in result

    def test_python_implementation_resolved_without_executor_registration(self):
        """Tools with python: implementation should resolve without explicit executor."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="json_dumps",
                description="JSON dumps",
                implementation="python:json.dumps",
                enabled=True,
            )
        )
        result = registry.execute_tool("json_dumps", {"obj": [1, 2, 3]})
        assert json.loads(result) == {"obj": [1, 2, 3]}


class MockClient(FFAIClientBase):
    """Mock client for testing AgentLoop."""

    model = "mock"
    system_instructions = "You are a test assistant."

    def __init__(self):
        self.chat_history: list[dict[str, Any]] = []
        self._next_response_list: list[str] = []
        self._queued_tool_calls: list[list[dict] | None] = []

    def generate_response(self, prompt: str, **kwargs) -> str:
        if not self._next_response:
            return ""
        response_text = self._next_response.pop(0)
        tool_calls = self._queued_tool_calls.pop(0) if self._queued_tool_calls else None

        self.chat_history.append({"role": "user", "content": prompt})
        msg: dict[str, Any] = {"role": "assistant", "content": response_text}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.chat_history.append(msg)

        return response_text

    def clear_conversation(self) -> None:
        self.chat_history = []

    def get_conversation_history(self) -> list[dict[str, Any]]:
        return list(self.chat_history)

    def set_conversation_history(self, history: list[dict[str, Any]]) -> None:
        self.chat_history = list(history)

    def clone(self) -> MockClient:
        return MockClient()

    def queue_response(self, text: str, tool_calls=None):
        self._next_response_list.append(text)
        self._queued_tool_calls.append(tool_calls)

    @property
    def _next_response(self):
        return getattr(self, "_next_response_list", [])

    @_next_response.setter
    def _next_response(self, value):
        self._next_response_list = value


def test_add_tool_result_default_on_base_client():
    """Default add_tool_result on FFAIClientBase should append to conversation history."""
    client = MockClient()
    client.chat_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    client.add_tool_result("tc_base", "base result")

    history = client.get_conversation_history()
    assert len(history) == 3
    assert history[-1]["role"] == "tool"
    assert history[-1]["tool_call_id"] == "tc_base"
    assert history[-1]["content"] == "base result"


def test_add_tool_result_empty_history_on_base_client():
    """add_tool_result should work with empty conversation history."""
    client = MockClient()
    client.chat_history = []

    client.add_tool_result("tc_empty", "result")

    history = client.get_conversation_history()
    assert len(history) == 1
    assert history[0]["role"] == "tool"


class TestAgentLoop:
    def test_no_tools_available(self):
        client = MockClient()
        client.queue_response("direct answer")
        registry = ToolRegistry()
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test prompt", tools=["nonexistent"])
        assert result.status == "success"
        assert result.response == "direct answer"
        assert result.total_llm_calls == 1
        assert result.tool_calls_count == 0

    def test_single_round_no_tool_calls(self):
        client = MockClient()
        client.queue_response("final answer", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="rag_search", description="Search"))
        registry.register_executor("rag_search", lambda args: "results")
        loop = AgentLoop(client, registry, max_rounds=5)
        result = loop.execute("search for X", tools=["rag_search"])
        assert result.status == "success"
        assert result.response == "final answer"
        assert result.total_rounds == 1
        assert result.tool_calls_count == 0

    def test_two_rounds_with_tool_call(self):
        client = MockClient()
        client.queue_response(
            "Let me search",
            tool_calls=[
                {
                    "id": "tc_1",
                    "function": {"name": "rag_search", "arguments": '{"query": "test"}'},
                },
            ],
        )
        client.queue_response("Based on search, here is the answer", tool_calls=None)
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="rag_search",
                description="Search",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            )
        )
        registry.register_executor("rag_search", lambda args: json.dumps({"results": ["doc1"]}))
        loop = AgentLoop(client, registry, max_rounds=5)
        result = loop.execute("search for X", tools=["rag_search"])
        assert result.status == "success"
        assert result.total_rounds == 2
        assert result.total_llm_calls == 2
        assert result.tool_calls_count == 1
        assert result.tool_calls[0].tool_name == "rag_search"
        assert result.tool_calls[0].round == 1
        user_messages = [m for m in client.chat_history if m.get("role") == "user"]
        assert user_messages[1]["content"] == (
            "Continue using the tool results to answer the original request."
        )

    def test_second_round_uses_continue_prompt_instead_of_empty_prompt(self):
        client = MockClient()
        client.queue_response(
            "Let me calculate",
            tool_calls=[
                {
                    "id": "tc_1",
                    "function": {"name": "calculate", "arguments": '{"expression": "2 + 2"}'},
                },
            ],
        )
        client.queue_response("The answer is 4", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="calculate", description="Calc"))
        registry.register_executor("calculate", lambda args: json.dumps({"result": 4}))
        loop = AgentLoop(client, registry, max_rounds=3)

        result = loop.execute("solve this", tools=["calculate"])

        assert result.status == "success"
        assert result.response == "The answer is 4"
        user_messages = [m for m in client.chat_history if m.get("role") == "user"]
        assert user_messages[-1]["content"] == (
            "Continue using the tool results to answer the original request."
        )

    def test_max_rounds_exceeded(self):
        client = MockClient()
        for i in range(10):
            client.queue_response(
                "searching...",
                tool_calls=[
                    {
                        "id": f"tc_{i}",
                        "function": {"name": "rag_search", "arguments": '{"query": "test"}'},
                    },
                ],
            )
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="rag_search", description="Search"))
        registry.register_executor("rag_search", lambda args: "results")
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("keep searching", tools=["rag_search"])
        assert result.status == "max_rounds_exceeded"
        assert result.total_rounds == 3

    def test_tool_error_continue(self):
        client = MockClient()
        client.queue_response(
            "calculating",
            tool_calls=[
                {
                    "id": "tc_err",
                    "function": {"name": "calculate", "arguments": '{"expression": "bad"}'},
                },
            ],
        )
        client.queue_response("error recovered, here is answer", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="calculate", description="Calc"))
        registry.register_executor(
            "calculate", lambda args: (_ for _ in ()).throw(RuntimeError("bad expr"))
        )
        loop = AgentLoop(client, registry, max_rounds=3, continue_on_tool_error=True)
        result = loop.execute("calculate", tools=["calculate"])
        assert result.status == "success"
        assert result.tool_calls_count == 1
        assert result.tool_calls[0].error is not None

    def test_tool_error_abort(self):
        client = MockClient()
        client.queue_response(
            "calculating",
            tool_calls=[
                {"id": "tc_err", "function": {"name": "calculate", "arguments": "{}"}},
            ],
        )
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="calculate", description="Calc"))
        registry.register_executor(
            "calculate", lambda args: (_ for _ in ()).throw(RuntimeError("Division by zero"))
        )
        loop = AgentLoop(client, registry, max_rounds=3, continue_on_tool_error=False)
        result = loop.execute("test", tools=["calculate"])
        assert result.status == "failed"
        assert "Division by zero" in result.tool_calls[0].error

    def test_llm_failure_first_round(self):
        client = MockClient()
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="rag_search", description="Search"))
        client.generate_response = MagicMock(side_effect=Exception("API error"))
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test", tools=["rag_search"])
        assert result.status == "failed"
        assert result.total_llm_calls == 1

    def test_multiple_tool_calls_single_round(self):
        client = MockClient()
        client.queue_response(
            "Using tools",
            tool_calls=[
                {
                    "id": "tc_a",
                    "function": {"name": "rag_search", "arguments": '{"query": "first"}'},
                },
                {
                    "id": "tc_b",
                    "function": {"name": "calculate", "arguments": '{"expression": "2+2"}'},
                },
            ],
        )
        client.queue_response("Final answer", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="rag_search", description="Search"))
        registry.register_executor("rag_search", lambda args: json.dumps({"results": ["doc1"]}))
        registry.register(ToolDefinition(name="calculate", description="Calc"))
        registry.register_executor("calculate", lambda args: json.dumps({"result": 4}))
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test", tools=["rag_search", "calculate"])
        assert result.status == "success"
        assert result.tool_calls_count == 2
        assert result.tool_calls[0].tool_name == "rag_search"
        assert result.tool_calls[1].tool_name == "calculate"

    def test_empty_tool_list(self):
        client = MockClient()
        client.queue_response("simple answer")
        registry = ToolRegistry()
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test", tools=[])
        assert result.status == "success"
        assert result.response == "simple answer"
        assert result.tool_calls_count == 0

    def test_max_rounds_one(self):
        client = MockClient()
        client.queue_response(
            "searching...",
            tool_calls=[
                {"id": "tc_1", "function": {"name": "rag_search", "arguments": "{}"}},
            ],
        )
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="rag_search", description="Search"))
        registry.register_executor("rag_search", lambda args: "results")
        loop = AgentLoop(client, registry, max_rounds=1)
        result = loop.execute("test", tools=["rag_search"])
        assert result.status == "max_rounds_exceeded"

    def test_tool_result_added_to_history(self):
        client = MockClient()
        client.queue_response(
            "searching",
            tool_calls=[
                {"id": "tc_1", "function": {"name": "search", "arguments": "{}"}},
            ],
        )
        client.queue_response("final")
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search"))
        registry.register_executor("search", lambda args: "found it")
        loop = AgentLoop(client, registry, max_rounds=3)
        loop.execute("test", tools=["search"])
        tool_msgs = [m for m in client.chat_history if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "tc_1"
        assert "found it" in tool_msgs[0]["content"]

    def test_invalid_json_arguments(self):
        client = MockClient()
        client.queue_response(
            "calculating",
            tool_calls=[
                {"id": "tc1", "function": {"name": "calculate", "arguments": "{invalid json"}},
            ],
        )
        client.queue_response("done", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="calculate", description="Calc"))
        registry.register_executor("calculate", lambda args: "0")
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test", tools=["calculate"])
        assert result.status == "success"
        assert result.tool_calls[0].arguments == {}

    def test_no_history_client(self):
        class NoHistoryClient(MockClient):
            def get_conversation_history(self):
                raise RuntimeError("no history")

        client = NoHistoryClient()
        client.queue_response(
            "no tools",
            tool_calls=[
                {"id": "tc1", "function": {"name": "search", "arguments": "{}"}},
            ],
        )
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search"))
        registry.register_executor("search", lambda args: "results")
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test", tools=["search"])
        assert result.tool_calls_count == 0

    def test_max_rounds_zero(self):
        client = MockClient()
        client.queue_response("answer")
        registry = ToolRegistry()
        loop = AgentLoop(client, registry, max_rounds=0)
        result = loop.execute("test", tools=[])
        assert result.status == "success"
        assert result.response == "answer"

    def test_kwargs_passed_to_generate(self):
        client = MockClient()
        client.queue_response("answer")
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search"))
        loop = AgentLoop(client, registry, max_rounds=3)
        call_kwargs: dict[str, Any] = {}
        original_generate = client.generate_response

        def capture(prompt, **kwargs):
            call_kwargs.update(kwargs)
            return original_generate(prompt, **kwargs)

        client.generate_response = capture
        result = loop.execute("test", tools=["search"], temperature=0.5, max_tokens=100)
        assert result.status == "success"
        assert call_kwargs.get("temperature") == 0.5
        assert call_kwargs.get("max_tokens") == 100
        assert "prompt_name" not in call_kwargs
        assert "history" not in call_kwargs

    def test_prompt_name_and_history_are_filtered_before_llm_call(self):
        client = MockClient()
        client.queue_response("answer")
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search"))
        loop = AgentLoop(client, registry, max_rounds=3)
        call_kwargs: dict[str, Any] = {}
        original_generate = client.generate_response

        def capture(prompt, **kwargs):
            call_kwargs.update(kwargs)
            return original_generate(prompt, **kwargs)

        client.generate_response = capture
        result = loop.execute(
            "test",
            tools=["search"],
            prompt_name="agent_test",
            history=["foo"],
            temperature=0.2,
        )

        assert result.status == "success"
        assert call_kwargs.get("temperature") == 0.2
        assert "prompt_name" not in call_kwargs
        assert "history" not in call_kwargs

    def test_tool_timeout(self):
        import time

        client = MockClient()
        client.queue_response(
            "calculating",
            tool_calls=[
                {"id": "tc_slow", "function": {"name": "slow_tool", "arguments": "{}"}},
            ],
        )
        client.queue_response("done", tool_calls=None)

        def slow_tool(args):
            time.sleep(2)
            return "result"

        registry = ToolRegistry()
        registry.register(ToolDefinition(name="slow_tool", description="Slow"))
        registry.register_executor("slow_tool", slow_tool)
        loop = AgentLoop(client, registry, max_rounds=3, tool_timeout=0.5)
        result = loop.execute("test", tools=["slow_tool"])
        assert result.status == "success"
        assert result.tool_calls_count == 1
        assert (
            "timed out" in result.tool_calls[0].error.lower()
            or result.tool_calls[0].error is not None
        )

    def test_no_dead_regex_import(self):
        import src.agent.agent_loop as mod

        assert not hasattr(mod, "_TOOL_CALLS_PATTERN") or mod._TOOL_CALLS_PATTERN is None


class TestValidationResultFields:
    def test_prompt_result_validation_defaults(self):
        from src.orchestrator.results.result import PromptResult

        result = PromptResult(sequence=1)
        assert result.validation_passed is None
        assert result.validation_attempts is None
        assert result.validation_critique is None

    def test_prompt_result_validation_in_to_dict_when_set(self):
        from src.orchestrator.results.result import PromptResult

        result = PromptResult(
            sequence=1,
            agent_mode=True,
            validation_passed=True,
            validation_attempts=1,
        )
        d = result.to_dict()
        assert d["validation_passed"] is True
        assert d["validation_attempts"] == 1
        assert d["validation_critique"] is None

    def test_prompt_result_validation_not_in_to_dict_when_unset(self):
        from src.orchestrator.results.result import PromptResult

        result = PromptResult(sequence=1, agent_mode=True)
        d = result.to_dict()
        assert "validation_passed" not in d
        assert "validation_attempts" not in d

    def test_prompt_result_validation_from_dict(self):
        from src.orchestrator.results.result import PromptResult

        data = {
            "sequence": 1,
            "validation_passed": False,
            "validation_attempts": 3,
            "validation_critique": "Response too short",
        }
        result = PromptResult.from_dict(data)
        assert result.validation_passed is False
        assert result.validation_attempts == 3
        assert result.validation_critique == "Response too short"

    def test_prompt_result_validation_roundtrip(self):
        from src.orchestrator.results.result import PromptResult

        original = PromptResult(
            sequence=5,
            agent_mode=True,
            validation_passed=False,
            validation_attempts=2,
            validation_critique="Missing numeric value",
        )
        restored = PromptResult.from_dict(original.to_dict())
        assert restored.validation_passed == original.validation_passed
        assert restored.validation_attempts == original.validation_attempts
        assert restored.validation_critique == original.validation_critique


class TestValidationBuilder:
    def test_with_validation_result_pass(self):
        from src.orchestrator.results.builder import ResultBuilder

        builder = ResultBuilder({"sequence": 1, "prompt": "test"})
        builder.with_validation_result(passed=True, attempts=1)
        result = builder.build()
        assert result.validation_passed is True
        assert result.validation_attempts == 1
        assert result.validation_critique is None

    def test_with_validation_result_fail(self):
        from src.orchestrator.results.builder import ResultBuilder

        builder = ResultBuilder({"sequence": 1, "prompt": "test"})
        builder.with_validation_result(passed=False, attempts=3, critique="Must be numeric")
        result = builder.build()
        assert result.validation_passed is False
        assert result.validation_attempts == 3
        assert result.validation_critique == "Must be numeric"

    def test_with_validation_result_chains(self):
        from src.orchestrator.results.builder import ResultBuilder

        builder = ResultBuilder({"sequence": 1, "prompt": "test"})
        result = builder.with_validation_result(passed=True, attempts=1).build()
        assert result.validation_passed is True

    def test_with_validation_result_in_dict(self):
        from src.orchestrator.results.builder import ResultBuilder

        builder = ResultBuilder({"sequence": 1, "prompt": "test"})
        builder.with_validation_result(passed=True, attempts=2)
        d = builder.build_dict()
        assert d["validation_passed"] is True
        assert d["validation_attempts"] == 2


class TestValidationConfig:
    def test_agent_validation_config_defaults(self):
        from src.config import AgentValidationConfig

        config = AgentValidationConfig()
        assert config.enabled is True
        assert config.max_retries == 2

    def test_agent_config_has_validation(self):
        from src.config import AgentConfig

        config = AgentConfig()
        assert hasattr(config, "validation")
        assert config.validation.enabled is True
        assert config.validation.max_retries == 2


class TestValidationWorkbookParsing:
    def test_prompts_headers_include_validation(self):
        from src.orchestrator.workbook_parser import WorkbookParser

        parser = WorkbookParser.__new__(WorkbookParser)
        assert "validation_prompt" in WorkbookParser.PROMPTS_HEADERS
        assert "max_validation_retries" in WorkbookParser.PROMPTS_HEADERS

    def test_results_headers_include_validation(self):
        from src.orchestrator.workbook_parser import WorkbookParser

        assert "validation_passed" in WorkbookParser.RESULTS_HEADERS
        assert "validation_attempts" in WorkbookParser.RESULTS_HEADERS
        assert "validation_critique" in WorkbookParser.RESULTS_HEADERS

    def test_sample_prompt_spec_includes_validation_columns(self):
        from scripts.sample_workbooks import DEFAULT_PROMPT_HEADERS, PromptSpec

        prompt = PromptSpec(
            sequence=1,
            name="validated",
            prompt="Use calculate to compute 9.",
            validation_prompt="The result must be 9.",
            max_validation_retries=2,
        )

        row = prompt.to_row()
        assert "validation_prompt" in DEFAULT_PROMPT_HEADERS
        assert "max_validation_retries" in DEFAULT_PROMPT_HEADERS
        assert row["validation_prompt"] == "The result must be 9."
        assert row["max_validation_retries"] == 2

    def test_sample_prompt_spec_includes_notes(self):
        from scripts.sample_workbooks import DEFAULT_PROMPT_HEADERS, PromptSpec

        prompt = PromptSpec(
            sequence=1,
            name="annotated",
            prompt="Say hello",
            notes="Helpful note for workbook users.",
        )

        row = prompt.to_row()
        assert "notes" in DEFAULT_PROMPT_HEADERS
        assert row["notes"] == "Helpful note for workbook users."


class TestValidationConditionEvaluator:
    def test_validation_passed_true(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        evaluator = ConditionEvaluator(results_by_name={})
        result = {
            "validation_passed": True,
            "validation_attempts": 1,
        }
        value = evaluator._compute_property(result, "validation_passed", True)
        assert value is True

    def test_validation_passed_false(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        evaluator = ConditionEvaluator(results_by_name={})
        result = {
            "validation_passed": False,
            "validation_attempts": 3,
        }
        value = evaluator._compute_property(result, "validation_passed", False)
        assert value is False

    def test_validation_passed_none(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        evaluator = ConditionEvaluator(results_by_name={})
        result = {"validation_passed": None}
        value = evaluator._compute_property(result, "validation_passed", None)
        assert value is None

    def test_validation_attempts(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        evaluator = ConditionEvaluator(results_by_name={})
        result = {"validation_attempts": 3}
        value = evaluator._compute_property(result, "validation_attempts", 3)
        assert value == 3

    def test_validation_attempts_none(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        evaluator = ConditionEvaluator(results_by_name={})
        result = {}
        value = evaluator._compute_property(result, "validation_attempts", None)
        assert value == 0

    def test_validation_condition_in_expression(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        evaluator = ConditionEvaluator(
            results_by_name={
                "my_prompt": {
                    "validation_passed": True,
                    "validation_attempts": 1,
                },
            }
        )
        assert evaluator.evaluate("{{my_prompt.validation_passed}} == True")
        assert evaluator.evaluate("{{my_prompt.validation_attempts}} == 1")

    def test_validation_failed_condition(self):
        from src.orchestrator.condition_evaluator import ConditionEvaluator

        evaluator = ConditionEvaluator(
            results_by_name={
                "my_prompt": {
                    "validation_passed": False,
                    "validation_attempts": 3,
                    "validation_critique": "Response too short",
                },
            }
        )
        result, error = evaluator.evaluate("{{my_prompt.validation_passed}} == True")
        assert not result
        result, error = evaluator.evaluate("{{my_prompt.validation_attempts}} >= 3")
        assert result


class TestValidationValidator:
    def test_validation_prompt_without_agent_mode_warns(self):
        from src.orchestrator.validation import OrchestratorValidator, ValidationResult

        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "test",
                    "prompt": "test prompt",
                    "agent_mode": False,
                    "validation_prompt": "Must be a number",
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        warnings = [
            e
            for e in result.errors
            if e.severity == "warning" and e.code == "VALIDATION_WITHOUT_AGENT"
        ]
        assert len(warnings) == 1

    def test_max_validation_retries_out_of_range(self):
        from src.orchestrator.validation import OrchestratorValidator, ValidationResult

        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "test",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": ["calculate"],
                    "validation_prompt": "Must be a number",
                    "max_validation_retries": 20,
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_INVALID_MAX_VALIDATION_RETRIES"]
        assert len(errors) == 1

    def test_max_validation_retries_valid(self):
        from src.orchestrator.validation import OrchestratorValidator, ValidationResult

        validator = OrchestratorValidator(
            prompts=[
                {
                    "sequence": 1,
                    "prompt_name": "test",
                    "prompt": "test",
                    "agent_mode": True,
                    "tools": ["calculate"],
                    "validation_prompt": "Must be a number",
                    "max_validation_retries": 3,
                },
            ],
            config={},
        )
        result = ValidationResult()
        validator._validate_agent_mode(result)
        errors = [e for e in result.errors if e.code == "AGENT_INVALID_MAX_VALIDATION_RETRIES"]
        assert len(errors) == 0
