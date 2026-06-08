"""Frontier model adapter with capability-ordered escalation.

The advisor is the intelligence-ceiling escalation primitive: a leaf dispatch
that reaches a tier more capable than the caller. The top tier is the local
``claude`` CLI (Opus via OAuth / flat-rate Claude Max) — invoked leaf-only (no
tools, no MCP, single shot) so we extract model-grade intelligence from the
agent binary without granting it agency. Below it, OpenAI via HTTP API is an
availability fallback.

Top tier (claude_cli):
  Requires the ``claude`` CLI on PATH, authenticated via OAuth. No API key.

Fallback tier (openai):
  OPENAI_API_KEY    — OpenAI API key
  OPENAI_BASE_URL   — default: https://api.openai.com (override for proxies)

With mcp-vault, the OpenAI key becomes a vault: reference in the mcp.json env
block, resolved transparently at process spawn.
"""

import asyncio
import json
import logging
import os
import shutil
import time

import httpx

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are being consulted as a frontier advisory model by a local AI system "
    "that handles most tasks independently. You are called only when the local "
    "model has determined it needs capabilities beyond its own. "
    "Be direct, substantive, and efficient with tokens. "
    "Do not repeat the question back. Do not pad with caveats. "
    "The local model is technically competent -- treat it as a peer."
)

# API-only output cap. Applies to the OpenAI HTTP tier; the claude CLI tier
# does not take a max-tokens argument.
MAX_TOKENS = 4096

# Capability-ordered escalation, top tier first. The top tier is Claude/Opus
# reached via the local `claude` CLI (OAuth / flat-rate); OpenAI/GPT-4.1 via
# HTTP API is an availability fallback below it -- a lower tier, not a sibling.
MODEL_PREFERENCE = [
    ("claude_cli", "opus"),
    ("openai", "gpt-4.1"),
]

# Timeout for the claude CLI subprocess. Cold start is ~12s; 180s absorbs it.
CLAUDE_CLI_TIMEOUT = 180

PROVIDER_CONFIG = {
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "env_base_url": "OPENAI_BASE_URL",
        "default_base_url": "https://api.openai.com",
    },
}


class FrontierAdapter:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=120.0)

    def _get_provider_config(self, provider: str) -> dict | None:
        """Resolve provider availability.

        claude_cli is binary-presence based (no API key); openai is key-based.
        """
        if provider == "claude_cli":
            binary = shutil.which("claude")
            if not binary:
                return None
            return {"binary": binary}

        cfg = PROVIDER_CONFIG.get(provider)
        if not cfg:
            return None
        api_key = os.environ.get(cfg["env_key"])
        if not api_key:
            return None
        return {
            "api_key": api_key,
            "base_url": os.environ.get(cfg["env_base_url"], cfg["default_base_url"]),
        }

    async def consult(
        self,
        question: str,
        context: str = "",
        system_prompt: str | None = None,
    ) -> dict:
        """Send question to frontier model with provider fallback.

        Tries each tier in escalation order until one succeeds.
        Returns dict with response, provider, model, token counts, latency.
        Raises RuntimeError if all tiers fail.
        """
        sys_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        last_error = None

        for provider, model_id in MODEL_PREFERENCE:
            creds = self._get_provider_config(provider)
            if not creds:
                continue
            try:
                start = time.monotonic()
                result = await self._call(
                    provider, model_id, question, context,
                    MAX_TOKENS, sys_prompt, creds,
                )
                latency = int((time.monotonic() - start) * 1000)
                return {
                    "response": result["text"],
                    "provider": provider,
                    "model": model_id,
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                    "latency_ms": latency,
                }
            except Exception as e:
                logger.warning("Provider %s/%s failed: %s", provider, model_id, e)
                last_error = e

        if last_error is not None:
            raise RuntimeError(f"All configured providers failed. Last error: {last_error}")
        raise RuntimeError(
            "No advisory tier available. The top tier is the local `claude` CLI "
            "(OAuth / flat-rate) -- ensure `claude` is on PATH and authenticated. "
            "For the OpenAI fallback tier, set OPENAI_API_KEY in the environment."
        )

    async def _call(self, provider, model, q, ctx, max_tok, sys_prompt, creds):
        if provider == "claude_cli":
            return await self._claude_cli(model, q, ctx, max_tok, sys_prompt, creds)
        return await self._openai(model, q, ctx, max_tok, sys_prompt, creds)

    async def _claude_cli(self, model, q, ctx, max_tok, sys_prompt, creds):
        user_content = q
        if ctx:
            user_content = (
                f"<advisory_context>\n{ctx}\n</advisory_context>\n\n"
                f"<advisory_question>\n{q}\n</advisory_question>"
            )

        # Leaf-only invariant: the advisor invokes a more-capable agent and must
        # keep it model-shaped -- no tools, no MCP, no recursion. --disallowedTools
        # "*" strips tools; --strict-mcp-config with NO --mcp-config gives zero MCP
        # servers, so the spawned `claude` cannot re-enter frontier-advisor or load
        # pi-subagents. (max_tok / MAX_TOKENS is API-only and does NOT apply here.)
        args = [
            creds["binary"],
            "-p", user_content,
            "--model", model,
            "--output-format", "json",
            "--system-prompt", sys_prompt,
            "--disallowedTools", "*",
            "--strict-mcp-config",
        ]

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=CLAUDE_CLI_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"claude CLI timed out after {CLAUDE_CLI_TIMEOUT}s")

        if proc.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited with code {proc.returncode}: "
                f"{stderr.decode(errors='replace').strip()}"
            )

        parsed = json.loads(stdout)
        # --output-format json returns a JSON ARRAY of event objects; find the
        # result event. Defensively handle a dict envelope (use it directly if it
        # carries a "result" key).
        if isinstance(parsed, dict):
            result_event = parsed if "result" in parsed else None
        else:
            result_event = next(
                (e for e in parsed
                 if isinstance(e, dict) and e.get("type") == "result"),
                None,
            )

        if result_event is None:
            raise RuntimeError("claude CLI returned no result event")
        if result_event.get("is_error"):
            raise RuntimeError("claude CLI reported is_error in the result event")
        if result_event.get("subtype") != "success":
            raise RuntimeError(
                f"claude CLI result subtype was {result_event.get('subtype')!r}, "
                "expected 'success'"
            )

        usage = result_event.get("usage") or {}
        return {
            "text": result_event["result"],
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        }

    async def _openai(self, model, q, ctx, max_tok, sys_prompt, creds):
        headers = {
            "Authorization": f"Bearer {creds['api_key']}",
            "Content-Type": "application/json",
        }
        msgs = [{"role": "system", "content": sys_prompt}]
        user_content = f"Context:\n{ctx}\n\nQuestion:\n{q}" if ctx else q
        msgs.append({"role": "user", "content": user_content})
        body = {
            "model": model,
            "max_tokens": max_tok,
            "messages": msgs,
        }
        resp = await self._client.post(
            f"{creds['base_url']}/v1/chat/completions", headers=headers, json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "text": data["choices"][0]["message"]["content"],
            "input_tokens": data["usage"]["prompt_tokens"],
            "output_tokens": data["usage"]["completion_tokens"],
        }
