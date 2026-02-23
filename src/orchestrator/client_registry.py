import os
import logging
from typing import Dict, Any, Optional, Type

from ..FFAIClientBase import FFAIClientBase
from ..Clients.FFMistral import FFMistral
from ..Clients.FFMistralSmall import FFMistralSmall
from ..Clients.FFAnthropic import FFAnthropic
from ..Clients.FFAnthropicCached import FFAnthropicCached
from ..Clients.FFGemini import FFGemini
from ..Clients.FFPerplexity import FFPerplexity
from ..Clients.FFOpenAIAssistant import FFOpenAIAssistant
from ..Clients.FFNvidiaDeepSeek import FFNvidiaDeepSeek
from ..Clients.FFAzureMistral import FFAzureMistral
from ..Clients.FFAzureMistralSmall import FFAzureMistralSmall
from ..Clients.FFAzureCodestral import FFAzureCodestral
from ..Clients.FFAzureDeepSeek import FFAzureDeepSeek
from ..Clients.FFAzureDeepSeekV3 import FFAzureDeepSeekV3
from ..Clients.FFAzureMSDeepSeekR1 import FFAzureMSDeepSeekR1
from ..Clients.FFAzurePhi import FFAzurePhi

logger = logging.getLogger(__name__)


class ClientRegistry:
    """
    Registry for AI clients with lazy instantiation.

    Supports per-prompt client selection via named client configurations
    defined in the workbook's 'clients' sheet.

    Usage:
        registry = ClientRegistry(default_client)
        registry.register("fast", "mistral-small", {"temperature": 0.3})
        registry.register("smart", "anthropic", {"model": "claude-3-5-sonnet"})

        client = registry.get("fast")  # Returns mistral-small client
        client = registry.get()  # Returns default client
    """

    CLIENT_MAP: Dict[str, Type[FFAIClientBase]] = {
        "mistral": FFMistral,
        "mistral-small": FFMistralSmall,
        "anthropic": FFAnthropic,
        "anthropic-cached": FFAnthropicCached,
        "gemini": FFGemini,
        "perplexity": FFPerplexity,
        "openai-assistant": FFOpenAIAssistant,
        "nvidia-deepseek": FFNvidiaDeepSeek,
        "azure-mistral": FFAzureMistral,
        "azure-mistral-small": FFAzureMistralSmall,
        "azure-codestral": FFAzureCodestral,
        "azure-deepseek": FFAzureDeepSeek,
        "azure-deepseek-v3": FFAzureDeepSeekV3,
        "azure-ms-deepseek-r1": FFAzureMSDeepSeekR1,
        "azure-phi": FFAzurePhi,
    }

    DEFAULT_API_KEY_ENVS = {
        "mistral": "MISTRAL_KEY",
        "mistral-small": "MISTRALSMALL_KEY",
        "anthropic": "ANTHROPIC_TOKEN",
        "anthropic-cached": "ANTHROPIC_TOKEN",
        "gemini": "GOOGLE_APPLICATION_CREDENTIALS",
        "perplexity": "PERPLEXITY_TOKEN",
        "openai-assistant": "OPENAI_API_KEY",
        "nvidia-deepseek": "NVIDIA_API_KEY",
        "azure-mistral": "AZURE_MISTRAL_KEY",
        "azure-mistral-small": "AZURE_MISTRALSMALL_KEY",
        "azure-codestral": "AZURE_CODESTRAL_KEY",
        "azure-deepseek": "AZURE_DEEPSEEK_KEY",
        "azure-deepseek-v3": "AZURE_DEEPSEEKV3_KEY",
        "azure-ms-deepseek-r1": "AZURE_MSDEEPSEEKR1_KEY",
        "azure-phi": "AZURE_PHI_KEY",
    }

    def __init__(self, default_client: FFAIClientBase):
        """
        Initialize registry with a default client.

        Args:
            default_client: The default client to use when no name specified
        """
        self._default_client = default_client
        self._clients: Dict[str, FFAIClientBase] = {}
        self._client_configs: Dict[str, Dict[str, Any]] = {}

    def register(
        self, name: str, client_type: str, config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a named client configuration.

        Args:
            name: Unique identifier for this client
            client_type: Client type from CLIENT_MAP (e.g., "mistral-small", "anthropic")
            config: Optional configuration (api_key_env, model, temperature, max_tokens, etc.)

        Raises:
            ValueError: If client_type is not recognized
        """
        if client_type not in self.CLIENT_MAP:
            raise ValueError(
                f"Unknown client type: '{client_type}'. "
                f"Available types: {list(self.CLIENT_MAP.keys())}"
            )

        self._client_configs[name] = {
            "client_type": client_type,
            "config": config or {},
        }

        logger.info(f"Registered client '{name}' of type '{client_type}'")

    def get(self, name: Optional[str] = None) -> FFAIClientBase:
        """
        Get client by name, creating it lazily if needed.

        Args:
            name: Client name, or None for default client

        Returns:
            The requested client instance

        Note:
            If name is not found, returns default client with a warning.
        """
        if name is None:
            return self._default_client

        if name not in self._client_configs:
            logger.warning(
                f"Client '{name}' not found in registry, falling back to default client"
            )
            return self._default_client

        if name not in self._clients:
            self._clients[name] = self._create_client(name)

        return self._clients[name]

    def clone(self, name: Optional[str] = None) -> FFAIClientBase:
        """
        Get a fresh clone of a client for parallel execution.

        Args:
            name: Client name, or None for default client

        Returns:
            A cloned client with empty history
        """
        return self.get(name).clone()

    def _create_client(self, name: str) -> FFAIClientBase:
        """
        Create a client instance from registered configuration.

        Args:
            name: The registered client name

        Returns:
            A new client instance
        """
        registration = self._client_configs[name]
        client_type = registration["client_type"]
        config = registration["config"]

        client_class = self.CLIENT_MAP[client_type]

        api_key_env = config.get("api_key_env") or self.DEFAULT_API_KEY_ENVS.get(
            client_type
        )
        api_key = os.getenv(api_key_env) if api_key_env else None

        kwargs: Dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if config.get("model"):
            kwargs["model"] = config["model"]
        if config.get("temperature") is not None:
            kwargs["temperature"] = float(config["temperature"])
        if config.get("max_tokens"):
            kwargs["max_tokens"] = int(config["max_tokens"])
        if config.get("system_instructions"):
            kwargs["system_instructions"] = config["system_instructions"]

        logger.debug(
            f"Creating client '{name}' of type '{client_type}' with config: {kwargs}"
        )

        return client_class(**kwargs)

    def has_client(self, name: str) -> bool:
        """Check if a client name is registered."""
        return name in self._client_configs

    def get_registered_names(self) -> list:
        """Get list of registered client names."""
        return list(self._client_configs.keys())

    @classmethod
    def get_available_client_types(cls) -> list:
        """Get list of available client types."""
        return list(cls.CLIENT_MAP.keys())

    @classmethod
    def get_default_api_key_env(cls, client_type: str) -> Optional[str]:
        """Get the default API key environment variable for a client type."""
        return cls.DEFAULT_API_KEY_ENVS.get(client_type)
