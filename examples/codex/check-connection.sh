#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/scripts/common.sh"
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Install Python 3 first: brew install python' >&2
  exit 1
fi
load_mcp_token
python3 scripts/mcp_smoke.py
