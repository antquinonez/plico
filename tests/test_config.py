# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Comprehensive tests for configuration system.

Tests cover:
- 12-factor precedence: init > env > yaml > pydantic defaults
- Singleton behavior (get_config, reload_config)
- Type safety and validation
- All config sections loading from YAML
- Client helper methods
"""

from __future__ import annotations

import pytest
from pydantic_core import ValidationError

from src.config import Config, get_config, reload_config


class TestConfigPrecedence:
    """Test configuration precedence follows 12-factor methodology.

    Priority order (highest first):
    1. Init arguments
    2. Environment variables
    3. YAML files
    4. Pydantic defaults
    """

    def test_env_overrides_yaml(self, monkeypatch):
        """Env var should override YAML value."""
        monkeypatch.setenv("ORCHESTRATOR__DEFAULT_CONCURRENCY", "7")
        config = reload_config()
        assert config.orchestrator.default_concurrency == 7

    def test_init_overrides_env(self, monkeypatch):
        """Init args should override env var."""
        monkeypatch.setenv("ORCHESTRATOR__DEFAULT_CONCURRENCY", "7")
        config = Config(orchestrator={"default_concurrency": 9})
        assert config.orchestrator.default_concurrency == 9

    def test_yaml_used_when_no_env_override(self):
        """YAML value used when no env override set."""
        config = reload_config()
        assert config.orchestrator.default_concurrency == 2

    def test_nested_env_override(self, monkeypatch):
        """Nested config can be overridden via double underscore."""
        monkeypatch.setenv("WORKBOOK__DEFAULTS__TEMPERATURE", "0.5")
        config = reload_config()
        assert config.workbook.defaults.temperature == 0.5

    def test_list_env_override(self, monkeypatch):
        """List values can be overridden via env (JSON-like)."""
        monkeypatch.setenv("DOCUMENT_PROCESSOR__TEXT_EXTENSIONS", '[".txt", ".md"]')
        config = reload_config()
        assert ".txt" in config.document_processor.text_extensions
        assert ".md" in config.document_processor.text_extensions

    def test_pydantic_default_as_fallback(self, monkeypatch, tmp_path):
        """Pydantic defaults used when YAML missing and no env."""
        config = Config()
        assert config.logging.level == "INFO"

    def test_bool_env_override(self, monkeypatch):
        """Boolean values can be overridden via env."""
        monkeypatch.setenv("RAG__ENABLED", "false")
        config = reload_config()
        assert config.rag.enabled is False

    def test_clear_env_allows_yaml_to_take_effect(self, monkeypatch):
        """Clearing env var allows YAML value to be used."""
        monkeypatch.setenv("ORCHESTRATOR__DEFAULT_CONCURRENCY", "7")
        config = reload_config()
        assert config.orchestrator.default_concurrency == 7

        monkeypatch.delenv("ORCHESTRATOR__DEFAULT_CONCURRENCY")
        config = reload_config()
        assert config.orchestrator.default_concurrency == 2


class TestConfigSingleton:
    """Test singleton behavior of get_config and reload_config."""

    def test_get_config_returns_singleton(self):
        """get_config should return the same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reload_config_creates_new_instance(self):
        """reload_config should create a new instance."""
        config1 = get_config()
        config2 = reload_config()
        assert config1 is not config2

    def test_reload_config_updates_global(self):
        """reload_config should update the global singleton."""
        config1 = get_config()
        config2 = reload_config()
        config3 = get_config()
        assert config1 is not config3
        assert config2 is config3


class TestConfigTypeSafety:
    """Test type coercion and validation."""

    def test_int_coercion_from_env(self, monkeypatch):
        """String env vars are coerced to int."""
        monkeypatch.setenv("ORCHESTRATOR__MAX_CONCURRENCY", "15")
        config = reload_config()
        assert config.orchestrator.max_concurrency == 15
        assert isinstance(config.orchestrator.max_concurrency, int)

    def test_float_coercion_from_env(self, monkeypatch):
        """String env vars are coerced to float."""
        monkeypatch.setenv("WORKBOOK__DEFAULTS__TEMPERATURE", "0.95")
        config = reload_config()
        assert config.workbook.defaults.temperature == 0.95
        assert isinstance(config.workbook.defaults.temperature, float)

    def test_bool_coercion_from_env(self, monkeypatch):
        """String env vars are coerced to bool."""
        monkeypatch.setenv("RAG__GENERATE_SUMMARIES", "true")
        config = reload_config()
        assert config.rag.generate_summaries is True

        monkeypatch.setenv("RAG__GENERATE_SUMMARIES", "false")
        config = reload_config()
        assert config.rag.generate_summaries is False

    def test_invalid_type_raises_error(self):
        """Invalid types should raise validation error."""
        with pytest.raises(ValidationError):
            Config(orchestrator={"default_concurrency": "not_a_number"})


