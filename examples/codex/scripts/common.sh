#!/usr/bin/env bash
set -euo pipefail

LAB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$LAB_ROOT"

require_dependencies() {
  if ! command -v python3 >/dev/null 2>&1; then
    printf 'Python 3 is required. Run: brew install python\n' >&2
    exit 1
  fi
  if ! command -v codex >/dev/null 2>&1; then
    printf 'Codex CLI is required. Run: npm install -g @openai/codex\n' >&2
    exit 1
  fi
}

load_mcp_token() {
  local value
  value="${REFERENCE_BROWSER_TOKEN:-}"
  if [[ -z "$value" ]]; then
    printf 'Paste the MCP API key (hidden; not stored): '
    IFS= read -r -s value || { printf '\nNo token provided.\n' >&2; exit 1; }
    printf '\n'
  fi
  # The value from an Authorization header begins with "Bearer "; Codex expects only the raw token.
  if [[ "$value" == 'Bearer '* ]]; then
    value="${value#Bearer }"
  fi
  if [[ -z "$value" || "$value" =~ [[:space:]] ]]; then
    printf 'Invalid token; expected the raw token or "Bearer <token>".\n' >&2
    exit 1
  fi
  export REFERENCE_BROWSER_TOKEN="$value"
}

REFERENCE_BROWSER_ORIGIN="${REFERENCE_BROWSER_ORIGIN:-http://127.0.0.1:8000}"
REFERENCE_BROWSER_ORIGIN="${REFERENCE_BROWSER_ORIGIN%/}"
export REFERENCE_BROWSER_ORIGIN

# Explicit flags avoid relying on project trust or overwriting global Codex configuration.
# No approval prompts, while retaining the filesystem sandbox and no direct shell network.
CODEX_FLAGS=(
  --ask-for-approval never
  --sandbox workspace-write
  --config 'sandbox_workspace_write.network_access=false'
  --config "mcp_servers.reference_browser.url=\"${REFERENCE_BROWSER_ORIGIN}/mcp\""
  --config 'mcp_servers.reference_browser.bearer_token_env_var="REFERENCE_BROWSER_TOKEN"'
  --config 'mcp_servers.reference_browser.required=true'
  --config 'mcp_servers.reference_browser.startup_timeout_sec=45'
  --config 'mcp_servers.reference_browser.tool_timeout_sec=120'
  --config 'mcp_servers.reference_browser.default_tools_approval_mode="approve"'
  --config 'mcp_servers.reference_browser.enabled_tools=["list_reference_sources","start_reference_research","get_research_status","inspect_reference","record_visual_review","finalize_reference_research","get_research_board","get_research_report"]'
)

connection_check() {
  printf 'Checking browser MCP (a sleeping hosted service may take a minute)...\n'
  python3 scripts/mcp_smoke.py --quiet
}
