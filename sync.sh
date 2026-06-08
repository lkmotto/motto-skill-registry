#!/usr/bin/env bash
# synck.sh — Cross-machine knowledge sync via git
# Usage: bash sync.sh [push|pull|auto]
set -euo pipefail

DIRECTION="${1:-auto}"
REPO_PATH="${HOME}/motto-skills"
KNOWLEDGE_REPO="${REPO_PATH}/knowledge"
KNOWLEDGE_LOCAL="${HOME}/.factory/knowledge"

# Files that merge by id (JSON arrays — union)
MERGEABLE_FILES=(
  "facts.json"
  "error-patterns.json"
  "workflows.json"
  "capability-gaps.json"
  "credential-health.json"
)

# Files that append (JSONL — concat, dedupe by id)
APPEND_FILES=("decisions.jsonl")

# Files that overwrite (take latest timestamp)
OVERWRITE_FILES=(
  "autonomy-policy.json"
  "drift-probes.json"
)

push_knowledge() {
  echo "Pushing local knowledge to repo..."
  cd "$REPO_PATH"
  git pull --rebase origin main 2>/dev/null || true

  for f in "${MERGEABLE_FILES[@]}"; do
    cp -f "${KNOWLEDGE_LOCAL}/${f}" "${KNOWLEDGE_REPO}/${f}" 2>/dev/null || true
  done
  for f in "${APPEND_FILES[@]}"; do
    cat "${KNOWLEDGE_REPO}/${f}" "${KNOWLEDGE_LOCAL}/${f}" 2>/dev/null | sort -u > "${KNOWLEDGE_REPO}/${f}.tmp"
    mv "${KNOWLEDGE_REPO}/${f}.tmp" "${KNOWLEDGE_REPO}/${f}" 2>/dev/null || true
  done
  for f in "${OVERWRITE_FILES[@]}"; do
    cp -f "${KNOWLEDGE_LOCAL}/${f}" "${KNOWLEDGE_REPO}/${f}" 2>/dev/null || true
  done

  cd "$REPO_PATH"
  git add knowledge/
  if ! git diff --cached --quiet; then
    HOSTNAME=$(hostname)
    TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M UTC")
    git commit -m "sync(${HOSTNAME}): knowledge push at ${TIMESTAMP}"
    git push
    echo "Pushed knowledge from ${HOSTNAME}"
  else
    echo "No knowledge changes to push"
  fi
}

pull_knowledge() {
  echo "Pulling shared knowledge from repo..."
  cd "$REPO_PATH"
  git pull --rebase origin main

  for f in "${MERGEABLE_FILES[@]}"; do
    if [ -f "${KNOWLEDGE_REPO}/${f}" ]; then
      python3 -c "
import json, sys
repo = json.load(open('${KNOWLEDGE_REPO}/${f}'))
try:
    local = json.load(open('${KNOWLEDGE_LOCAL}/${f}'))
except:
    local = repo
for k, v in repo.items():
    if isinstance(v, list) and k in local and isinstance(local[k], list):
        ids = {i.get('id') or i.get('signature') or i.get('name'): True for i in local[k] if isinstance(i, dict)}
        for item in v:
            item_id = item.get('id') or item.get('signature') or item.get('name') if isinstance(item, dict) else None
            if item_id and item_id not in ids:
                local[k].append(item)
                ids[item_id] = True
    elif k not in local or k == 'version':
        local[k] = v
json.dump(local, open('${KNOWLEDGE_LOCAL}/${f}','w'), indent=2)
" 2>/dev/null || cp "${KNOWLEDGE_REPO}/${f}" "${KNOWLEDGE_LOCAL}/${f}"
    fi
  done

  for f in "${APPEND_FILES[@]}"; do
    if [ -f "${KNOWLEDGE_REPO}/${f}" ]; then
      cat "${KNOWLEDGE_REPO}/${f}" "${KNOWLEDGE_LOCAL}/${f}" 2>/dev/null | sort -u > "${KNOWLEDGE_LOCAL}/${f}.tmp"
      mv "${KNOWLEDGE_LOCAL}/${f}.tmp" "${KNOWLEDGE_LOCAL}/${f}" 2>/dev/null || true
    fi
  done

  for f in "${OVERWRITE_FILES[@]}"; do
    if [ -f "${KNOWLEDGE_REPO}/${f}" ] && [ -f "${KNOWLEDGE_LOCAL}/${f}" ]; then
      if [ "${KNOWLEDGE_REPO}/${f}" -nt "${KNOWLEDGE_LOCAL}/${f}" ]; then
        cp "${KNOWLEDGE_REPO}/${f}" "${KNOWLEDGE_LOCAL}/${f}"
        echo "  Updated ${f} (repo newer)"
      fi
    elif [ -f "${KNOWLEDGE_REPO}/${f}" ]; then
      cp "${KNOWLEDGE_REPO}/${f}" "${KNOWLEDGE_LOCAL}/${f}"
      echo "  Created ${f} from repo"
    fi
  done

  echo "Knowledge pulled from repo"
}

case "$DIRECTION" in
  push) push_knowledge ;;
  pull) pull_knowledge ;;
  auto) pull_knowledge; push_knowledge ;;
  *)   echo "Usage: bash sync.sh [push|pull|auto]"; exit 1 ;;
esac
