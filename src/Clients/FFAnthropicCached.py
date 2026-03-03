# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from __future__ import annotations

import logging
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from ..ConversationHistory import ConversationHistory
from ..OrderedPromptHistory import OrderedPromptHistory
from ..PermanentHistory import PermanentHistory

load_dotenv()

logger = logging.getLogger(__name__)


class FFAnthropicCached:
    def __init__(self, config: dict | None = None, **kwargs):
        logger.info("Initializing FFAnthropicCached")

        default_model = "claude-3-5-sonnet-20240620"
        default_max_tokens = 2000
        default_temperature = 0.5

        default_instructions = "Respond accurately to user queries. Never start with a preamble, such as 'The provided JSON data structure has been reordered and formatted as valid'. Immediately address the ask or request. Do not add meta information about your response. If there's nothing to do, answer with ''"

        all_config = {**(config or {}), **kwargs}

        self.api_key = (
            all_config.get("api_key", os.getenv("ANTHROPIC_TOKEN"))
            if all_config
            else os.getenv("ANTHROPIC_TOKEN")
        )
        self.model = (
            all_config.get("model", default_model)
            if all_config
            else os.getenv("ANTHROPIC_MODEL", default_model)
        )
        self.max_tokens = (
            int(all_config.get("max_tokens", default_max_tokens))
            if all_config
            else int(os.getenv("ANTHROPIC_MAX_TOKENS", default_max_tokens))
        )
        self.temperature = (
            float(all_config.get("temperature", default_temperature))
            if all_config
            else float(os.getenv("ANTHROPIC_TEMPERATURE", default_temperature))
        )
        self.system_instructions = (
            config.get("system_instructions", default_instructions)
            if config
            else os.getenv("ANTHROPIC_ASSISTANT_INSTRUCTIONS", default_instructions)
        )

        self.conversation_history = ConversationHistory()
        self.permanent_history = PermanentHistory()
        self.ordered_history = OrderedPromptHistory()

        self.client: Anthropic = self._initialize_client()

        logger.debug(
            f"Model: {self.model}, Temperature: {self.temperature}, Max Tokens: {self.max_tokens}"
        )
        logger.debug(f"System instructions: {self.system_instructions}")

    def _initialize_client(self) -> Anthropic:
        logger.info("Initializing Anthropic client")
        api_key = self.api_key
        if not api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")
        return Anthropic(api_key=api_key)

    def generate_response(
        self,
        prompt: str,
        model: str | None = None,
        prompt_name: str | None = None,
    ) -> str:
        logger.debug(f"Generating response for prompt: {prompt}")
        used_model = model if model else self.model
        logger.debug(f"Using model: {used_model}")
        try:
            self.conversation_history.add_turn_user(prompt)
            self.permanent_history.add_turn_user(prompt)

            turns = self.conversation_history.get_turns()
            if not turns:
                logger.error("Conversation history is empty")
                raise ValueError("Conversation history is empty")

            response = self.client.messages.create(
                model=used_model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=[
                    {
                        "type": "text",
                        "text": self.system_instructions,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=turns,
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
            )

            assistant_response = response.content[0].text

            self.conversation_history.add_turn_assistant(assistant_response)
            self.permanent_history.add_turn_assistant(assistant_response)
            self.ordered_history.add_interaction(
                used_model, prompt, assistant_response, prompt_name
            )

            logger.info("Response generated successfully")
            return assistant_response

        except Exception as e:
            logger.error("Problem with response generation")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- model: {used_model}")
            logger.error(f"  -- system: {self.system_instructions}")
            logger.error(f"  -- conversation history: {self.conversation_history.get_turns()}")
            logger.error(f"  -- max_tokens: {self.max_tokens}")
            logger.error(f"  -- temperature: {self.temperature}")

            raise RuntimeError(f"Error generating response from Claude: {str(e)}")

    def get_interaction_history(self) -> list[dict[str, Any]]:
        interactions = self.ordered_history.get_all_interactions()
        return [i.to_dict() for i in interactions]

    def get_last_n_interactions(self, n: int) -> list[dict[str, Any]]:
        all_interactions = self.ordered_history.get_all_interactions()
        return [i.to_dict() for i in all_interactions[-n:]]

    def get_interaction(self, sequence_number: int) -> dict[str, Any] | None:
        all_interactions = self.ordered_history.get_all_interactions()
        interaction = next(
            (i for i in all_interactions if i.sequence_number == sequence_number), None
        )
        return interaction.to_dict() if interaction else None

    def get_model_interactions(self, model: str) -> list[dict[str, Any]]:
        all_interactions = self.ordered_history.get_all_interactions()
        return [i.to_dict() for i in all_interactions if i.model == model]

    def get_interactions_by_prompt_name(self, prompt_name: str) -> list[dict[str, Any]]:
        return [
            i.to_dict() for i in self.ordered_history.get_interactions_by_prompt_name(prompt_name)
        ]

    def get_latest_interaction(self) -> dict[str, Any] | None:
        all_interactions = self.ordered_history.get_all_interactions()
        return all_interactions[-1].to_dict() if all_interactions else None

    def get_prompt_history(self) -> list[str]:
        return [i.prompt for i in self.ordered_history.get_all_interactions()]

    def get_response_history(self) -> list[str]:
        return [i.response for i in self.ordered_history.get_all_interactions()]

    def get_model_usage_stats(self) -> dict[str, int]:
        usage_stats: dict[str, int] = {}
        for interaction in self.ordered_history.get_all_interactions():
            usage_stats[interaction.model] = usage_stats.get(interaction.model, 0) + 1
        return usage_stats

    def get_prompt_name_usage_stats(self) -> dict[str, int]:
        return self.ordered_history.get_prompt_name_usage_stats()

    def clear_conversation(self):
        logger.info("Clearing conversation history (permanent and ordered histories retained)")
        self.conversation_history = ConversationHistory()

    def get_prompt_dict(self) -> dict[str, list[dict[str, Any]]]:
        return self.ordered_history.to_dict()
