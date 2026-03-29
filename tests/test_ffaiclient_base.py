"""Tests for FFAIClientBase abstract class."""

from __future__ import annotations

from typing import Any

import pytest

from src.FFAIClientBase import FFAIClientBase


class ConcreteClient(FFAIClientBase):
    """Minimal concrete implementation for testing."""

    model = "test-model"
    system_instructions = "You are a test."

    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []

    def generate_response(self, prompt: str, **kwargs: Any) -> str:
        return f"Response to: {prompt}"

    def clear_conversation(self) -> None:
        self._history.clear()

    def get_conversation_history(self) -> list[dict[str, Any]]:
        return self._history

    def set_conversation_history(self, history: list[dict[str, Any]]) -> None:
        self._history = history

    def clone(self) -> ConcreteClient:
        return ConcreteClient()


class TestGetDefaultRetryConfig:
    def test_returns_dict(self):
        config = FFAIClientBase.get_default_retry_config()
        assert isinstance(config, dict)

    def test_has_expected_keys(self):
        config = FFAIClientBase.get_default_retry_config()
        expected_keys = [
            "max_attempts",
            "min_wait_seconds",
            "max_wait_seconds",
            "exponential_base",
            "exponential_jitter",
            "log_level",
        ]
        for key in expected_keys:
            assert key in config

    def test_default_values(self):
        config = FFAIClientBase.get_default_retry_config()
        assert config["max_attempts"] == 3
        assert config["min_wait_seconds"] == 1
        assert config["max_wait_seconds"] == 60
        assert config["exponential_base"] == 2
        assert config["exponential_jitter"] is True
        assert config["log_level"] == "INFO"


class TestConfigureRetry:
    def test_configure_with_explicit_config(self):
        client = ConcreteClient()
        custom = {"max_attempts": 5, "min_wait_seconds": 2}
        client.configure_retry(custom)
        assert client.retry_config == custom

    def test_configure_with_none_uses_defaults(self):
        client = ConcreteClient()
        client.configure_retry(None)
        assert client.retry_config is not None
        assert client.retry_config["max_attempts"] == 3

    def test_configure_defaults_called(self):
        client = ConcreteClient()
        client.configure_retry()
        assert client.retry_config is not None
        assert "max_attempts" in client.retry_config


class TestAddToolResult:
    def test_add_tool_result(self):
        client = ConcreteClient()
        client.add_tool_result("call_123", "tool output")
        history = client.get_conversation_history()
        assert len(history) == 1
        assert history[0]["role"] == "tool"
        assert history[0]["tool_call_id"] == "call_123"
        assert history[0]["content"] == "tool output"

    def test_add_tool_result_appends_to_existing(self):
        client = ConcreteClient()
        client.set_conversation_history([{"role": "user", "content": "hello"}])
        client.add_tool_result("call_456", "result")
        history = client.get_conversation_history()
        assert len(history) == 2
        assert history[1]["role"] == "tool"
        assert history[1]["tool_call_id"] == "call_456"


class TestCannotInstantiateAbstract:
    def test_cannot_instantiate_base_class(self):
        with pytest.raises(TypeError):
            FFAIClientBase()
