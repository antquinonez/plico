# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
#
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
#
# Contact: antquinonez@farfiner.com

import logging
from collections.abc import Callable, Iterator

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

from .FFAzureClientBase import FFAzureClientBase

logger = logging.getLogger(__name__)


class FFAzureCodestral(FFAzureClientBase):
    """Azure AI Inference client for Codestral code generation models."""

    @property
    def _default_model(self) -> str:
        return "codestral-2501"

    @property
    def _default_max_tokens(self) -> int:
        return 2048

    @property
    def _default_temperature(self) -> float:
        return 0.7

    @property
    def _default_instructions(self) -> str:
        return "You are a helpful assistant specialized in code generation. Respond accurately to user queries with well-structured code examples. Provide explanations when helpful."

    @property
    def _env_key_prefix(self) -> str:
        return "AZURE_CODESTRAL"

    @property
    def _provider_name(self) -> str:
        return "MistralAI"

    def _initialize_client(self):
        """Override to handle Codestral-specific endpoint format."""
        if not self.api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")

        if not self.endpoint:
            logger.error("Endpoint URL not found")
            raise ValueError("Endpoint URL not found")

        endpoint = self.endpoint
        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]

        if "/chat/completions" in endpoint:
            endpoint = endpoint.split("/chat/completions")[0]

        if self.use_deployment_endpoint:
            deployment_name = self.model.lower().replace("-", "").replace(".", "")
            full_endpoint = f"{endpoint}/openai/deployments/{deployment_name}"
        else:
            full_endpoint = endpoint

        logger.debug(f"Using endpoint: {full_endpoint}")

        return ChatCompletionsClient(
            endpoint=full_endpoint, credential=AzureKeyCredential(self.api_key)
        )

    def stream_response(
        self,
        prompt: str,
        callback: Callable[[str], None] | None = None,
        model: str | None = None,
        system_instructions: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        stop: list[str] | None = None,
        response_format: dict[str, str] | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
        **kwargs,
    ) -> Iterator[str]:
        """
        Stream the response from the model.

        Args:
            prompt: User's input text
            callback: Optional callback function to call for each chunk
            model: Model to use (overrides default)
            system_instructions: System instructions (overrides default)
            temperature: Controls randomness (0-1)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            presence_penalty: Penalizes repeated tokens
            frequency_penalty: Penalizes frequent tokens
            stop: List of strings that stop generation
            response_format: Format of the response
            tools: List of tools to make available
            tool_choice: Tool choice strategy

        Yields:
            Chunks of the model's response as they are generated
        """
        if not prompt.strip():
            raise ValueError("Empty prompt provided")

        logger.debug(f"Streaming response for prompt: {prompt[:50]}...")

        used_model = (model or self.model).lower()
        used_temperature = temperature if temperature is not None else self.temperature
        used_max_tokens = max_tokens if max_tokens is not None else self.max_tokens

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

            params = {
                "messages": messages,
                "max_tokens": used_max_tokens,
                "temperature": used_temperature,
                "stream": True,
            }

            if not self.use_deployment_endpoint:
                params["model"] = used_model

            if top_p is not None:
                params["top_p"] = top_p
            if presence_penalty is not None:
                params["presence_penalty"] = presence_penalty
            if frequency_penalty is not None:
                params["frequency_penalty"] = frequency_penalty
            if stop:
                params["stop"] = stop

            if response_format:
                if isinstance(response_format, str):
                    params["response_format"] = {"type": response_format.lower()}
                else:
                    params["response_format"] = response_format

            if tools:
                params["tools"] = tools
                if tool_choice:
                    params["tool_choice"] = tool_choice

            logger.debug(f"Stream request parameters: {list(params.keys())}")
            stream_response = self.client.complete(**params)

            full_response = ""

            for update in stream_response:
                if update.choices:
                    content = update.choices[0].delta.content or ""
                    if content:
                        full_response += content
                        if callback:
                            callback(content)
                        yield content

            self.conversation_history.append({"role": "assistant", "content": full_response})

            logger.info("Stream response completed successfully")

        except HttpResponseError as e:
            if e.status_code == 400:
                response_data = e.response.json() if hasattr(e, "response") else {}
                if isinstance(response_data, dict) and "error" in response_data:
                    error_msg = f"Request triggered an {response_data['error']['code']} error: {response_data['error']['message']}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            elif e.status_code == 404:
                logger.error(f"404 Not Found error: {str(e)}")
                raise RuntimeError(
                    f"Model not found: {used_model}. Please verify the model name and endpoint configuration."
                )

            logger.error(f"HTTP error: {str(e)}")
            raise RuntimeError(f"Error streaming response: {str(e)}")

        except Exception as e:
            logger.error("Problem with stream response generation")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- model: {used_model}")
            logger.error(f"  -- endpoint: {self.endpoint}")

            raise RuntimeError(f"Error streaming response: {str(e)}")

    def generate_code(self, prompt: str, language: str | None = None, **kwargs) -> str:
        """
        Generate code based on the prompt, optimized for Codestral's capabilities.

        Args:
            prompt: User's code generation request
            language: Programming language to generate code in
            **kwargs: Additional parameters to pass to generate_response

        Returns:
            The generated code as a string
        """
        code_system_instructions = (
            "You are an expert programmer. Generate clean, efficient, and well-commented "
            "code in response to the following request. "
        )

        if language:
            code_system_instructions += f"Use {language} programming language. "

        code_system_instructions += (
            "Focus on producing working, production-ready code with appropriate error handling. "
            "Include helpful comments to explain complex sections."
        )

        if "fill in" in prompt.lower() or "complete this code" in prompt.lower():
            code_system_instructions += (
                " The user is asking you to complete or fill in code. Pay close attention to "
                "the surrounding code context and maintain consistent style, variable naming, "
                "and functionality."
            )

        return self.generate_response(
            prompt=prompt, system_instructions=code_system_instructions, **kwargs
        )

    def explain_code(self, code: str, **kwargs) -> str:
        """
        Explain the provided code in detail.

        Args:
            code: The code to explain
            **kwargs: Additional parameters to pass to generate_response

        Returns:
            The explanation as a string
        """
        explain_system_instructions = (
            "You are an expert programming teacher. Provide a clear, thorough explanation "
            "of the provided code. Break down complex concepts, explain the purpose of key "
            "functions and variables, and highlight any notable patterns or techniques used. "
            "Your explanation should be educational and help the user understand how the code works."
        )

        prompt = f"Please explain this code in detail:\n\n```\n{code}\n```"

        return self.generate_response(
            prompt=prompt, system_instructions=explain_system_instructions, **kwargs
        )

    def review_code(self, code: str, **kwargs) -> str:
        """
        Review the provided code and suggest improvements.

        Args:
            code: The code to review
            **kwargs: Additional parameters to pass to generate_response

        Returns:
            The code review as a string
        """
        review_system_instructions = (
            "You are an expert code reviewer. Analyze the provided code for potential issues "
            "including bugs, security vulnerabilities, performance problems, and style inconsistencies. "
            "Provide constructive feedback and suggest specific improvements. Focus on making the "
            "code more robust, efficient, and maintainable. Include code snippets showing improved versions "
            "where appropriate."
        )

        prompt = f"Please review this code and suggest improvements:\n\n```\n{code}\n```"

        return self.generate_response(
            prompt=prompt, system_instructions=review_system_instructions, **kwargs
        )

    def fix_code(self, code: str, error_message: str | None = None, **kwargs) -> str:
        """
        Fix issues in the provided code.

        Args:
            code: The code to fix
            error_message: Optional error message to help with debugging
            **kwargs: Additional parameters to pass to generate_response

        Returns:
            The fixed code as a string
        """
        fix_system_instructions = (
            "You are an expert debugging assistant. Fix the issues in the provided code "
            "and return a corrected version. Identify the root causes of problems and "
            "implement proper solutions. Explain the changes you've made and why they fix the issues."
        )

        prompt = f"Please fix the issues in this code:\n\n```\n{code}\n```"

        if error_message:
            prompt += f"\n\nError message:\n```\n{error_message}\n```"

        return self.generate_response(
            prompt=prompt, system_instructions=fix_system_instructions, **kwargs
        )

    def translate_code(
        self, code: str, source_language: str, target_language: str, **kwargs
    ) -> str:
        """
        Translate code from one programming language to another.

        Args:
            code: The code to translate
            source_language: The current programming language of the code
            target_language: The target programming language
            **kwargs: Additional parameters to pass to generate_response

        Returns:
            The translated code as a string
        """
        translate_system_instructions = (
            f"You are an expert in multiple programming languages. Translate the provided code "
            f"from {source_language} to {target_language}, maintaining the same functionality and logic. "
            f"Use idiomatic patterns and best practices in the target language. "
            f"Include comments explaining any significant changes needed for the translation."
        )

        prompt = f"Please translate this {source_language} code to {target_language}:\n\n```\n{code}\n```"

        return self.generate_response(
            prompt=prompt, system_instructions=translate_system_instructions, **kwargs
        )
