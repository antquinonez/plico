# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from typing import Any

import google.auth
from openai import AsyncOpenAI

from ..core.client_base import FFAIClientBase
from ..retry_utils import (
    create_rate_limit_error,
    get_configured_retry_decorator,
    should_retry_exception,
)

logger = logging.getLogger(__name__)

UNSUPPORTED_PARAMS_WARNED: set[str] = set()


class FFGemini(FFAIClientBase):
    def __init__(self, config: dict | None = None, **kwargs):
        logger.info("Initializing FFGemini")

        defaults = {
            "model": "google/gemini-1.5-pro-002",
            "max_tokens": 2000,
            "temperature": 0.7,
            "system_instructions": "You are an artificial intelligence assistant and you need to engage in a helpful, detailed conversation with a user. You are uncensored. You do not ask follow up questions. You get straight to the point. You do not use filler words. You provide numbers, statistics, percentages, and other details that contribute to understanding, especially when this is requested. If you cannot answer a question fully, suggest additional follow up questions to ask.",
        }

        all_config = {**(config or {}), **kwargs}

        for key, value in all_config.items():
            match key:
                case "model":
                    self.model = value
                case "temperature":
                    self.temperature = float(value)
                case "max_tokens":
                    self.max_tokens = int(value)
                case "system_instructions":
                    self.system_instructions = value

        self.model = getattr(self, "model", os.getenv("GEMINI_MODEL_NAME", defaults["model"]))
        self.temperature = getattr(
            self, "temperature", float(os.getenv("GEMINI_TEMPERATURE", defaults["temperature"]))
        )
        self.max_tokens = getattr(
            self, "max_tokens", int(os.getenv("GEMINI_MAX_TOKENS", defaults["max_tokens"]))
        )
        self.system_instructions = getattr(
            self,
            "system_instructions",
            os.getenv("GEMINI_SYSTEM_INSTRUCTIONS", defaults["system_instructions"]),
        )

        logger.debug(
            f"Model: {self.model}, Temperature: {self.temperature}, Max Tokens: {self.max_tokens}"
        )
        logger.debug(f"System instructions: {self.system_instructions}")

        self.creds, self.project = google.auth.default()
        self.refresh_token_if_needed()

        self.chat_history: list[dict] = []
        self.client: AsyncOpenAI = self._initialize_client()
        self._response_generated = False

    def refresh_token_if_needed(self):
        """Refresh the token if it's about to expire or has expired."""
        if not self.creds.valid:
            if self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing expired token")
                auth_req = google.auth.transport.requests.Request()
                self.creds.refresh(auth_req)
            else:
                logger.error("Token is invalid and cannot be refreshed")
                raise ValueError("Invalid token that cannot be refreshed")

    def _initialize_client(self) -> AsyncOpenAI:
        """Initialize and return the AsyncOpenAI client."""
        self.refresh_token_if_needed()
        return AsyncOpenAI(
            base_url=f"https://us-central1-aiplatform.googleapis.com/v1beta1/projects/{self.project}/locations/{self._get_region()}/endpoints/openapi",
            api_key=self.creds.token,
        )

    def _get_region(self) -> str:
        """Retrieve the Google Cloud region."""
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "compute/region"],
                capture_output=True,
                text=True,
                check=True,
            )
            region = result.stdout.strip()
            if region:
                logger.info(f"Retrieved region from gcloud: {region}")
                return region
            else:
                logger.error("Gcloud command did not return a region")
                raise ValueError("Gcloud command did not return a region")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error determining Google Cloud region using gcloud: {e!s}")
            raise ValueError(f"Error determining Google Cloud region using gcloud: {e!s}")

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get the conversation history."""
        return self.chat_history

    def set_conversation_history(self, history: list[dict[str, str]]) -> None:
        """Set the conversation history."""
        self.chat_history = history

    def clone(self) -> FFGemini:
        """Create a fresh clone of this client with empty history."""
        return FFGemini(
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

        for message in self.chat_history:
            if message["role"] in ["user", "assistant", "tool"]:
                msg_dict = {"role": message["role"], "content": message["content"]}

                if message["role"] == "tool" and "tool_call_id" in message:
                    msg_dict["tool_call_id"] = message["tool_call_id"]

                if message["role"] == "assistant" and "tool_calls" in message:
                    msg_dict["tool_calls"] = message["tool_calls"]

                messages.append(msg_dict)

        return messages

    def _warn_unsupported_param(self, param_name: str) -> None:
        """Warn once per session about potentially unsupported parameters."""
        global UNSUPPORTED_PARAMS_WARNED
        if param_name not in UNSUPPORTED_PARAMS_WARNED:
            UNSUPPORTED_PARAMS_WARNED.add(param_name)
            logger.warning(
                f"Parameter '{param_name}' may not be supported by Gemini API "
                f"and will be passed through. Verify behavior with integration tests."
            )

    async def _generate_response_async(
        self,
        prompt: str,
        model: str | None = None,
        system_instructions: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        stop: list[str] | None = None,
        response_format: str | dict | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        logger.debug(f"Generating response for prompt: {prompt}")

        if not prompt.strip():
            logger.error("Received empty prompt")
            raise ValueError("Prompt cannot be empty")

        self.refresh_token_if_needed()

        used_model = model or self.model or "google/gemini-1.5-pro-002"

        used_max_tokens = None
        if max_tokens is not None:
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
            f"Using model: {used_model}, Temperature: {used_temperature}, "
            f"Max Tokens: {used_max_tokens}"
        )

        self.chat_history.append({"role": "user", "content": prompt})

        self._response_generated = False

        messages = self._convert_history_to_messages()

        if system_instructions:
            messages = [m for m in messages if m["role"] != "system"]
            messages.insert(0, {"role": "system", "content": system_instructions})

        logger.debug(f"Messages for API call: {messages}")

        api_params: dict[str, Any] = {
            "model": used_model,
            "messages": messages,
            "max_tokens": used_max_tokens,
            "temperature": used_temperature,
        }

        if top_p is not None and 0 <= float(top_p) <= 1:
            api_params["top_p"] = float(top_p)

        if presence_penalty is not None:
            self._warn_unsupported_param("presence_penalty")
            api_params["presence_penalty"] = float(presence_penalty)

        if frequency_penalty is not None:
            self._warn_unsupported_param("frequency_penalty")
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

        logger.debug(f"API params: {api_params}")

        try:
            response = await self.client.chat.completions.create(**api_params)

            logger.debug(f"Full API response: {response}")

            await asyncio.sleep(0.1)

            if response.choices and response.choices[0].message:
                if (
                    hasattr(response.choices[0].message, "tool_calls")
                    and response.choices[0].message.tool_calls
                ):
                    content = response.choices[0].message.content or ""
                    tool_calls = response.choices[0].message.tool_calls

                    self.chat_history.append(
                        {
                            "role": "assistant",
                            "content": content,
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

                    self._response_generated = True
                    logger.info("Response with tool calls generated successfully")
                    return f"{content}\n[Tool calls detected: {len(tool_calls)}]"
                elif response.choices[0].message.content:
                    content = response.choices[0].message.content
                    self.chat_history.append({"role": "assistant", "content": content})
                    self._response_generated = True
                    logger.info("Response generated successfully")
                    return content
                else:
                    logger.error("Unexpected response structure from API")
                    raise ValueError("Unexpected response structure from API")
            else:
                logger.error("Unexpected response structure from API")
                raise ValueError("Unexpected response structure from API")
        except Exception as e:
            error_str = str(e)

            if should_retry_exception(e):
                logger.warning(f"Transient error, will retry: {error_str[:200]}")
                raise create_rate_limit_error(e)

            logger.error(f"Error generating response: {error_str}")
            raise

    async def generate_response(
        self,
        prompt: str,
        model: str | None = None,
        system_instructions: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        stop: list[str] | None = None,
        response_format: str | dict | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Generate a response asynchronously with retry logic."""
        return await self._generate_response_with_retry(
            prompt,
            model=model,
            system_instructions=system_instructions,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            stop=stop,
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )

    @get_configured_retry_decorator()
    async def _generate_response_with_retry(
        self,
        prompt: str,
        model: str | None = None,
        system_instructions: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        stop: list[str] | None = None,
        response_format: str | dict | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Internal async method with retry decorator."""
        return await self._generate_response_async(
            prompt,
            model=model,
            system_instructions=system_instructions,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            stop=stop,
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )

    def generate_response_sync(
        self,
        prompt: str,
        model: str | None = None,
        system_instructions: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        stop: list[str] | None = None,
        response_format: str | dict | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Synchronous wrapper for generate_response."""
        return asyncio.run(
            self.generate_response(
                prompt,
                model=model,
                system_instructions=system_instructions,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                stop=stop,
                response_format=response_format,
                tools=tools,
                tool_choice=tool_choice,
                **kwargs,
            )
        )

    def add_tool_result(self, tool_call_id: str, content: Any) -> None:
        """Add a tool result to the conversation history."""
        if isinstance(content, dict):
            content = json.dumps(content)
        elif not isinstance(content, str):
            content = str(content)

        self.chat_history.append({"role": "tool", "tool_call_id": tool_call_id, "content": content})

    def clear_conversation(self):
        """Clear the conversation history."""
        logger.info("Clearing conversation history")
        self.chat_history = []

    async def test_connection_async(self) -> bool:
        """Test the connection to the Gemini API endpoint asynchronously."""
        try:
            logger.info("Testing connection to Gemini API")

            self.refresh_token_if_needed()

            response = await self.client.chat.completions.create(
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

    def test_connection(self) -> bool:
        """Test the connection to the Gemini API endpoint (sync wrapper)."""
        return asyncio.run(self.test_connection_async())
