# Hook script — called by Droid on SessionEnd to sync knowledge to the repo
# Works on Windows (PowerShell). For Linux/Mac use sync-knowledge.sh
param()

$SYNC_SCRIPT = "$env:USERPROFILE\motto-skills\sync.ps1"

if (Test-Path $SYNC_SCRIPT) {
  & $SYNC_SCRIPT push *>&1 | Out-Null
}

# Always exit 0 — sync is a best-effort background task
exit 0
