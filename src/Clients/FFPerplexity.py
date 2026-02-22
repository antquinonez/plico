# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
#
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
#
# Contact: antquinonez@farfiner.com
# filename: src/lib/AI/FFPerplexity.py

import os
import time
import logging
from typing import Optional, List, Dict, Any, Union
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class FFPerplexity:
    def __init__(self, config: Optional[dict] = None, **kwargs):
        logger.info("Initializing FFPerplexity")

        # DEFAULT VALUES
        defaults = {
            "model": "sonar",
            "max_tokens": 4000,
            "temperature": 0.5,
            "instructions": "Respond accurately to user queries. Never start with a preamble. Immediately address the ask or request. Do not add meta information about your response. If there's nothing to do, answer with ''",
        }

        # Combine config and kwargs, with kwargs taking precedence
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
                    self.max_tokens = int(value)
                case "system_instructions":
                    self.system_instructions = value

        # Set default values if not set
        self.api_key = getattr(self, "api_key", os.getenv("PERPLEXITY_TOKEN"))
        self.model = getattr(
            self, "model", os.getenv("PERPLEXITY_MODEL", defaults["model"])
        )
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

        self.conversation_history = []
        self.client: OpenAI = self._initialize_client()

    def _initialize_client(self) -> OpenAI:
        """Initialize and return the OpenAI client."""
        logger.info("Initializing Perplexity client")
        api_key = self.api_key
        if not api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")

        return OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get the conversation history."""
        return self.conversation_history

    def set_conversation_history(self, history: List[Dict[str, str]]) -> None:
        """Set the conversation history."""
        self.conversation_history = history

    def generate_response(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_instructions: Optional[str] = None,
    ) -> str:
        if not prompt.strip():
            raise ValueError("Empty prompt provided")

        logger.debug(f"Generating response for prompt: {prompt}")

        # are we using the model and is_o1 from init or the one passed with the generate_response method?
        used_model = model if model else self.model
        logger.debug(f"Using model: {used_model}")

        try:
            self.conversation_history.append({"role": "user", "content": prompt})

            messages = [
                {
                    "role": "system",
                    "content": system_instructions or self.system_instructions,
                },
                *self.conversation_history,
            ]

            response = self.client.chat.completions.create(
                model=used_model, messages=messages, temperature=self.temperature
            )

            assistant_response = response.choices[0].message.content
            self.conversation_history.append(
                {"role": "assistant", "content": assistant_response}
            )

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

            raise RuntimeError(f"Error generating response from Perplexity: {str(e)}")

    def clear_conversation(self):
        logger.info("Clearing conversation history")
        self.conversation_history = []
