# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from ..core.client_base import FFAIClientBase

load_dotenv()

logger = logging.getLogger(__name__)


class FFPerplexity(FFAIClientBase):
    def __init__(self, config: dict | None = None, **kwargs):
        logger.info("Initializing FFPerplexity")

        defaults = {
            "model": "sonar",
            "max_tokens": 4000,
            "temperature": 0.5,
            "instructions": "Respond accurately to user queries. Never start with a preamble. Immediately address the ask or request. Do not add meta information about your response. If there's nothing to do, answer with ''",
        }

        all_config = {**(config or {}), **kwargs}

        for key, value in all_config.items():
            match key:
                case "api_key":
                    self.api_key = value or os.getenv("PERPLEXITY_TOKEN")
                case "model":
                    self.model = value
                case "temperature":
                    self.temperature = float(value)
                case "max_tokens":
                    self.max_tokens = int(value) if value is not None else defaults["max_tokens"]
                case "system_instructions":
                    self.system_instructions = value

        self.api_key = getattr(self, "api_key", os.getenv("PERPLEXITY_TOKEN"))
        self.model = getattr(self, "model", os.getenv("PERPLEXITY_MODEL", defaults["model"]))
        self.temperature = getattr(
            self,
            "temperature",
            float(os.getenv("PERPLEXITY_TEMPERATURE", defaults["temperature"])),
        )
        self.max_tokens = getattr(
            self,
            "max_tokens",
            int(os.getenv("PERPLEXITY_MAX_TOKENS", defaults["max_tokens"])),
        )
        self.system_instructions = getattr(
            self,
            "system_instructions",
            os.getenv("PERPLEXITY_ASSISTANT_INSTRUCTIONS", defaults["instructions"]),
        )

        logger.debug(
            f"Model: {self.model}, Temperature: {self.temperature}, Max Tokens: {self.max_tokens}"
        )
        logger.debug(f"System instructions: {self.system_instructions}")

        self.conversation_history: list[dict[str, str]] = []
        self.client: OpenAI = self._initialize_client()

    def _initialize_client(self) -> OpenAI:
        """Initialize and return the OpenAI client."""
        logger.info("Initializing Perplexity client")
        api_key = self.api_key
        if not api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")

        return OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get the conversation history."""
        return self.conversation_history

    def set_conversation_history(self, history: list[dict[str, str]]) -> None:
        """Set the conversation history."""
        self.conversation_history = history

    def clone(self) -> FFPerplexity:
        """Create a fresh clone of this client with empty history."""
        return FFPerplexity(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            system_instructions=self.system_instructions,
        )

    def _convert_history_to_messages(self) -> list[dict[str, str]]:
        """Convert conversation history to OpenAI message format."""
        messages = []

        if self.system_instructions:
            messages.append({"role": "system", "content": self.system_instructions})

        for message in self.conversation_history:
            if message["role"] in ["user", "assistant", "tool"]:
                msg_dict = {"role": message["role"], "content": message["content"]}

                if message["role"] == "tool" and "tool_call_id" in message:
                    msg_dict["tool_call_id"] = message["tool_call_id"]

                if message["role"] == "assistant" and "tool_calls" in message:
                    msg_dict["tool_calls"] = message["tool_calls"]

                messages.append(msg_dict)

        return messages

    def generate_response(
        self,
        prompt: str,
        model: str | None = None,
        system_instructions: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_completion_tokens: int | None = None,
        top_p: float | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        stop: list[str] | None = None,
        response_format: str | dict | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        if not prompt.strip():
            raise ValueError("Empty prompt provided")

        logger.debug(f"Generating response for prompt: {prompt}")

        self._reset_usage()

        used_model = model or self.model or "sonar"

        used_max_tokens = None
        if max_completion_tokens is not None:
            try:
                used_max_tokens = int(max_completion_tokens)
            except (ValueError, TypeError):
                logger.warning(f"Invalid max_completion_tokens value: {max_completion_tokens}")

        if used_max_tokens is None and max_tokens is not None:
            try:
                used_max_tokens = int(max_tokens)
            except (ValueError, TypeError):
                logger.warning(f"Invalid max_tokens value: {max_tokens}")

        if used_max_tokens is None or used_max_tokens <= 0:
            used_max_tokens = self.max_tokens

        used_temperature = None
        if temperature is not None:
            try:
                used_temperature = float(temperature)
                if not 0 <= used_temperature <= 2:
                    logger.warning(
                        f"Temperature value {used_temperature} outside valid range [0,2]"
                    )
                    used_temperature = None
            except (ValueError, TypeError):
                logger.warning(f"Invalid temperature value: {temperature}")

        if used_temperature is None:
            used_temperature = self.temperature

        logger.debug(
            f"Using model: {used_model}, Temperature: {used_temperature}, Max Tokens: {used_max_tokens}"
        )

        try:
            with self._trace_llm_call(used_model):
                messages = self._convert_history_to_messages()
                messages.append({"role": "user", "content": prompt})

                if system_instructions:
                    messages = [m for m in messages if m["role"] != "system"]
                    messages.insert(0, {"role": "system", "content": system_instructions})

                api_params: dict[str, Any] = {
                    "model": used_model,
                    "messages": messages,
                    "max_tokens": used_max_tokens,
                    "temperature": used_temperature,
                }

                if top_p is not None and 0 <= float(top_p) <= 1:
                    api_params["top_p"] = float(top_p)

                if presence_penalty is not None:
                    api_params["presence_penalty"] = float(presence_penalty)

                if frequency_penalty is not None:
                    api_params["frequency_penalty"] = float(frequency_penalty)

                if stop is not None:
                    if isinstance(stop, (list, tuple, set)):
                        api_params["stop"] = list(stop)
                    elif isinstance(stop, str):
                        api_params["stop"] = [stop]

                if response_format:
                    if isinstance(response_format, dict):
                        api_params["response_format"] = response_format
                    elif isinstance(response_format, str) and "json" in response_format.lower():
                        api_params["response_format"] = {"type": "json_object"}

                if tools and isinstance(tools, list):
                    api_params["tools"] = tools

                    if tool_choice:
                        api_params["tool_choice"] = tool_choice

                logger.debug(f"Calling Perplexity API with params: {api_params}")

                response = self.client.chat.completions.create(**api_params)

                self._extract_token_usage(response, used_model)

                self.conversation_history.append({"role": "user", "content": prompt})

                if (
                    hasattr(response.choices[0].message, "tool_calls")
                    and response.choices[0].message.tool_calls
                ):
                    assistant_response = response.choices[0].message.content or ""
                    tool_calls = response.choices[0].message.tool_calls

                    self.conversation_history.append(
                        {
                            "role": "assistant",
                            "content": assistant_response,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in tool_calls
                            ],
                        }
                    )

                    return f"{assistant_response}\n[Tool calls detected: {len(tool_calls)}]"
                else:
                    assistant_response = response.choices[0].message.content

                    self.conversation_history.append(
                        {"role": "assistant", "content": assistant_response}
                    )

                    logger.info("Response generated successfully")
                    return assistant_response

        except Exception as e:
            logger.error("Problem with response generation")
            logger.error(f"  -- exception: {e!s}")
            logger.error(f"  -- model: {self.model}")
            logger.error(f"  -- system: {self.system_instructions}")
            logger.error(f"  -- conversation history: {self.conversation_history}")
            logger.error(f"  -- max_tokens: {self.max_tokens}")
            logger.error(f"  -- temperature: {self.temperature}")

            raise RuntimeError(f"Error generating response from Perplexity: {e!s}")

    def add_tool_result(self, tool_call_id: str, content: Any) -> None:
        if isinstance(content, dict):
            content = json.dumps(content)
        elif not isinstance(content, str):
            content = str(content)

        self.conversation_history.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": content}
        )

    def clear_conversation(self) -> None:
        """Clear the conversation history."""
        logger.info("Clearing conversation history")
        self.conversation_history = []

    def test_connection(self) -> bool:
        """Test the connection to the Perplexity API endpoint."""
        try:
            logger.info("Testing connection to Perplexity API")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Test connection"},
                    {"role": "user", "content": "Hello"},
                ],
                max_tokens=5,
            )

            logger.info("Connection successful")
            return True

        except Exception as e:
            logger.error(f"Connection test failed: {e!s}")
            return False
