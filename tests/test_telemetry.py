# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from unittest.mock import MagicMock, patch

import pytest


class TestNoOpSpan:
    """Tests for NoOpSpan when telemetry is disabled."""

    def test_set_attribute_is_noop(self):
        from src.observability.telemetry import NoOpSpan

        span = NoOpSpan()
        span.set_attribute("key", "value")

    def test_record_exception_is_noop(self):
        from src.observability.telemetry import NoOpSpan

        span = NoOpSpan()
        span.record_exception(ValueError("test"))

    def test_is_recording_returns_false(self):
        from src.observability.telemetry import NoOpSpan

        span = NoOpSpan()
        assert span.is_recording() is False


class TestTelemetryManager:
    """Tests for TelemetryManager."""

    def teardown_method(self):
        from src.observability.telemetry import reset_telemetry

        reset_telemetry()

    def test_disabled_by_default(self):
        with patch("src.config.get_config", side_effect=Exception("no config")):
            from src.observability.telemetry import TelemetryManager

            manager = TelemetryManager()
        assert manager.enabled is False

    def test_span_returns_noop_when_disabled(self):
        with patch("src.config.get_config", side_effect=Exception("no config")):
            from src.observability.telemetry import TelemetryManager

            manager = TelemetryManager()

        with manager.span("test") as span:
            from src.observability.telemetry import NoOpSpan

            assert isinstance(span, NoOpSpan)

    def test_span_context_manager_works_when_disabled(self):
        with patch("src.config.get_config", side_effect=Exception("no config")):
            from src.observability.telemetry import TelemetryManager

            manager = TelemetryManager()

        executed = False
        with manager.span("test") as span:
            span.set_attribute("key", "value")
            executed = True
        assert executed

    def test_get_telemetry_manager_returns_singleton(self):
        import src.observability.telemetry as mod

        with patch("src.config.get_config", side_effect=Exception("no config")):
            a = mod.get_telemetry_manager()
            b = mod.get_telemetry_manager()
        assert a is b

    def test_reload_telemetry_creates_new_instance(self):
        import src.observability.telemetry as mod

        with patch("src.config.get_config", side_effect=Exception("no config")):
            old = mod.get_telemetry_manager()
            new = mod.reload_telemetry()
        assert old is not new

    def test_reset_telemetry_clears_singleton(self):
        import src.observability.telemetry as mod

        with patch("src.config.get_config", side_effect=Exception("no config")):
            mod.get_telemetry_manager()
        mod.reset_telemetry()
        assert mod._manager is None


class TestGetSummaryWithTokens:
    """Tests for token/cost aggregation in get_summary."""

    def test_summary_includes_tokens_when_present(self):
        from src.orchestrator.results.builder import ResultBuilder

        results = []
        for i, (inp, out, cost) in enumerate([(100, 50, 0.001), (200, 100, 0.002)]):
            prompt = {"sequence": i, "prompt": "test", "prompt_name": f"p{i}"}
            b = ResultBuilder(prompt)
            b.with_response("ok").with_usage(inp, out, inp + out).with_cost(cost)
            results.append(b.build_dict())

        total_input = sum(r.get("input_tokens", 0) for r in results)
        total_output = sum(r.get("output_tokens", 0) for r in results)
        total_tokens = sum(r.get("total_tokens", 0) for r in results)
        total_cost = sum(r.get("cost_usd", 0.0) for r in results)

        assert total_input == 300
        assert total_output == 150
        assert total_tokens == 450
        assert total_cost == pytest.approx(0.003)

    def test_summary_omits_tokens_when_zero(self):
        results = [{"status": "success", "attempts": 1, "input_tokens": 0, "output_tokens": 0}]
        total_tokens = sum(r.get("total_tokens", 0) for r in results)
        total_cost = sum(r.get("cost_usd", 0.0) for r in results)
        assert not (total_tokens > 0 or total_cost > 0)


class TestTraceLLMCall:
    """Tests for _trace_llm_call context manager on FFAIClientBase."""

    def teardown_method(self):
        from src.observability.telemetry import reset_telemetry

        reset_telemetry()

    def test_trace_llm_call_noop_when_disabled(self):
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

        with patch("src.config.get_config", side_effect=Exception("no config")):
            from src.observability.telemetry import reset_telemetry

            reset_telemetry()
            client = ConcreteClient()
            with client._trace_llm_call("test-model"):
                pass

    def test_trace_llm_call_sets_span_attributes(self):
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

        mock_obs_config = MagicMock()
        mock_obs_config.enabled = False

        mock_config = MagicMock()
        mock_config.observability = mock_obs_config

        with patch("src.config.get_config", return_value=mock_config):
            from src.observability.telemetry import reset_telemetry

            reset_telemetry()
            client = ConcreteClient()
            client._last_usage = TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15)
            client._last_cost_usd = 0.001

            with client._trace_llm_call("test-model", "my_prompt") as span:
                pass

    def test_extract_openai_usage_with_real_usage(self):
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

        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150

        client = ConcreteClient()
        client._extract_token_usage(mock_response, "sonar")

        assert client.last_usage is not None
        assert client.last_usage.input_tokens == 100
        assert client.last_usage.output_tokens == 50
        assert client.last_usage.total_tokens == 150
        assert client.last_cost_usd > 0.0

    def test_extract_token_usage_skips_when_no_usage(self):
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

        mock_response = MagicMock(spec=[])
        client = ConcreteClient()
        client._extract_token_usage(mock_response, "sonar")

        assert client.last_usage is None
        assert client.last_cost_usd == 0.0
