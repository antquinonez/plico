# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Integration tests for FFMistralSmall client with real API.

These tests require MISTRALSMALL_KEY environment variable.
Run with: pytest tests/integration/test_ffmistralsmall_integration.py -v
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def real_mistralsmall_client():
    """Create a real FFMistralSmall client with API key from environment."""
    api_key = os.getenv("MISTRALSMALL_KEY")
    if not api_key:
        pytest.skip("MISTRALSMALL_KEY not set in environment")

    from src.Clients.FFMistralSmall import FFMistralSmall

    client = FFMistralSmall(
        api_key=api_key,
        model="mistral-small-latest",
        temperature=0.3,
        max_tokens=100,
        system_instructions="You are a helpful assistant. Give very brief answers.",
    )
    return client


@pytest.fixture
def real_mistralsmall_2503():
    """Create a real FFMistralSmall client with specific model version."""
    api_key = os.getenv("MISTRALSMALL_KEY")
    if not api_key:
        pytest.skip("MISTRALSMALL_KEY not set in environment")

    from src.Clients.FFMistralSmall import FFMistralSmall

    client = FFMistralSmall(
        api_key=api_key,
        model="mistral-small-2503",
        temperature=0.3,
        max_tokens=100,
        system_instructions="You are a helpful assistant. Give very brief answers - just the answer.",
    )
    return client


@pytest.mark.integration
class TestFFMistralSmallRealAPI:
    """Integration tests using real Mistral API."""

    def test_connection_succeeds(self, real_mistralsmall_client):
        """Test that connection to Mistral API succeeds."""
        result = real_mistralsmall_client.test_connection()
        assert result is True

    def test_basic_response(self, real_mistralsmall_client):
        """Test basic response generation."""
        response = real_mistralsmall_client.generate_response("Say 'hello' and nothing else.")
        assert response is not None
        assert len(response) > 0
        assert "hello" in response.lower()

    def test_response_adds_to_history(self, real_mistralsmall_client):
        """Test that responses are added to conversation history."""
        real_mistralsmall_client.clear_conversation()

        response = real_mistralsmall_client.generate_response("Say 'test' and nothing else.")

        history = real_mistralsmall_client.get_conversation_history()
        assert len(history) >= 2
        assert history[-2]["role"] == "user"
        assert history[-1]["role"] == "assistant"

    def test_conversation_context_maintained(self, real_mistralsmall_client):
        """Test that conversation context is maintained across turns."""
        real_mistralsmall_client.clear_conversation()

        real_mistralsmall_client.generate_response("My name is Alice. Remember it.")
        response = real_mistralsmall_client.generate_response("What is my name? Just say the name.")

        assert "alice" in response.lower()

    def test_model_override(self, real_mistralsmall_client):
        """Test that model can be overridden per-request."""
        response = real_mistralsmall_client.generate_response(
            "Say 'ok' and nothing else.", model="mistral-small-latest"
        )
        assert response is not None

    def test_temperature_override(self, real_mistralsmall_client):
        """Test temperature override."""
        response = real_mistralsmall_client.generate_response(
            "Say 'temperature test' and nothing else.", temperature=0.1
        )
        assert response is not None

    def test_max_tokens_respected(self, real_mistralsmall_client):
        """Test that max_tokens limit is respected."""
        response = real_mistralsmall_client.generate_response("Count from 1 to 100.", max_tokens=20)
        assert response is not None
        assert len(response.split()) < 50

    def test_clear_conversation(self, real_mistralsmall_client):
        """Test clearing conversation history."""
        real_mistralsmall_client.generate_response("Say 'test'")
        real_mistralsmall_client.clear_conversation()

        history = real_mistralsmall_client.get_conversation_history()
        assert len(history) == 0

    def test_clone_isolation(self, real_mistralsmall_client):
        """Test that cloned clients have isolated history."""
        real_mistralsmall_client.clear_conversation()
        real_mistralsmall_client.generate_response("Say 'original'")

        clone = real_mistralsmall_client.clone()

        assert len(clone.get_conversation_history()) == 0
        assert len(real_mistralsmall_client.get_conversation_history()) >= 2


