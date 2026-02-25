# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
#
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
#
# Contact: antquinonez@farfiner.com
# filename: src/lib/AI/FFAI.py

"""Declarative context handling API wrapper for AI clients.

This module provides the FFAI class which wraps AI client implementations
and adds declarative context management, history tracking, and DataFrame
export capabilities.
"""

import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable

# =============================
# Persistence Decorator
# =============================
from functools import wraps
from typing import Any

import polars as pl

from .FFAIClientBase import FFAIClientBase
from .OrderedPromptHistory import OrderedPromptHistory
from .PermanentHistory import PermanentHistory


def auto_persist(method: Callable[..., pl.DataFrame]) -> Callable[..., pl.DataFrame]:
    """Persist DataFrame after method execution if auto_persist is enabled."""

    @wraps(method)
    def wrapper(self: "FFAI", *args: Any, **kwargs: Any) -> pl.DataFrame:  # noqa: ANN401
        df = method(self, *args, **kwargs)
        if self.auto_persist and self.persist_name and not df.is_empty():
            file_path = os.path.join(
                self.persist_dir, f"{self.persist_name}_{method.__name__}.parquet"
            )
            try:
                df.write_parquet(file_path)
                logger.info(f"Auto-persisted DataFrame to {file_path}")
            except Exception as e:
                logger.error(f"Failed to auto-persist DataFrame: {str(e)}")
        return df

    return wrapper


# Configure logging
logger = logging.getLogger(__name__)


