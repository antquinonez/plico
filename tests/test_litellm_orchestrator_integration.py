# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for FFLiteLLMClient integration with orchestrator."""

from unittest.mock import MagicMock, patch

from src.Clients.FFLiteLLMClient import FFLiteLLMClient
from src.FFAI import FFAI
from src.orchestrator.client_registry import ClientRegistry


class TestClientRegistryLiteLLM:
    """Test ClientRegistry with LiteLLM client types."""

    def test_litellm_in_available_types(self):
        """LiteLLM types should be in available client types."""
        types = ClientRegistry.get_available_client_types()
        assert "litellm" in types
        assert "litellm-azure" in types
        assert "litellm-anthropic" in types
        assert "litellm-mistral" in types
        assert "litellm-openai" in types
        assert "litellm-gemini" in types

    def test_registry_creates_litellm_client(self):
        """Registry should create FFLiteLLMClient for litellm type."""
        default = FFLiteLLMClient(model_string="openai/gpt-4")
        registry = ClientRegistry(default)
        registry.register(
            "test",
            "litellm",
            {"model": "anthropic/claude-3-opus"},
        )
        client = registry.get("test")
        assert isinstance(client, FFLiteLLMClient)
        assert client._model_string == "anthropic/claude-3-opus"

    def test_registry_litellm_azure_prefix(self):
        """litellm-azure type should add azure/ prefix."""
        default = FFLiteLLMClient(model_string="openai/gpt-4")
        registry = ClientRegistry(default)
        registry.register(
            "azure-client",
            "litellm-azure",
            {"model": "mistral-small-2503"},
        )
        client = registry.get("azure-client")
        assert client._model_string == "azure/mistral-small-2503"

    def test_registry_litellm_anthropic_prefix(self):
        """litellm-anthropic type should add anthropic/ prefix."""
        default = FFLiteLLMClient(model_string="openai/gpt-4")
        registry = ClientRegistry(default)
        registry.register(
            "anthropic-client",
            "litellm-anthropic",
            {"model": "claude-3-opus"},
        )
        client = registry.get("anthropic-client")
        assert client._model_string == "anthropic/claude-3-opus"

    def test_registry_litellm_with_temperature(self):
        """Registry should pass temperature to LiteLLM client."""
        default = FFLiteLLMClient(model_string="openai/gpt-4")
        registry = ClientRegistry(default)
        registry.register(
            "low-temp",
            "litellm",
            {"model": "gpt-4", "temperature": 0.2},
        )
        client = registry.get("low-temp")
        assert client.temperature == 0.2

    def test_registry_litellm_with_max_tokens(self):
        """Registry should pass max_tokens to LiteLLM client."""
        default = FFLiteLLMClient(model_string="openai/gpt-4")
        registry = ClientRegistry(default)
        registry.register(
            "short-response",
            "litellm",
            {"model": "gpt-4", "max_tokens": 500},
        )
        client = registry.get("short-response")
        assert client.max_tokens == 500

    def test_registry_clone_litellm_client(self):
        """Registry.clone() should return fresh FFLiteLLMClient."""
        default = FFLiteLLMClient(model_string="openai/gpt-4")
        registry = ClientRegistry(default)
        registry.register(
            "to-clone",
            "litellm",
            {"model": "anthropic/claude-3-opus"},
        )

        original = registry.get("to-clone")
        original.conversation_history.append({"role": "user", "content": "test"})

        clone = registry.clone("to-clone")
        assert isinstance(clone, FFLiteLLMClient)
        assert len(clone.conversation_history) == 0
        assert len(original.conversation_history) == 1


class TestFFAIWithLiteLLM:
    """Test FFAI wrapper with FFLiteLLMClient."""

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_ffai_generate_response(self, mock_completion):
        """FFAI should work with FFLiteLLMClient."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_completion.return_value = mock_response

        client = FFLiteLLMClient(model_string="openai/gpt-4")
        ffai = FFAI(client)

        response = ffai.generate_response("Hello", prompt_name="greeting")

        assert response.response == "Test response"
        assert len(ffai.history) == 1
        assert ffai.history[0]["prompt_name"] == "greeting"

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_ffai_with_declarative_context(self, mock_completion):
        """FFAI declarative context should work with FFLiteLLMClient."""
        call_count = [0]

        def mock_complete(**kwargs):
            call_count[0] += 1
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            if call_count[0] == 1:
                mock_resp.choices[0].message.content = "2 + 2 = 4"
            else:
                mock_resp.choices[0].message.content = "Your question was about math"
            return mock_resp

        mock_completion.side_effect = mock_complete

        client = FFLiteLLMClient(model_string="openai/gpt-4")
        ffai = FFAI(client)

        ffai.generate_response("What is 2 + 2?", prompt_name="math")
        response = ffai.generate_response(
            "What was my question?",
            prompt_name="recall",
            history=["math"],
        )

        assert "math" in response.response.lower()
        assert call_count[0] == 2


class TestParallelExecutionWithLiteLLM:
    """Test parallel execution patterns with FFLiteLLMClient."""

    def test_multiple_clones_isolated(self):
        """Multiple clones should have isolated state."""
        client = FFLiteLLMClient(model_string="openai/gpt-4")

        clones = [client.clone() for _ in range(5)]

        for i, clone in enumerate(clones):
            clone.conversation_history.append({"role": "user", "content": f"msg {i}"})

        for i, clone in enumerate(clones):
            assert len(clone.conversation_history) == 1
            assert clone.conversation_history[0]["content"] == f"msg {i}"

        assert len(client.conversation_history) == 0

    @patch("src.Clients.FFLiteLLMClient.completion")
    def test_parallel_execution_simulation(self, mock_completion):
        """Simulate parallel execution with clones."""
        from unittest.mock import MagicMock

        def make_response(**kwargs):
            mock = MagicMock()
            mock.choices = [MagicMock()]
            mock.choices[0].message.content = "Response"
            mock.usage.prompt_tokens = 10
            mock.usage.completion_tokens = 5
            mock.usage.total_tokens = 15
            return mock

        mock_completion.side_effect = make_response

        base_client = FFLiteLLMClient(model_string="openai/gpt-4")
        shared_history = []
        import threading

        history_lock = threading.Lock()

        def execute_prompt(prompt_text, prompt_name):
            clone = base_client.clone()
            ffai = FFAI(
                clone,
                shared_prompt_attr_history=shared_history,
                history_lock=history_lock,
            )
            return ffai.generate_response(prompt_text, prompt_name=prompt_name)

        results = []
        threads = []
        for i in range(3):
            t = threading.Thread(
                target=lambda idx=i: results.append(
                    execute_prompt(f"Prompt {idx}", f"prompt_{idx}")
                )
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 3
        assert len(shared_history) == 3