class TestConfigSections:
    """Test all config sections load correctly from YAML."""

    def test_logging_section(self):
        """Logging section loads from logging.yaml."""
        config = get_config()
        assert hasattr(config, "logging")
        assert config.logging.directory == "logs"
        assert config.logging.filename == "orchestrator.log"
        assert config.logging.level == "INFO"
        assert hasattr(config.logging, "rotation")
        assert config.logging.rotation.when == "midnight"
        assert config.logging.rotation.backup_count == 10

    def test_paths_section(self):
        """Paths section loads from paths.yaml."""
        config = get_config()
        assert hasattr(config, "paths")
        assert config.paths.ffai_data == "./ffai_data"
        assert config.paths.doc_cache == "doc_cache"
        assert config.paths.library == "library"
        assert config.paths.output_dir == "./outputs"
        assert config.paths.manifest_dir == "./manifests"

    def test_workbook_section(self):
        """Workbook section loads from main.yaml."""
        config = get_config()
        assert hasattr(config, "workbook")
        assert hasattr(config.workbook, "sheet_names")
        assert config.workbook.sheet_names.config == "config"
        assert config.workbook.sheet_names.prompts == "prompts"
        assert hasattr(config.workbook, "defaults")
        assert config.workbook.defaults.model == "mistral-small-2503"
        assert config.workbook.defaults.max_retries == 3
        assert hasattr(config.workbook, "batch")
        assert config.workbook.batch.mode == "per_row"

    def test_orchestrator_section(self):
        """Orchestrator section loads from main.yaml."""
        config = get_config()
        assert hasattr(config, "orchestrator")
        assert config.orchestrator.default_concurrency == 2
        assert config.orchestrator.max_concurrency == 10

    def test_document_processor_section(self):
        """Document processor section loads from main.yaml."""
        config = get_config()
        assert hasattr(config, "document_processor")
        assert config.document_processor.checksum_length == 8
        assert ".txt" in config.document_processor.text_extensions
        assert ".py" in config.document_processor.text_extensions

    def test_rag_section(self):
        """RAG section loads from main.yaml."""
        config = get_config()
        assert hasattr(config, "rag")
        assert config.rag.enabled is True
        assert config.rag.persist_dir == "./chroma_db"
        assert config.rag.chunk_size == 1000
        assert hasattr(config.rag, "chunking")
        assert hasattr(config.rag, "search")
        assert hasattr(config.rag, "hierarchical")

    def test_clients_section(self):
        """Clients section loads from clients.yaml."""
        config = get_config()
        assert hasattr(config, "clients")
        assert config.clients.default_client == "litellm-mistral-small"
        assert hasattr(config.clients, "client_types")

    def test_model_defaults_section(self):
        """Model defaults section loads from model_defaults.yaml."""
        config = get_config()
        assert hasattr(config, "model_defaults")
        assert hasattr(config.model_defaults, "generic")
        assert config.model_defaults.generic.get("max_tokens") == 4096

    def test_sample_section(self):
        """Sample section loads from sample_workbook.yaml."""
        config = get_config()
        assert hasattr(config, "sample")
        assert config.sample.default_model == "mistral-small-latest"
        assert config.sample.default_temperature == 0.7
        assert hasattr(config.sample, "workbooks")
        assert hasattr(config.sample, "sample_clients")


class TestConfigClientMethods:
    """Test client-related helper methods."""

    def test_get_client_type_config(self):
        """get_client_type_config returns correct config."""
        config = get_config()
        client_config = config.get_client_type_config("litellm-mistral")
        assert client_config is not None
        assert client_config.type == "litellm"
        assert client_config.provider_prefix == "mistral/"

    def test_get_client_type_config_unknown_returns_none(self):
        """get_client_type_config returns None for unknown client."""
        config = get_config()
        client_config = config.get_client_type_config("nonexistent-client")
        assert client_config is None

    def test_get_default_client_type(self):
        """get_default_client_type returns default client name."""
        config = get_config()
        default = config.get_default_client_type()
        assert default == "litellm-mistral-small"

    def test_get_available_client_types(self):
        """get_available_client_types returns list of clients."""
        config = get_config()
        clients = config.get_available_client_types()
        assert isinstance(clients, list)
        assert "litellm-mistral" in clients
        assert "litellm-anthropic" in clients

    def test_get_api_key_from_env(self, monkeypatch):
        """get_api_key retrieves key from environment."""
        monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
        config = reload_config()
        api_key = config.get_api_key("litellm-mistral")
        assert api_key == "test-mistral-key"

    def test_get_api_key_returns_none_for_unknown(self):
        """get_api_key returns None for unknown client."""
        config = get_config()
        api_key = config.get_api_key("nonexistent-client")
        assert api_key is None

    def test_get_litellm_prefix(self):
        """get_litellm_prefix returns correct prefix."""
        config = get_config()
        prefix = config.get_litellm_prefix("litellm-mistral")
        assert prefix == "mistral/"

    def test_get_litellm_prefix_unknown_returns_empty(self):
        """get_litellm_prefix returns empty string for unknown."""
        config = get_config()
        prefix = config.get_litellm_prefix("nonexistent-client")
        assert prefix == ""

    def test_get_client_config_legacy_returns_none_for_client_type(self):
        """get_client_config returns None for client_types (not legacy format)."""
        config = get_config()
        client_config = config.get_client_config("litellm-mistral")
        assert client_config is None


class TestConfigEnvFormat:
    """Test environment variable format for nested config."""

    def test_double_underscore_separator(self, monkeypatch):
        """Double underscore accesses nested values."""
        monkeypatch.setenv("WORKBOOK__DEFAULTS__MODEL", "gpt-4")
        config = reload_config()
        assert config.workbook.defaults.model == "gpt-4"

    def test_triple_nested_path(self, monkeypatch):
        """Triple nested config works."""
        monkeypatch.setenv("RAG__SEARCH__N_RESULTS_DEFAULT", "10")
        config = reload_config()
        assert config.rag.search.n_results_default == 10

    def test_case_insensitive_env_vars(self, monkeypatch):
        """Environment variable names are case-insensitive (handled by pydantic)."""
        monkeypatch.setenv("orchestrator__default_concurrency", "8")
        config = reload_config()
        assert config.orchestrator.default_concurrency == 8


class TestConfigExtraFields:
    """Test handling of extra/unknown fields."""

    def test_extra_yaml_fields_ignored(self, tmp_path):
        """Extra fields in YAML are ignored (extra='ignore')."""
        config = Config()
        assert config.model_config.get("extra") == "ignore"
