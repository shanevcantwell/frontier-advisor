# ADR-001: mcp-vault — Transparent Credential Proxy for MCP Servers

**Status:** Proposed
**Date:** 2026-03-03
**Author:** Shane
**Deciders:** Shane (sole maintainer)

---

## Context

### The Problem

MCP server configurations require credentials (API keys, PATs, database passwords) stored as plaintext in `mcp.json`. This file is routinely shared in troubleshooting contexts — Discord help channels, Reddit posts, GitHub issues — where the user's attention is on their actual problem, not on scrubbing secrets from config they're pasting.

This is not a theoretical risk. It happened today: a GitHub PAT was shared in a conversation while troubleshooting MCP server setup. The user was focused on architecture, not credential hygiene. The secret was in the file because there was no alternative.

### The Ecosystem Failure

The problem has been recognized for over a year. None of the responses have gained traction:

- **MCP spec (2025-03-26):** Added OAuth 2.1 authorization for HTTP-transport servers. Stdio servers — which is what LM Studio, Claude Desktop, and most local setups use — are explicitly out of scope. One year later, no client has implemented even the HTTP auth.
- **Enterprise vault solutions (Infisical, Doppler, HashiCorp Vault):** Every "best practices" blog post recommends these. No one running local models on consumer hardware is going to deploy a secrets management platform for their mcp.json.
- **mcp-secrets-plugin (52 stars, 3 commits):** Uses Python `keyring` to read from OS credential store. Requires each server author to import the library and call `get_secret()`. Fatal flaw: depends on server-side adoption that will never reach critical mass across hundreds of community MCP servers.
- **MCP servers issue #754 (March 2025):** Proposed credential management best practices. Read like a compliance checklist. Nothing shipped.
- **Wrapper/launcher scripts:** Individual developers writing one-off PowerShell or bash scripts to inject secrets at launch. Works but not shareable, not discoverable, not standardized.

### The Market Signal

The MCP spec added auth support. The ecosystem looked at it and collectively moved on. In a year where model capabilities doubled multiple times over, credential management remained "just put it in env." This is not a gap waiting to be filled by a better spec proposal. The market has rejected the top-down approach. The solution has to work bottom-up — from the user's immediate pain — without requiring cooperation from MCP clients, server authors, or the protocol spec.

### The Constraint: "Can Handle mcp.json and No More"

The target user can set up LM Studio, configure MCP servers via mcp.json, run Docker containers, and troubleshoot tool-calling issues. They are not comfortable with: setting up development environments, managing dotenv patterns, understanding OAuth implementation details, or running infrastructure services. The solution must be operable by this user with no more complexity than editing mcp.json.

---

## Decision

Build **mcp-vault**: a single cross-platform binary that sits at the process spawn boundary between MCP clients and MCP servers, transparently resolving credential references from the OS-native secret store before launching the upstream server.

### Core Design Principle

**The spawn boundary is the universal intervention point.** Every MCP client — LM Studio, Claude Desktop, Cursor, VS Code — spawns server processes via the `command` + `args` fields in mcp.json. mcp-vault inserts itself at this point. It requires zero changes from MCP clients, zero changes from server authors, and zero changes to the MCP protocol.

### How It Works

Current (insecure):
```json
"webfetch": {
  "command": "node",
  "args": ["server.mjs"],
  "env": {
    "API_KEY": "sk-1234567890abcdef"
  }
}
```

With mcp-vault (secure):
```json
"webfetch": {
  "command": "mcp-vault",
  "args": ["--", "node", "server.mjs"],
  "env": {
    "API_KEY": "vault:webfetch/api-key"
  }
}
```

At launch:
1. mcp-vault scans its own environment for values prefixed with `vault:`
2. Each reference is resolved from the OS credential store (Windows Credential Manager / macOS Keychain / Linux libsecret)
3. Resolved values replace the references in the environment
4. mcp-vault spawns the command specified after `--`, with stdio piped through
5. mcp-vault is invisible to both the MCP client and the server

### Docker Support

Many MCP servers run as Docker containers where secrets appear in `-e` flags inside the `args` array, not in the `env` block:

```json
"github": {
  "command": "mcp-vault",
  "args": ["--", "docker", "run", "-i", "--rm",
           "-e", "GITHUB_TOKEN=vault:github/pat",
           "ghcr.io/github/github-mcp-server"]
}
```

mcp-vault scans both the environment block AND the args array for `vault:` references, resolving them before passing the final args to the child process. This handles the Docker `-e KEY=value` pattern without requiring restructuring of existing configurations.

### Credential Storage

One-time, per credential:
```
mcp-vault store webfetch/api-key
> Enter secret value: ****
> Stored in Windows Credential Manager as 'mcp-vault:webfetch/api-key'
```

The naming convention `service/purpose` is a suggestion, not enforced. The user can use whatever names make sense to them.

### Migration