@pytest.mark.integration
class TestFFMistralSmall2503RealAPI:
    """Integration tests for mistral-small-2503 model."""

    def test_basic_response_2503(self, real_mistralsmall_2503):
        """Test basic response with mistral-small-2503."""
        response = real_mistralsmall_2503.generate_response("What is 2 + 2? Just give the number.")
        assert "4" in response

    def test_context_assembly(self, real_mistralsmall_2503):
        """Test that context is properly assembled from history."""
        real_mistralsmall_2503.clear_conversation()

        real_mistralsmall_2503.generate_response("The capital of France is Paris.")
        response = real_mistralsmall_2503.generate_response(
            "What is the capital of France? Just say the city name."
        )

        assert "paris" in response.lower()

    def test_json_response(self, real_mistralsmall_2503):
        """Test JSON formatted response."""
        response = real_mistralsmall_2503.generate_response(
            'Return JSON: {"status": "ok"}. Just return the JSON.',
            response_format={"type": "json_object"},
        )
        assert "ok" in response.lower()
        assert "{" in response


@pytest.mark.integration
class TestFFMistralSmallLargeContext:
    """Tests for large context handling."""

    def test_extended_context(self, real_mistralsmall_client):
        """Test with extended context (Mistral Small supports 128k)."""
        real_mistralsmall_client.clear_conversation()

        context_parts = []
        for i in range(10):
            context_parts.append(f"Item {i + 1}: Value_{i + 1}")

        context = "\n".join(context_parts)
        prompt = f"Here is a list:\n{context}\n\nWhat is Item 5's value? Just say the value."

        response = real_mistralsmall_client.generate_response(prompt)
        assert "value_5" in response.lower()


@pytest.mark.integration
class TestFFMistralSmallErrorHandling:
    """Tests for error handling with real API."""

    def test_empty_prompt_raises(self, real_mistralsmall_client):
        """Test that empty prompt raises ValueError."""
        with pytest.raises(ValueError, match="Empty prompt"):
            real_mistralsmall_client.generate_response("")

    def test_whitespace_prompt_raises(self, real_mistralsmall_client):
        """Test that whitespace-only prompt raises ValueError."""
        with pytest.raises(ValueError, match="Empty prompt"):
            real_mistralsmall_client.generate_response("   ")


@pytest.mark.integration
class TestFFMistralSmallWithFFAI:
    """Tests for FFMistralSmall wrapped in FFAI."""

    def test_ffai_with_real_client(self, real_mistralsmall_client):
        """Test FFAI wrapper with real Mistral client."""
        from src.FFAI import FFAI

        ffai = FFAI(real_mistralsmall_client)

        response = ffai.generate_response("Say 'wrapped' and nothing else.")
        assert "wrapped" in response.lower()

    def test_ffai_named_prompts(self, real_mistralsmall_client):
        """Test FFAI with named prompts."""
        from src.FFAI import FFAI

        ffai = FFAI(real_mistralsmall_client)

        ffai.generate_response("My favorite color is blue.", prompt_name="color")
        response = ffai.generate_response(
            "What is my favorite color? Just say the color.", prompt_name="recall"
        )

        assert "blue" in response.lower()

    def test_ffai_history_reference(self, real_mistralsmall_client):
        """Test FFAI history references."""
        from src.FFAI import FFAI

        ffai = FFAI(real_mistralsmall_client)

        ffai.generate_response("X equals 5.", prompt_name="x_value")
        ffai.generate_response("Y equals 3.", prompt_name="y_value")
        response = ffai.generate_response(
            "What is X + Y? Just give the number.",
            prompt_name="sum",
            history=["x_value", "y_value"],
        )

        assert "8" in str(response)
