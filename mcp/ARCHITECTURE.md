# frontier-advisor

## What It Is

An MCP server that gives a local model a **tool for consulting frontier AI**. The local model decides *when* to escalate. The scaffold decides *whether* to allow it. The server routes the request and returns the result.

This is the infrastructure for a **90:10 local-to-frontier ratio**.

## What Exists Today (March 2026)

| Approach | What It Does | Gap |
|---|---|---|
| **LiteLLM Proxy** | Routes ALL inference through gateway with budget tracking | Not local-first. Proxy for everything, not selective escalation. |
| **codev consult script** | Thin CLI wrapper, Claude Code calls Gemini | No governance. Acknowledged as unsafe. |
| **MCP + Ollama** | Local models using MCP tools for file/search | Tools extend the model -- none consult a smarter model. |
| **PAL Model Bridge** | MCP server connecting models to each other | No sovereign framing. Context-heavy. |

**The gap**: No MCP tool for stateless advisory consultation with provider fallback.

## Architecture

```
Local Model (qwen3-30b on local HW)
  -> decides it needs help
  -> MCP tool call: consult_advisor(question, context)
  -> frontier-advisor MCP server
    -> provider fallback (claude CLI / OAuth -> OpenAI)
  -> Frontier model (system prompt: treat local model as peer)
  -> response + metadata returned to local model
```

Access control (how often, how much) is the scaffold's responsibility — not the MCP server's. The server is stateless: it routes and returns.

## Tool Exposed

| Tool | Purpose |
|---|---|
| consult_advisor | Ask frontier model a question with optional context and system prompt override |

## Model Preference

The server tries providers in order, using the first available:

| Priority | Provider | Reached via | Model |
|---|---|---|---|
| 1 | Anthropic | local `claude` CLI (OAuth / flat-rate) | Claude Opus |
| 2 | OpenAI | HTTP API (`OPENAI_API_KEY`) | GPT-4.1 |

No tiers, no budgets. One model preference list, provider fallback. The scaffold controls access policy.

The top tier shells out to the `claude` CLI **leaf-only** (`--disallowedTools "*"`,
`--strict-mcp-config` with no MCP config) — a single shot with no tools and no MCP, so
the advisor extracts model-grade intelligence from the agent binary without granting it
agency or letting it re-enter frontier-advisor.

## Credentials

The two tiers are provisioned differently:

| Tier | Requirement |
|---|---|
| `claude_cli` (top) | The `claude` CLI on PATH, authenticated via **OAuth** (flat-rate Claude Max). No API key. The CLI reads creds from `$HOME/.claude/.credentials.json`. |
| `openai` (fallback) | `OPENAI_API_KEY` in the environment (optional — only needed for the fallback tier). |
| — | `OPENAI_BASE_URL` (optional) — default `https://api.openai.com`, override for proxies. |

### Docker: no baked secrets

The image bundles only the `claude` CLI binary — **no API key or OAuth credential is
baked** into any layer (`ARG`/`ENV`/`COPY`). At `docker run` time the host's OAuth creds
are supplied via a **read-only volume mount** of `~/.claude` into the container's
`$HOME/.claude` (`/home/advisor/.claude`):

```
docker run -i --rm \
  -v "$HOME/.claude:/home/advisor/.claude:ro" \
  mcp/frontier-advisor
```

The optional OpenAI fallback key, if used, is passed as `-e OPENAI_API_KEY=...`. For an
OS-keychain-backed alternative for that single key, see
[mcp-vault](https://github.com/shanevcantwell/mcp-vault) — its `vault:` references resolve
`OPENAI_API_KEY` from the credential store at process spawn (the Anthropic tier needs no
key, so mcp-vault is no longer required for it).

## Connection to LAS

Natural fit as an MCP tool for GraphOrchestrator. Specialists call consult_advisor directly via MCP (MCP = System Calls in LAS — bypasses Router). The scaffold controls access by deciding whether to expose the tool to a given specialist.

## Dependencies

```
pip install mcp httpx
```

No frameworks, no orchestration libraries, no database. Single package, stdio. The top
tier additionally requires the `claude` CLI (npm `@anthropic-ai/claude-code`) on PATH;
the Docker image bundles it.

### Host-side dev / tests

For running the tests locally, use a project virtualenv rather than
`pip install --break-system-packages` (which mutates the system interpreter and is
brittle):

```
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
