#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
require_dependencies
load_mcp_token
connection_check
mkdir -p reports
printf '\nStarting a 28-reference live research test with no approval prompts.\n'
exec codex "${CODEX_FLAGS[@]}" exec \
  --output-last-message reports/codex-last-message.md \
  - < prompts/02-live-research.md
