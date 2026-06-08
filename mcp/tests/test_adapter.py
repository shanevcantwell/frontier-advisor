"""Tests for FrontierAdapter."""

import json
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from frontier_advisor.adapter import (
    FrontierAdapter,
    MODEL_PREFERENCE,
    MAX_TOKENS,
    DEFAULT_SYSTEM_PROMPT,
    PROVIDER_CONFIG,
)


def _make_proc(stdout_bytes: bytes, returncode: int = 0):
    """Build a fake subprocess whose .communicate() yields (stdout, b"")."""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout_bytes, b""))
    proc.returncode = returncode
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=returncode)
    return proc


def _result_envelope(text="Advisory response.", input_tokens=10, output_tokens=8):
    """Canonical --output-format json envelope: a JSON ARRAY of event objects."""
    return json.dumps([
        {"type": "system", "subtype": "init", "tools": [], "mcp_servers": []},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": text,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        },
    ]).encode()


class TestAdapterConfig:
    def test_model_preference_not_empty(self):
        assert len(MODEL_PREFERENCE) > 0

    def test_model_preference_has_claude_cli(self):
        providers = [p for p, _ in MODEL_PREFERENCE]
        assert "claude_cli" in providers

    def test_model_preference_has_openai(self):
        providers = [p for p, _ in MODEL_PREFERENCE]
        assert "openai" in providers

    def test_claude_cli_is_top_tier(self):
        assert MODEL_PREFERENCE[0][0] == "claude_cli"

    def test_no_anthropic_http_provider(self):
        providers = [p for p, _ in MODEL_PREFERENCE]
        assert "anthropic" not in providers
        assert "anthropic" not in PROVIDER_CONFIG

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
    async def test_no_provider_raises_runtime_error(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = FrontierAdapter()
        # No claude CLI on PATH and no OpenAI key -> terminal error.
        with patch("frontier_advisor.adapter.shutil.which", return_value=None):
            with pytest.raises(
                RuntimeError,
                match=r"(All configured providers failed|No advisory tier available)",
            ):
                await adapter.consult(question="test")

    def test_get_provider_config_claude_cli_present(self):
        adapter = FrontierAdapter()
        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"):
            cfg = adapter._get_provider_config("claude_cli")
        assert cfg is not None
        assert cfg["binary"] == "/usr/bin/claude"

    def test_get_provider_config_claude_cli_absent(self):
        adapter = FrontierAdapter()
        with patch("frontier_advisor.adapter.shutil.which", return_value=None):
            assert adapter._get_provider_config("claude_cli") is None

    def test_get_provider_config_openai_missing_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = FrontierAdapter()
        assert adapter._get_provider_config("openai") is None

    def test_get_provider_config_openai_present_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        adapter = FrontierAdapter()
        cfg = adapter._get_provider_config("openai")
        assert cfg is not None
        assert cfg["api_key"] == "sk-test"
        assert "api.openai.com" in cfg["base_url"]

    def test_get_provider_config_unknown_provider(self, monkeypatch):
        """Test that unknown provider returns None."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        adapter = FrontierAdapter()
        assert adapter._get_provider_config("unknown_provider") is None
        assert adapter._get_provider_config("google") is None
        assert adapter._get_provider_config("") is None
        assert adapter._get_provider_config(None) is None

    def test_get_provider_config_custom_base_url(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:8080")
        adapter = FrontierAdapter()
        cfg = adapter._get_provider_config("openai")
        assert cfg["base_url"] == "http://localhost:8080"


class TestAdapterClaudeCli:
    """Tests for the claude CLI top tier (subprocess boundary mocked)."""

    @pytest.mark.asyncio
    async def test_claude_cli_success(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = FrontierAdapter()

        proc = _make_proc(_result_envelope(
            text="This is the advisory response.", input_tokens=10, output_tokens=8,
        ))

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec",
                   new=AsyncMock(return_value=proc)):
            result = await adapter.consult(question="What is 2+2?")

        assert result["response"] == "This is the advisory response."
        assert result["provider"] == "claude_cli"
        assert result["model"] == "opus"
        assert result["input_tokens"] == 10
        assert result["output_tokens"] == 8
        assert "latency_ms" in result
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_claude_cli_argv_and_context(self, monkeypatch):
        """Verify leaf-only argv and XML-wrapped context."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = FrontierAdapter()
        context = "The user is working on a Python project."
        question = "Should I use pytest or unittest?"

        proc = _make_proc(_result_envelope(text="Use pytest."))
        mock_exec = AsyncMock(return_value=proc)

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec", new=mock_exec):
            await adapter.consult(question=question, context=context)

        args = mock_exec.call_args.args
        argv = list(args)
        assert argv[0] == "/usr/bin/claude"
        # Leaf-only flags present
        assert "--disallowedTools" in argv
        assert argv[argv.index("--disallowedTools") + 1] == "*"
        assert "--strict-mcp-config" in argv
        assert "--mcp-config" not in argv  # no MCP config => no recursion
        assert "--output-format" in argv
        assert argv[argv.index("--output-format") + 1] == "json"
        assert "--model" in argv
        assert argv[argv.index("--model") + 1] == "opus"
        # Prompt carries XML-wrapped context
        prompt = argv[argv.index("-p") + 1]
        assert "<advisory_context>" in prompt
        assert "<advisory_question>" in prompt
        assert context in prompt
        assert question in prompt
        # System prompt routed to --system-prompt
        sys_prompt = argv[argv.index("--system-prompt") + 1]
        assert sys_prompt == DEFAULT_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_claude_cli_no_context_plain_question(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = FrontierAdapter()

        proc = _make_proc(_result_envelope())
        mock_exec = AsyncMock(return_value=proc)

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec", new=mock_exec):
            await adapter.consult(question="just the question")

        argv = list(mock_exec.call_args.args)
        prompt = argv[argv.index("-p") + 1]
        assert prompt == "just the question"
        assert "<advisory_context>" not in prompt

    @pytest.mark.asyncio
    async def test_claude_cli_dict_envelope_fallback(self, monkeypatch):
        """Defensive: a dict envelope with a result key is used directly."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = FrontierAdapter()

        envelope = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "dict-shaped response",
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }).encode()
        proc = _make_proc(envelope)

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec",
                   new=AsyncMock(return_value=proc)):
            result = await adapter.consult(question="test")

        assert result["response"] == "dict-shaped response"
        assert result["input_tokens"] == 3
        assert result["output_tokens"] == 4

    @pytest.mark.asyncio
    async def test_claude_cli_absent_falls_back_to_openai(self, monkeypatch, respx_mock):
        """which -> None: claude_cli tier skipped, OpenAI fallback used."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        adapter = FrontierAdapter()

        respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
            json={
                "choices": [{"message": {"content": "OpenAI fallback."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
            status_code=200,
        )

        with patch("frontier_advisor.adapter.shutil.which", return_value=None):
            result = await adapter.consult(question="test")

        assert result["provider"] == "openai"
        assert result["response"] == "OpenAI fallback."

    @pytest.mark.asyncio
    async def test_claude_cli_nonzero_exit_falls_back_to_openai(self, monkeypatch, respx_mock):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        adapter = FrontierAdapter()

        proc = _make_proc(b"", returncode=1)
        proc.communicate = AsyncMock(return_value=(b"", b"boom"))

        respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
            json={
                "choices": [{"message": {"content": "Fallback after CLI failure."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
            status_code=200,
        )

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec",
                   new=AsyncMock(return_value=proc)):
            result = await adapter.consult(question="test")

        assert result["provider"] == "openai"
        assert result["response"] == "Fallback after CLI failure."

    @pytest.mark.asyncio
    async def test_claude_cli_is_error_falls_back_to_openai(self, monkeypatch, respx_mock):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        adapter = FrontierAdapter()

        envelope = json.dumps([
            {
                "type": "result",
                "subtype": "error_during_execution",
                "is_error": True,
                "result": "",
                "usage": {"input_tokens": 1, "output_tokens": 0},
            }
        ]).encode()
        proc = _make_proc(envelope)

        respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
            json={
                "choices": [{"message": {"content": "Fallback after is_error."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
            status_code=200,
        )

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec",
                   new=AsyncMock(return_value=proc)):
            result = await adapter.consult(question="test")

        assert result["provider"] == "openai"
        assert result["response"] == "Fallback after is_error."

    @pytest.mark.asyncio
    async def test_claude_cli_timeout_kills_and_falls_back(self, monkeypatch, respx_mock):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        adapter = FrontierAdapter()

        proc = MagicMock()
        proc.communicate = AsyncMock(side_effect=TimeoutError())
        proc.kill = MagicMock()
        proc.wait = AsyncMock(return_value=-9)

        respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
            json={
                "choices": [{"message": {"content": "Fallback after timeout."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
            status_code=200,
        )

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec",
                   new=AsyncMock(return_value=proc)):
            result = await adapter.consult(question="test")

        proc.kill.assert_called_once()
        assert result["provider"] == "openai"
        assert result["response"] == "Fallback after timeout."


class TestAdapterOpenAI:
    """Tests for OpenAI provider integration."""

    @pytest.mark.asyncio
    async def test_openai_success(self, monkeypatch, respx_mock):
        """Test successful OpenAI API call."""
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")

        adapter = FrontierAdapter()

        mock_response = {
            "choices": [
                {
                    "message": {"content": "OpenAI advisory response."},
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 6},
        }
        respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
            json=mock_response, status_code=200
        )

        # No claude CLI -> OpenAI is the only available tier.
        with patch("frontier_advisor.adapter.shutil.which", return_value=None):
            result = await adapter.consult(question="What is the capital of France?")

        assert result["response"] == "OpenAI advisory response."
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4.1"
        assert result["input_tokens"] == 12
        assert result["output_tokens"] == 6
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_openai_with_context(self, monkeypatch, respx_mock):
        """Test OpenAI API call with context."""
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")

        adapter = FrontierAdapter()
        context = "Project uses React and TypeScript."
        question = "Should I use Redux or Zustand?"

        captured_body = None

        def respond_with_capture(request):
            nonlocal captured_body
            captured_body = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "Use Zustand."}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 3},
                }
            )

        route = respx_mock.post("https://api.openai.com/v1/chat/completions")
        route.side_effect = respond_with_capture

        with patch("frontier_advisor.adapter.shutil.which", return_value=None):
            await adapter.consult(question=question, context=context)

        # Verify system and user messages
        messages = captured_body["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert context in messages[1]["content"]
        assert question in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_openai_custom_base_url(self, monkeypatch, respx_mock):
        """Test OpenAI with custom base URL (e.g., local proxy)."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:8080")

        adapter = FrontierAdapter()

        mock_response = {
            "choices": [{"message": {"content": "Response from local proxy."}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
        }
        respx_mock.post("http://localhost:8080/v1/chat/completions").respond(
            json=mock_response, status_code=200
        )

        with patch("frontier_advisor.adapter.shutil.which", return_value=None):
            result = await adapter.consult(question="test")

        assert result["response"] == "Response from local proxy."
        assert result["provider"] == "openai"


class TestAdapterFallback:
    """Tests for tier fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_claude_cli_to_openai(self, monkeypatch, respx_mock):
        """Test fallback from claude CLI to OpenAI when the CLI fails."""
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")

        adapter = FrontierAdapter()

        proc = _make_proc(b"", returncode=1)
        proc.communicate = AsyncMock(return_value=(b"", b"err"))

        respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
            json={
                "choices": [{"message": {"content": "Fallback response."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
            status_code=200,
        )

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec",
                   new=AsyncMock(return_value=proc)):
            result = await adapter.consult(question="test")

        assert result["provider"] == "openai"
        assert result["response"] == "Fallback response."

    @pytest.mark.asyncio
    async def test_fallback_prefers_claude_cli(self, monkeypatch, respx_mock):
        """Test that claude CLI is tried first when both are available."""
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")

        adapter = FrontierAdapter()

        proc = _make_proc(_result_envelope(text="Claude response."))

        # OpenAI also configured but should NOT be used.
        respx_mock.post("https://api.openai.com/v1/chat/completions").respond(
            json={
                "choices": [{"message": {"content": "OpenAI response."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
            status_code=200,
        )

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec",
                   new=AsyncMock(return_value=proc)):
            result = await adapter.consult(question="test")

        assert result["provider"] == "claude_cli"
        assert result["response"] == "Claude response."

    @pytest.mark.asyncio
    async def test_custom_system_prompt(self, monkeypatch):
        """Test custom system prompt is routed to --system-prompt."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        adapter = FrontierAdapter()
        custom_prompt = "You are a helpful coding assistant."

        proc = _make_proc(_result_envelope())
        mock_exec = AsyncMock(return_value=proc)

        with patch("frontier_advisor.adapter.shutil.which", return_value="/usr/bin/claude"), \
             patch("frontier_advisor.adapter.asyncio.create_subprocess_exec", new=mock_exec):
            await adapter.consult(question="test", system_prompt=custom_prompt)

        argv = list(mock_exec.call_args.args)
        assert argv[argv.index("--system-prompt") + 1] == custom_prompt
