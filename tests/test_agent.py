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
        assert d == {
            "round": 1,
            "tool_name": "rag_search",
            "tool_call_id": "tc_123",
            "arguments": {"query": "test"},
            "result": "found 3 docs",
            "duration_ms": 150.5,
            "error": None,
        }

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
        assert record.tool_call_id == "tc_456"
        assert record.arguments == {"expression": "2+2"}
        assert record.result == "4"
        assert record.duration_ms == 10.0
        assert record.error is None

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
        assert restored == original

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
            response="test response",
            tool_calls=[
                ToolCallRecord(
                    round=1,
                    tool_name="calculate",
                    tool_call_id="tc_001",
                    arguments={"expr": "2+2"},
                    result="4",
                    duration_ms=12.3,
                )
            ],
            total_rounds=1,
            total_llm_calls=2,
            status="success",
        )
        restored = AgentResult.from_dict(original.to_dict())
        assert restored.response == "test response"
        assert restored.total_rounds == 1
        assert restored.total_llm_calls == 2
        assert restored.status == "success"
        assert len(restored.tool_calls) == 1
        assert restored.tool_calls[0] == ToolCallRecord(
            round=1,
            tool_name="calculate",
            tool_call_id="tc_001",
            arguments={"expr": "2+2"},
            result="4",
            duration_ms=12.3,
        )

    def test_defaults(self):
        result = AgentResult()
        assert result.response == ""
        assert result.tool_calls == []
        assert result.status == "success"
        assert result.tool_calls_count == 0
        assert result.last_tool_name == ""


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
        assert result == "{'key': 'value'}"

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

    def test_unknown_implementation_prefix(self):
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="custom",
                description="Custom",
                implementation="custom:my_tool",
            )
        )
        with pytest.raises(RuntimeError, match="No executor found"):
            registry.execute_tool("custom", {})

    def test_unknown_builtin_implementation(self):
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="x",
                description="X",
                implementation="builtin:nonexistent",
            )
        )
        with pytest.raises(RuntimeError, match="No executor found"):
            registry.execute_tool("x", {})

    def test_load_python_callable_invalid_path(self):
        assert ToolRegistry.load_python_callable("json") is None

    def test_load_python_callable_not_callable(self):
        assert ToolRegistry.load_python_callable("math.pi") is None

    def test_load_python_callable_nonexistent_module(self):
        assert ToolRegistry.load_python_callable("nonexistent_module.func") is None

    def test_load_python_callable_nonexistent_attribute(self):
        assert ToolRegistry.load_python_callable("json.nonexistent_func") is None


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
        assert "timed out" in result.tool_calls[0].error.lower()

    def test_no_dead_regex_import(self):
        import src.agent.agent_loop as mod

        assert not hasattr(mod, "_TOOL_CALLS_PATTERN") or mod._TOOL_CALLS_PATTERN is None

    def test_tool_result_truncated_at_10k_chars(self):
        long_result = "x" * 20000
        client = MockClient()
        client.queue_response(
            "searching",
            tool_calls=[
                {"id": "tc_1", "function": {"name": "search", "arguments": "{}"}},
            ],
        )
        client.queue_response("done", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search"))
        registry.register_executor("search", lambda args: long_result)
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test", tools=["search"])
        assert len(result.tool_calls[0].result) == 10000

    def test_dict_arguments_not_double_parsed(self):
        """Tool calls with dict arguments (already parsed) should not be JSON-decoded again."""
        client = MockClient()
        client.queue_response(
            "searching",
            tool_calls=[
                {
                    "id": "tc_1",
                    "function": {
                        "name": "search",
                        "arguments": {"query": "already a dict"},
                    },
                },
            ],
        )
        client.queue_response("done", tool_calls=None)
        registry = ToolRegistry()
        received_args = []

        def capture_tool(args):
            received_args.append(args)
            return "ok"

        registry.register(ToolDefinition(name="search", description="Search"))
        registry.register_executor("search", capture_tool)
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test", tools=["search"])
        assert result.tool_calls[0].arguments == {"query": "already a dict"}
        assert received_args[0] == {"query": "already a dict"}

    def test_tool_choice_passed_only_on_first_round(self):
        """tool_choice should be 'specific' on round 1, 'auto' on subsequent rounds."""
        client = MockClient()
        client.queue_response(
            "using tool",
            tool_calls=[
                {"id": "tc_1", "function": {"name": "search", "arguments": "{}"}},
            ],
        )
        client.queue_response("done", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search"))
        registry.register_executor("search", lambda args: "ok")

        captured_kwargs = []
        original_generate = client.generate_response

        def capture(prompt, **kwargs):
            captured_kwargs.append(kwargs.copy())
            return original_generate(prompt, **kwargs)

        client.generate_response = capture
        loop = AgentLoop(client, registry, max_rounds=3)
        loop.execute("test", tools=["search"], tool_choice="specific")

        assert captured_kwargs[0]["tool_choice"] == "specific"
        assert captured_kwargs[1]["tool_choice"] == "auto"

    def test_llm_failure_after_first_round_returns_partial(self):
        """LLM failure after round 1 returns accumulated results, not a failed AgentResult."""
        client = MockClient()
        client.queue_response(
            "using tool",
            tool_calls=[
                {"id": "tc_1", "function": {"name": "search", "arguments": "{}"}},
            ],
        )
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search"))
        registry.register_executor("search", lambda args: "found")

        call_count = [0]
        original_generate = client.generate_response

        def fail_on_second(prompt, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return original_generate(prompt, **kwargs)
            raise RuntimeError("API error on round 2")

        client.generate_response = fail_on_second
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test", tools=["search"])
        assert result.status == "success"
        assert result.response == "using tool"
        assert result.tool_calls_count == 1
        assert result.total_rounds == 2
        assert result.total_llm_calls == 2

    def test_tool_error_feed_back_to_client(self):
        """When a tool errors, the error result should be fed back via add_tool_result."""
        client = MockClient()
        client.queue_response(
            "calculating",
            tool_calls=[
                {"id": "tc_err", "function": {"name": "calc", "arguments": "{}"}},
            ],
        )
        client.queue_response("recovered", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="calc", description="Calc"))
        registry.register_executor("calc", lambda args: (_ for _ in ()).throw(RuntimeError("boom")))
        loop = AgentLoop(client, registry, max_rounds=3, continue_on_tool_error=True)
        loop.execute("test", tools=["calc"])
        tool_msgs = [m for m in client.chat_history if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "boom" in tool_msgs[0]["content"]


class TestToolCallRecordMissingFields:
    def test_from_dict_empty_uses_defaults(self):
        record = ToolCallRecord.from_dict({})
        assert record.round == 0
        assert record.tool_name == ""
        assert record.tool_call_id == ""
        assert record.arguments == {}
        assert record.result == ""
        assert record.duration_ms == 0.0
        assert record.error is None

    def test_from_dict_preserves_error(self):
        record = ToolCallRecord.from_dict({"round": 1, "tool_name": "t", "error": "fail"})
        assert record.error == "fail"


class TestAgentResultMissingFields:
    def test_from_dict_empty_uses_defaults(self):
        result = AgentResult.from_dict({})
        assert result.response == ""
        assert result.tool_calls == []
        assert result.total_rounds == 0
        assert result.total_llm_calls == 0
        assert result.status == "success"

    def test_from_dict_with_multiple_tool_calls(self):
        data = {
            "response": "final",
            "tool_calls": [
                {"round": 1, "tool_name": "search", "tool_call_id": "tc_1"},
                {"round": 2, "tool_name": "calc", "tool_call_id": "tc_2", "error": "overflow"},
            ],
            "total_rounds": 2,
            "total_llm_calls": 3,
            "status": "success",
        }
        result = AgentResult.from_dict(data)
        assert result.tool_calls_count == 2
        assert result.last_tool_name == "calc"
        assert len(result.failed_tool_calls) == 1
        assert result.failed_tool_calls[0].tool_name == "calc"

    def test_to_dict_roundtrip_preserves_all_fields(self):
        original = AgentResult(
            response="test",
            tool_calls=[
                ToolCallRecord(round=1, tool_name="calc", tool_call_id="tc_1"),
                ToolCallRecord(round=2, tool_name="search", error="not found"),
            ],
            total_rounds=2,
            total_llm_calls=3,
            status="success",
        )
        restored = AgentResult.from_dict(original.to_dict())
        assert restored == original


class TestAgentResultInvariants:
    def test_tool_calls_count_equals_len_tool_calls(self):
        calls = [
            ToolCallRecord(round=1, tool_name="a"),
            ToolCallRecord(round=2, tool_name="b"),
            ToolCallRecord(round=3, tool_name="c"),
        ]
        result = AgentResult(response="done", tool_calls=calls, total_rounds=3)
        assert result.tool_calls_count == 3
        assert result.tool_calls_count == len(result.tool_calls)

    def test_failed_tool_calls_returns_exact_records(self):
        ok_tc = ToolCallRecord(round=1, tool_name="search", error=None)
        fail_tc1 = ToolCallRecord(round=2, tool_name="calc", error="overflow")
        fail_tc2 = ToolCallRecord(round=3, tool_name="search", error="timeout")
        result = AgentResult(
            response="partial",
            tool_calls=[ok_tc, fail_tc1, fail_tc2],
        )
        failed = result.failed_tool_calls
        assert len(failed) == 2
        assert failed[0] is fail_tc1
        assert failed[1] is fail_tc2

    def test_from_dict_ignores_unknown_fields(self):
        result = AgentResult.from_dict(
            {
                "response": "test",
                "total_rounds": 1,
                "total_llm_calls": 2,
                "status": "success",
                "unknown_field": "ignored",
                "extra": 42,
            }
        )
        assert result.response == "test"
        assert result.total_rounds == 1
        assert result.total_llm_calls == 2
        assert not hasattr(result, "unknown_field")

    def test_to_dict_contains_serialized_tool_calls(self):
        tc = ToolCallRecord(
            round=2,
            tool_name="calc",
            tool_call_id="tc_42",
            arguments={"expr": "1+1"},
            result="2",
            duration_ms=3.7,
            error="bad",
        )
        result = AgentResult(
            response="final",
            tool_calls=[tc],
            total_rounds=2,
            total_llm_calls=3,
            status="failed",
        )
        d = result.to_dict()
        assert d["response"] == "final"
        assert d["status"] == "failed"
        assert d["total_rounds"] == 2
        assert d["total_llm_calls"] == 3
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["tool_name"] == "calc"
        assert d["tool_calls"][0]["round"] == 2
        assert d["tool_calls"][0]["arguments"] == {"expr": "1+1"}
        assert d["tool_calls"][0]["error"] == "bad"

    def test_last_tool_name_with_multiple_calls(self):
        result = AgentResult(
            tool_calls=[
                ToolCallRecord(round=1, tool_name="search"),
                ToolCallRecord(round=2, tool_name="calc"),
                ToolCallRecord(round=3, tool_name="summarize"),
            ],
        )
        assert result.last_tool_name == "summarize"


class TestAgentLoopMaxRoundsZeroWithTools:
    def test_max_rounds_zero_with_registered_tools_returns_max_rounds_exceeded(self):
        client = MockClient()
        client.queue_response("answer")
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search"))
        registry.register_executor("search", lambda args: "results")
        loop = AgentLoop(client, registry, max_rounds=0)
        result = loop.execute("test", tools=["search"])
        assert result.status == "max_rounds_exceeded"
        assert result.total_rounds == 0
        assert result.total_llm_calls == 0
        assert result.response == ""


class TestAgentLoopExtractToolCalls:
    def test_no_assistant_messages_returns_empty(self):
        client = MockClient()
        client.chat_history = [
            {"role": "user", "content": "hello"},
        ]
        registry = ToolRegistry()
        loop = AgentLoop(client, registry)
        assert loop._extract_tool_calls() == []

    def test_assistant_without_tool_calls_key_returns_empty(self):
        client = MockClient()
        client.chat_history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        registry = ToolRegistry()
        loop = AgentLoop(client, registry)
        assert loop._extract_tool_calls() == []

    def test_multiple_assistants_reads_last_one(self):
        client = MockClient()
        client.chat_history = [
            {"role": "assistant", "content": "first"},
            {"role": "user", "content": "continue"},
            {"role": "assistant", "content": "second", "tool_calls": [{"id": "tc_last"}]},
        ]
        registry = ToolRegistry()
        loop = AgentLoop(client, registry)
        calls = loop._extract_tool_calls()
        assert len(calls) == 1
        assert calls[0]["id"] == "tc_last"


class TestAgentLoopToolCallIdPropagation:
    def test_tool_call_id_passed_to_add_tool_result(self):
        client = MockClient()
        client.queue_response(
            "using tool",
            tool_calls=[
                {"id": "call_abc123", "function": {"name": "search", "arguments": "{}"}},
            ],
        )
        client.queue_response("done", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="search", description="Search"))
        registry.register_executor("search", lambda args: "found")
        loop = AgentLoop(client, registry, max_rounds=3)
        loop.execute("test", tools=["search"])
        tool_msgs = [m for m in client.chat_history if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "call_abc123"
        assert tool_msgs[0]["content"] == "found"


class TestAgentLoopDurationTracking:
    def test_tool_call_records_have_positive_duration(self):
        client = MockClient()
        client.queue_response(
            "using tool",
            tool_calls=[
                {"id": "tc_1", "function": {"name": "echo", "arguments": '{"msg": "hi"}'}},
            ],
        )
        client.queue_response("done", tool_calls=None)
        registry = ToolRegistry()
        registry.register(ToolDefinition(name="echo", description="Echo"))
        registry.register_executor("echo", lambda args: json.dumps(args))
        loop = AgentLoop(client, registry, max_rounds=3)
        result = loop.execute("test", tools=["echo"])
        assert result.tool_calls_count == 1
        assert result.tool_calls[0].duration_ms >= 0.0
        assert result.tool_calls[0].arguments == {"msg": "hi"}
