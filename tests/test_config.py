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
        """get_available_client_types returns list of known client type names."""
        config = get_config()
        clients = config.get_available_client_types()
        assert len(clients) > 0
        assert "litellm-mistral" in clients
        assert "litellm-anthropic" in clients

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

    def test_extra_fields_ignored_on_init(self):
        """Extra fields passed to Config are silently ignored, not rejected."""
        config = Config(orchestrator={"default_concurrency": 2}, unknown_field="should_be_ignored")
        assert config.orchestrator.default_concurrency == 2
        assert not hasattr(config, "unknown_field")


class TestAgentValidationConfig:
    def test_agent_validation_config_defaults(self):
        from src.config import AgentValidationConfig

        config = AgentValidationConfig()
        assert config.enabled is True
        assert config.max_retries == 2

    def test_agent_config_has_validation(self):
        from src.config import AgentConfig

        config = AgentConfig()
        assert config.validation.enabled is True
        assert config.validation.max_retries == 2


class TestRetryConfig:
    """Test retry configuration values loaded from main.yaml."""

    def test_retry_section_values(self):
        config = get_config()
        assert config.retry.max_attempts == 3
        assert config.retry.min_wait_seconds == 1.0
        assert config.retry.max_wait_seconds == 60.0
        assert config.retry.exponential_base == 2.0
        assert config.retry.exponential_jitter is True
        assert config.retry.retry_on_status_codes == [429, 503, 502, 504]
        assert config.retry.log_level == "INFO"


class TestPlanningConfig:
    """Test planning configuration values."""

    def test_planning_section_values(self):
        config = get_config()
        assert config.planning.enabled is True
        assert config.planning.save_artifacts is False
        assert config.planning.generated_sequence_base == "auto"
        assert config.planning.generated_sequence_step == 10
        assert config.planning.continue_on_parse_error is True


class TestEvaluationConfig:
    """Test evaluation/scoring configuration values."""

    def test_evaluation_section_values(self):
        config = get_config()
        assert config.evaluation.default_strategy == "balanced"
        assert config.evaluation.scoring_failure_threshold == 0.5
        assert config.evaluation.max_synthesis_context_chars == 30000
        assert config.evaluation.weight_tier_enabled is True
        assert config.evaluation.weight_tier_num_tiers == 3
        assert config.evaluation.weight_tier_prefix == "tier_"


class TestObservabilityConfig:
    """Test observability configuration values."""

    def test_observability_section_values(self):
        config = get_config()
        assert config.observability.enabled is False
        assert config.observability.otel.service_name == "plico"
        assert config.observability.otel.endpoint == "http://localhost:4317"
        assert config.observability.otel.export_traces is True
        assert config.observability.otel.insecure is True
        assert config.observability.token_tracking is True
        assert config.observability.cost_tracking is True


class TestPreScreeningConfig:
    """Test pre-screening configuration values."""

    def test_pre_screening_section_values(self):
        config = get_config()
        assert config.pre_screening.enabled is True
        assert config.pre_screening.embedding_model == "mistral/mistral-embed"
        assert config.pre_screening.bm25_min_score == 0.0
        assert config.pre_screening.bm25_min_overlap_ratio == 0.05
        assert config.pre_screening.embedding_cache_size == 512


class TestAgentConfigExtended:
    """Test agent configuration values in detail."""

    def test_agent_section_values(self):
        config = get_config()
        assert config.agent.enabled is True
        assert config.agent.max_tool_rounds == 5
        assert config.agent.tool_timeout == 30.0
        assert config.agent.continue_on_tool_error is True


