import json
from unittest.mock import MagicMock, patch

import pytest

from src.Clients.FFMistralSmall import FFMistralSmall


@pytest.fixture
def mock_mistral_client():
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "Test response"
    response.choices[0].message.tool_calls = None
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    client.chat.complete.return_value = response
    return client


@pytest.fixture
def client(mock_mistral_client):
    with patch("src.Clients.FFMistralSmall.Mistral", return_value=mock_mistral_client):
        c = FFMistralSmall(
            api_key="test-key",
            model="mistral-small-2503",
            temperature=0.5,
            max_tokens=1024,
            system_instructions="Be brief.",
        )
    return c


class TestFFMistralSmallInit:
    def test_config_via_kwargs(self, client):
        assert client.model == "mistral-small-2503"
        assert client.temperature == 0.5
        assert client.max_tokens == 1024
        assert client.system_instructions == "Be brief."

    def test_config_via_dict(self, mock_mistral_client):
        with patch("src.Clients.FFMistralSmall.Mistral", return_value=mock_mistral_client):
            c = FFMistralSmall(
                config={"model": "custom-model", "temperature": 0.3, "max_tokens": 512},
                api_key="test-key",
            )
        assert c.model == "custom-model"
        assert c.temperature == 0.3
        assert c.max_tokens == 512

    def test_raises_without_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="API key not found"):
                FFMistralSmall(
                    api_key=None,
                    model="m",
                    temperature=0.5,
                    max_tokens=128,
                    system_instructions="x",
                )


class TestFFMistralSmallClone:
    def test_clone_preserves_config(self, client):
        clone = client.clone()
        assert clone.model == client.model
        assert clone.temperature == client.temperature
        assert clone.max_tokens == client.max_tokens
        assert clone.system_instructions == client.system_instructions

    def test_clone_has_empty_history(self, client):
        client.conversation_history.append({"role": "user", "content": "hi"})
        clone = client.clone()
        assert clone.conversation_history == []


class TestFFMistralSmallConversationHistory:
    def test_get_set_history(self, client):
        history = [{"role": "user", "content": "hello"}]
        client.set_conversation_history(history)
        assert client.get_conversation_history() == history

    def test_clear_conversation(self, client):
        client.conversation_history.append({"role": "user", "content": "x"})
        client.clear_conversation()
        assert client.conversation_history == []


class TestFFMistralSmallGenerateResponse:
    def test_basic_response(self, client, mock_mistral_client):
        result = client.generate_response("Hello")
        assert result == "Test response"
        assert len(client.conversation_history) == 2
        assert client.conversation_history[0]["role"] == "user"
        assert client.conversation_history[1]["role"] == "assistant"

    def test_empty_prompt_raises(self, client):
        with pytest.raises(ValueError, match="Empty prompt"):
            client.generate_response("   ")

    def test_system_instructions_override(self, client, mock_mistral_client):
        client.generate_response("Hello", system_instructions="Custom system")
        call_kwargs = mock_mistral_client.chat.complete.call_args
        messages = call_kwargs.kwargs["messages"]
        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "Custom system"

    def test_model_override(self, client, mock_mistral_client):
        client.generate_response("Hello", model="override-model")
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["model"] == "override-model"

    def test_temperature_override(self, client, mock_mistral_client):
        client.generate_response("Hello", temperature=0.1)
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["temperature"] == 0.1

    def test_max_tokens_override(self, client, mock_mistral_client):
        client.generate_response("Hello", max_tokens=256)
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["max_tokens"] == 256

    def test_max_completion_tokens_used(self, client, mock_mistral_client):
        client.generate_response("Hello", max_completion_tokens=512)
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["max_tokens"] == 512

    def test_json_response_format(self, client, mock_mistral_client):
        client.generate_response("Return JSON", response_format="json")
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["response_format"] == {"type": "json_object"}

    def test_dict_response_format(self, client, mock_mistral_client):
        fmt = {"type": "json_object"}
        client.generate_response("Return JSON", response_format=fmt)
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["response_format"] == fmt

    def test_stop_as_list(self, client, mock_mistral_client):
        client.generate_response("Hello", stop=["END", "STOP"])
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["stop"] == ["END", "STOP"]

    def test_stop_as_string(self, client, mock_mistral_client):
        client.generate_response("Hello", stop="END")
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["stop"] == ["END"]

    def test_tools_passed_through(self, client, mock_mistral_client):
        tools = [{"type": "function", "function": {"name": "f"}}]
        client.generate_response("Hello", tools=tools, tool_choice="auto")
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["tools"] == tools
        assert call_kwargs.kwargs["tool_choice"] == "auto"

    def test_safe_mode(self, client, mock_mistral_client):
        client.generate_response("Hello", safe_mode=True)
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["safe_prompt"] is True

    def test_top_p_passed(self, client, mock_mistral_client):
        client.generate_response("Hello", top_p=0.9)
        call_kwargs = mock_mistral_client.chat.complete.call_args
        assert call_kwargs.kwargs["top_p"] == 0.9


class TestFFMistralSmallToolCalls:
    def test_tool_calls_detected(self, client, mock_mistral_client):
        tc = MagicMock()
        tc.id = "call_123"
        tc.function.name = "get_weather"
        tc.function.arguments = '{"city": "Paris"}'

        mock_mistral_client.chat.complete.return_value.choices[0].message.content = ""
        mock_mistral_client.chat.complete.return_value.choices[0].message.tool_calls = [tc]

        result = client.generate_response("Weather in Paris?", tools=[{}])

        assert "Tool calls detected: 1" in result
        assert len(client.conversation_history) == 2
        assistant_msg = client.conversation_history[1]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["tool_calls"][0]["id"] == "call_123"
        assert assistant_msg["tool_calls"][0]["function"]["name"] == "get_weather"


class TestFFMistralSmallAddToolResult:
    def test_add_dict_content(self, client):
        client.add_tool_result("call_123", {"temp": 22})
        msg = client.conversation_history[-1]
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "call_123"
        assert msg["content"] == json.dumps({"temp": 22})

    def test_add_string_content(self, client):
        client.add_tool_result("call_456", "Sunny")
        msg = client.conversation_history[-1]
        assert msg["content"] == "Sunny"

    def test_add_non_string_content(self, client):
        client.add_tool_result("call_789", 42)
        msg = client.conversation_history[-1]
        assert msg["content"] == "42"


class TestFFMistralSmallConvertHistory:
    def test_system_instructions_prepended(self, client):
        client.conversation_history.append({"role": "user", "content": "hi"})
        messages = client._convert_history_to_messages()
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Be brief."

    def test_tool_message_includes_call_id(self, client):
        client.conversation_history.append(
            {"role": "tool", "tool_call_id": "call_abc", "content": "result"}
        )
        messages = client._convert_history_to_messages()
        tool_msg = [m for m in messages if m["role"] == "tool"][0]
        assert tool_msg["tool_call_id"] == "call_abc"

    def test_filters_non_standard_roles(self, client):
        client.conversation_history.append({"role": "system", "content": "sys"})
        messages = client._convert_history_to_messages()
        assert all(m["role"] in ["system", "user", "assistant", "tool"] for m in messages)


class TestFFMistralSmallTestConnection:
    def test_success_returns_true(self, client, mock_mistral_client):
        assert client.test_connection() is True

    def test_failure_returns_false(self, client, mock_mistral_client):
        mock_mistral_client.chat.complete.side_effect = Exception("timeout")
        assert client.test_connection() is False
