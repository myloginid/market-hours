#!/usr/bin/env bash
# Build a standalone app and install exactly one copy under ~/Applications.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VENV="${ROOT}/.market-hours-venv/bin/python"
DEST="${HOME}/Applications/Market Hours.app"

if [[ ! -x "${ROOT}/.market-hours-venv/bin/python" ]]; then
  echo "Missing .market-hours-venv — create it first (see README)." >&2
  exit 1
fi

pkill -x "Market Hours" 2>/dev/null || true
"$VENV" setup_market_hours.py py2app

ditto "${ROOT}/dist/Market Hours.app" "${DEST}"
rm -rf "${ROOT}/dist/Market Hours.app"

echo "Installed: ${DEST}"
echo "Open once from Applications (not from the project folder)."
open "${DEST}"