class TestRAGConfigDetail:
    """Test RAG configuration sub-sections in detail."""

    def test_rag_chunking_config(self):
        config = get_config()
        assert config.rag.chunking.strategy == "recursive"
        assert config.rag.chunking.chunk_size == 1000
        assert config.rag.chunking.chunk_overlap == 200
        assert config.rag.chunking.contextual_headers is True
        assert config.rag.chunking.dedup_enabled is False

    def test_rag_chunking_markdown_config(self):
        config = get_config()
        assert config.rag.chunking.markdown.split_headers == ["h1", "h2", "h3"]
        assert config.rag.chunking.markdown.preserve_structure is True
        assert config.rag.chunking.markdown.max_chunk_fallback is True

    def test_rag_chunking_code_config(self):
        config = get_config()
        assert config.rag.chunking.code.language == "python"
        assert config.rag.chunking.code.split_by == "function"

    def test_rag_search_config(self):
        config = get_config()
        assert config.rag.search.mode == "vector"
        assert config.rag.search.n_results_default == 5
        assert config.rag.search.hybrid_alpha == 0.6
        assert config.rag.search.rerank is False
        assert config.rag.search.query_expansion is False
        assert config.rag.search.query_expansion_variations == 3
        assert config.rag.search.summary_boost == 1.5

    def test_rag_hierarchical_config(self):
        config = get_config()
        assert config.rag.hierarchical.enabled is False
        assert config.rag.hierarchical.parent_context is True
        assert config.rag.hierarchical.parent_chunk_size == 1500
        assert config.rag.hierarchical.levels == 2

    def test_rag_base_config(self):
        config = get_config()
        assert config.rag.embedding_model == "mistral/mistral-embed"
        assert config.rag.collection_name == "plico_kb"
        assert config.rag.local_embeddings is False
        assert config.rag.embedding_cache_size == 256
        assert config.rag.generate_summaries is False


class TestWorkbookConfigDetail:
    """Test workbook configuration sub-sections."""

    def test_workbook_defaults(self):
        config = get_config()
        assert config.workbook.defaults.model == "mistral-small-2503"
        assert config.workbook.defaults.api_key_env == "MISTRALSMALL_KEY"
        assert config.workbook.defaults.max_retries == 3
        assert config.workbook.defaults.temperature == 0.8
        assert config.workbook.defaults.max_tokens == 32000

    def test_workbook_batch_config(self):
        config = get_config()
        assert config.workbook.batch.mode == "per_row"
        assert config.workbook.batch.output == "combined"
        assert config.workbook.batch.on_error == "continue"

    def test_workbook_formatting_config(self):
        config = get_config()
        assert config.workbook.formatting.features.freeze_panes == {"enabled": True, "rows": 1}
        assert config.workbook.formatting.features.auto_filter == {
            "enabled": True,
            "all_sheets": True,
        }
        assert config.workbook.formatting.rows["auto_fit_height"] is True
        assert config.workbook.formatting.rows["wrap_text_height_multiplier"] == 15

    def test_workbook_sheet_names(self):
        config = get_config()
        assert config.workbook.sheet_names.config == "config"
        assert config.workbook.sheet_names.prompts == "prompts"
        assert config.workbook.sheet_names.data == "data"
        assert config.workbook.sheet_names.clients == "clients"
        assert config.workbook.sheet_names.documents == "documents"


class TestDocumentProcessorConfig:
    """Test document processor configuration."""

    def test_text_extensions_count(self):
        config = get_config()
        assert len(config.document_processor.text_extensions) == 32

    def test_text_extensions_contains_key_types(self):
        config = get_config()
        ext = config.document_processor.text_extensions
        assert ".py" in ext
        assert ".md" in ext
        assert ".json" in ext
        assert ".yaml" in ext
        assert ".csv" in ext
        assert ".txt" in ext


class TestOrchestratorConfigDetail:
    """Test orchestrator abort config."""

    def test_abort_config(self):
        config = get_config()
        assert config.orchestrator.abort.response_default == "-1"


