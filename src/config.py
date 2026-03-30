# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Configuration management using pydantic-settings.

Provides centralized configuration loaded from config/*.yaml files with
environment variable overrides and type-safe access.

Config files:
  config/main.yaml          - Core app settings (workbook, orchestrator, etc.)
  config/logging.yaml       - Logging configuration
  config/paths.yaml         - File system paths
  config/clients.yaml       - AI client configurations
  config/model_defaults.yaml - Per-model default parameters
  config/sample_workbook.yaml - Sample workbook defaults
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


def _find_config_dir() -> Path:
    """Find config directory starting from current directory up to project root."""
    candidates = [
        Path.cwd() / "config",
        Path(__file__).parent.parent / "config",
        Path.cwd().parent / "config",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return Path("config")


def _load_yaml_file(filename: str) -> dict[str, Any]:
    """Load a single YAML file from the config directory."""
    config_dir = _find_config_dir()
    filepath = config_dir / filename
    if not filepath.exists():
        return {}
    with open(filepath, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_all_configs() -> dict[str, Any]:
    """Load all configuration files and merge them."""
    clients_yaml = _load_yaml_file("clients.yaml")
    return {
        "logging": _load_yaml_file("logging.yaml").get("logging", {}),
        "paths": _load_yaml_file("paths.yaml").get("paths", {}),
        "workbook": _load_yaml_file("main.yaml").get("workbook", {}),
        "orchestrator": _load_yaml_file("main.yaml").get("orchestrator", {}),
        "retry": _load_yaml_file("main.yaml").get("retry", {}),
        "document_processor": _load_yaml_file("main.yaml").get("document_processor", {}),
        "rag": _load_yaml_file("main.yaml").get("rag", {}),
        "agent": _load_yaml_file("main.yaml").get("agent", {}),
        "clients": clients_yaml,
        "model_defaults": _load_yaml_file("model_defaults.yaml").get("model_defaults", {}),
        "sample": _load_yaml_file("sample_workbook.yaml").get("sample_workbooks", {}),
    }


class YamlConfigSource(PydanticBaseSettingsSource):
    """Custom settings source that reads from merged YAML files."""

    def __init__(self, settings_cls: type[BaseSettings], yaml_data: dict[str, Any]):
        super().__init__(settings_cls)
        self._yaml_data = yaml_data

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        field_value = self._yaml_data.get(field_name)
        return field_value, field_name, False

    def __call__(self) -> dict[str, Any]:
        return self._yaml_data


class LoggingRotationConfig(BaseSettings):
    """Logging rotation configuration."""

    when: str = "midnight"
    interval: int = 1
    backup_count: int = 10


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    directory: str = "logs"
    filename: str = "orchestrator.log"
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    rotation: LoggingRotationConfig = Field(default_factory=LoggingRotationConfig)


class PathsConfig(BaseSettings):
    """Path configuration for various directories."""

    ffai_data: str = "./ffai_data"
    doc_cache: str = "doc_cache"
    library: str = "library"
    output_dir: str = "./outputs"
    manifest_dir: str = "./manifests"


class WorkbookSheetNamesConfig(BaseSettings):
    """Workbook sheet name configuration."""

    config: str = "config"
    prompts: str = "prompts"
    data: str = "data"
    clients: str = "clients"
    documents: str = "documents"
    tools: str = "tools"
    scoring: str = "scoring"


class WorkbookDefaultsConfig(BaseSettings):
    """Default values for workbook configuration."""

    model: str = "mistral-small-2503"
    api_key_env: str = "MISTRALSMALL_KEY"
    max_retries: int = 3
    temperature: float = 0.8
    max_tokens: int = 4096
    system_instructions: str = "You are a helpful assistant. Respond accurately to user queries."


class WorkbookBatchConfig(BaseSettings):
    """Batch mode configuration."""

    mode: str = "per_row"
    output: str = "combined"
    on_error: str = "continue"


class WorkbookFormattingFeaturesConfig(BaseSettings):
    """Excel features configuration."""

    freeze_panes: dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "rows": 1})
    auto_filter: dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "all_sheets": True}
    )


class WorkbookFormattingConfig(BaseSettings):
    """Workbook formatting configuration."""

    column_widths: dict[str, dict[str, int] | str] = Field(default_factory=dict)
    word_wrap: dict[str, Any] = Field(default_factory=dict)
    rows: dict[str, Any] = Field(
        default_factory=lambda: {"auto_fit_height": True, "wrap_text_height_multiplier": 15}
    )
    features: WorkbookFormattingFeaturesConfig = Field(
        default_factory=WorkbookFormattingFeaturesConfig
    )


class WorkbookConfig(BaseSettings):
    """Workbook configuration."""

    sheet_names: WorkbookSheetNamesConfig = Field(default_factory=WorkbookSheetNamesConfig)
    defaults: WorkbookDefaultsConfig = Field(default_factory=WorkbookDefaultsConfig)
    batch: WorkbookBatchConfig = Field(default_factory=WorkbookBatchConfig)
    formatting: WorkbookFormattingConfig = Field(default_factory=WorkbookFormattingConfig)


class OrchestratorConfig(BaseSettings):
    """Orchestrator configuration."""

    default_concurrency: int = 2
    max_concurrency: int = 10


class RetryConfig(BaseSettings):
    """Retry configuration for API calls."""

    max_attempts: int = 3
    min_wait_seconds: float = 1.0
    max_wait_seconds: float = 60.0
    exponential_base: float = 2.0
    exponential_jitter: bool = True
    retry_on_status_codes: list[int] = Field(default_factory=lambda: [429, 503, 502, 504])
    log_level: str = "INFO"


class DocumentProcessorConfig(BaseSettings):
    """Document processor configuration."""

    checksum_length: int = 8
    text_extensions: set[str] = {
        ".txt",
        ".md",
        ".py",
        ".js",
        ".html",
        ".htm",
        ".css",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".conf",
        ".sh",
        ".bat",
        ".csv",
        ".tsv",
        ".log",
        ".sql",
        ".r",
        ".c",
        ".cpp",
        ".h",
        ".java",
        ".kt",
        ".go",
        ".rs",
        ".php",
        ".rb",
        ".pl",
        ".swift",
    }


class RAGChunkingMarkdownConfig(BaseSettings):
    """Markdown chunking configuration."""

    split_headers: list[str] = Field(default_factory=lambda: ["h1", "h2", "h3"])
    preserve_structure: bool = True
    max_chunk_fallback: bool = True


class RAGChunkingCodeConfig(BaseSettings):
    """Code chunking configuration."""

    language: str = "python"
    split_by: str = "function"


class RAGChunkingConfig(BaseSettings):
    """Chunking strategy configuration."""

    strategy: str = "recursive"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    contextual_headers: bool = True
    dedup_enabled: bool = False
    dedup_mode: str = "exact"
    markdown: RAGChunkingMarkdownConfig = Field(default_factory=RAGChunkingMarkdownConfig)
    code: RAGChunkingCodeConfig = Field(default_factory=RAGChunkingCodeConfig)


class RAGSearchConfig(BaseSettings):
    """Search strategy configuration."""

    mode: str = "vector"
    n_results_default: int = 5
    hybrid_alpha: float = 0.6
    rerank: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    query_expansion: bool = False
    query_expansion_variations: int = 3
    summary_boost: float = 1.5


class RAGHierarchicalConfig(BaseSettings):
    """Hierarchical chunking configuration."""

    enabled: bool = False
    parent_context: bool = True
    parent_chunk_size: int = 1500
    levels: int = 2


class RAGConfig(BaseSettings):
    """RAG (Retrieval-Augmented Generation) configuration."""

    enabled: bool = True
    persist_dir: str = "./chroma_db"
    collection_name: str = "plico_kb"
    embedding_model: str = "mistral/mistral-embed"
    local_embeddings: bool = False
    embedding_cache_size: int = 256
    generate_summaries: bool = False
    chunk_size: int = 1000
    chunk_overlap: int = 200
    n_results_default: int = 5
    chunking: RAGChunkingConfig = Field(default_factory=RAGChunkingConfig)
    search: RAGSearchConfig = Field(default_factory=RAGSearchConfig)
    hierarchical: RAGHierarchicalConfig = Field(default_factory=RAGHierarchicalConfig)


class AgentValidationConfig(BaseSettings):
    """Agent response validation configuration."""

    enabled: bool = True
    max_retries: int = 2


class AgentConfig(BaseSettings):
    """Agent mode configuration."""

    enabled: bool = True
    max_tool_rounds: int = 5
    tool_timeout: float = 30.0
    continue_on_tool_error: bool = True
    validation: AgentValidationConfig = AgentValidationConfig()


class ClientConfig(BaseSettings):
    """Individual client configuration (legacy format)."""

    type: str = "litellm"
    provider_prefix: str = ""
    model: str = ""
    api_key_env: str = ""
    api_key: str = ""
    client_class: str = ""
    azure_endpoint: str = ""
    azure_deployment: str = ""
    api_base: str = ""
    api_version: str = ""
    fallbacks: list[str] = Field(default_factory=list)


class ClientTypeConfig(BaseSettings):
    """Configuration for a single client type."""

    client_class: str = ""
    type: Literal["native", "litellm"] = "litellm"
    api_key_env: str = ""
    provider_prefix: str = ""
    default_model: str = ""


class ClientsConfig(BaseSettings):
    """All clients configuration with client type definitions."""

    model_config = SettingsConfigDict(extra="allow")

    default_client: str = "litellm-mistral-small"
    client_types: dict[str, ClientTypeConfig] = Field(default_factory=dict)

    def get_client(self, name: str) -> ClientConfig | None:
        """Get a client configuration by name (legacy support)."""
        data = getattr(self, name, None)
        if data is None:
            return None
        if isinstance(data, dict):
            return ClientConfig(**data)
        return data

    def get_client_type(self, name: str) -> ClientTypeConfig | None:
        """Get a client type configuration by name."""
        return self.client_types.get(name)

    def get_available_client_types(self) -> list[str]:
        """Get list of available client type names."""
        return list(self.client_types.keys())


class StrategyConfig(BaseSettings):
    """Configuration for an evaluation strategy."""

    description: str = ""
    criteria_overrides: dict[str, float] = Field(default_factory=dict)


class EvaluationConfig(BaseSettings):
    """Evaluation (scoring/synthesis) configuration."""

    default_strategy: str = "balanced"
    scoring_failure_threshold: float = 0.5
    max_synthesis_context_chars: int = 30000
    strategies: dict[str, StrategyConfig] = Field(default_factory=dict)

    model_config = SettingsConfigDict(extra="ignore")


class ModelDefaultsGenericConfig(BaseSettings):
    """Generic model defaults."""

    max_tokens: int = 4096
    temperature: float = 0.7
    system_instructions: str = "You are a helpful assistant. Respond accurately to user queries."


class ModelDefaultsConfig(BaseSettings):
    """Model-specific defaults configuration."""

    generic: dict[str, Any] = Field(
        default_factory=lambda: {
            "max_tokens": 4096,
            "temperature": 0.7,
            "system_instructions": "You are a helpful assistant. Respond accurately to user queries.",
        }
    )
    models: dict[str, dict[str, Any]] = Field(default_factory=dict)


class SampleWorkbookPathsConfig(BaseSettings):
    """Sample workbook file paths."""

    basic: str = "./sample_workbook.xlsx"
    multiclient: str = "./sample_workbook_multiclient.xlsx"
    conditional: str = "./sample_workbook_conditional.xlsx"
    documents: str = "./sample_workbook_documents.xlsx"
    batch: str = "./sample_workbook_batch.xlsx"
    max: str = "./sample_workbook_max.xlsx"
    agent: str = "./sample_workbook_agent.xlsx"


class SampleClientConfig(BaseSettings):
    """Sample client configuration for workbook generators."""

    client_type: str = "litellm-mistral"
    api_key_env: str = "MISTRAL_API_KEY"
    model: str = "mistral-small-latest"
    temperature: float = 0.7
    max_tokens: int = 300


class SampleConfig(BaseSettings):
    """Sample workbook configuration."""

    default_client_type: str = "litellm-mistral"
    default_model: str = "mistral-small-latest"
    default_temperature: float = 0.7
    default_max_tokens: int = 300
    default_retries: int = 2
    default_system_instructions: str = (
        "You are a helpful assistant. Give brief, concise answers. "
        "For math questions, just give the number."
    )
    output_dir: str = "."
    workbooks: SampleWorkbookPathsConfig = Field(default_factory=SampleWorkbookPathsConfig)
    sample_clients: dict[str, SampleClientConfig] = Field(default_factory=dict)


class Config(BaseSettings):
    """Main configuration class."""

    model_config = SettingsConfigDict(
        extra="ignore",
        validate_default=True,
        env_nested_delimiter="__",
    )

    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    workbook: WorkbookConfig = Field(default_factory=WorkbookConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    document_processor: DocumentProcessorConfig = Field(default_factory=DocumentProcessorConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    clients: ClientsConfig = Field(default_factory=ClientsConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    model_defaults: ModelDefaultsConfig = Field(default_factory=ModelDefaultsConfig)
    sample: SampleConfig = Field(default_factory=SampleConfig)

    @model_validator(mode="before")
    @classmethod
    def _validate_agent_field(cls, values: Any) -> Any:
        if (
            isinstance(values, dict)
            and "agent" in values
            and not isinstance(values["agent"], dict | AgentConfig)
        ):
            values["agent"] = AgentConfig()
        return values

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_data = _load_all_configs()
        yaml_source = YamlConfigSource(settings_cls, yaml_data)
        return (init_settings, env_settings, yaml_source)

    def get_client_config(self, name: str) -> ClientConfig | None:
        """Get a client configuration by name (legacy support)."""
        return self.clients.get_client(name)

    def get_client_type_config(self, name: str) -> ClientTypeConfig | None:
        """Get a client type configuration by name."""
        return self.clients.get_client_type(name)

    def get_default_client_type(self) -> str:
        """Get the default client type name."""
        return self.clients.default_client

    def get_available_client_types(self) -> list[str]:
        """Get list of available client type names."""
        return self.clients.get_available_client_types()

    def get_api_key(self, client_name: str) -> str | None:
        """Get API key for a client, checking direct key first, then env var."""
        client_type_config = self.get_client_type_config(client_name)
        if client_type_config is None:
            return None

        if client_type_config.api_key_env:
            return os.getenv(client_type_config.api_key_env)

        return None

    def get_litellm_prefix(self, client_name: str) -> str:
        """Get LiteLLM provider prefix for a client."""
        client_type_config = self.get_client_type_config(client_name)
        if client_type_config is None:
            return ""
        return client_type_config.provider_prefix


_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from files."""
    global _config
    _config = Config()
    return _config
