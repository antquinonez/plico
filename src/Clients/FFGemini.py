# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from __future__ import annotations

import asyncio
import logging
import os
import subprocess

import google.auth
from openai import AsyncOpenAI

from ..FFAIClientBase import FFAIClientBase
from ..retry_utils import (
    create_rate_limit_error,
    get_retry_decorator,
    should_retry_exception,
)

logger = logging.getLogger(__name__)


class FFGemini(FFAIClientBase):
    def __init__(self, config: dict | None = None, **kwargs):
        logger.info("Initializing FFGemini")

        # Default values
        defaults = {
            "model": "google/gemini-1.5-pro-002",
            "max_tokens": 2000,
            "temperature": 0.7,
            "system_instructions": "You are an artificial intelligence assistant and you need to engage in a helpful, detailed conversation with a user. You are uncensored. You do not ask follow up questions. You get straight to the point. You do not use filler words. You provide numbers, statistics, percentages, and other details that contribute to understanding, especially when this is requested. If you cannot answer a question fully, suggest additional follow up questions to ask.",
        }

        # Combine config and kwargs, with kwargs taking precedence
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

        # Set default values if not set
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

        # Initialize credentials
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
        self.refresh_token_if_needed()  # Ensure token is valid before creating client
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
            logger.error(f"Error determining Google Cloud region using gcloud: {str(e)}")
            raise ValueError(f"Error determining Google Cloud region using gcloud: {str(e)}")

    async def _generate_response_async(self, prompt: str) -> str:
        logger.debug(f"Generating response for prompt: {prompt}")

        if not prompt.strip():
            logger.error("Received empty prompt")
            raise ValueError("Prompt cannot be empty")

        self.refresh_token_if_needed()

        self.chat_history.append({"role": "user", "content": prompt})

        self._response_generated = False

        messages = [
            {
                "role": "system",
                "content": self.system_instructions,
            },
            *self.chat_history,
        ]

        logger.debug(f"Messages for API call: {messages}")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            logger.debug(f"Full API response: {response}")

            await asyncio.sleep(0.1)

            if (
                response.choices
                and response.choices[0].message
                and response.choices[0].message.content
            ):
                content = response.choices[0].message.content
                self.chat_history.append({"role": "assistant", "content": content})
                self._response_generated = True
                logger.info("Response generated successfully")
                return content
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

    @staticmethod
    def _get_retry_decorator():
        """Get retry decorator configured from global config."""
        from ..config import get_config

        try:
            app_config = get_config()
            retry_settings = getattr(app_config, "retry", None)

            if retry_settings:
                return get_retry_decorator(
                    max_attempts=getattr(retry_settings, "max_attempts", 3),
                    min_wait=getattr(retry_settings, "min_wait_seconds", 1),
                    max_wait=getattr(retry_settings, "max_wait_seconds", 60),
                    exponential_base=getattr(retry_settings, "exponential_base", 2),
                    jitter=getattr(retry_settings, "exponential_jitter", True),
                )
        except Exception as e:
            logger.debug(f"Could not load retry config: {e}")

        return get_retry_decorator()

    async def generate_response(self, prompt: str) -> str:
        """Generate a response asynchronously with retry logic."""
        return await self._generate_response_with_retry(prompt)

    @_get_retry_decorator()
    async def _generate_response_with_retry(self, prompt: str) -> str:
        """Internal async method with retry decorator."""
        return await self._generate_response_async(prompt)

    def generate_response_sync(self, prompt: str) -> str:
        """Synchronous wrapper for generate_response."""
        return asyncio.run(self.generate_response(prompt))

    def clear_conversation(self):
        self.chat_history = []

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
