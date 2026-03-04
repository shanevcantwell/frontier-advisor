# frontier-advisor-mcp

MCP server that gives local models a tool for consulting frontier AI APIs. The local model decides when to escalate. The scaffold controls access. The server routes, logs, and returns.

See [ARCHITECTURE.md](ARCHITECTURE.md) for design rationale.

## Tools

| Tool | Purpose |
|---|---|
| `consult_frontier` | Ask a frontier model a question (quick/standard/deep tiers) |
| `advisory_history` | Review recent consultations to avoid re-asking |
| `describe_advisory_tiers` | List available tiers and their costs |

## Setup

### Environment Variables

| Variable | Required | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | At least one provider | — |
| `OPENAI_API_KEY` | At least one provider | — |
| `ANTHROPIC_BASE_URL` | No | `https://api.anthropic.com` |
| `OPENAI_BASE_URL` | No | `https://api.openai.com` |

### Install from source

```bash
pip install -e .
frontier-advisor
```

### Docker

```bash
docker build -t frontier-advisor .
```

## MCP Client Configuration

### Direct (env vars)

```json
{
  "mcpServers": {
    "frontier-advisor": {
      "command": "frontier-advisor",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

### Docker

```json
{
  "mcpServers": {
    "frontier-advisor": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "ANTHROPIC_API_KEY=sk-ant-...",
        "frontier-advisor"
      ]
    }
  }
}
```

### With mcp-vault

```json
{
  "mcpServers": {
    "frontier-advisor": {
      "command": "mcp-vault",
      "args": [
        "--", "docker", "run", "-i", "--rm",
        "-e", "ANTHROPIC_API_KEY=vault:anthropic/api-key",
        "-e", "OPENAI_API_KEY=vault:openai/api-key",
        "frontier-advisor"
      ]
    }
  }
}
```

Store credentials once:
```bash
mcp-vault store anthropic/api-key
mcp-vault store openai/api-key
```

## Advisory Tiers

| Tier | Use Case | Max Tokens | Models |
|---|---|---|---|
| quick | Factual verification, syntax | 512 | Haiku 4.5, GPT-4.1-mini |
| standard | Complex reasoning | 2048 | Sonnet 4.5, GPT-4.1 |
| deep | Architecture, novel synthesis | 4096 | Opus 4.6, o3 |

The local model picks the tier. The server picks the provider (first available in the tier's preference list, with fallback).

## Development

```bash
pip install -e ".[dev]"
pytest
```
