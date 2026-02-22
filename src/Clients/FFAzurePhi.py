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

class FFAzurePhi:
    def __init__(self, config: Optional[dict] = None, **kwargs):
        logger.info("Initializing Phi-4")

        # DEFAULT VALUES
        defaults = {
            'model': "Phi-4",
            'max_tokens': 12000,
            'temperature': 0.7,
            'instructions': "You are a helpful assistant. Respond accurately to user queries. Be concise and clear."
        }

        # Combine config and kwargs, with kwargs taking precedence
        all_config = {**(config or {}), **kwargs}
        
        # Changed default to False to use the newer models endpoint format
        self.use_deployment_endpoint = all_config.get('use_deployment_endpoint', False)

        for key, value in all_config.items():
            match key:
                case 'api_key':
                    self.api_key = value or os.getenv('AZURE_PHI_KEY')
                case 'endpoint':
                    self.endpoint = value or os.getenv('AZURE_PHI_ENDPOINT')
                case 'model':
                    self.model = value
                case 'temperature':
                    self.temperature = float(value)
                case 'max_tokens':
                    self.max_tokens = int(value) if value is not None else defaults['max_tokens']
                case 'system_instructions':
                    self.system_instructions = value
                case 'use_deployment_endpoint':
                    self.use_deployment_endpoint = bool(value)

        # Set default values if not set
        self.api_key = getattr(self, 'api_key', os.getenv('AZURE_PHI_KEY'))
        self.endpoint = getattr(self, 'endpoint', os.getenv('AZURE_PHI_ENDPOINT'))
        self.model = getattr(self, 'model', os.getenv('AZURE_PHI_MODEL', defaults['model']))
        self.temperature = getattr(self, 'temperature', float(os.getenv('AZURE_PHI_TEMPERATURE', defaults['temperature'])))
        self.max_tokens = getattr(self, 'max_tokens', int(os.getenv('AZURE_PHI_MAX_TOKENS', defaults['max_tokens'])))
        self.system_instructions = getattr(self, 'system_instructions', os.getenv('AZURE_PHIL_ASSISTANT_INSTRUCTIONS', defaults['instructions']))

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
        logger.info("Initializing Azure Phi client")
        
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
            
        if self.use_deployment_endpoint:
            # For the old deployments endpoint format
            deployment_name = self.model.lower().replace("-", "").replace(".", "")
            full_endpoint = f"{endpoint}/openai/deployments/{deployment_name}"
        else:
            # For the new models endpoint format - FIXED PATH
            full_endpoint = f"{endpoint}/models"
        
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
                          max_completion_tokens: Optional[int] = None,
                          top_p: Optional[float] = None,
                          presence_penalty: Optional[float] = None,
                          frequency_penalty: Optional[float] = None,
                          stop: Optional[List[str]] = None,
                          response_format: Optional[Union[str, Dict]] = None,
                          tools: Optional[List[Dict]] = None,
                          tool_choice: Optional[str] = None,
                          safe_mode: Optional[bool] = None,
                          **kwargs) -> str:
        """
        Generate a response from the model with robust parameter handling.
        
        Args:
            prompt: User's input text
            model: Model to use (overrides default)
            system_instructions: System instructions (overrides default)
            temperature: Controls randomness (0-1)
            max_tokens: Maximum tokens to generate
            max_completion_tokens: Alternative name for max_tokens (for compatibility)
            top_p: Nucleus sampling parameter
            presence_penalty: Penalizes repeated tokens
            frequency_penalty: Penalizes frequent tokens
            stop: List of strings that stop generation when encountered
            response_format: Format of the response ("text" or "json")
            tools: List of tools to make available to the model
            tool_choice: Tool choice strategy ("auto", "none", or specific tool)
            safe_mode: Whether to enable Mistral's safe mode
            **kwargs: Any additional parameters that may be passed but aren't used
            
        Returns:
            The model's response as a string
        """
        if not prompt.strip():
            raise ValueError("Empty prompt provided")
        
        logger.debug(f"Generating response for prompt: {prompt}")
        
        # Parameter normalization
        used_model = model or self.model or "Phi-4"
        
        # Handle max tokens
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
        
        # Handle temperature
        used_temperature = None
        if temperature is not None:
            try:
                used_temperature = float(temperature)
                if not 0 <= used_temperature <= 2:
                    logger.warning(f"Temperature value {used_temperature} outside valid range [0,2]")
                    used_temperature = None
            except (ValueError, TypeError):
                logger.warning(f"Invalid temperature value: {temperature}")
        
        if used_temperature is None:
            used_temperature = self.temperature
        
        logger.debug(f"Using model: {used_model}, Temperature: {used_temperature}, Max Tokens: {used_max_tokens}")

        try:
            # Add user prompt to history
            self.conversation_history.append({"role": "user", "content": prompt})
            
            # Create messages list
            messages = self._convert_history_to_messages()
            
            # Handle system instructions
            if system_instructions:
                # Remove existing system message if present
                if messages and isinstance(messages[0], SystemMessage):
                    messages = messages[1:]
                # Add new system message at the beginning
                messages.insert(0, SystemMessage(content=system_instructions))
            
            # Build parameters dict for API call
            api_params = {
                "messages": messages,
                "max_tokens": used_max_tokens,
                "temperature": used_temperature,
                "stream": False  # Explicitly disable streaming
            }
            
            # For models endpoint format, include the model name in the request
            if not self.use_deployment_endpoint:
                api_params["model"] = used_model
            
            # Add optional parameters only if they have valid values
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
            
            # Mistral-specific parameters
            model_extras = {}
            if safe_mode is not None:
                model_extras["safe_mode"] = bool(safe_mode)
                
            if model_extras:
                api_params["model_extras"] = model_extras
            
            logger.debug(f"Calling Azure API with params: {api_params}")
            
            # Call Azure API
            response = self.client.complete(**api_params)
            
            # Handle tool calls if present
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
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
                
                # For compatibility with the simple interface, return a string with tool call info
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
            raise RuntimeError(f"Error generating response from Azure Mistral: {str(e)}")
            
        except Exception as e:
            logger.error("Problem with response generation")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- model: {self.model}")
            logger.error(f"  -- system: {self.system_instructions}")
            logger.error(f"  -- conversation history: {self.conversation_history}")
            logger.error(f"  -- max_tokens: {self.max_tokens}")
            logger.error(f"  -- temperature: {self.temperature}")
            
            raise RuntimeError(f"Error generating response from Azure Mistral: {str(e)}")


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