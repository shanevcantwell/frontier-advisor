#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────
#  frontier-advisor installer
# ─────────────────────────────────────────────

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_NAME="mcp/frontier-advisor"

bold="\033[1m"
dim="\033[2m"
cyan="\033[36m"
yellow="\033[33m"
green="\033[32m"
reset="\033[0m"

banner() {
  echo ""
  echo -e "${bold}  ┌─────────────────────────────────────────┐${reset}"
  echo -e "${bold}  │       frontier-advisor  setup             │${reset}"
  echo -e "${bold}  └─────────────────────────────────────────┘${reset}"
  echo ""
}

menu() {
  echo -e "  ${cyan}1)${reset}  Docker                 ${dim}(claude CLI / OAuth, recommended)${reset}"
  echo -e "  ${cyan}2)${reset}  Docker MCP Toolkit     ${dim}(gateway + mcp.json)${reset}"
  echo ""
  echo -ne "  ${bold}Pick an option [1/2]:${reset} "
}

build_image() {
  echo ""
  echo -e "  ${dim}Building Docker image (bundles the claude CLI)...${reset}"
  docker build -t "$IMAGE_NAME" "$REPO_DIR" --quiet > /dev/null
  echo -e "  ${green}✓${reset} Image built: ${bold}${IMAGE_NAME}${reset}"
}

# ── Shared: claude CLI OAuth prerequisite ────

check_claude_auth() {
  echo ""
  echo -e "  ${bold}Top tier: local ${cyan}claude${reset}${bold} CLI (Opus via OAuth / flat-rate Claude Max)${reset}"
  echo ""
  if [ -f "$HOME/.claude/.credentials.json" ]; then
    echo -e "  ${green}✓${reset} Found OAuth credentials at ${dim}~/.claude/.credentials.json${reset}"
  else
    echo -e "  ${yellow}!${reset} No ~/.claude/.credentials.json found."
    echo -e "    Authenticate the CLI once on the host, then re-run if needed:"
    echo -e "      ${dim}claude${reset}   ${dim}# sign in via OAuth, then exit${reset}"
    echo -e "    The container mounts ~/.claude read-only — no API key is baked or needed."
  fi
}

prompt_openai_optional() {
  echo ""
  echo -e "  ${bold}Optional: OpenAI fallback tier (GPT-4.1)${reset}"
  echo -e "  ${dim}Used only when the claude CLI tier is unavailable. Press Enter to skip.${reset}"
  echo -ne "  OPENAI_API_KEY (Enter to skip): "
  read -rs openai_key
  echo ""
  if [ -n "$openai_key" ]; then
    OPENAI_LINE=$'\n        "-e", "OPENAI_API_KEY='"$openai_key"$'",'
    echo -e "  ${green}✓${reset} OpenAI fallback enabled (key will be inlined in the snippet below)"
    echo -e "  ${dim}Prefer not to inline it? Use mcp-vault: \"OPENAI_API_KEY=vault:openai/api-key\".${reset}"
  else
    OPENAI_LINE=""
    echo -e "  ${dim}Skipped — top tier (claude CLI) only.${reset}"
  fi
}

print_config_snippet() {
  echo ""
  echo -e "  ${bold}Add this to your MCP client config (mcp.json):${reset}"
  echo ""
  echo '    "frontier-advisor": {'
  echo '      "command": "docker",'
  echo '      "args": ['
  echo '        "run", "-i", "--rm",'
  echo '        "-v", "${HOME}/.claude:/home/advisor/.claude:ro",'"$OPENAI_LINE"
  echo '        "mcp/frontier-advisor"'
  echo '      ]'
  echo '    }'
  echo ""
  echo -e "  ${dim}The read-only ~/.claude mount supplies OAuth creds at runtime —${reset}"
  echo -e "  ${dim}nothing is baked into the image. (Base config also in mcp.json.example.)${reset}"
}

# ── Option 1: Docker ─────────────────────────

install_docker() {
  build_image
  check_claude_auth
  prompt_openai_optional
  print_config_snippet
}

# ── Option 2: Docker MCP Toolkit ─────────────

install_toolkit() {
  build_image
  check_claude_auth

  echo ""
  if ! docker mcp version > /dev/null 2>&1; then
    echo -e "  ${yellow}✗${reset} Docker MCP plugin not found."
    echo -e "    Update Docker Desktop to 4.62+ and enable MCP Toolkit."
    exit 1
  fi

  # Create catalog (ignore if exists)
  docker mcp catalog create "$IMAGE_NAME" 2>/dev/null || true

  docker mcp catalog add "$IMAGE_NAME" "$IMAGE_NAME" \
    "$REPO_DIR/docker-mcp-catalog.yaml" --force > /dev/null

  docker mcp server enable "$IMAGE_NAME" 2>/dev/null || true

  echo -e "  ${green}✓${reset} Registered in MCP Toolkit (tools visible via gateway)"
  echo ""
  echo -e "  ${dim}Note: Custom catalog servers don't yet appear in the Desktop UI.${reset}"
  echo -e "  ${dim}Tools are routed through the gateway to connected clients.${reset}"

  prompt_openai_optional
  print_config_snippet

  echo ""
  echo -e "  ${bold}Then connect a client:${reset}"
  echo -e "    ${dim}docker mcp client connect claude${reset}"
  echo -e "    ${dim}docker mcp client connect cursor${reset}"
}

# ── Main ─────────────────────────────────────

banner
menu
read -r choice

case "$choice" in
  1) install_docker ;;
  2) install_toolkit ;;
  *)
    echo -e "\n  ${yellow}!${reset} Invalid choice. Run this script again."
    exit 1
    ;;
esac

echo ""
echo -e "  ${green}Done.${reset} See README.md for usage details."
echo ""
