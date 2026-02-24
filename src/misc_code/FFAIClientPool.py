# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
# 
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
# 
# Contact: antquinonez@farfiner.com
# filename: src/lib/AI/FFAIClientPool.py

from typing import Dict, Optional, List, Union, Tuple, Type
from enum import Enum
from threading import Lock
import logging
import hashlib

from .FFAIClientBase import FFAIClientBase
from .FFAI import FFAI

# Configure logging
logger = logging.getLogger(__name__)

from enum import Enum
from typing import Type
from .FFAIClientBase import FFAIClientBase

# Import client implementations
from .ffai_v1.FFAzureOpenAI import FFAzureOpenAI
from .FFAnthropic import FFAnthropic
from .FFAnthropicCached import FFAnthropicCached
from .FFGemini import FFGemini
from .FFOpenAIAssistant import FFOpenAIAssistant
from .FFPerplexity import FFPerplexity
from .FFAzureMistral import FFAzureMistral
from .FFAzureDeepSeek import FFAzureDeepSeek
from .FFAzurePhi import FFAzurePhi

class FFAIClient(Enum):
    """
    Enum representing different types of FFAI clients
    Each enum value is associated with its corresponding client class
    """

    # enum members with their associated client classes
    ANTHROPIC = FFAnthropic
    ANTHROPIC_CACHED = FFAnthropicCached
    AZURE_DEEPSEEK = FFAzureDeepSeek
    AZURE_MISTRAL = FFAzureMistral
    AZURE_OPENAI = FFAzureOpenAI
    GEMINI = FFGemini
    MISTRAL = FFAzureMistral
    OPENAI_ASSISTANT = FFOpenAIAssistant
    PERPLEXITY = FFPerplexity
    AZURE_PHI = FFAzurePhi

    def __new__(cls, client_class: Type[FFAIClientBase]):
        obj = object.__new__(cls)
        obj._value_ = len(cls.__members__) + 1
        obj.client_class = client_class
        return obj

    def create_client(self, **kwargs) -> FFAI:
        """
        Create an instance of this client type wrapped with FFAI
        
        Args:
            **kwargs: Arguments to pass to client constructor
            
        Returns:
            An FFAI-wrapped instance of the client
        """
        base_client = self.client_class(**kwargs)
        return FFAI(base_client)

    @classmethod
    def get_client_class(cls, client_type: 'FFAIClient') -> Type[FFAIClientBase]:
        """Get the client class for a specific type"""
        return client_type.client_class

class ClientConfig:
    """Configuration for a client in the pool"""
    def __init__(self, ffai_client: FFAI, default_model: Optional[str] = None, 
                 config: Optional[Dict] = None):
        self.ffai_client = ffai_client
        self.default_model = default_model
        self.config = self._normalize_config(config or {})
        
    def _normalize_config(self, config: Dict) -> Dict:
        """Normalize configuration values to ensure consistent comparison"""
        normalized = {}
        for key, value in config.items():
            # Handle lists by taking first value
            if isinstance(value, list):
                value = value[0] if value else None
                
            # Convert known numeric values
            if key in ('max_tokens', 'max_completion_tokens') and value is not None:
                value = int(value)
            elif key in ('temperature') and value is not None:
                value = float(value)
                
            # Only include non-None values
            if value is not None:
                normalized[key] = value
                
        return normalized
        
    def matches_config(self, other_config: Optional[Dict]) -> bool:
        """Check if core configuration parameters match"""
        if not other_config:
            return True
            
        # Only check core configuration parameters
        # note: question: What does all() do?
        #       answer: all() returns True if all elements of the iterable are true. If not, it returns False.
        core_params = {'model', 'endpoint_url', 'api_version'}
        normalized_other = self._normalize_config(other_config)
        return all(
            key in self.config and self.config[key] == value for key, value in normalized_other.items() if key in core_params
        )

