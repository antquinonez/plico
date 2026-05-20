# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_default_values(self):
        from src.core.usage import TokenUsage

        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0

    def test_custom_values(self):
        from src.core.usage import TokenUsage

        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150

    def test_addition(self):
        from src.core.usage import TokenUsage

        a = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        b = TokenUsage(input_tokens=200, output_tokens=75, total_tokens=275)
        result = a + b
        assert result.input_tokens == 300
        assert result.output_tokens == 125
        assert result.total_tokens == 425

    def test_addition_does_not_mutate(self):
        from src.core.usage import TokenUsage

        a = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        b = TokenUsage(input_tokens=200, output_tokens=75, total_tokens=275)
        _ = a + b
        assert a.input_tokens == 100
        assert b.input_tokens == 200


class TestClientBaseUsage:
    """Tests for usage metadata on FFAIClientBase."""

    def test_reset_usage(self):
        from src.core.client_base import FFAIClientBase
        from src.core.usage import TokenUsage

        class ConcreteClient(FFAIClientBase):
            def generate_response(self, prompt, **kwargs):
                return ""

            def clear_conversation(self):
                pass

            def get_conversation_history(self):
                return []

            def set_conversation_history(self, history):
                pass

            def clone(self):
                return ConcreteClient()

        client = ConcreteClient()
        client._last_usage = TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)
        client._last_cost_usd = 0.001

        client._reset_usage()
        assert client.last_usage is None
        assert client.last_cost_usd == 0.0

    def test_initial_state(self):
        from src.core.client_base import FFAIClientBase

        class ConcreteClient(FFAIClientBase):
            def generate_response(self, prompt, **kwargs):
                return ""

            def clear_conversation(self):
                pass

            def get_conversation_history(self):
                return []

            def set_conversation_history(self, history):
                pass

            def clone(self):
                return ConcreteClient()

        client = ConcreteClient()
        assert client.last_usage is None
        assert client.last_cost_usd == 0.0


class TestResultBuilderUsage:
    """Tests for usage metadata in ResultBuilder."""

    def test_with_usage(self):
        from src.orchestrator.results.builder import ResultBuilder

        prompt = {"sequence": 1, "prompt": "test", "prompt_name": "p1"}
        builder = ResultBuilder(prompt)
        builder.with_usage(input_tokens=100, output_tokens=50, total_tokens=150)
        result = builder.build()

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150

    def test_with_cost(self):
        from src.orchestrator.results.builder import ResultBuilder

        prompt = {"sequence": 1, "prompt": "test"}
        builder = ResultBuilder(prompt)
        builder.with_cost(0.00234)
        result = builder.build()

        assert result.cost_usd == 0.00234

    def test_with_duration(self):
        from src.orchestrator.results.builder import ResultBuilder

        prompt = {"sequence": 1, "prompt": "test"}
        builder = ResultBuilder(prompt)
        builder.with_duration(1234.5)
        result = builder.build()

        assert result.duration_ms == 1234.5

    def test_chained_usage_cost_duration(self):
        from src.orchestrator.results.builder import ResultBuilder

        prompt = {"sequence": 1, "prompt": "test"}
        result = (
            ResultBuilder(prompt)
            .with_response("hello")
            .with_usage(200, 100, 300)
            .with_cost(0.005)
            .with_duration(500.0)
            .build()
        )

        assert result.response == "hello"
        assert result.status == "success"
        assert result.input_tokens == 200
        assert result.output_tokens == 100
        assert result.total_tokens == 300
        assert result.cost_usd == 0.005
        assert result.duration_ms == 500.0

    def test_to_dict_includes_usage_fields(self):
        from src.orchestrator.results.builder import ResultBuilder

        prompt = {"sequence": 1, "prompt": "test"}
        builder = ResultBuilder(prompt)
        builder.with_usage(50, 25, 75).with_cost(0.001).with_duration(100.0)
        d = builder.build_dict()

        assert d["input_tokens"] == 50
        assert d["output_tokens"] == 25
        assert d["total_tokens"] == 75
        assert d["cost_usd"] == 0.001
        assert d["duration_ms"] == 100.0

    def test_from_dict_roundtrip(self):
        from src.orchestrator.results.result import PromptResult

        data = {
            "sequence": 1,
            "prompt": "test",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "cost_usd": 0.003,
            "duration_ms": 250.0,
        }
        result = PromptResult.from_dict(data)

        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150
        assert result.cost_usd == 0.003
        assert result.duration_ms == 250.0

    def test_default_values(self):
        from src.orchestrator.results.result import PromptResult

        result = PromptResult(sequence=1)
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.total_tokens == 0
        assert result.cost_usd == 0.0
        assert result.duration_ms == 0.0


class TestClientBaseRetryFallback:
    """Tests for get_default_retry_config fallback path (lines 62-65)."""

    def test_fallback_defaults_when_config_unavailable(self):
        from unittest.mock import patch

        from src.core.client_base import FFAIClientBase

        with patch("src.config.get_config", side_effect=Exception("no config")):
            defaults = FFAIClientBase.get_default_retry_config()

        assert defaults["max_attempts"] == 3
        assert defaults["min_wait_seconds"] == 1
        assert defaults["max_wait_seconds"] == 60
        assert defaults["exponential_base"] == 2
        assert defaults["exponential_jitter"] is True
        assert defaults["log_level"] == "INFO"


class TestClientBaseAbstractMethodBodies:
    """Tests that abstract base class pass-through bodies return None (lines 184, 189, 199, 209, 238)."""

    @staticmethod
    def _make_delegating_client():
        from src.core.client_base import FFAIClientBase

        class DelegatingClient(FFAIClientBase):
            model = "test"
            system_instructions = ""

            def generate_response(self, prompt, **kwargs):
                return super().generate_response(prompt, **kwargs)

            def clear_conversation(self):
                return super().clear_conversation()

            def get_conversation_history(self):
                return super().get_conversation_history()

            def set_conversation_history(self, history):
                return super().set_conversation_history(history)

            def clone(self):
                return super().clone()

        return DelegatingClient()

    def test_super_generate_response_returns_none(self):
        client = self._make_delegating_client()
        assert client.generate_response("test") is None

    def test_super_clear_conversation_returns_none(self):
        client = self._make_delegating_client()
        assert client.clear_conversation() is None

    def test_super_get_conversation_history_returns_none(self):
        client = self._make_delegating_client()
        assert client.get_conversation_history() is None

    def test_super_set_conversation_history_returns_none(self):
        client = self._make_delegating_client()
        assert client.set_conversation_history([]) is None

    def test_super_clone_returns_none(self):
        client = self._make_delegating_client()
        assert client.clone() is None
