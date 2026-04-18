# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from mistralai import Mistral

from ..core.client_base import FFAIClientBase

load_dotenv()

logger = logging.getLogger(__name__)


class FFMistral(FFAIClientBase):
    def __init__(self, config: dict | None = None, **kwargs):
        logger.info("Initializing FFMistral")

        # DEFAULT VALUES
        defaults = {
            "model": "mistral-large-latest",
            "max_tokens": 4096,
            "temperature": 0.8,
            "instructions": "You are a helpful assistant. Respond accurately to user queries. Be concise and clear.",
        }

        # Combine config and kwargs, with kwargs taking precedence
        all_config = {**(config or {}), **kwargs}

        for key, value in all_config.items():
            match key:
                case "api_key":
                    self.api_key = value or os.getenv("MISTRAL_API_KEY")
                case "model":
                    self.model = value
                case "temperature":
                    self.temperature = float(value)
                case "max_tokens":
                    self.max_tokens = int(value) if value is not None else defaults["max_tokens"]
                case "system_instructions":
                    self.system_instructions = value

        # Set default values if not set
        self.api_key = getattr(self, "api_key", os.getenv("MISTRAL_API_KEY"))
        self.model = getattr(self, "model", os.getenv("MISTRAL_MODEL", defaults["model"]))
        self.temperature = getattr(
            self,
            "temperature",
            float(os.getenv("MISTRAL_TEMPERATURE", defaults["temperature"])),
        )
        self.max_tokens = getattr(
            self,
            "max_tokens",
            int(os.getenv("MISTRAL_MAX_TOKENS", defaults["max_tokens"])),
        )
        self.system_instructions = getattr(
            self,
            "system_instructions",
            os.getenv("MISTRAL_SYSTEM_INSTRUCTIONS", defaults["instructions"]),
        )

        logger.debug(
            f"Model: {self.model}, Temperature: {self.temperature}, Max Tokens: {self.max_tokens}"
        )
        logger.debug(f"System instructions: {self.system_instructions}")

        self.conversation_history: list[dict[str, str]] = []
        self.client = self._initialize_client()

    def _initialize_client(self) -> Mistral:
        """Initialize and return the Mistral client."""
        logger.info("Initializing Mistral client")

        api_key = self.api_key

        if not api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")

        client = Mistral(api_key=api_key)

        return client

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get the conversation history."""
        return self.conversation_history

    def set_conversation_history(self, history: list[dict[str, str]]) -> None:
        """Set the conversation history."""
        self.conversation_history = history

    def clone(self) -> FFMistral:
        """Create a fresh clone of this client with empty history."""
        return FFMistral(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            system_instructions=self.system_instructions,
        )

    def _convert_history_to_messages(self) -> list[dict[str, str]]:
        """Convert conversation history to Mistral message format."""
        messages = []

        # Add system message
        if self.system_instructions:
            messages.append({"role": "system", "content": self.system_instructions})

        # Add conversation history
        for message in self.conversation_history:
            if message["role"] in ["user", "assistant", "tool"]:
                messages.append({"role": message["role"], "content": message["content"]})

                # Add tool_call_id if present for tool messages
                if message["role"] == "tool" and "tool_call_id" in message:
                    messages[-1]["tool_call_id"] = message["tool_call_id"]

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
        safe_mode: bool | None = None,
        **kwargs,
    ) -> str:
        """
        Generate a response from the model with robust parameter handling.

        Args:
            prompt: User's input text
            model: Model to use (overrides default)
            system_instructions: System instructions (overrides default)
            temperature: Controls randomness (0-1)
            max_tokens: Maximum tokens to generate
            max_completion_tokens: Alternative name for max_tokens (for compatibility)
            top_p: Nucleus sampling parameter
            presence_penalty: Penalizes repeated tokens
            frequency_penalty: Penalizes frequent tokens
            stop: List of strings that stop generation when encountered
            response_format: Format of the response ("text" or "json")
            tools: List of tools to make available to the model
            tool_choice: Tool choice strategy ("auto", "none", or specific tool)
            safe_mode: Whether to enable Mistral's safe mode
            **kwargs: Any additional parameters that may be passed but aren't used

        Returns:
            The model's response as a string
        """
        if not prompt.strip():
            raise ValueError("Empty prompt provided")

        logger.debug(f"Generating response for prompt: {prompt}")

        self._reset_usage()

        # Parameter normalization
        used_model = model or self.model or "mistral-large-latest"

        # Handle max tokens
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

        # Handle temperature
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

                api_params = {
                    "model": used_model,
                    "messages": messages,
                    "max_tokens": used_max_tokens,
                    "temperature": used_temperature,
                }

                if top_p is not None and 0 <= float(top_p) <= 1:
                    api_params["top_p"] = float(top_p)

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

                if safe_mode is not None:
                    api_params["safe_prompt"] = bool(safe_mode)

                logger.debug(f"Calling Mistral API with params: {api_params}")

                response = self.client.chat.complete(**api_params)

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

            raise RuntimeError(f"Error generating response from Mistral: {e!s}")

    def add_tool_result(self, tool_call_id: str, content: Any) -> None:
        """
        Add a tool result to the conversation history.

        Args:
            tool_call_id: The ID of the tool call this is responding to
            content: The content/result from the tool
        """
        if isinstance(content, dict):
            content = json.dumps(content)
        elif not isinstance(content, str):
            content = str(content)

        self.conversation_history.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": content}
        )

    def clear_conversation(self):
        """Clear the conversation history."""
        logger.info("Clearing conversation history")
        self.conversation_history = []

    def test_connection(self) -> bool:
        """
        Test the connection to the Mistral API endpoint.

        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            logger.info("Testing connection to Mistral API")

            # Make a simple request to test the connection
            response = self.client.chat.complete(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Test connection"},
                    {"role": "user", "content": "Hello"},
                ],
                max_tokens=5,  # Keep it minimal for quicker response
            )

            logger.info("Connection successful")
            return True

        except Exception as e:
            logger.error(f"Connection test failed: {e!s}")
            return False
