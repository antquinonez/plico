# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
# 
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
# 
# Contact: antquinonez@farfiner.com

# filename: src/lib/AI/_FactoryFFAzureOpenAI.py

"""
Factory for creating Azure OpenAI clients.
Handles client instantiation based on model type and configuration.
"""

import logging
from typing import Optional, Dict, Any, Type
from .ffai_v2._BaseFFAzureOpenAI import FFAzureOpenAIBase
from .ffai_v2.FFAzureOpenAIo1 import FFAzureOpenAIo1
from .ffai_v2.FFAzureOpenAIo1Mini import FFAzureOpenAIo1Mini
from .ffai_v2.FFAzureOpenAIGPT4o import FFAzureOpenAIGPT4o

logger = logging.getLogger(__name__)

class FFAzureOpenAIFactory:
    """Factory class for creating Azure OpenAI clients."""
    
    # Map model names to their implementation classes
    _MODEL_MAP: Dict[str, Type[FFAzureOpenAIBase]] = {
        'o1': FFAzureOpenAIo1,
        'o1-mini': FFAzureOpenAIo1Mini,
        'gpt-4o': FFAzureOpenAIGPT4o
    }

    @classmethod
    def _validate_config(cls, model: str, config: Optional[Dict[str, Any]] = None, **kwargs) -> None:
        """
        Validate configuration before client creation.
        
        Args:
            model: The model name
            config: Configuration dictionary
            **kwargs: Additional configuration parameters
            
        Raises:
            ValueError: If configuration is invalid
        """
        combined_config = {**(config or {}), **kwargs}
        
        # Validate temperature if present
        if 'temperature' in combined_config:
            temp = float(combined_config['temperature'])
            if not 0 <= temp <= 1:
                raise ValueError(f"Temperature must be between 0 and 1, got {temp}")
        
        # Validate token limits
        if model in ['o1', 'o1-mini']:
            if 'max_completion_tokens' in combined_config:
                tokens = int(combined_config['max_completion_tokens'])
                if tokens <= 0:
                    raise ValueError(f"max_completion_tokens must be positive, got {tokens}")
        else:
            if 'max_tokens' in combined_config:
                tokens = int(combined_config['max_tokens'])
                if tokens <= 0:
                    raise ValueError(f"max_tokens must be positive, got {tokens}")
        
        # Validate reasoning effort for o1
        if model == 'o1' and 'reasoning_effort' in combined_config:
            effort = combined_config['reasoning_effort']
            if effort not in ['low', 'medium', 'high']:
                raise ValueError(f"reasoning_effort must be 'low', 'medium', or 'high', got {effort}")

    @classmethod
    def create_client(cls, 
                     model: str, 
                     config: Optional[Dict[str, Any]] = None, 
                     **kwargs) -> FFAzureOpenAIBase:
        """
        Create an appropriate Azure OpenAI client based on the model name.
        
        Args:
            model: The model name ('o1', 'o1-mini', 'gpt-4o')
            config: Optional configuration dictionary
            **kwargs: Additional keyword arguments for client initialization
            
        Returns:
            An instance of the appropriate client class
            
        Raises:
            ValueError: If the model is not supported
            
        Example:
            >>> client = FFAzureOpenAIFactory.create_client('o1', {'max_completion_tokens': 50000})
            >>> response = client.generate_response("Hello, how are you?")
        """
        model = model.lower()
        
        if model not in cls._MODEL_MAP:
            supported_models = list(cls._MODEL_MAP.keys())
            raise ValueError(
                f"Unsupported model: {model}. "
                f"Supported models are: {supported_models}"
            )
            
        client_class = cls._MODEL_MAP[model]
        logger.info(f"Creating client for model: {model}")
        logger.debug(f"Configuration: {config}")
        logger.debug(f"Additional arguments: {kwargs}")
        
        try:
            # Validate configuration before creating client
            cls._validate_config(model, config, **kwargs)
            return client_class(config, **kwargs)
        except Exception as e:
            logger.error(f"Error creating client for model {model}")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- config: {config}")
            logger.error(f"  -- kwargs: {kwargs}")
            raise

    @classmethod
    def get_model_capabilities(cls, model: str) -> Dict[str, Any]:
        """
        Get the capabilities and limits of a specific model.
        
        Args:
            model: The model name
            
        Returns:
            Dictionary containing model capabilities and limits
            
        Example:
            >>> caps = FFAzureOpenAIFactory.get_model_capabilities('o1')
            >>> print(f"Max completion tokens: {caps['max_completion_tokens']}")
        """
        model = model.lower()
        if model not in cls._MODEL_MAP:
            raise ValueError(f"Unsupported model: {model}")
            
        client_class = cls._MODEL_MAP[model]
        limits = client_class._get_model_limits()
        
        capabilities = {
            'max_context_length': limits['max_context_length'],
            'supports_temperature': model in ['o1-mini', 'gpt-4o'],
            'supports_reasoning_effort': model == 'o1',
            'token_limit': limits['max_completion_tokens'],
            'recommended_use': {
                'o1': 'Best for complex reasoning tasks requiring thorough analysis',
                'o1-mini': 'Efficient for shorter completion tasks with temperature control',
                'gpt-4o': 'Balanced performance for general use cases'
            }.get(model, '')
        }
        
        return capabilities

    @classmethod
    def supported_models(cls) -> list:
        """
        Return a list of supported models.
        
        Returns:
            List of model names that can be used with create_client
        """
        return list(cls._MODEL_MAP.keys())

    @classmethod
    def create_default_client(cls, model: str) -> FFAzureOpenAIBase:
        """
        Create a client with default configuration.
        
        Args:
            model: The model name
            
        Returns:
            A client instance with default configuration
            
        Example:
            >>> client = FFAzureOpenAIFactory.create_default_client('o1')
        """
        return cls.create_client(model)

    @classmethod
    def get_client_class(cls, model: str) -> Type[FFAzureOpenAIBase]:
        """
        Get the client class for a given model without instantiating it.
        
        Args:
            model: The model name
            
        Returns:
            The client class for the specified model
            
        Raises:
            ValueError: If the model is not supported
        """
        model = model.lower()
        if model not in cls._MODEL_MAP:
            supported_models = list(cls._MODEL_MAP.keys())
            raise ValueError(
                f"Unsupported model: {model}. "
                f"Supported models are: {supported_models}"
            )
        return cls._MODEL_MAP[model]