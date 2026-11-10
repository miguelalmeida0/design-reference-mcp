#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
require_dependencies
load_mcp_token
connection_check
printf '\nCodex is ready. Type /mcp to inspect the tools.\n'
exec codex "${CODEX_FLAGS[@]}" "${@}"
