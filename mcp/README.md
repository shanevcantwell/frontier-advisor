# frontier-advisor

MCP server that gives local models a tool for consulting frontier AI APIs. The local model decides when to escalate. The scaffold controls access. The server routes and returns.

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

The installer builds the Docker image and walks you through setup:

```
  ┌─────────────────────────────────────────┐
  │       frontier-advisor  setup             │
  └─────────────────────────────────────────┘

  1)  Docker + mcp-vault     (OS keychain, recommended)
  2)  Docker + env vars      (quick start)
  3)  Docker MCP Toolkit     (gateway + mcp.json)

  Pick an option [1/2/3]:
```

**Option 1** uses [mcp-vault](https://github.com/shanevcantwell/mcp-vault) to keep API keys in your OS credential store. Your `mcp.json` becomes safe to share, screenshot, or paste in help channels.

**Option 2** gets you running fast with env vars in `mcp.json`. Fine for trying it out, but consider option 1 for regular use.

**Option 3** registers the server in Docker Desktop's MCP gateway for tool routing via `docker mcp client connect`. API keys still go in `mcp.json` — custom catalog servers don't yet appear in the Desktop UI secrets panel.

See [mcp.json.example](mcp.json.example) for the recommended client configuration.

### Manual install (no Docker)

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

```bash
pip install -e ".[dev]"
pytest
```
