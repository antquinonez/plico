import os
import time
import logging
import json
from typing import Optional, List, Dict, Any, Union, Iterator, Callable
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import (
    SystemMessage, UserMessage, AssistantMessage, ToolMessage
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class FFAzureCodestral:
    def __init__(self, config: Optional[dict] = None, **kwargs):
        logger.info("Initializing FFCodestral")

        # DEFAULT VALUES
        defaults = {
            'model': "codestral-2501",
            'max_tokens': 2048,
            'temperature': 0.7,
            'instructions': "You are a helpful assistant specialized in code generation. Respond accurately to user queries with well-structured code examples. Provide explanations when helpful."
        }

        # Combine config and kwargs, with kwargs taking precedence
        all_config = {**(config or {}), **kwargs}
        
        # Changed default to False to use the newer models endpoint format. False uses the new models endpoint format.
        self.use_deployment_endpoint = all_config.get('use_deployment_endpoint', False)

        for key, value in all_config.items():
            match key:
                case 'api_key':
                    self.api_key = value or os.getenv('AZURE_CODESTRAL_KEY')
                case 'endpoint':
                    self.endpoint = value or os.getenv('AZURE_CODESTRAL_ENDPOINT')
                case 'model':
                    self.model = value
                case 'temperature':
                    self.temperature = float(value)
                case 'max_tokens':
                    self.max_tokens = int(value)
                case 'system_instructions':
                    self.system_instructions = value
                case 'use_deployment_endpoint':
                    self.use_deployment_endpoint = bool(value)

        # Set default values if not set
        self.api_key = getattr(self, 'api_key', os.getenv('AZURE_CODESTRAL_KEY'))
        self.endpoint = getattr(self, 'endpoint', os.getenv('AZURE_CODESTRAL_ENDPOINT'))
        self.model = getattr(self, 'model', os.getenv('AZURE_CODESTRAL_MODEL', defaults['model']))
        self.temperature = getattr(self, 'temperature', float(os.getenv('AZURE_CODESTRAL_TEMPERATURE', defaults['temperature'])))
        self.max_tokens = getattr(self, 'max_tokens', int(os.getenv('AZURE_CODESTRAL_MAX_TOKENS', defaults['max_tokens'])))
        self.system_instructions = getattr(self, 'system_instructions', os.getenv('AZURE_CODESTRAL_ASSISTANT_INSTRUCTIONS', defaults['instructions']))

        # Validate endpoint
        if self.endpoint and not self.endpoint.startswith(('http://', 'https://')):
            self.endpoint = f"https://{self.endpoint}"
            
        # Normalize model name (Azure often requires lowercase model names)
        self.model = self.model.lower()

        logger.debug(f"Model: {self.model}, Temperature: {self.temperature}, Max Tokens: {self.max_tokens}")
        logger.debug(f"System instructions: {self.system_instructions}")
        logger.debug(f"Using endpoint: {self.endpoint}")
        logger.debug(f"Using deployment endpoint: {self.use_deployment_endpoint}")

        self.conversation_history = []
        self.client = self._initialize_client()

    def _initialize_client(self) -> ChatCompletionsClient:
        """Initialize and return the Azure AI Inference ChatCompletionsClient."""
        logger.info("Initializing Azure Codestral client")
        
        api_key = self.api_key
        endpoint = self.endpoint
        
        if not api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")
            
        if not endpoint:
            logger.error("Endpoint URL not found")
            raise ValueError("Endpoint URL not found")
        
        # Make sure endpoint doesn't end with a slash
        if endpoint.endswith('/'):
            endpoint = endpoint[:-1]
            
        # Check if the endpoint already contains the path we need
        if "/chat/completions" in endpoint:
            endpoint = endpoint.split("/chat/completions")[0]
            
        if self.use_deployment_endpoint:
            # For the old deployments endpoint format
            deployment_name = self.model.lower().replace("-", "").replace(".", "")
            full_endpoint = f"{endpoint}/openai/deployments/{deployment_name}"
        else:
            # For the models endpoint format
            # The endpoint appears to already include the base path needed, so we don't append "/models"
            full_endpoint = endpoint
        
        logger.debug(f"Using endpoint: {full_endpoint}")
        
        return ChatCompletionsClient(
            endpoint=full_endpoint,
            credential=AzureKeyCredential(api_key)
        )

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get the conversation history."""
        return self.conversation_history
    
    def set_conversation_history(self, history: List[Dict[str, str]]) -> None:
        """Set the conversation history."""
        self.conversation_history = history
        
    def _convert_history_to_messages(self) -> List[Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage]]:
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
            elif message["role"] == "tool":
                messages.append(ToolMessage(tool_call_id=message.get("tool_call_id", ""), content=message["content"]))
        
        return messages

    def generate_response(self, 
                            prompt: str, 
                            model: Optional[str] = None, 
                            system_instructions: Optional[str] = None,
                            temperature: Optional[float] = None,
                            max_tokens: Optional[int] = None,
                            top_p: Optional[float] = None,
                            presence_penalty: Optional[float] = None,
                            frequency_penalty: Optional[float] = None,
                            stop: Optional[List[str]] = None,
                            response_format: Optional[Union[str, Dict]] = None,
                            tools: Optional[List[Dict]] = None,
                            tool_choice: Optional[str] = None,
                            safe_mode: Optional[bool] = None) -> str:
        """
        Generate a response from the model.
        
        Args:
            prompt: User's input text
            model: Model to use (overrides default)
            system_instructions: System instructions (overrides default)
            temperature: Controls randomness (0-1)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            presence_penalty: Penalizes repeated tokens
            frequency_penalty: Penalizes frequent tokens
            stop: List of strings that stop generation when encountered
            response_format: Format of the response ("text" or "json")
            tools: List of tools to make available to the model
            tool_choice: Tool choice strategy ("auto", "none", or specific tool)
            safe_mode: Whether to enable Codestral's safe mode
            
        Returns:
            The model's response as a string
        """
        if not prompt.strip():
            raise ValueError("Empty prompt provided")
        
        logger.debug(f"Generating response for prompt: {prompt}")

        # Determine parameters to use
        used_model = model if model else self.model
        used_temperature = temperature if temperature is not None else self.temperature
        used_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"Using model: {used_model}, Temperature: {used_temperature}, Max Tokens: {used_max_tokens}")

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
            
            # Set up parameters for the API call
            params = {
                "messages": messages,
                "max_tokens": used_max_tokens,
                "temperature": used_temperature,
            }
            
            # For models endpoint format, include the model name in the request
            if not self.use_deployment_endpoint:
                # For Azure AI models in the newer format, we need to ensure the model param is set
                params["model"] = used_model
                
                # Don't modify the client's base URL here - we'll handle it in the initialization
            
            # Add optional parameters if provided
            if top_p is not None:
                params["top_p"] = top_p
            if presence_penalty is not None:
                params["presence_penalty"] = presence_penalty
            if frequency_penalty is not None:
                params["frequency_penalty"] = frequency_penalty
            if stop:
                params["stop"] = stop
            
            # Handle response format
            if response_format:
                # Check if response_format is already a dict
                if isinstance(response_format, dict):
                    params["response_format"] = response_format
                # Check if it's a string that contains "json"
                elif isinstance(response_format, str) and "json" in response_format.lower():
                    params["response_format"] = {"type": "json_object"}
                # Default to text format
                else:
                    params["response_format"] = {"type": "text"}
            
            # Handle tools
            if tools:
                params["tools"] = tools
                
                if tool_choice:
                    params["tool_choice"] = tool_choice
            
            # Handle Codestral-specific parameters (like safe_mode)
            model_extras = {}
            if safe_mode is not None:
                model_extras["safe_mode"] = safe_mode
                
            if model_extras:
                params["model_extras"] = model_extras
            
            logger.debug(f"Calling Azure API with params: {params}")
            
            # Call Azure API
            response = self.client.complete(**params)
            
            # Handle tool calls if present
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                # Return tool calls to be handled by the caller
                assistant_response = response.choices[0].message.content or ""
                tool_calls = response.choices[0].message.tool_calls
                
                # Add assistant's response to history
                self.conversation_history.append({
                    "role": "assistant", 
                    "content": assistant_response,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in tool_calls
                    ]
                })
                
                # For compatibility with the simple interface, we'll return a string with tool call info
                return f"{assistant_response}\n[Tool calls detected: {len(tool_calls)}]"
            else:
                # Extract standard response
                assistant_response = response.choices[0].message.content
                
                # Add assistant's response to history
                self.conversation_history.append({"role": "assistant", "content": assistant_response})
                
                logger.info("Response generated successfully")
                return assistant_response
            
        except HttpResponseError as e:
            # Handle content filtering errors
            if e.status_code == 400:
                response = e.response.json() if hasattr(e, 'response') else {}
                if isinstance(response, dict) and "error" in response:
                    error_msg = f"Request triggered an {response['error']['code']} error: {response['error']['message']}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            
            logger.error(f"HTTP error: {str(e)}")
            raise RuntimeError(f"Error generating response from Azure Codestral: {str(e)}")
            
        except Exception as e:
            logger.error("Problem with response generation")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- model: {self.model}")
            logger.error(f"  -- system: {self.system_instructions}")
            logger.error(f"  -- conversation history: {self.conversation_history}")
            logger.error(f"  -- max_tokens: {self.max_tokens}")
            logger.error(f"  -- temperature: {self.temperature}")
            
            raise RuntimeError(f"Error generating response from Azure Codestral: {str(e)}")

    def get_model_info(self):
        """Get information about the model."""
        try:
            logger.debug(f"Getting model info for: {self.model}")
            # For models endpoint, just return basic info since /info might not be available
            if not self.use_deployment_endpoint:
                # Create a simple model info object with the data we know
                from collections import namedtuple
                ModelInfo = namedtuple('ModelInfo', ['model_name', 'model_type', 'model_provider_name'])
                return ModelInfo(
                    model_name=self.model,
                    model_type="chat-completions",
                    model_provider_name="MistralAI"
                )
            else:
                # For deployment endpoint, try to get the model info
                return self.client.get_model_info(model=self.model)
        except Exception as e:
            logger.error(f"Failed to get model info: {str(e)}")
            raise RuntimeError(f"Error getting model info: {str(e)}")

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
            
        self.conversation_history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        })

    def stream_response(self, 
                         prompt: str, 
                         callback: Optional[Callable[[str], None]] = None,
                         model: Optional[str] = None, 
                         system_instructions: Optional[str] = None,
                         temperature: Optional[float] = None,
                         max_tokens: Optional[int] = None,
                         top_p: Optional[float] = None,
                         presence_penalty: Optional[float] = None,
                         frequency_penalty: Optional[float] = None,
                         stop: Optional[List[str]] = None,
                         response_format: Optional[Dict[str, str]] = None,
                         tools: Optional[List[Dict]] = None,
                         tool_choice: Optional[Union[str, Dict]] = None,
                         safe_mode: Optional[bool] = None) -> Iterator[str]:
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
            stop: List of strings that stop generation when encountered
            response_format: Format of the response (dict with "type": "text" or "json")
            tools: List of tools to make available to the model
            tool_choice: Tool choice strategy ("auto", "none", or specific tool)
            safe_mode: Whether to enable Codestral's safe mode
            
        Yields:
            Chunks of the model's response as they are generated
        """
        if not prompt.strip():
            raise ValueError("Empty prompt provided")
        
        logger.debug(f"Streaming response for prompt: {prompt}")
        
        # Determine parameters to use
        used_model = model.lower() if model else self.model
        used_temperature = temperature if temperature is not None else self.temperature
        used_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        logger.debug(f"Using model: {used_model}, Temperature: {used_temperature}, Max Tokens: {used_max_tokens}")
        
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
            
            # Set up parameters for the API call
            params = {
                "messages": messages,
                "max_tokens": used_max_tokens,
                "temperature": used_temperature,
                "stream": True
            }
            
            # For models endpoint format, include the model name in the request
            if not self.use_deployment_endpoint:
                params["model"] = used_model
            
            # Add optional parameters if provided
            if top_p is not None:
                params["top_p"] = top_p
            if presence_penalty is not None:
                params["presence_penalty"] = presence_penalty
            if frequency_penalty is not None:
                params["frequency_penalty"] = frequency_penalty
            if stop:
                params["stop"] = stop
            
            # Handle response format correctly
            if response_format:
                if isinstance(response_format, str):
                    # Convert string to dict format
                    params["response_format"] = {"type": response_format.lower()}
                else:
                    params["response_format"] = response_format
            elif response_format is not None:
                # If string is provided, convert to dict
                if response_format.lower() == "json":
                    params["response_format"] = {"type": "json"}
                else:
                    params["response_format"] = {"type": "text"}
            
            # Handle tools properly
            if tools:
                params["tools"] = tools
                
                if tool_choice:
                    params["tool_choice"] = tool_choice
            
            # Handle Codestral-specific parameters (like safe_mode)
            if safe_mode is not None:
                # Check if Azure API supports this parameter
                logger.debug(f"Attempting to use safe_mode={safe_mode}")
                try:
                    params["extra_body"] = {"safe_mode": safe_mode}
                except Exception as e:
                    logger.warning(f"Failed to set safe_mode: {str(e)}")
            
            # Call Azure API with streaming enabled
            logger.debug(f"Stream request parameters: {params}")
            stream_response = self.client.complete(**params)
            
            # Build the full response while yielding chunks
            full_response = ""
            
            for update in stream_response:
                if update.choices:
                    content = update.choices[0].delta.content or ""
                    if content:
                        full_response += content
                        if callback:
                            callback(content)
                        yield content
            
            # Add assistant's response to history
            self.conversation_history.append({"role": "assistant", "content": full_response})
            
            logger.info("Stream response completed successfully")
            
        except HttpResponseError as e:
            # Handle content filtering errors
            if e.status_code == 400:
                response = e.response.json() if hasattr(e, 'response') else {}
                if isinstance(response, dict) and "error" in response:
                    error_msg = f"Request triggered an {response['error']['code']} error: {response['error']['message']}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            elif e.status_code == 404:
                logger.error(f"404 Not Found error: {str(e)}")
                logger.error(f"Check if the model '{used_model}' exists and is properly configured in your Azure account")
                raise RuntimeError(f"Model not found: {used_model}. Please verify the model name and endpoint configuration.")
            
            logger.error(f"HTTP error: {str(e)}")
            raise RuntimeError(f"Error streaming response from Azure Codestral: {str(e)}")
            
        except Exception as e:
            logger.error("Problem with stream response generation")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- model: {used_model}")
            logger.error(f"  -- endpoint: {self.endpoint}")
            logger.error(f"  -- system: {self.system_instructions}")
            logger.error(f"  -- conversation history: {self.conversation_history}")
            logger.error(f"  -- max_tokens: {used_max_tokens}")
            logger.error(f"  -- temperature: {used_temperature}")
            
            raise RuntimeError(f"Error streaming response from Azure Codestral: {str(e)}")
            
    def clear_conversation(self):
        """Clear the conversation history."""
        logger.info("Clearing conversation history")
        self.conversation_history = []
        
    def test_connection(self) -> bool:
        """
        Test the connection to the Azure AI endpoint.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            logger.info(f"Testing connection to endpoint: {self.endpoint}")
            
            # For the models endpoint format, we test by making a simple request
            if not self.use_deployment_endpoint:
                response = self.client.complete(
                    messages=[
                        SystemMessage(content="Test connection"),
                        UserMessage(content="Hello")
                    ],
                    max_tokens=5,  # Keep it minimal for quicker response
                    model=self.model  # Include model name for models endpoint
                )
                logger.info("Connection successful")
                return True
            
            # For deployment endpoint format, try to get available models list
            else:
                # Get the list of available models
                models = self.client.list_models()
                logger.info(f"Connection successful. Available models: {[m.model_name for m in models]}")
                return True
                
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False

    def generate_code(self, 
                      prompt: str, 
                      language: Optional[str] = None,
                      **kwargs) -> str:
        """
        Generate code based on the prompt, optimized for Codestral's capabilities.
        
        Args:
            prompt: User's code generation request
            language: Programming language to generate code in (e.g., "python", "javascript")
            **kwargs: Additional parameters to pass to generate_response
            
        Returns:
            The generated code as a string
        """
        # Enhance the system instructions for code generation
        code_system_instructions = (
            f"You are an expert programmer. Generate clean, efficient, and well-commented "
            f"code in response to the following request. "
        )
        
        if language:
            code_system_instructions += f"Use {language} programming language. "
            
        code_system_instructions += (
            f"Focus on producing working, production-ready code with appropriate error handling. "
            f"Include helpful comments to explain complex sections."
        )
        
        # Add fill-in-the-middle capability hint for Codestral
        if "fill in" in prompt.lower() or "complete this code" in prompt.lower():
            code_system_instructions += (
                f" The user is asking you to complete or fill in code. Pay close attention to "
                f"the surrounding code context and maintain consistent style, variable naming, "
                f"and functionality."
            )

        return self.generate_response(
            prompt=prompt, 
            system_instructions=code_system_instructions,
            **kwargs
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
        # Enhance the system instructions for code explanation
        explain_system_instructions = (
            "You are an expert programming teacher. Provide a clear, thorough explanation "
            "of the provided code. Break down complex concepts, explain the purpose of key "
            "functions and variables, and highlight any notable patterns or techniques used. "
            "Your explanation should be educational and help the user understand how the code works."
        )
        
        prompt = f"Please explain this code in detail:\n\n```\n{code}\n```"
        
        return self.generate_response(
            prompt=prompt,
            system_instructions=explain_system_instructions,
            **kwargs
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
        # Enhance the system instructions for code review
        review_system_instructions = (
            "You are an expert code reviewer. Analyze the provided code for potential issues "
            "including bugs, security vulnerabilities, performance problems, and style inconsistencies. "
            "Provide constructive feedback and suggest specific improvements. Focus on making the "
            "code more robust, efficient, and maintainable. Include code snippets showing improved versions "
            "where appropriate."
        )
        
        prompt = f"Please review this code and suggest improvements:\n\n```\n{code}\n```"
        
        return self.generate_response(
            prompt=prompt,
            system_instructions=review_system_instructions,
            **kwargs
        )
    
    def fix_code(self, code: str, error_message: Optional[str] = None, **kwargs) -> str:
        """
        Fix issues in the provided code.
        
        Args:
            code: The code to fix
            error_message: Optional error message to help with debugging
            **kwargs: Additional parameters to pass to generate_response
            
        Returns:
            The fixed code as a string
        """
        # Enhance the system instructions for code fixing
        fix_system_instructions = (
            "You are an expert debugging assistant. Fix the issues in the provided code "
            "and return a corrected version. Identify the root causes of problems and "
            "implement proper solutions. Explain the changes you've made and why they fix the issues."
        )
        
        prompt = f"Please fix the issues in this code:\n\n```\n{code}\n```"
        
        if error_message:
            prompt += f"\n\nError message:\n```\n{error_message}\n```"
        
        return self.generate_response(
            prompt=prompt,
            system_instructions=fix_system_instructions,
            **kwargs
        )
    
    def translate_code(self, code: str, source_language: str, target_language: str, **kwargs) -> str:
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
        # Enhance the system instructions for code translation
        translate_system_instructions = (
            f"You are an expert in multiple programming languages. Translate the provided code "
            f"from {source_language} to {target_language}, maintaining the same functionality and logic. "
            f"Use idiomatic patterns and best practices in the target language. "
            f"Include comments explaining any significant changes needed for the translation."
        )
        
        prompt = f"Please translate this {source_language} code to {target_language}:\n\n```\n{code}\n```"
        
        return self.generate_response(
            prompt=prompt,
            system_instructions=translate_system_instructions,
            **kwargs
        )