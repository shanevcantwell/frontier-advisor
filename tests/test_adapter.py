"""Tests for FrontierAdapter."""

import pytest
from frontier_advisor.adapter import (
    FrontierAdapter,
    MODEL_PREFERENCE,
    MAX_TOKENS,
    DEFAULT_SYSTEM_PROMPT,
    PROVIDER_CONFIG,
)


class TestAdapterConfig:
    def test_model_preference_not_empty(self):
        assert len(MODEL_PREFERENCE) > 0

    def test_model_preference_has_anthropic(self):
        providers = [p for p, _ in MODEL_PREFERENCE]
        assert "anthropic" in providers

    def test_model_preference_has_openai(self):
        providers = [p for p, _ in MODEL_PREFERENCE]
        assert "openai" in providers

    def test_max_tokens_positive(self):
        assert MAX_TOKENS > 0

    def test_system_prompt_not_empty(self):
        assert len(DEFAULT_SYSTEM_PROMPT) > 0

    def test_provider_config_has_env_keys(self):
        for provider, cfg in PROVIDER_CONFIG.items():
            assert "env_key" in cfg
            assert "default_base_url" in cfg


class TestAdapterInit:
    def test_creates_http_client(self):
        adapter = FrontierAdapter()
        assert adapter._client is not None

    @pytest.mark.asyncio
    async def test_no_keys_raises_runtime_error(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = FrontierAdapter()
        with pytest.raises(RuntimeError, match="No provider available"):
            await adapter.consult(question="test")

    def test_get_provider_config_missing_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        adapter = FrontierAdapter()
        assert adapter._get_provider_config("anthropic") is None

    def test_get_provider_config_present_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        adapter = FrontierAdapter()
        cfg = adapter._get_provider_config("anthropic")
        assert cfg is not None
        assert cfg["api_key"] == "sk-test"
        assert "api.anthropic.com" in cfg["base_url"]

    def test_get_provider_config_custom_base_url(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:8080")
        adapter = FrontierAdapter()
        cfg = adapter._get_provider_config("openai")
        assert cfg["base_url"] == "http://localhost:8080"
