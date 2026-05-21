from src.Clients.model_defaults import get_model_defaults, register_model_defaults


class TestGetModelDefaults:
    def test_known_model_returns_copy(self):
        defaults = get_model_defaults("mistral-small-2503")
        assert isinstance(defaults, dict)
        assert "temperature" in defaults or "max_tokens" in defaults

    def test_returns_copy_not_reference(self):
        defaults = get_model_defaults("mistral-small-2503")
        defaults["temperature"] = 999
        fresh = get_model_defaults("mistral-small-2503")
        assert fresh.get("temperature") != 999

    def test_unknown_model_returns_generic(self):
        defaults = get_model_defaults("nonexistent-model-xyz")
        assert isinstance(defaults, dict)
        assert "temperature" in defaults
        assert "max_tokens" in defaults

    def test_provider_prefixed_model(self):
        defaults = get_model_defaults("azure/mistral-small-2503")
        assert isinstance(defaults, dict)
        assert "temperature" in defaults
        assert "max_tokens" in defaults


class TestRegisterModelDefaults:
    def test_register_custom_defaults(self):
        register_model_defaults("test-custom-model", {"temperature": 0.5})
        defaults = get_model_defaults("test-custom-model")
        assert defaults["temperature"] == 0.5

    def test_registered_overrides_generic(self):
        register_model_defaults("unique-override-test", {"max_tokens": 4096})
        defaults = get_model_defaults("unique-override-test")
        assert defaults["max_tokens"] == 4096
