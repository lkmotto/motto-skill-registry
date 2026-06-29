#!/usr/bin/env bash
# Hook script — called by Droid on SessionEnd to sync knowledge to the repo
set -euo pipefail

SYNC_SCRIPT="${HOME}/motto-skills/sync.sh"

if [ -f "$SYNC_SCRIPT" ]; then
  bash "$SYNC_SCRIPT" push 2>/dev/null || true
fi

# Always exit 0 — sync is a best-effort background task
exit 0
