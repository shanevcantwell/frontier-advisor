# frontier-advisor

Infrastructure for a **90:10 local-to-frontier ratio**. Gives local models a governed tool for consulting frontier AI — the intelligence-ceiling escalation primitive of the agent system.

The local model decides *when* to escalate. The scaffold decides *whether* to allow it. The server routes and returns.

The advisor is a leaf dispatch (mechanically "down"/out in the call tree) that reaches a tier *more capable than the caller itself* — *call down to delegate up*. The top tier is the local `claude` CLI (Opus via OAuth / flat-rate Claude Max), invoked leaf-only (no tools, no MCP, single shot) so we get the ceiling's intelligence without its agency. Below it, OpenAI GPT-4.1 via HTTP API is an availability fallback.

---

## MCP Server

The stdio MCP server is the mechanism by which the orchestrator reaches the primitive:

```bash
cd mcp
pip install -e .
```

**How it works:**

```
LLM calls consult_advisor(question, context?)
  → MCP stdio transport
  → tries the local `claude` CLI (Opus, OAuth) first
  → falls back to OpenAI GPT-4.1 (API key) if the CLI is unavailable
  → JSON-RPC result returned to LLM
```

See [mcp/README.md](mcp/README.md) for details.

---

## Tool

| Tool | Purpose |
|---|---|
| `consult_advisor` | Ask a frontier model a question (Claude/Opus via the local CLI primary, GPT-4.1 fallback) |

Parameters: `question` (required), `context` (optional), `system_prompt` (optional override).

---

## Credentials

| Tier | Requirement |
|---|---|
| `claude_cli` (top) | The `claude` CLI on PATH (npm `@anthropic-ai/claude-code`), authenticated via OAuth. No API key. |
| `openai` (fallback) | `OPENAI_API_KEY` set in the environment (optional — only for the fallback tier). |
| — | `OPENAI_BASE_URL` (optional) — default `https://api.openai.com`, override for proxies. |

### Docker: no baked secrets, creds mounted at runtime

The image bundles only the `claude` CLI binary — no API key or OAuth credential is baked
into any layer. At runtime the host's OAuth creds are supplied via a read-only mount of
`~/.claude` into the container (the CLI reads `$HOME/.claude/.credentials.json`):

```bash
docker run -i --rm \
  -v "$HOME/.claude:/home/advisor/.claude:ro" \
  mcp/frontier-advisor
```

Authenticate the `claude` CLI once on the host first (run `claude`, sign in via OAuth). Add
`-e OPENAI_API_KEY=...` to enable the optional fallback. See [mcp/README.md](mcp/README.md)
for the full install flow.

---

## Design

See [mcp/ARCHITECTURE.md](mcp/ARCHITECTURE.md) for the gap analysis, connection to LAS, and rationale.
