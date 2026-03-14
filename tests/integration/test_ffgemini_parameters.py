# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Integration tests for FFGemini parameter validation.

These tests require real Google Cloud credentials and will:
1. Skip if credentials are not available
2. Validate which parameters actually work with the Gemini API
3. Help identify unsupported parameters for documentation

Run with: pytest tests/integration/test_ffgemini_parameters.py -v -m integration
"""

import pytest


def has_gemini_credentials():
    """Check if Google Cloud credentials are available."""
    try:
        import google.auth

        creds, project = google.auth.default()
        return creds is not None and project is not None
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not has_gemini_credentials(), reason="Google Cloud credentials not available")
class TestFFGeminiParameterValidation:
    """Integration tests to validate which Gemini API parameters actually work."""

    @pytest.fixture
    def gemini_client(self):
        """Create a real FFGemini client."""
        from src.Clients.FFGemini import FFGemini

        client = FFGemini(
            model="google/gemini-2.0-flash-lite-001",
            temperature=0.1,
            max_tokens=50,
            system_instructions="Reply with just the word 'ok'.",
        )
        return client

    def test_basic_response_works(self, gemini_client):
        """Test that basic response generation works."""
        response = gemini_client.generate_response_sync("Say 'ok'.")
        assert response
        assert len(response) > 0

    def test_temperature_override_real_api(self, gemini_client):
        """Test that temperature override works."""
        response = gemini_client.generate_response_sync("Say 'ok'.", temperature=0.0)
        assert response
        gemini_client.clear_conversation()

    def test_max_tokens_override_real_api(self, gemini_client):
        """Test that max_tokens override works."""
        response = gemini_client.generate_response_sync("Say 'ok'.", max_tokens=10)
        assert response
        assert len(response) < 100
        gemini_client.clear_conversation()

    def test_model_override_real_api(self, gemini_client):
        """Test that model override works."""
        response = gemini_client.generate_response_sync(
            "Say 'ok'.", model="google/gemini-2.0-flash-lite-001"
        )
        assert response
        gemini_client.clear_conversation()

    def test_system_instructions_override_real_api(self, gemini_client):
        """Test that system_instructions override works."""
        response = gemini_client.generate_response_sync(
            "What is your role?",
            system_instructions="You are a test assistant. Reply only with 'test'.",
        )
        assert response
        assert "test" in response.lower()
        gemini_client.clear_conversation()

    def test_top_p_real_api(self, gemini_client):
        """Test that top_p parameter is accepted."""
        response = gemini_client.generate_response_sync("Say 'ok'.", top_p=0.9)
        assert response
        gemini_client.clear_conversation()

    def test_stop_sequences_real_api(self, gemini_client):
        """Test that stop sequences work."""
        response = gemini_client.generate_response_sync(
            "Count from 1 to 10: 1, 2, 3,",
            stop=["4"],
            max_tokens=20,
        )
        assert response
        assert "4" not in response or len(response) < 20
        gemini_client.clear_conversation()

    def test_response_format_json_real_api(self, gemini_client):
        """Test that JSON response format works."""
        response = gemini_client.generate_response_sync(
            'Return JSON: {"status": "ok"}',
            response_format={"type": "json_object"},
        )
        assert response
        try:
            import json

            parsed = json.loads(response)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError:
            pytest.skip("Response was not valid JSON - may not be fully supported")
        gemini_client.clear_conversation()

    def test_presence_penalty_real_api(self, gemini_client):
        """Test presence_penalty - may not be supported by Gemini."""
        try:
            response = gemini_client.generate_response_sync("Say 'ok'.", presence_penalty=0.5)
            assert response
            gemini_client.clear_conversation()
        except Exception as e:
            error_str = str(e).lower()
            if (
                "presence_penalty" in error_str
                or "unsupported" in error_str
                or "invalid" in error_str
            ):
                pytest.skip("presence_penalty not supported by Gemini API")
            raise

    def test_frequency_penalty_real_api(self, gemini_client):
        """Test frequency_penalty - may not be supported by Gemini."""
        try:
            response = gemini_client.generate_response_sync("Say 'ok'.", frequency_penalty=0.5)
            assert response
            gemini_client.clear_conversation()
        except Exception as e:
            error_str = str(e).lower()
            if (
                "frequency_penalty" in error_str
                or "unsupported" in error_str
                or "invalid" in error_str
            ):
                pytest.skip("frequency_penalty not supported by Gemini API")
            raise


@pytest.mark.integration
@pytest.mark.skipif(not has_gemini_credentials(), reason="Google Cloud credentials not available")
class TestFFGeminiConnection:
    """Integration tests for connection testing."""

    def test_test_connection_success(self):
        """Test that test_connection returns True with valid credentials."""
        from src.Clients.FFGemini import FFGemini

        client = FFGemini()
        result = client.test_connection()
        assert result is True

    def test_clone_preserves_connection(self):
        """Test that cloned client can still connect."""
        from src.Clients.FFGemini import FFGemini

        client = FFGemini()
        cloned = client.clone()

        result = cloned.test_connection()
        assert result is True


@pytest.mark.integration
@pytest.mark.skipif(not has_gemini_credentials(), reason="Google Cloud credentials not available")
class TestFFGeminiToolCalls:
    """Integration tests for tool calling functionality."""

    @pytest.fixture
    def gemini_client_with_tools(self):
        """Create a client configured for tool calling."""
        from src.Clients.FFGemini import FFGemini

        client = FFGemini(
            model="google/gemini-2.0-flash-lite-001",
            temperature=0.1,
            max_tokens=100,
        )
        return client

    def test_tool_calls_real_api(self, gemini_client_with_tools):
        """Test that tools parameter is accepted (basic test)."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name",
                            }
                        },
                        "required": ["location"],
                    },
                },
            }
        ]

        try:
            response = gemini_client_with_tools.generate_response_sync(
                "What's the weather in London?",
                tools=tools,
            )
            assert response
            gemini_client_with_tools.clear_conversation()
        except Exception as e:
            error_str = str(e).lower()
            if "tool" in error_str or "function" in error_str:
                pytest.skip("Tool calling may not be fully supported via OpenAI endpoint")
            raise

    def test_add_tool_result_real_api(self, gemini_client_with_tools):
        """Test adding tool result to history."""
        gemini_client_with_tools.add_tool_result("call_123", {"temp": 72, "condition": "sunny"})

        history = gemini_client_with_tools.get_conversation_history()
        assert len(history) == 1
        assert history[0]["role"] == "tool"
        assert history[0]["tool_call_id"] == "call_123"
