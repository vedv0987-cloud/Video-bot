#!/usr/bin/env bash
#
# Open the studio dashboard. Everything the terminal did, in a browser.
#
#   ./scripts/dashboard.sh

set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$REPO/.venv/bin/videobot-dashboard" ]; then
  # The venv predates the dashboard entry point. Reinstalling is idempotent and
  # takes seconds; building the venv from scratch is setup-mac.sh's job.
  if [ ! -x "$REPO/.venv/bin/pip" ]; then
    echo "No .venv yet — run ./scripts/setup-mac.sh first." >&2
    exit 1
  fi
  "$REPO/.venv/bin/pip" install -q -e "$REPO[dev]"
fi

exec "$REPO/.venv/bin/videobot-dashboard" --root "$REPO" "$@"
