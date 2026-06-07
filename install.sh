#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MOTTO_SKILLS_HOME="${MOTTO_SKILLS_HOME:-$SCRIPT_DIR}"
SOURCE_SKILLS_DIR="$MOTTO_SKILLS_HOME/skills"
TARGET_SKILLS_DIR="$HOME/.factory/skills"
TARGET_TOOLS_PATH="$HOME/motto-skills/tools/"

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
done

echo "Installed skills into: $TARGET_SKILLS_DIR"
echo "Required CLIs to install if missing:"
echo "  - scrapfly (https://scrapfly.io/docs/sdk/python)"
echo "  - wrangler (npm i -g wrangler)"
echo "  - vercel (npm i -g vercel)"
