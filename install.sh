#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MOTTO_SKILLS_HOME="${MOTTO_SKILLS_HOME:-$SCRIPT_DIR}"
SOURCE_SKILLS_DIR="$MOTTO_SKILLS_HOME/skills"
TARGET_SKILLS_DIR="$HOME/.factory/skills"
TARGET_KNOWLEDGE_DIR="$HOME/.factory/knowledge"
TARGET_POLICY_FILE="$HOME/.factory/skill-broker.policy.json"
TARGET_TOOLS_PATH="$HOME/motto-skills/tools/"

echo "=== motto-skills installer ==="

# --- Skills ---
echo "Installing skills..."
mkdir -p "$TARGET_SKILLS_DIR"

for skill_dir in "$SOURCE_SKILLS_DIR"/*; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  dest_dir="$TARGET_SKILLS_DIR/$skill_name"
  mkdir -p "$dest_dir"
  cp -a "$skill_dir"/. "$dest_dir"/

  skill_md="$dest_dir/SKILL.md"
  if [ -f "$skill_md" ]; then
    sed -i "s|C:\\\\Users\\\\lkmot\\\\tools\\\\|$TARGET_TOOLS_PATH|g" "$skill_md"
    sed -i 's|\$MOTTO_SKILLS_HOME/tools/|'"$TARGET_TOOLS_PATH"'|g' "$skill_md"
  fi
  echo "  + $skill_name"
done

# --- Knowledge Store ---
echo "Installing knowledge store..."
mkdir -p "$TARGET_KNOWLEDGE_DIR"
mkdir -p "$TARGET_KNOWLEDGE_DIR/postmortems"
mkdir -p "$TARGET_KNOWLEDGE_DIR/skill-proposals"

if [ -d "$MOTTO_SKILLS_HOME/knowledge" ]; then
  for kfile in "$MOTTO_SKILLS_HOME/knowledge"/*.json "$MOTTO_SKILLS_HOME/knowledge"/*.jsonl; do
    [ -f "$kfile" ] || continue
    kname="$(basename "$kfile")"
    if [ ! -f "$TARGET_KNOWLEDGE_DIR/$kname" ]; then
      cp "$kfile" "$TARGET_KNOWLEDGE_DIR/$kname"
      echo "  + knowledge/$kname (bootstrap)"
    else
      echo "  ~ knowledge/$kname (already exists, skipped)"
    fi
  done
fi

# --- Skill Broker Policy ---
echo "Installing skill-broker policy..."
if [ -f "$MOTTO_SKILLS_HOME/policy/skill-broker.policy.json" ]; then
  if [ ! -f "$TARGET_POLICY_FILE" ]; then
    cp "$MOTTO_SKILLS_HOME/policy/skill-broker.policy.json" "$TARGET_POLICY_FILE"
    echo "  + skill-broker.policy.json (fresh)"
  else
    echo "  ~ skill-broker.policy.json (already exists, skipped — merge manually if needed)"
  fi
fi

echo ""
echo "=== Done ==="
echo "Skills installed into: $TARGET_SKILLS_DIR"
echo "Knowledge store at:   $TARGET_KNOWLEDGE_DIR"
echo ""
echo "Required CLIs to install if missing:"
echo "  - scrapfly (https://scrapfly.io/docs/sdk/python)"
echo "  - wrangler (npm i -g wrangler)"
echo "  - vercel (npm i -g vercel)"
echo "  - smithery (npm i -g @smithery/cli)"
echo "  - doppler (https://docs.doppler.com/docs/install-cli)"
