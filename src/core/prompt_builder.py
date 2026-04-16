# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Prompt assembly with history resolution and variable interpolation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from .prompt_utils import interpolate_prompt

logger = logging.getLogger(__name__)

REFERENCES_PATTERN = re.compile(r"<REFERENCES>.*?</REFERENCES>\s*", re.DOTALL)


class PromptBuilder:
    """Builds final prompts with history context and variable interpolation.

    Reads from the shared prompt-attribute history to resolve
    ``{{prompt_name.response}}`` patterns and assemble conversation
    context blocks.

    Args:
        prompt_attr_history: The shared prompt-attribute history list.

    """

    def __init__(self, prompt_attr_history: list[dict[str, Any]]) -> None:
        self._prompt_attr_history = prompt_attr_history
        self.last_resolved_prompt: str | None = None

    def build_prompt(
        self,
        prompt: str,
        history: list[str] | None = None,
        dependencies: dict | None = None,
    ) -> tuple[str, set[str]]:
        """Build the final prompt with history and variable interpolation.

        Args:
            prompt: The prompt template (may contain {{}} interpolation patterns)
            history: List of prompt names to include in conversation history
            dependencies: Additional dependencies (unused but kept for compatibility)

        Returns:
            Tuple of (final_prompt, set_of_interpolated_prompt_names)

        """
        if not history:
            logger.debug("No history provided, checking for interpolation only")
            history = []

        logger.info(f"Building prompt with history references: {history}")
        logger.info(f"Current history size: {len(self._prompt_attr_history)}")

        for idx, entry in enumerate(self._prompt_attr_history):
            logger.debug("==================================================================")
            logger.debug(f"History entry {idx}:")
            logger.debug("==================================================================")
            logger.debug(f"  Prompt name: {entry.get('prompt_name')}")
            logger.debug("------------------------------------------------------------------")
            logger.debug(f"  Prompt: {entry.get('prompt')}")
            logger.debug("------------------------------------------------------------------")
            logger.debug(f"  Response: {entry.get('response')}")

        history_dict: dict[str, str] = {}
        for entry in self._prompt_attr_history:
            prompt_name = entry.get("prompt_name")
            if prompt_name:
                response = entry.get("response")
                if isinstance(response, dict):
                    response = json.dumps(response)
                elif response is not None:
                    response = str(response)
                else:
                    response = ""
                history_dict[prompt_name] = response

        resolved_prompt, interpolated_names = interpolate_prompt(prompt, history_dict)

        if interpolated_names:
            logger.info(f"Interpolated {len(interpolated_names)} prompt(s): {interpolated_names}")

        history_entries = []
        for prompt_name in history:
            logger.debug(
                "==================================================================================="
            )
            logger.debug(f"Looking for stored named interactions with prompt_name: {prompt_name}")
            matching_entries = [
                entry
                for entry in self._prompt_attr_history
                if entry.get("prompt_name") == prompt_name
            ]

            if len(matching_entries) == 0:
                logger.warning(f"-- No matching entries for requested prompt_name: {prompt_name}")
            else:
                logger.debug(f"-- Found {len(matching_entries)} matching entries")

            if matching_entries:
                latest = matching_entries[-1]
                stored_prompt = latest["prompt"]
                resolved_history_prompt, _ = interpolate_prompt(stored_prompt, history_dict)
                resolved_history_prompt = REFERENCES_PATTERN.sub(
                    "", resolved_history_prompt
                ).strip()
                history_entries.append(
                    {
                        "prompt_name": latest.get("prompt_name"),
                        "prompt": resolved_history_prompt,
                        "response": latest["response"],
                    }
                )
                logger.debug(
                    f"Added entry for {prompt_name}: {latest['prompt']} -> {latest['response']}"
                )

        filtered_history = [
            entry for entry in history_entries if entry.get("prompt_name") not in interpolated_names
        ]

        formatted_history = []
        for entry in filtered_history:
            formatted_entry = (
                f"<interaction prompt_name='{entry['prompt_name']}'>\n"
                f"USER: {entry['prompt']}\n"
                f"SYSTEM: {entry['response']}\n"
                f"</interaction>"
            )
            formatted_history.append(formatted_entry)

        if formatted_history:
            final_prompt = (
                "<conversation_history>\n"
                + "\n".join(formatted_history)
                + "\n</conversation_history>\n"
                + "===\n"
                + "Based on the conversation history above, please answer: "
                + resolved_prompt
            )
        else:
            final_prompt = resolved_prompt

        logger.info(f"Final constructed prompt:\n{final_prompt}")
        return final_prompt, interpolated_names