```
mcp-vault import mcp.json
> Found 4 potential secrets:
>   env.GITHUB_PERSONAL_ACCESS_TOKEN in 'github' -> store as github/pat? [Y/n]
>   env.SEARXNG_BASE in 'webfetch' -> skip (not a secret) [y/N]
>   args[4] contains 'github_pat_...' in 'desktop-commander' -> store as desktop-commander/github-pat? [Y/n]
>   ...
> Stored 3 secrets. Updated mcp.json. Original backed up as mcp.json.bak
```

Detection heuristics: values matching patterns for known token formats (github_pat_*, sk-*, ghp_*, etc.), env var names containing TOKEN, KEY, SECRET, PASSWORD, PAT, CREDENTIAL. The user confirms each one. Non-secrets (like SEARXNG_BASE URLs) are skipped by default.

---

## Killer Features for Adoption

### 1. The Screenshot Test
After migration, mcp.json is safe to paste anywhere — help forums, screenshots, chat conversations, GitHub issues. This is the feature users *feel*. Not "improved security posture." Just: sharing config for help no longer risks leaking credentials.

### 2. Less Work Than Plaintext
Store once, reference everywhere. When GitHub forces a PAT rotation, update one credential:
```
mcp-vault store github/pat
```
Every server entry referencing `vault:github/pat` picks it up on next launch. No find-and-replace across config files.

### 3. Machine Migration
```
mcp-vault export > secrets-manifest.txt
```
Produces a list of credential *names* (not values), which serves as a checklist when setting up a new machine. The user re-creates each credential on the new machine. The mcp.json copies over unchanged because it only contains references.

### 4. Audit
```
mcp-vault list
> github/pat              -> used by: github, desktop-commander
> webfetch/api-key        -> used by: webfetch
> brave/api-key           -> used by: webfetch
> Last accessed: github/pat at 2026-03-03T14:22:00
```

### 5. Doctor
```
mcp-vault doctor mcp.json
> ! 'desktop-commander' has plaintext secret in args[4] (matches github_pat_* pattern)
> ! 'github' has plaintext secret in env.GITHUB_PERSONAL_ACCESS_TOKEN
> ok 'webfetch' — all credentials use vault references
> ok 'memory' — no credentials detected
```

Runnable as a pre-commit hook, a periodic check, or just when the user wonders "did I clean everything up?"

---

## Future-Proofing

### Pluggable Backends

v1 uses the OS-native credential store exclusively. The architecture supports future backends without changing the user-facing `vault:` reference format:

- **1Password CLI** (`op://vault/item/field`) — for users already in the 1Password ecosystem
- **Bitwarden CLI** — same pattern
- **KeePassXC** — via its CLI or socket interface, common among privacy-focused local-first users
- **Cloud KMS** (AWS SSM, Azure Key Vault) — for the rare local user who also has cloud infra

Backend selection via config file or env var:
```
MCP_VAULT_BACKEND=1password  # or: keychain (default), bitwarden, keepassxc
```

The `vault:` prefix in mcp.json stays the same regardless of backend. The user can switch backends without touching any server configuration.

### Credential Rotation

Because secrets are referenced by name, rotation is atomic:
```
mcp-vault store github/pat    # overwrites the existing value
```
Next server launch picks up the new value. No config file edits. No process restarts needed beyond the normal MCP server lifecycle (servers are spawned per-session anyway).

Future: `mcp-vault rotate github/pat --provider github` could automate the full cycle — revoke old PAT, generate new one via GitHub API, store it — but this is v2+ scope and requires OAuth integration with each provider. The manual store-and-replace path covers the immediate need.

### Composability with mcp-throttle

mcp-vault and mcp-throttle (the rate-limiting proxy from the same design session) compose naturally:

```json
"webfetch": {
  "command": "mcp-vault",
  "args": ["--", "mcp-throttle"],
  "env": {
    "UPSTREAM_COMMAND": "node",
    "UPSTREAM_ARGS": "server.mjs",
    "API_KEY": "vault:webfetch/api-key",
    "THROTTLE_WEB_FETCH": "6/30"
  }
}
```

mcp-vault resolves credentials, then launches mcp-throttle, which handles rate limiting and launches the actual server. Layered infrastructure concerns, each handled by a focused tool, all invisible to the model.

### When MCP Clients Eventually Support Auth

If LM Studio or another client eventually adds native credential management, mcp-vault doesn't break — it just becomes unnecessary for that client. The `vault:` references in env values would pass through unresolved (since the client would handle auth differently), so the migration path off mcp-vault is also clean. The user removes `mcp-vault` from the command chain and uses whatever native mechanism the client provides. No lock-in.

---

## Implementation

### Language: Rust or Go

Single static binary, no runtime dependencies. The user downloads one file, puts it on PATH, done. No Python, no Node, no pip install. This is non-negotiable for the target audience.

Rust advantages: better Windows credential store bindings (windows-credentials crate), smaller binary. Go advantages: faster to prototype, easier for community contributors. Either works.

### OS Credential Store Access

| Platform | Store | API/Crate |
|----------|-------|-----------|
| Windows | Credential Manager | `windows-credentials` (Rust) / `wincred` (Go) |
| macOS | Keychain | `security-framework` (Rust) / `go-keychain` (Go) |
| Linux | libsecret (GNOME Keyring / KWallet) | `libsecret` bindings |

