# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

import logging
import os

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import AssistantMessage, SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class FFAzureMSDeepSeekR1:
    def __init__(self, config: dict | None = None, **kwargs):
        logger.info("Initializing FFDeepSeek")

        # DEFAULT VALUES
        defaults = {
            "model": "MAI-DS-R1",
            "max_tokens": 2048,
            "temperature": 0.5,
            "instructions": "Respond accurately to user queries. Never start with a preamble. Immediately address the ask or request. Do not add meta information about your response. If there's nothing to do, answer with ''",
        }

        # Combine config and kwargs, with kwargs taking precedence
        all_config = {**(config or {}), **kwargs}

        for key, value in all_config.items():
            match key:
                case "api_key":
                    self.api_key = value or os.getenv("AZURE_MSDEEPSEEK_KEY")
                case "endpoint":
                    self.endpoint = value or os.getenv("AZURE_MSDEEPSEEK_ENDPOINT")
                case "model":
                    self.model = value
                case "temperature":
                    self.temperature = float(value)
                case "max_tokens":
                    self.max_tokens = int(value)
                case "system_instructions":
                    self.system_instructions = value

        # Set default values if not set
        self.api_key = getattr(self, "api_key", os.getenv("AZURE_MSDEEPSEEK_KEY"))
        self.endpoint = getattr(self, "endpoint", os.getenv("AZURE_MSDEEPSEEK_ENDPOINT"))
        self.model = getattr(self, "model", os.getenv("AZURE_MSDEEPSEEK_MODEL", defaults["model"]))
        self.temperature = getattr(
            self,
            "temperature",
            float(os.getenv("AZURE_MSDEEPSEEK_TEMPERATURE", defaults["temperature"])),
        )
        self.max_tokens = getattr(
            self,
            "max_tokens",
            int(os.getenv("AZURE_MSDEEPSEEK_MAX_TOKENS", defaults["max_tokens"])),
        )
        self.system_instructions = getattr(
            self,
            "system_instructions",
            os.getenv("AZURE_MSDEEPSEEK_SYSTEM_INSTRUCTIONS", defaults["instructions"]),
        )

        logger.debug(
            f"Model: {self.model}, Temperature: {self.temperature}, Max Tokens: {self.max_tokens}"
        )
        logger.debug(f"System instructions: {self.system_instructions}")

        self.conversation_history = []
        self.client = self._initialize_client()

    def _initialize_client(self) -> ChatCompletionsClient:
        """Initialize and return the Azure AI Inference ChatCompletionsClient."""
        logger.info("Initializing Azure DeepSeek client")

        api_key = self.api_key
        endpoint = self.endpoint

        if not api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")

        if not endpoint:
            logger.error("Endpoint URL not found")
            raise ValueError("Endpoint URL not found")

        return ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get the conversation history."""
        return self.conversation_history

    def set_conversation_history(self, history: list[dict[str, str]]) -> None:
        """Set the conversation history."""
        self.conversation_history = history

    def _convert_history_to_messages(self) -> list[SystemMessage | UserMessage | AssistantMessage]:
        """Convert conversation history to Azure AI message format."""
        messages = []

        # Add system message
        if self.system_instructions:
            messages.append(SystemMessage(content=self.system_instructions))

        # Add conversation history
        for message in self.conversation_history:
            if message["role"] == "user":
                messages.append(UserMessage(content=message["content"]))
            elif message["role"] == "assistant":
                messages.append(AssistantMessage(content=message["content"]))

        return messages

    def generate_response(
        self,
        prompt: str,
        model: str | None = None,
        system_instructions: str | None = None,
        **kwargs,
    ) -> str:
        if not prompt.strip():
            raise ValueError("Empty prompt provided")

        logger.debug(f"Generating response for prompt: {prompt}")

        # Determine model to use
        used_model = model if model else self.model
        logger.debug(f"Using model: {used_model}")

        try:
            # Add user prompt to history
            self.conversation_history.append({"role": "user", "content": prompt})

            # Create messages list
            messages = self._convert_history_to_messages()

            # If system_instructions parameter is provided, replace the system message
            if system_instructions:
                # Remove existing system message if present
                if messages and isinstance(messages[0], SystemMessage):
                    messages = messages[1:]
                # Add new system message at the beginning
                messages.insert(0, SystemMessage(content=system_instructions))

            # Call Azure API
            response = self.client.complete(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                model=used_model,
            )

            # Extract response
            assistant_response = response.choices[0].message.content

            # Add assistant's response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            logger.info("Response generated successfully")
            return assistant_response

        except Exception as e:
            logger.error("Problem with response generation")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- model: {self.model}")
            logger.error(f"  -- system: {self.system_instructions}")
            logger.error(f"  -- conversation history: {self.conversation_history}")
            logger.error(f"  -- max_tokens: {self.max_tokens}")
            logger.error(f"  -- temperature: {self.temperature}")

            raise RuntimeError(f"Error generating response from Azure DeepSeek: {str(e)}")

    def stream_response(
        self, prompt: str, model: str | None = None, system_instructions: str | None = None
    ):
        """Stream the response from the model."""
        if not prompt.strip():
            raise ValueError("Empty prompt provided")

        logger.debug(f"Streaming response for prompt: {prompt}")

        # Determine model to use
        used_model = model if model else self.model
        logger.debug(f"Using model: {used_model}")

        try:
            # Add user prompt to history
            self.conversation_history.append({"role": "user", "content": prompt})

            # Create messages list
            messages = self._convert_history_to_messages()

            # If system_instructions parameter is provided, replace the system message
            if system_instructions:
                # Remove existing system message if present
                if messages and isinstance(messages[0], SystemMessage):
                    messages = messages[1:]
                # Add new system message at the beginning
                messages.insert(0, SystemMessage(content=system_instructions))

            # Call Azure API with streaming enabled
            stream_response = self.client.complete(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                model=used_model,
                stream=True,
            )

            # Build the full response while yielding chunks
            full_response = ""

            for update in stream_response:
                if update.choices:
                    content = update.choices[0].delta.content or ""
                    full_response += content
                    yield content

            # Add assistant's response to history
            self.conversation_history.append({"role": "assistant", "content": full_response})

            logger.info("Stream response completed successfully")

        except Exception as e:
            logger.error("Problem with stream response generation")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- model: {self.model}")
            logger.error(f"  -- system: {self.system_instructions}")
            logger.error(f"  -- conversation history: {self.conversation_history}")
            logger.error(f"  -- max_tokens: {self.max_tokens}")
            logger.error(f"  -- temperature: {self.temperature}")

            raise RuntimeError(f"Error streaming response from Azure DeepSeek: {str(e)}")

    def clear_conversation(self):
        logger.info("Clearing conversation history")
        self.conversation_history = []
