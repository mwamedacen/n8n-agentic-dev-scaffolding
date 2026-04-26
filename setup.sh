#!/bin/bash
# =============================================================================
# n8n-harness setup wrapper
#
# `n8n-harness --setup` is the canonical interactive flow. This script exists
# only for users without `uv` on PATH: it installs the harness via pip and
# delegates to the Python `--setup` command.
#
# Usage:
#   bash setup.sh
# =============================================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v n8n-harness >/dev/null 2>&1; then
    echo "n8n-harness not on PATH; installing..."
    if command -v uv >/dev/null 2>&1; then
        uv tool install -e "$PROJECT_DIR"
    else
        python3 -m pip install --user -e "$PROJECT_DIR"
    fi
fi

exec n8n-harness --setup
