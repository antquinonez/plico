# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import (
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class FFAzureClientBase(ABC):
    """
    Base class for Azure AI Inference clients.

    Provides common functionality for Azure-hosted models including:
    - Client initialization and authentication
    - Conversation history management
    - Response generation with parameter handling
    - Tool call support
    - Connection testing
    """

    @property
    @abstractmethod
    def _default_model(self) -> str:
        """Return the default model name for this client."""
        pass

    @property
    @abstractmethod
    def _default_max_tokens(self) -> int:
        """Return the default max_tokens for this client."""
        pass

    @property
    @abstractmethod
    def _default_temperature(self) -> float:
        """Return the default temperature for this client."""
        pass

    @property
    @abstractmethod
    def _default_instructions(self) -> str:
        """Return the default system instructions for this client."""
        pass

    @property
    @abstractmethod
    def _env_key_prefix(self) -> str:
        """Return the environment variable prefix (e.g., 'AZURE_MISTRAL')."""
        pass

    @property
    def _provider_name(self) -> str:
        """Return the provider name for model info. Override if needed."""
        return "AzureAI"

    def __init__(self, config: dict | None = None, **kwargs):
        logger.info(f"Initializing {self.__class__.__name__}")

        all_config = {**(config or {}), **kwargs}

        self.use_deployment_endpoint = all_config.get("use_deployment_endpoint", False)

        env_prefix = self._env_key_prefix

        for key, value in all_config.items():
            match key:
                case "api_key":
                    self.api_key = value or os.getenv(f"{env_prefix}_KEY")
                case "endpoint":
                    self.endpoint = value or os.getenv(f"{env_prefix}_ENDPOINT")
                case "model":
                    self.model = value
                case "temperature":
                    self.temperature = float(value)
                case "max_tokens":
                    self.max_tokens = int(value) if value is not None else self._default_max_tokens
                case "system_instructions":
                    self.system_instructions = value
                case "use_deployment_endpoint":
                    self.use_deployment_endpoint = bool(value)

        self.api_key = getattr(self, "api_key", os.getenv(f"{env_prefix}_KEY"))
        self.endpoint = getattr(self, "endpoint", os.getenv(f"{env_prefix}_ENDPOINT"))
        self.model = getattr(self, "model", os.getenv(f"{env_prefix}_MODEL", self._default_model))
        self.temperature = getattr(
            self,
            "temperature",
            float(os.getenv(f"{env_prefix}_TEMPERATURE", str(self._default_temperature))),
        )
        self.max_tokens = getattr(
            self,
            "max_tokens",
            int(os.getenv(f"{env_prefix}_MAX_TOKENS", str(self._default_max_tokens))),
        )
        self.system_instructions = getattr(
            self,
            "system_instructions",
            os.getenv(f"{env_prefix}_ASSISTANT_INSTRUCTIONS", self._default_instructions),
        )

        if self.endpoint and not self.endpoint.startswith(("http://", "https://")):
            self.endpoint = f"https://{self.endpoint}"

        self.model = self.model.lower()

        logger.debug(
            f"Model: {self.model}, Temperature: {self.temperature}, Max Tokens: {self.max_tokens}"
        )
        logger.debug(f"System instructions: {self.system_instructions[:50]}...")
        logger.debug(f"Using endpoint: {self.endpoint}")
        logger.debug(f"Using deployment endpoint: {self.use_deployment_endpoint}")

        self.conversation_history: list[dict[str, Any]] = []
        self.client: ChatCompletionsClient = self._initialize_client()

    def _initialize_client(self) -> ChatCompletionsClient:
        """Initialize and return the Azure AI Inference ChatCompletionsClient."""
        logger.info(f"Initializing {self.__class__.__name__} client")

        if not self.api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")

        if not self.endpoint:
            logger.error("Endpoint URL not found")
            raise ValueError("Endpoint URL not found")

        endpoint = self.endpoint
        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]

        if self.use_deployment_endpoint:
            deployment_name = self.model.lower().replace("-", "").replace(".", "")
            full_endpoint = f"{endpoint}/openai/deployments/{deployment_name}"
        else:
            full_endpoint = f"{endpoint}/models"

        logger.debug(f"Using endpoint: {full_endpoint}")

        return ChatCompletionsClient(
            endpoint=full_endpoint, credential=AzureKeyCredential(self.api_key)
        )

    def _convert_history_to_messages(
        self,
    ) -> list[SystemMessage | UserMessage | AssistantMessage | ToolMessage]:
        """Convert conversation history to Azure AI message format."""
        messages = []

        if self.system_instructions:
            messages.append(SystemMessage(content=self.system_instructions))

        for message in self.conversation_history:
            if message["role"] == "user":
                messages.append(UserMessage(content=message["content"]))
            elif message["role"] == "assistant":
                messages.append(AssistantMessage(content=message["content"]))
            elif message["role"] == "tool":
                messages.append(
                    ToolMessage(
                        tool_call_id=message.get("tool_call_id", ""),
                        content=message["content"],
                    )
                )

        return messages

    def get_conversation_history(self) -> list[dict[str, Any]]:
        """Get the conversation history."""
        return self.conversation_history

    def set_conversation_history(self, history: list[dict[str, Any]]) -> None:
        """Set the conversation history."""
        self.conversation_history = history

    def clear_conversation(self) -> None:
        """Clear the conversation history."""
        logger.info("Clearing conversation history")
        self.conversation_history = []

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
        """
        Generate a response from the model with robust parameter handling.

        Args:
            prompt: User's input text
            model: Model to use (overrides default)
            system_instructions: System instructions (overrides default)
            temperature: Controls randomness (0-2)
            max_tokens: Maximum tokens to generate
            max_completion_tokens: Alternative name for max_tokens
            top_p: Nucleus sampling parameter
            presence_penalty: Penalizes repeated tokens
            frequency_penalty: Penalizes frequent tokens
            stop: List of strings that stop generation
            response_format: Format of the response ("text" or "json")
            tools: List of tools to make available
            tool_choice: Tool choice strategy
            **kwargs: Additional parameters

        Returns:
            The model's response as a string
        """
        if not prompt.strip():
            raise ValueError("Empty prompt provided")

        logger.debug(f"Generating response for prompt: {prompt[:50]}...")

        used_model = model or self.model or self._default_model

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
            self.conversation_history.append({"role": "user", "content": prompt})

            messages = self._convert_history_to_messages()

            if system_instructions:
                if messages and isinstance(messages[0], SystemMessage):
                    messages = messages[1:]
                messages.insert(0, SystemMessage(content=system_instructions))

            api_params = {
                "messages": messages,
                "max_tokens": used_max_tokens,
                "temperature": used_temperature,
                "stream": False,
            }

            if not self.use_deployment_endpoint:
                api_params["model"] = used_model

            if top_p is not None and 0 <= float(top_p) <= 1:
                api_params["top_p"] = float(top_p)

            if presence_penalty is not None and -2 <= float(presence_penalty) <= 2:
                api_params["presence_penalty"] = float(presence_penalty)

            if frequency_penalty is not None and -2 <= float(frequency_penalty) <= 2:
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
                else:
                    api_params["response_format"] = {"type": "text"}

            if tools and isinstance(tools, list):
                api_params["tools"] = tools
                if tool_choice:
                    api_params["tool_choice"] = tool_choice

            logger.debug(f"Calling Azure API with params: {list(api_params.keys())}")

            response = self.client.complete(**api_params)

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

        except HttpResponseError as e:
            if e.status_code == 400:
                response_data = e.response.json() if hasattr(e, "response") else {}
                if isinstance(response_data, dict) and "error" in response_data:
                    error_msg = f"Request triggered an {response_data['error']['code']} error: {response_data['error']['message']}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

            logger.error(f"HTTP error: {str(e)}")
            raise RuntimeError(
                f"Error generating response from {self.__class__.__name__}: {str(e)}"
            )

        except Exception as e:
            logger.error("Problem with response generation")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- model: {self.model}")
            logger.error(f"  -- max_tokens: {self.max_tokens}")
            logger.error(f"  -- temperature: {self.temperature}")

            raise RuntimeError(
                f"Error generating response from {self.__class__.__name__}: {str(e)}"
            )

    def get_model_info(self):
        """Get information about the model."""
        try:
            logger.debug(f"Getting model info for: {self.model}")
            if not self.use_deployment_endpoint:
                from collections import namedtuple

                ModelInfo = namedtuple(
                    "ModelInfo", ["model_name", "model_type", "model_provider_name"]
                )
                return ModelInfo(
                    model_name=self.model,
                    model_type="chat-completions",
                    model_provider_name=self._provider_name,
                )
            else:
                return self.client.get_model_info(model=self.model)
        except Exception as e:
            logger.error(f"Failed to get model info: {str(e)}")
            raise RuntimeError(f"Error getting model info: {str(e)}")

    def test_connection(self) -> bool:
        """
        Test the connection to the Azure AI endpoint.

        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            logger.info(f"Testing connection to endpoint: {self.endpoint}")

            if not self.use_deployment_endpoint:
                response = self.client.complete(
                    messages=[
                        SystemMessage(content="Test connection"),
                        UserMessage(content="Hello"),
                    ],
                    max_tokens=5,
                    model=self.model,
                )
                logger.info("Connection successful")
                return True
            else:
                models = self.client.list_models()
                logger.info(
                    f"Connection successful. Available models: {[m.model_name for m in models]}"
                )
                return True

        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