All three platforms have mature, well-tested bindings. This is solved infrastructure.

### Credential Naming

Stored as: `mcp-vault:{user-chosen-name}`
Example: `mcp-vault:github/pat`

The `mcp-vault:` prefix namespaces credentials to avoid collision with other applications using the same OS store. The remainder is opaque to mcp-vault — the user picks whatever naming scheme works for them.

### Stdio Passthrough

mcp-vault must be transparent to the MCP JSON-RPC protocol flowing over stdio between client and server. Implementation: pipe child process stdin/stdout directly to parent stdin/stdout. No parsing, no buffering, no modification. mcp-vault's only job after launch is keeping the pipes connected until the child exits.

### Error Handling

- **Missing credential:** Print clear error to stderr and exit non-zero. The MCP client will see the server failed to start. Example: `mcp-vault: credential 'github/pat' not found in Windows Credential Manager. Run: mcp-vault store github/pat`
- **Locked keychain (macOS):** User gets the standard OS prompt to unlock. mcp-vault waits.
- **No vault: prefix found:** mcp-vault passes through as a pure process wrapper. This means a user can adopt mcp-vault in their command chain before migrating any secrets — it's a no-op until they start adding references.

---

## Adoption Strategy

### Phase 1: Ship and Self-Use
Build the binary, use it on the author's own setup, shake out edge cases with real MCP server configurations (Desktop Commander, Docker containers, webfetch, memory, etc.).

### Phase 2: The Post
Write the PSA post for r/LocalLLaMA. Not "here's a security tool" but "I accidentally shared my GitHub PAT while asking for MCP help, here's the two-minute fix." Same format and subreddit as the Qwen3.5 parser post. Include the screenshot of a clean mcp.json. Show the `mcp-vault import` one-liner.

### Phase 3: Doctor as Gateway
`mcp-vault doctor mcp.json` is useful even without adopting vault references — it tells you where your exposed secrets are. This is the low-commitment entry point. "Just run doctor on your config and see what it finds." Once the user sees the warnings, the migration path is obvious.

### Phase 4: Community Templates
Publish example mcp.json configurations for popular servers (GitHub, filesystem, memory, webfetch) with vault references pre-configured. New users copy a template that's secure by default. The plaintext-PAT pattern stops being the first thing people encounter.

---

## Consequences

### Positive
- Config files become safe to share in any context
- Single-credential updates propagate to all servers that reference them
- Zero changes required from MCP clients, server authors, or the protocol
- Works with every existing MCP server and every MCP client that uses mcp.json
- No lock-in: removing mcp-vault from the chain restores direct server launch
- Composable with other spawn-boundary tools (mcp-throttle, future middleware)

### Negative
- Adds one process hop to the server launch chain (negligible latency, but one more thing that can fail)
- OS credential store requires the user session to be unlocked (not suitable for headless/CI — but that's not the target audience)
- First-time setup requires one `mcp-vault store` per credential (lower friction than the alternative, but not zero)
- On Linux, libsecret requires a running D-Bus session and a keyring daemon — this may not be present on minimal server distros (again, not the target audience)

### Risks
- If the binary isn't trivially easy to install (single download, no dependencies), adoption fails regardless of the design
- If `mcp-vault import` heuristics produce too many false positives (flagging non-secrets as secrets), users will distrust the tool
- If stdio passthrough introduces any observable latency or protocol errors, the tool is dead on arrival

---

## What Sells It to the Cynical Dev

The dev who laughs about .env getting committed already knows secrets in plaintext are wrong. They don't need a lecture. They need the secure path to be *less friction* than the insecure one:

1. **`mcp-vault import mcp.json` is one command.** It finds the secrets, stores them, rewrites the config. Thirty seconds, done. The insecure alternative (copy PAT from GitHub settings, open JSON, find env block, paste, save, remember to never share) is more steps.

2. **No server patches.** mcp-secrets-plugin dies because it needs `from secrets_manager import get_secret` in server code. mcp-vault doesn't touch server code. The server sees `process.env.GITHUB_TOKEN` exactly like it always did.

3. **No infrastructure.** Infisical, Doppler, Vault — great products, wrong audience. mcp-vault uses the credential store the OS already provides and the user already trusts (it's where their browser passwords live).

4. **The before/after screenshot.** A config full of `vault:github/pat` references next to the same config with raw PATs. The visual is the argument.

---

## References

- MCP Authorization Spec (2025-03-26): HTTP-transport only, stdio explicitly out of scope
- mcp-secrets-plugin: github.com/amirshk/mcp-secrets-plugin (server-side approach, requires author adoption)
- MCP servers issue #754: Credential management proposal, no implementation
- Docker MCP Gateway issue #317: Credential env vars overwritten by gateway config
- Medium: "MCP configuration is a sh*tshow" — documents the user-side frustration
- Author's prior art: r/LocalLLaMA PSA on LM Studio parser breaking Qwen3.5 tool calling
