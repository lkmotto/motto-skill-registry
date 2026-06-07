#!/usr/bin/env bash
# Idempotent one-shot agent standup: installs Factory skills + required CLIs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing Factory skills"
bash "$SCRIPT_DIR/install.sh"

have() { command -v "$1" >/dev/null 2>&1; }

pip_cmd() {
  if have pip3; then echo "pip3";
  elif have pip; then echo "pip";
  elif have python3; then echo "python3 -m pip";
  else echo ""; fi
}

echo
echo "==> Ensuring required CLIs (idempotent)"

# scrapfly-sdk (Python library; no standalone binary)
if python3 -c "import scrapfly" >/dev/null 2>&1; then
  echo "  - scrapfly-sdk already present, skipping"
else
  PIP="$(pip_cmd)"
  if [ -z "$PIP" ]; then
    echo "  ! python/pip not found; cannot install scrapfly-sdk" >&2
  else
    echo "  - installing scrapfly-sdk"
    if ! $PIP install scrapfly-sdk >/dev/null 2>&1; then
      # Fallback for PEP 668 externally-managed environments
      $PIP install --break-system-packages scrapfly-sdk >/dev/null 2>&1 || \
        echo "  ! scrapfly-sdk install failed" >&2
    fi
  fi
fi

# wrangler (Cloudflare)
if have wrangler; then
  echo "  - wrangler already present, skipping"
else
  echo "  - installing wrangler"
  npm i -g wrangler >/dev/null 2>&1 || echo "  ! wrangler install failed" >&2
fi

# vercel
if have vercel; then
  echo "  - vercel already present, skipping"
else
  echo "  - installing vercel"
  npm i -g vercel >/dev/null 2>&1 || echo "  ! vercel install failed" >&2
fi

echo
echo "==> Readiness summary"
SKILLS_DIR="$HOME/.factory/skills"
SKILL_COUNT=0
if [ -d "$SKILLS_DIR" ]; then
  SKILL_COUNT="$(find "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')"
fi
echo "  skills installed: $SKILL_COUNT (in $SKILLS_DIR)"

scrapfly_ver="$(python3 -c "import scrapfly; print(getattr(scrapfly,'__version__','installed'))" 2>/dev/null || echo "NOT INSTALLED")"
echo "  scrapfly-sdk: $scrapfly_ver"
echo "  wrangler:     $(have wrangler && wrangler --version 2>/dev/null || echo 'NOT INSTALLED')"
echo "  vercel:       $(have vercel && vercel --version 2>/dev/null || echo 'NOT INSTALLED')"

echo
echo "Standup complete."
