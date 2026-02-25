# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
#
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
#
# Contact: antquinonez@farfiner.com
# filename: src/lib/AI/FFOpenAIAssistant.py

import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class FFOpenAIAssistant:
    """
    A class to interact with OpenAI's API, specifically designed for chat-based models.

    This class provides methods to initialize an OpenAI client, manage assistants,
    and generate responses using the OpenAI API.

    Attributes:
        api_key (str)
        model (str): The name of the OpenAI model to use.
        temperature (float)
        max_tokens (int): The maximum number of tokens to generate in the response.
        system_instructions (str)
        assistant_name (str): The name of the assistant to use or create.
        assistant_id (str): The ID of the assistant being used.
        thread_id (str): The ID of the current conversation thread.
        client (OpenAI): The OpenAI client instance.
        response_format (str): The format of the response. Defaults to "auto". Options:
            {"type": "json_object"}
            {"type": "text"}
            'auto'

            or something like this:
                {
                "type": "json_schema",
                "json_schema": {
                    "name": "test_schema",
                    "schema": Messages.model_json_schema()
                }
            }

            where Messages is a Pydantic model, as in:
            class Message(BaseModel):
                user_question: str
                ai_response: str
                confidence: float

            class Messages(BaseModel):
                messages: list[Message]

    """

    def __init__(self, config: dict | None = None, **kwargs):
        """
        Initialize the FFOpenAI instance.

        Args:
            config (Optional[dict]): A dictionary of configuration parameters.
            **kwargs: Additional keyword arguments to override config and defaults.

        The initialization process prioritizes values in the following order:
        1. Keyword arguments
        2. Configuration dictionary
        3. Environment variables
        4. Default values
        """
        logger.info("Initializing FFOpenAI")

        # DEFAULT VALUES
        defaults = {
            "model": "gpt-4o-mini",
            "max_tokens": 1000,
            "temperature": 0.5,
            "assistant_name": "default",
            "response_format": "auto",
            "system_instructions": "Respond accurately to user queries. Be thorough but not repetitive. Be helpful and obliging.",
        }

        # Combine config and kwargs, with kwargs taking precedence
        all_config = {**(config or {}), **kwargs}

        # Set attributes based on the combined configuration
        for key, value in all_config.items():
            match key:
                case "api_key":
                    self.api_key = value or os.getenv("OPENAI_TOKEN")
                case "model":
                    self.model = value
                case "temperature":
                    self.temperature = float(value)
                case "max_tokens":
                    self.max_tokens = int(value)
                case "system_instructions":
                    self.system_instructions = value
                case "assistant_name":
                    self.assistant_name = value
                case "assistant_id":
                    self.assistant_id = value
                case "thread_id":
                    self.thread_id = value
                case "response_format":
                    self.response_format = value

        # Set default values if not set
        self.api_key = getattr(self, "api_key", os.getenv("OPENAI_TOKEN"))
        self.model = getattr(self, "model", os.getenv("OPENAI_MODEL", defaults["model"]))
        self.temperature = getattr(
            self, "temperature", float(os.getenv("OPENAI_TEMPERATURE", defaults["temperature"]))
        )
        self.max_tokens = getattr(
            self, "max_tokens", int(os.getenv("OPENAI_MAX_TOKENS", defaults["max_tokens"]))
        )
        self.system_instructions = getattr(
            self,
            "system_instructions",
            os.getenv("OPENAI_ASSISTANT_INSTRUCTIONS", defaults["system_instructions"]),
        )
        self.assistant_name = getattr(
            self, "assistant_name", os.getenv("OPENAI_ASSISTANT_NAME", defaults["assistant_name"])
        )
        self.assistant_id = getattr(self, "assistant_id", None)
        self.thread_id = getattr(self, "thread_id", None)
        self.response_format = getattr(
            self,
            "response_format",
            os.getenv("OPENAI_RESPONSE_FORMAT", defaults["response_format"]),
        )

        logger.debug(
            f"Model: {self.model}, Temperature: {self.temperature}, Max Tokens: {self.max_tokens}"
        )
        logger.debug(f"System instructions: {self.system_instructions}")
        logger.debug(f"Assistant name: {self.assistant_name}")

        # Initialize the OpenAI client and get the assistant
        self.client: OpenAI = self._initialize_client()
        self.assistant_id = self._get_assistant(self.assistant_id)

    def _initialize_client(self) -> OpenAI:
        """
        Initialize and return the OpenAI client.

        Returns:
            OpenAI: An instance of the OpenAI client.
        """
        logger.info("Initializing OpenAI client")
        if not self.api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")

        return OpenAI(api_key=self.api_key)

    def _get_assistant(self, assistant_id: str | None) -> str:
        """
        Retrieve an existing assistant or create a new one if it doesn't exist.

        Args:
            assistant_id (Optional[str]): The ID of the assistant to retrieve.

        Returns:
            str: The ID of the retrieved or created assistant.
        """
        logger.info("Getting or creating assistant")
        if assistant_id:
            try:
                assistant = self.client.beta.assistants.retrieve(assistant_id)
                logger.info(f"Retrieved existing assistant with ID: {assistant_id}")
                return assistant.id
            except Exception as e:
                logger.error(f"Error retrieving assistant with ID {assistant_id}: {str(e)}")

        try:
            assistants = self.client.beta.assistants.list(order="desc")
            for assistant in assistants.data:
                if assistant.name == self.assistant_name:
                    logger.info(f"Found existing assistant with name: {self.assistant_name}")
                    return assistant.id
        except Exception as e:
            logger.error(f"Error listing assistants: {str(e)}")

        logger.info("Creating new assistant")
        return self._create_assistant(self.assistant_name)

    def _create_assistant(self, name: str) -> str:
        """
        Create a new OpenAI assistant.

        Args:
            name (str): The name of the assistant to create.

        Returns:
            str: The ID of the created assistant.
        """
        try:
            assistant = self.client.beta.assistants.create(
                name=name,
                instructions=self.system_instructions,
                model=self.model,
                response_format=self.response_format,
            )
            logger.info(f"Created new assistant with ID: {assistant.id}")
            return assistant.id
        except Exception as e:
            logger.error(f"Error creating OpenAI assistant: {str(e)}")
            raise RuntimeError(f"Error creating OpenAI assistant: {str(e)}")

    def _ensure_thread(self) -> None:
        """
        Ensure a valid thread exists, creating a new one if necessary.
        """
        if self.thread_id is None:
            thread = self.client.beta.threads.create()
            self.thread_id = thread.id
            logger.info(f"Created new thread with ID: {self.thread_id}")
        else:
            logger.debug(f"Using existing thread with ID: {self.thread_id}")

    def _run_conversation(self, prompt: str) -> str:
        """
        Run a conversation in the current thread and return the response.

        Args:
            prompt (str): The user's input prompt.

        Returns:
            str: The assistant's response.
        """
        logger.debug(f"Running conversation with prompt: {prompt}")
        self._ensure_thread()

        try:
            # Add the user's message to the thread
            self.client.beta.threads.messages.create(
                thread_id=self.thread_id, role="user", content=prompt
            )
            logger.debug("Added user message to thread")

            # Create and monitor the run
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread_id, assistant_id=self.assistant_id
            )
            logger.debug(f"Created run with ID: {run.id}")

            # Wait for the run to complete
            while run.status in ["queued", "in_progress"]:
                time.sleep(1)
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread_id, run_id=run.id
                )
                logger.debug(f"Run status: {run.status}")

            if run.status != "completed":
                logger.error(f"Run failed with status: {run.status}")
                raise RuntimeError(f"Run failed with status: {run.status}")

            # Retrieve the assistant's response
            messages = self.client.beta.threads.messages.list(thread_id=self.thread_id)
            response = messages.data[0].content[0].text.value
            logger.info("Retrieved assistant's response")
            return response

        except Exception as e:
            logger.error(f"Error in OpenAI conversation: {str(e)}")
            raise RuntimeError(f"Error in OpenAI conversation: {str(e)}")

    def generate_response(self, prompt: str) -> str:
        """
        Generate a response to the given prompt.

        Args:
            prompt (str): The user's input prompt.

        Returns:
            str: The generated response from the OpenAI model.
        """
        logger.info("Generating response")
        return self._run_conversation(prompt)