class FFAI:
    """Declarative context handling wrapper for AI clients.

    This class wraps an AI client implementation and adds:
    - Named prompt management for declarative context assembly
    - Multiple history tracking mechanisms
    - DataFrame export capabilities
    - Automatic persistence of history data

    Attributes:
        client: The underlying AI client instance.
        history: Raw interaction history.
        clean_history: Cleaned interaction history.
        prompt_attr_history: History indexed by prompt attributes.
        ordered_history: Ordered prompt-response history.
        permanent_history: Chronological turn history.

    """

    def __init__(
        self,
        client: FFAIClientBase,
        persist_dir: str = "./ffai_data",
        persist_name: str | None = None,
        auto_persist: bool = False,
        shared_prompt_attr_history: list[dict[str, Any]] | None = None,
        history_lock: threading.Lock | None = None,
    ) -> None:
        """Initialize the FFAI wrapper.

        Args:
            client: AI client instance to wrap.
            persist_dir: Directory for persistence files.
            persist_name: Base name for persisted files.
            auto_persist: Whether to automatically persist DataFrames.
            shared_prompt_attr_history: Optional shared history list for parallel execution.
            history_lock: Optional lock for thread-safe history access.

        """
        logger.info("Initializing FFAI wrapper")

        # =============================
        # Persistence Configuration
        # =============================
        self.persist_dir = persist_dir
        self.persist_name = persist_name
        self.auto_persist = auto_persist
        os.makedirs(self.persist_dir, exist_ok=True)

        self.client = client
        self._history_lock = history_lock

        self.history = []
        self.clean_history = []

        if shared_prompt_attr_history is not None:
            self.prompt_attr_history = shared_prompt_attr_history
        else:
            self.prompt_attr_history = []

        self.permanent_history = PermanentHistory()
        self.ordered_history = OrderedPromptHistory()
        self.clean_ordered_history = OrderedPromptHistory()
        self.named_prompt_ordered_history = OrderedPromptHistory()

    def set_client(self, client: FFAIClientBase) -> None:
        """Switch to a different AI client."""
        logger.info(f"Switching client to {client.__class__.__name__}")
        self.client = client

    def _extract_json(self, text: str) -> Any | None:  # noqa: ANN401
        """Extract JSON from text, handling markdown code blocks and JSON within first 20 chars."""
        _MARKDOWN_PATTERN = re.compile(r"```(?:json)?\s*(?P<content>[\s\S]*?)\s*```")

        def _clean_text(text: str) -> str:
            return text.strip().replace("\ufeff", "")

        def _extract_from_markdown(text: str) -> str | None:
            if match := _MARKDOWN_PATTERN.search(text):
                return _clean_text(match.group("content"))
            return None

        # Check if JSON is within first 20 characters
        first_20_chars = text[:20]
        try:
            if json.loads(first_20_chars):
                # If JSON found in first 20 chars, try markdown first
                markdown_content = _extract_from_markdown(text)
                if markdown_content:
                    try:
                        return json.loads(markdown_content)
                    except json.JSONDecodeError:
                        pass

                # If no valid markdown JSON, parse the entire text
                return json.loads(_clean_text(text))
        except json.JSONDecodeError:
            pass

        return None

    # get the system instructions from the client; this is stored in self.client.system_instructions
    def get_system_instructions(self) -> str | None:
        """Get system instructions from the client."""
        if hasattr(self.client, "system_instructions"):
            return self.client.system_instructions
        return None

    def _clean_response(self, response: Any) -> Any:  # noqa: ANN401
        """Process and validate the evaluation response."""
        logger.debug(f"Cleaning response: {response}")

        if not isinstance(response, str):
            return response

        response = re.sub(r"<think[\s\S]*?</think\s*>", "", response)
        logger.debug(f"Response after removing think tags: {response}")

        cleaned_json = self._extract_json(response)
        logger.debug(f"cleaned_json: {cleaned_json}")

        if cleaned_json is not None:
            if isinstance(cleaned_json, dict):
                for key, value in cleaned_json.items():
                    if isinstance(value, str):
                        cleaned_json[key] = re.sub(r"<think[\s\S]*?</think\s*>", "", value)
            return cleaned_json
        return response

    def _build_prompt(
        self,
        prompt: str,
        history: list[str] | None = None,
        dependencies: dict | None = None,
    ) -> str:
        if not history:
            logger.debug("No history provided, returning original prompt")
            return prompt

        logger.info(f"Building prompt with history references: {history}")
        logger.info(f"Current history size: {len(self.prompt_attr_history)}")

        for idx, entry in enumerate(self.prompt_attr_history):
            logger.debug("==================================================================")
            logger.debug(f"History entry {idx}:")
            logger.debug("==================================================================")
            logger.debug(f"  Prompt name: {entry.get('prompt_name')}")
            logger.debug("------------------------------------------------------------------")
            logger.debug(f"  Prompt: {entry.get('prompt')}")
            logger.debug("------------------------------------------------------------------")
            logger.debug(f"  Response: {entry.get('response')}")

        history_entries = []
        for prompt_name in history:
            logger.debug(
                "==================================================================================="
            )
            logger.debug(f"Looking for stored named interactions with prompt_name: {prompt_name}")
            matching_entries = [
                entry
                for entry in self.prompt_attr_history
                if entry.get("prompt_name") == prompt_name
            ]

            if len(matching_entries) == 0:
                logger.warning(f"-- No matching entries for requested prompt_name: {prompt_name}")
            else:
                logger.debug(f"-- Found {len(matching_entries)} matching entries")

            if matching_entries:
                latest = matching_entries[-1]
                history_entries.append(
                    {
                        "prompt_name": latest.get("prompt_name"),
                        "prompt": latest["prompt"],
                        "response": latest["response"],
                    }
                )
                logger.debug(
                    f"Added entry for {prompt_name}: {latest['prompt']} -> {latest['response']}"
                )

        formatted_history = []
        for entry in history_entries:
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
                + prompt
            )
        else:
            final_prompt = prompt

        logger.info(f"Final constructed prompt:\n{final_prompt}")
        return final_prompt

    def generate_response(
        self,
        prompt: str,
        model: str | None = None,
        prompt_name: str | None = None,
        history: list[str] | None = None,
        dependencies: list[str] | None = None,
        system_instructions: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> str:
        """Generate response using the configured AI client."""
        logger.debug(
            "\n==================================================================================="
        )
        logger.info(f"Generating response for prompt: '{prompt}'")
        logger.debug(f"Prompt_name: '{prompt_name}'")
        logger.debug(
            f"System instructions: '{system_instructions}'"
        ) if system_instructions else logger.debug("No system instructions provided")
        logger.debug(f"History: {history}") if history else logger.debug("No history provided")
        logger.debug(f"Dependencies: {dependencies}") if dependencies else logger.debug(
            "No dependencies provided"
        )

        used_model = model if model else self.client.model
        logger.debug(f"Using model: {used_model}")

        # Initialize cleaned_response as None
        cleaned_response = None

        try:
            # Dedupe dependencies
            if dependencies:
                dependencies_set = set(dependencies)
                dependencies = list(dependencies_set)

            # Build prompt with history
            final_prompt = self._build_prompt(prompt, history, dependencies)
            logger.debug(f"final_prompt built: {final_prompt}")

            # Ensure system_instructions is included in kwargs if provided
            if system_instructions is not None:
                kwargs["system_instructions"] = system_instructions

            # Filter kwargs based on client type
            response = self.client.generate_response(
                prompt=final_prompt, model=used_model, **kwargs
            )

            logger.debug(f"Generated response: {response}")

            # Clean the response
            cleaned_response = self._clean_response(response)
            logger.debug(f"cleaned_response: {cleaned_response}")

            # Add to permanent history
            self.permanent_history.add_turn_user(prompt)
            self.permanent_history.add_turn_assistant(cleaned_response)

            # Record interaction
            logger.debug(f"""Adding interaction:
                            model: {used_model}
                            prompt: {prompt}
                            response: {cleaned_response}
                            prompt_name: {prompt_name}
                            history: {history}
            """)

            # Store interaction in histories
            interaction = {
                "prompt": prompt,
                "response": cleaned_response,
                "prompt_name": prompt_name,
                "timestamp": time.time(),
                "model": used_model,
                "history": history,
            }

            self.history.append(interaction)
            logger.debug(f"Added new interaction to self.history: {interaction}")

            # Store cleaned interaction
            self.clean_history.append(interaction)
            logger.debug(f"Added new interaction to self.clean_history: {interaction}")

            # Store in prompt_attr_history (thread-safe if lock provided)
            if isinstance(cleaned_response, dict):
                logger.debug("Response was JSON.")
                for attr, value in cleaned_response.items():
                    logger.debug(f"Response has attribute(s). attr: {attr} | value: {value}")

                    attr_interaction = {
                        "prompt": attr,
                        "response": value,
                        "prompt_name": attr,
                        "timestamp": time.time(),
                        "model": used_model,
                        "history": history,
                    }

                    if self._history_lock:
                        with self._history_lock:
                            self.prompt_attr_history.append(attr_interaction)
                    else:
                        self.prompt_attr_history.append(attr_interaction)
                    logger.debug(
                        f"Added new attr interaction to self.prompt_attr_history: {attr_interaction}"
                    )
            else:
                if self._history_lock:
                    with self._history_lock:
                        self.prompt_attr_history.append(interaction)
                else:
                    self.prompt_attr_history.append(interaction)
                logger.debug(
                    "Interaction was not JSON, saving original 'prompt' and 'response' to prompt_attr_history."
                )
                logger.debug(f"Added new interaction to self.prompt_attr_history: {interaction}")

            # Store in ordered history
            self.ordered_history.add_interaction(
                model=used_model,
                prompt=prompt,
                response=cleaned_response,
                prompt_name=prompt_name,
                history=history,
            )

            return cleaned_response

        except Exception as e:
            logger.error(f"Problem with response generation: {str(e)}")
            logger.error(f"Prompt: {prompt}")
            logger.error(f"Model: {used_model}")
            logger.error(f"Prompt name: {prompt_name}")
            logger.error(
                f"Response: {cleaned_response if cleaned_response is not None else 'No response generated'}"
            )
            logger.error(f"History: {history}")
            raise

    def clear_conversation(self) -> None:
        """Clear conversation in client but retain history."""
        self.client.clear_conversation()

    def get_interaction_history(self) -> list[dict[str, Any]]:
        """Get complete history."""
        return self.history

    def get_clean_interaction_history(self) -> list[dict[str, Any]]:
        """Get complete clean history."""
        return self.clean_history

    def get_prompt_attr_history(self) -> list[dict[str, Any]]:
        """Get prompt attribute history."""
        return self.prompt_attr_history

    def get_all_interactions(self) -> list[dict[str, Any]]:
        """Get all interactions as dictionaries."""
        return self.ordered_history.get_all_interactions()

    def get_latest_interaction_by_prompt_name(self, prompt_name: str) -> dict[str, Any] | None:
        """Get most recent interaction for a prompt name."""
        matching = [e for e in self.history if e.get("prompt_name") == prompt_name]
        return matching[-1] if matching else None

    # ===========================================================================
    def get_last_n_interactions(self, n: int) -> list[dict[str, Any]]:
        """Get the last n interactions as dictionaries."""
        all_interactions = self.ordered_history.get_all_interactions()
        return [i.to_dict() for i in all_interactions[-n:]]

    def get_interaction(self, sequence_number: int) -> dict[str, Any] | None:
        """Get a specific interaction by sequence number."""
        all_interactions = self.ordered_history.get_all_interactions()
        interaction = next(
            (i for i in all_interactions if i.sequence_number == sequence_number), None
        )
        return interaction.to_dict() if interaction else None

    def get_model_interactions(self, model: str) -> list[dict[str, Any]]:
        """Get all interactions for a specific model."""
        all_interactions = self.ordered_history.get_all_interactions()
        return [i.to_dict() for i in all_interactions if i.model == model]

    def get_interactions_by_prompt_name(self, prompt_name: str) -> list[dict[str, Any]]:
        """Get all interactions for a specific prompt name."""
        return [
            i.to_dict() for i in self.ordered_history.get_interactions_by_prompt_name(prompt_name)
        ]

    def get_latest_interaction(self) -> dict[str, Any] | None:
        """Get the most recent interaction."""
        all_interactions = self.ordered_history.get_all_interactions()
        return all_interactions[-1].to_dict() if all_interactions else None

    def get_prompt_history(self) -> list[str]:
        """Get all prompts in order."""
        return [i.prompt for i in self.ordered_history.get_all_interactions()]

    def get_response_history(self) -> list[str]:
        """Get all responses in order."""
        return [i.response for i in self.ordered_history.get_all_interactions()]

    def get_model_usage_stats(self) -> dict[str, int]:
        """Get statistics on model usage."""
        usage_stats = {}
        for interaction in self.ordered_history.get_all_interactions():
            usage_stats[interaction.model] = usage_stats.get(interaction.model, 0) + 1
        return usage_stats

    def get_prompt_name_usage_stats(self) -> dict[str, int]:
        """Get statistics on prompt name usage."""
        return self.ordered_history.get_prompt_name_usage_stats()

    def get_prompt_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Get the complete history as an ordered dictionary keyed by prompts.

        Returns:
            Dict[str, List[Dict[str, Any]]]: OrderedDict where:
                - keys are prompt names (or prompts if no name was provided)
                - values are lists of interaction dictionaries for that prompt.

        """
        return self.ordered_history.to_dict()

    def get_latest_responses_by_prompt_names(
        self, prompt_names: list[str]
    ) -> dict[str, dict[str, str]]:
        """Get the latest prompt and response for each specified prompt name.

        Args:
            prompt_names: List of prompt names to retrieve

        Returns:
            Dictionary with prompt names as keys and dictionaries containing
            'prompt' and 'response' as values

        """
        return self.ordered_history.get_latest_responses_by_prompt_names(prompt_names)

    def get_formatted_responses(self, prompt_names: list[str]) -> str:
        """Get formatted string output of latest prompts and responses.

        Args:
            prompt_names: List of prompt names to include

        Returns:
            Formatted string in the format:
            <prompt:[prompt text]>[response]</prompt:[prompt text]>

        """
        return self.ordered_history.get_formatted_responses(prompt_names)

    # ===========================================================================
    # RAW CONVERSATION HISTORY ACCESS
    # ===========================================================================

    def get_client_conversation_history(self) -> list[dict[str, str]]:
        """Get the raw conversation history from the underlying client.

        This provides direct access to the format used by the model client.

        Returns:
            The raw conversation history as a list of message dictionaries.
            Format typically includes role (user/assistant/system) and content.

        """
        logger.info("Retrieving raw conversation history from client")
        try:
            if hasattr(self.client, "get_conversation_history"):
                history = self.client.get_conversation_history()
                logger.debug(f"Retrieved conversation history: {history}")
                return history
            else:
                logger.warning("Client does not support retrieving conversation history")
                return []
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            return []

    def set_client_conversation_history(self, history: list[dict[str, str]]) -> bool:
        """Set the raw conversation history in the underlying client.

        This allows direct manipulation of the conversation state.

        Args:
            history: List of message dictionaries in the format expected by the client.
                    Typically includes 'role' and 'content' keys.

        Returns:
            True if successful, False otherwise.

        """
        logger.info(f"Setting raw conversation history in client: {history}")
        try:
            if hasattr(self.client, "set_conversation_history"):
                self.client.set_conversation_history(history)
                logger.debug("Successfully set conversation history")
                return True
            else:
                logger.warning("Client does not support setting conversation history")
                return False
        except Exception as e:
            logger.error(f"Error setting conversation history: {str(e)}")
            return False

    def add_client_message(self, role: str, content: str, **kwargs: Any) -> bool:  # noqa: ANN401
        """Add a single message to the client's conversation history.

        Args:
            role: The role of the message sender (e.g., 'user', 'assistant', 'system')
            content: The message content
            **kwargs: Additional message attributes (e.g., tool_call_id for tool messages)

        Returns:
            True if successful, False otherwise

        """
        logger.info(
            f"Adding message to client conversation history: role={role}, content={content}"
        )
        try:
            # Get current history
            history = self.get_client_conversation_history()

            # Create new message
            message = {"role": role, "content": content, **kwargs}

            # Add message to history
            history.append(message)

            # Set updated history
            return self.set_client_conversation_history(history)
        except Exception as e:
            logger.error(f"Error adding message to conversation history: {str(e)}")
            return False

    def _convert_unix_seconds_to_datetime(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert Unix timestamps in seconds to datetime.

        Works with older versions of polars.

        Args:
            df: Polars DataFrame with a 'timestamp' column.

        Returns:
            DataFrame with added 'datetime' column.

        """
        if "timestamp" not in df.columns:
            return df

        try:
            # For older polars versions, we need to convert manually
            # Multiply seconds by 1,000,000 to get microseconds
            df = df.with_columns(
                (pl.col("timestamp") * 1_000_000).cast(pl.Int64).alias("timestamp_us")
            )

            # Now convert microseconds to datetime
            df = df.with_columns(pl.col("timestamp_us").cast(pl.Datetime).alias("datetime"))

            # Drop the temporary column
            df = df.drop("timestamp_us")

            return df
        except Exception as e:
            logger.error(f"Error converting timestamp to datetime: {str(e)}")
            return df

    @auto_persist
    def history_to_dataframe(self) -> pl.DataFrame:
        """Convert the full interaction history to a polars DataFrame.

        Returns:
            pl.DataFrame: A dataframe with all interaction data

        """
        logger.info("Converting history to polars DataFrame")

        if not self.history:
            logger.warning("History is empty, returning empty DataFrame")
            return pl.DataFrame()

        try:
            # Handle the case where responses might be JSON objects
            cleaned_history = []
            for item in self.history:
                entry = item.copy()
                if isinstance(entry["response"], dict):
                    entry["response"] = str(entry["response"])
                cleaned_history.append(entry)

            # Convert to DataFrame
            df = pl.from_dicts(cleaned_history)

            # Convert timestamp to datetime using compatible method
            df = self._convert_unix_seconds_to_datetime(df)

            logger.info(f"Successfully created DataFrame with {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Error converting history to DataFrame: {str(e)}")
            return pl.DataFrame()

    @auto_persist
    def clean_history_to_dataframe(self) -> pl.DataFrame:
        """Convert the clean interaction history to a polars DataFrame.

        Returns:
            pl.DataFrame: A dataframe with clean interaction data

        """
        logger.info("Converting clean history to polars DataFrame")

        if not self.clean_history:
            logger.warning("Clean history is empty, returning empty DataFrame")
            return pl.DataFrame()

        try:
            # Handle the case where responses might be JSON objects
            cleaned_history = []
            for item in self.clean_history:
                entry = item.copy()
                if isinstance(entry["response"], dict):
                    entry["response"] = str(entry["response"])
                cleaned_history.append(entry)

            # Convert to DataFrame
            df = pl.from_dicts(cleaned_history)

            # Convert timestamp to datetime
            df = self._convert_unix_seconds_to_datetime(df)

            logger.info(f"Successfully created DataFrame with {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Error converting clean history to DataFrame: {str(e)}")
            return pl.DataFrame()

    @auto_persist
    def prompt_attr_history_to_dataframe(self) -> pl.DataFrame:
        """Convert the prompt attribute history to a polars DataFrame.

        Returns:
            pl.DataFrame: A dataframe with prompt attribute history data

        """
        logger.info("Converting prompt attribute history to polars DataFrame")

        if not self.prompt_attr_history:
            logger.warning("Prompt attribute history is empty, returning empty DataFrame")
            return pl.DataFrame()

        try:
            # Handle the case where responses might be JSON objects
            cleaned_history = []
            for item in self.prompt_attr_history:
                entry = item.copy()
                if isinstance(entry["response"], dict):
                    entry["response"] = str(entry["response"])
                cleaned_history.append(entry)

            # Convert to DataFrame
            df = pl.from_dicts(cleaned_history)

            # Convert timestamp to datetime
            df = self._convert_unix_seconds_to_datetime(df)

            logger.info(f"Successfully created DataFrame with {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Error converting prompt attribute history to DataFrame: {str(e)}")
            return pl.DataFrame()

    @auto_persist
    def ordered_history_to_dataframe(self) -> pl.DataFrame:
        """Convert the ordered interaction history to a polars DataFrame.

        Returns:
            pl.DataFrame: A dataframe with ordered interaction data

        """
        logger.info("Converting ordered history to polars DataFrame")

        all_interactions = self.ordered_history.get_all_interactions()

        if not all_interactions:
            logger.warning("Ordered history is empty, returning empty DataFrame")
            return pl.DataFrame()

        try:
            # Convert Interaction objects to dictionaries
            interactions_dicts = [interaction.to_dict() for interaction in all_interactions]

            # Handle the case where responses might be JSON objects
            cleaned_interactions = []
            for item in interactions_dicts:
                entry = item.copy()
                if isinstance(entry["response"], dict):
                    entry["response"] = str(entry["response"])
                cleaned_interactions.append(entry)

            # Convert to DataFrame
            df = pl.from_dicts(cleaned_interactions)

            # Convert to DataFrame
            # df = pl.from_dicts(cleaned_history)

            # Convert timestamp to datetime
            df = self._convert_unix_seconds_to_datetime(df)

            logger.info(f"Successfully created DataFrame with {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"Error converting ordered history to DataFrame: {str(e)}")
            return pl.DataFrame()

    def search_history(
        self,
        text: str | None = None,
        prompt_name: str | None = None,
        model: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> pl.DataFrame:
        """Search interaction history with flexible filtering options.

        Args:
            text: Text to search for in prompts and responses
            prompt_name: Filter by prompt name
            model: Filter by model name
            start_time: Filter by timestamp (start time in epoch seconds)
            end_time: Filter by timestamp (end time in epoch seconds)

        Returns:
            pl.DataFrame: Filtered dataframe of interactions

        """
        logger.info(
            f"Searching history with filters: text={text}, prompt_name={prompt_name}, model={model}"
        )

        # Get the complete dataframe
        df = self.history_to_dataframe()

        if df.is_empty():
            return df

        # Apply filters
        if text is not None:
            text_lower = text.lower()
            df = df.filter(
                pl.col("prompt").str.contains(text_lower, literal=True)
                | pl.col("response").str.contains(text_lower, literal=True)
            )

        if prompt_name is not None:
            df = df.filter(pl.col("prompt_name") == prompt_name)

        if model is not None:
            df = df.filter(pl.col("model") == model)

        if start_time is not None:
            df = df.filter(pl.col("timestamp") >= start_time)

        if end_time is not None:
            df = df.filter(pl.col("timestamp") <= end_time)

        logger.info(f"Search returned {len(df)} results")
        return df

    def get_model_stats_df(self) -> pl.DataFrame:
        """Get statistics on model usage as a DataFrame.

        Returns:
            pl.DataFrame: DataFrame with model usage statistics

        """
        stats = self.get_model_usage_stats()
        return pl.DataFrame({"model": list(stats.keys()), "count": list(stats.values())})

    def get_prompt_name_stats_df(self) -> pl.DataFrame:
        """Get statistics on prompt name usage as a DataFrame.

        Returns:
            pl.DataFrame: DataFrame with prompt name usage statistics

        """
        stats = self.get_prompt_name_usage_stats()
        return pl.DataFrame({"prompt_name": list(stats.keys()), "count": list(stats.values())})

    def get_response_length_stats(self) -> pl.DataFrame:
        """Get statistics on response lengths by prompt name.

        Returns:
            pl.DataFrame: DataFrame with response length statistics by prompt name

        """
        df = self.history_to_dataframe()

        if df.is_empty():
            return pl.DataFrame()

        try:
            pd_df = df.to_pandas()
            pd_df["response_length"] = pd_df["response"].str.len()

            grouped = (
                pd_df.groupby("prompt_name")
                .agg({"response_length": ["mean", "min", "max", "count"]})
                .reset_index()
            )

            grouped.columns = [
                "prompt_name",
                "mean_length",
                "min_length",
                "max_length",
                "count",
            ]

            grouped = grouped.sort_values("mean_length", ascending=False)
            result_df = pl.from_pandas(grouped)

            return result_df

        except Exception as e:
            logger.error(f"Error calculating response length statistics: {str(e)}")
            return pl.DataFrame()

    def interaction_counts_by_date(self) -> pl.DataFrame:
        """Get counts of interactions grouped by date.

        Returns:
            pl.DataFrame: DataFrame with interaction counts by date

        """
        df = self.history_to_dataframe()

        if df.is_empty() or "timestamp" not in df.columns:
            return pl.DataFrame({"date": [], "count": []})

        return (
            df.with_columns(
                pl.col("timestamp").cast(pl.Float64).cast(pl.Datetime).dt.date().alias("date")
            )
            .group_by("date")
            .count()
            .sort("date")
        )

    # =============================
    # Batch Persistence Method
    # =============================
    def persist_all_histories(self) -> bool:
        """Persist all histories to Parquet files in the configured directory."""
        if not self.persist_name:
            logger.warning("Persistence name not set. Skipping persistence.")
            return False
        try:
            file_map = {
                "history": self.history_to_dataframe(),
                "clean_history": self.clean_history_to_dataframe(),
                "prompt_attr": self.prompt_attr_history_to_dataframe(),
                "ordered": self.ordered_history_to_dataframe(),
            }
            for key, df in file_map.items():
                if not df.is_empty():
                    file_path = os.path.join(self.persist_dir, f"{self.persist_name}_{key}.parquet")
                    df.write_parquet(file_path)
                    logger.info(f"Persisted {key} to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error persisting histories: {str(e)}")
            return False
