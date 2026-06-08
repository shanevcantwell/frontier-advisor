# frontier-advisor

MCP server that gives local models a tool for consulting frontier AI — the
intelligence-ceiling **escalation primitive** (`consult_advisor()`) of the agent system.
The local model decides when to escalate. The scaffold controls access. The server routes
and returns.

See [ARCHITECTURE.md](ARCHITECTURE.md) for design rationale.

## Tool

| Tool | Purpose |
|---|---|
| `consult_advisor` | Ask a frontier model a question (Claude/Opus via the local CLI primary, GPT-4.1 fallback) |

Parameters: `question` (required), `context` (optional), `system_prompt` (optional override).

## Advisory tiers

Capability-ordered escalation, top tier first:

1. **`claude_cli` (top tier)** — Claude/Opus reached through the local `claude` CLI
   (OAuth / flat-rate Claude Max). It is invoked **leaf-only** — no tools, no MCP, a
   single shot — so the advisor extracts model-grade intelligence from the agent
   binary without granting it agency. **Requires the `claude` CLI on PATH,
   authenticated via OAuth. No API key.**
2. **`openai` (fallback tier)** — GPT-4.1 via the HTTP API. Used only when the CLI tier
   is unavailable. Requires `OPENAI_API_KEY`.

## Quick Start

```bash
git clone https://github.com/shanevcantwell/frontier-advisor.git
cd frontier-advisor/mcp
bash install.sh        # Linux / macOS / Git Bash
install.bat            # Windows (cmd or PowerShell)
```

The installer builds the Docker image (bundling the `claude` CLI), checks your OAuth
credentials, and walks you through setup:

```
  ┌─────────────────────────────────────────┐
  │       frontier-advisor  setup             │
  └─────────────────────────────────────────┘

  1)  Docker                 (claude CLI / OAuth, recommended)
  2)  Docker MCP Toolkit     (gateway + mcp.json)

  Pick an option [1/2]:
```

**Option 1** runs the server as a plain `docker run` and prints the `mcp.json` snippet. The
top tier needs no API key — it uses the `claude` CLI authenticated via OAuth, supplied to
the container through a read-only mount of `~/.claude` (see below).

**Option 2** also registers the server in Docker Desktop's MCP gateway for tool routing via
`docker mcp client connect`.

Both options offer to enable the **optional** OpenAI fallback (`OPENAI_API_KEY`).

See [mcp.json.example](mcp.json.example) for the recommended client configuration.

### Credentials mount (top tier)

No API key or OAuth credential is ever baked into the image. The `claude` CLI inside the
container reads OAuth creds from `$HOME/.claude/.credentials.json`; the host's `~/.claude`
is mounted **read-only** at runtime:

```bash
docker run -i --rm \
  -v "$HOME/.claude:/home/advisor/.claude:ro" \
  mcp/frontier-advisor
```

Prerequisite: authenticate the `claude` CLI once on the host (run `claude` and sign in via
OAuth) so `~/.claude/.credentials.json` exists. To also enable the OpenAI fallback, add
`-e OPENAI_API_KEY=...` (or a `vault:openai/api-key` reference via
[mcp-vault](https://github.com/shanevcantwell/mcp-vault)).

### Manual install (no Docker)

Requires the `claude` CLI on PATH (npm `@anthropic-ai/claude-code`), authenticated via
OAuth, for the top tier.

```bash
pip install -e .
```

```json
{
  "mcpServers": {
    "frontier-advisor": {
      "command": "frontier-advisor"
    }
  }
}
```

The top tier needs no `env` block — it uses the `claude` CLI on PATH (OAuth). Add
`OPENAI_API_KEY` to `env` only if you want the OpenAI fallback tier.

## Requirements & Environment Variables

The top tier requires the **`claude` CLI on PATH, authenticated via OAuth** (run it once
interactively to sign in). No API key is needed for the top tier.

| Variable | Required | Default |
|---|---|---|
| `OPENAI_API_KEY` | Only for the OpenAI fallback tier | — |
| `OPENAI_BASE_URL` | No | `https://api.openai.com` |

## Development

Use a project virtualenv for host-side dev/tests — the non-brittle alternative to
`pip install --break-system-packages`, which mutates the system interpreter:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