class TestClientsConfigMethods:
    """Test ClientsConfig active methods."""

    def test_get_client_type_returns_config(self):
        from src.config import ClientsConfig, ClientTypeConfig

        cc = ClientsConfig(
            client_types={
                "custom": ClientTypeConfig(
                    client_class="FFCustom",
                    type="native",
                    api_key_env="CUSTOM_KEY",
                    provider_prefix="custom/",
                    default_model="custom-v1",
                )
            }
        )
        result = cc.get_client_type("custom")
        assert result is not None
        assert result.default_model == "custom-v1"
        assert result.provider_prefix == "custom/"

    def test_get_client_type_returns_none_for_missing(self):
        from src.config import ClientsConfig

        cc = ClientsConfig()
        assert cc.get_client_type("missing") is None

    def test_get_available_client_types_returns_keys(self):
        from src.config import ClientsConfig, ClientTypeConfig

        cc = ClientsConfig(
            client_types={
                "alpha": ClientTypeConfig(default_model="a"),
                "beta": ClientTypeConfig(default_model="b"),
            }
        )
        names = cc.get_available_client_types()
        assert names == ["alpha", "beta"]


class TestConfigGetYamlHelpers:
    """Test _find_config_dir fallback and _load_yaml_file missing file."""

    def test_find_config_dir_finds_project_config(self):
        from src.config import _find_config_dir

        result = _find_config_dir()
        assert result.name == "config"
        assert result.exists()
        assert (result / "main.yaml").exists()

    def test_load_yaml_file_missing_returns_empty(self, tmp_path, monkeypatch):
        from src.config import _load_yaml_file

        monkeypatch.chdir(tmp_path)
        result = _load_yaml_file("does_not_exist.yaml")
        assert result == {}


class TestConfigModelDefaults:
    """Test model_defaults specific model overrides."""

    def test_model_defaults_contains_known_models(self):
        config = get_config()
        models = config.model_defaults.models
        assert "azure/mistral-small-2503" in models
        assert models["azure/mistral-small-2503"]["max_tokens"] == 40000
        assert models["azure/codestral"]["temperature"] == 0.3

    def test_model_defaults_generic_values(self):
        config = get_config()
        generic = config.model_defaults.generic
        assert generic["max_tokens"] == 4096
        assert generic["temperature"] == 0.7


class TestConfigSampleWorkbook:
    """Test sample workbook configuration details."""

    def test_sample_workbook_paths(self):
        config = get_config()
        assert config.sample.workbooks.basic == "./sample_workbook.xlsx"
        assert config.sample.workbooks.multiclient == "./sample_workbook_multiclient.xlsx"
        assert config.sample.workbooks.conditional == "./sample_workbook_conditional.xlsx"

    def test_sample_client_configs(self):
        config = get_config()
        assert "default" in config.sample.sample_clients
        default_client = config.sample.sample_clients["default"]
        assert default_client.model == "mistral-small-latest"
        assert default_client.temperature == 0.7
        assert default_client.max_tokens == 300

        fast_client = config.sample.sample_clients["fast"]
        assert fast_client.temperature == 0.3
        assert fast_client.max_tokens == 100


class TestConfigValidateAgentField:
    """Test _validate_agent_field model validator."""

    def test_agent_field_coerced_from_non_dict(self):
        config = Config(agent="invalid_string")
        assert isinstance(config.agent, type(config.agent))
        assert config.agent.enabled is True

    def test_agent_field_kept_as_dict(self):
        config = Config(agent={"enabled": False, "max_tool_rounds": 3})
        assert config.agent.enabled is False
        assert config.agent.max_tool_rounds == 3


class TestConfigLoggingRotation:
    """Test logging rotation sub-config."""

    def test_rotation_defaults(self):
        from src.config import LoggingRotationConfig

        r = LoggingRotationConfig()
        assert r.when == "midnight"
        assert r.interval == 1
        assert r.backup_count == 10

    def test_logging_rotation_via_config(self):
        config = get_config()
        assert config.logging.rotation.when == "midnight"
        assert config.logging.rotation.interval == 1
        assert config.logging.rotation.backup_count == 10