class FFAIClientPool:
    """Manages a pool of FFAI-wrapped AI clients with thread-safe access"""
    def __init__(self):
        """Initialize an empty client pool"""
        self._clients: Dict[str, ClientConfig] = {}
        self._default_client_name: Optional[str] = None
        self._lock = Lock()
        logger.info("Initialized new FFAIClientPool")
        
    def create_client_identifier(self, client_type: str, model: str, 
                            endpoint_url: Optional[str] = None,
                            api_version: Optional[str] = None) -> str:
        """
        Generate a unique client identifier based on core client configuration only
        """
        base_name = f"{client_type}_{model}"
        if endpoint_url or api_version:
            # Only hash the truly unique identifying parameters
            config_str = f"{endpoint_url or ''}_{api_version or ''}"
            config_hash = hashlib.md5(config_str.encode()).hexdigest()[:6]
            return f"{base_name}_{config_hash}"
        return base_name
            
    def add_client(self, name: str, client: Union[FFAIClientBase, FFAI], 
                  default_model: Optional[str] = None,
                  config: Optional[Dict] = None,
                  make_default: bool = False) -> None:
        """
        Add a client to the pool, automatically wrapping it with FFAI if needed
        
        Args:
            name: Unique identifier for the client
            client: The client instance to add (either raw client or FFAI-wrapped)
            default_model: Optional default model for this client
            config: Configuration dictionary for this client
            make_default: Whether to make this the default client
        """
        with self._lock:
            if name in self._clients:
                existing_config = self._clients[name]
                if existing_config.matches_config(config):
                    logger.debug(f"Client '{name}' already exists with matching config")
                    return
                    
                # Log the mismatch for debugging
                logger.error(f"Config mismatch for client '{name}':")
                logger.error(f"Existing config: {existing_config.config}")
                logger.error(f"New config: {ClientConfig(client, config=config).config}")
                raise ValueError(f"Client with name '{name}' already exists with different config")
                
            logger.info(f"Adding client '{name}' to pool")
            
            # Wrap the client with FFAI if it's not already wrapped
            ffai_client = client if isinstance(client, FFAI) else FFAI(client)
            self._clients[name] = ClientConfig(
                ffai_client=ffai_client,
                default_model=default_model,
                config=config
            )
            
            if make_default or self._default_client_name is None:
                self._default_client_name = name
                logger.info(f"Set '{name}' as default client")
                
    def remove_client(self, name: str) -> None:
        """
        Remove a client from the pool
        
        Args:
            name: Name of the client to remove
            
        Raises:
            KeyError: If client name doesn't exist
        """
        with self._lock:
            if name not in self._clients:
                raise KeyError(f"Client '{name}' not found")
                
            logger.info(f"Removing client '{name}' from pool")
            del self._clients[name]
            
            if self._default_client_name == name:
                self._default_client_name = next(iter(self._clients)) if self._clients else None
                logger.info(f"Updated default client to '{self._default_client_name}'")
                    
    def get_client(self, name: Optional[str] = None, config: Optional[Dict] = None) -> Tuple[FFAI, Optional[str]]:
        """
        Get an FFAI-wrapped client by name or get the default client
        
        Args:
            name: Name of client to retrieve, or None for default client
            config: Optional configuration to match
            
        Returns:
            Tuple of (FFAI-wrapped client instance, default model name)
            
        Raises:
            ValueError: If no default client set when requesting default
            KeyError: If specified client name not found
        """
        with self._lock:
            if name is None:
                if self._default_client_name is None:
                    raise ValueError("No default client set")
                client_config = self._clients[self._default_client_name]
                logger.debug(f"Retrieved default client '{self._default_client_name}'")
            else:
                if name not in self._clients:
                    raise KeyError(f"Client '{name}' not found")
                client_config = self._clients[name]
                if config and not client_config.matches_config(config):
                    raise ValueError(f"Client '{name}' exists but with different configuration")
                logger.debug(f"Retrieved client '{name}'")
                
            return client_config.ffai_client, client_config.default_model
            
    def set_default_client(self, name: str) -> None:
        """
        Set the default client
        
        Args:
            name: Name of client to make default
            
        Raises:
            KeyError: If client name doesn't exist
        """
        with self._lock:
            if name not in self._clients:
                raise KeyError(f"Client '{name}' not found")
            
            logger.info(f"Setting default client to '{name}'")
            self._default_client_name = name
            
    def get_default_client_name(self) -> Optional[str]:
        """Get the name of the current default client"""
        return self._default_client_name
            
    def get_client_names(self) -> List[str]:
        """Get list of all client names"""
        return list(self._clients.keys())