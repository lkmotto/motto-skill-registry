# motto-skills installer (PowerShell / Windows)
# Clones or refreshes skills + knowledge + hooks from the motto-skills repo.
#
# Usage:
#   .\install.ps1          Install everything (skips existing knowledge/policy)
#   .\install.ps1 -Force   Overwrite existing knowledge store and policy
param([switch]$Force)

$ErrorActionPreference = "Stop"
$MOTTO_SKILLS_HOME = if ($env:MOTTO_SKILLS_HOME) { $env:MOTTO_SKILLS_HOME } else { $PSScriptRoot }
$SOURCE_SKILLS_DIR = "$MOTTO_SKILLS_HOME\skills"
$TARGET_SKILLS_DIR = "$env:USERPROFILE\.factory\skills"
$TARGET_KNOWLEDGE_DIR = "$env:USERPROFILE\.factory\knowledge"
$TARGET_POLICY_FILE = "$env:USERPROFILE\.factory\skill-broker.policy.json"
$TARGET_HOOKS_FILE = "$env:USERPROFILE\.factory\hooks.json"
$TARGET_TOOLS_PATH = "$env:USERPROFILE\motto-skills\tools\"

Write-Host "=== motto-skills installer ==="

# --- Skills ---
Write-Host "Installing skills..."
New-Item -ItemType Directory -Force -Path $TARGET_SKILLS_DIR | Out-Null

Get-ChildItem -Path $SOURCE_SKILLS_DIR -Directory | ForEach-Object {
  $skillName = $_.Name
  $destDir = "$TARGET_SKILLS_DIR\$skillName"
  Copy-Item -Recurse -Force "$($_.FullName)" "$destDir"
  Write-Host "  + $skillName"
}

# --- Knowledge Store ---
Write-Host "Installing knowledge store..."
New-Item -ItemType Directory -Force -Path $TARGET_KNOWLEDGE_DIR | Out-Null
New-Item -ItemType Directory -Force -Path "$TARGET_KNOWLEDGE_DIR\postmortems" | Out-Null
New-Item -ItemType Directory -Force -Path "$TARGET_KNOWLEDGE_DIR\skill-proposals" | Out-Null

if (Test-Path "$MOTTO_SKILLS_HOME\knowledge") {
  Get-ChildItem -Path "$MOTTO_SKILLS_HOME\knowledge" -File | ForEach-Object {
    $destFile = "$TARGET_KNOWLEDGE_DIR\$($_.Name)"
    if (-not (Test-Path $destFile) -or $Force) {
      Copy-Item -Force $_.FullName $destFile
      Write-Host "  + knowledge/$($_.Name) (fresh)"
    } else {
      Write-Host "  ~ knowledge/$($_.Name) (already exists, skipped)"
    }
  }
}

# --- Skill Broker Policy ---
Write-Host "Installing skill-broker policy..."
if (Test-Path "$MOTTO_SKILLS_HOME\policy\skill-broker.policy.json") {
  if (-not (Test-Path $TARGET_POLICY_FILE) -or $Force) {
    Copy-Item -Force "$MOTTO_SKILLS_HOME\policy\skill-broker.policy.json" $TARGET_POLICY_FILE
    Write-Host "  + skill-broker.policy.json (fresh)"
  } else {
    Write-Host "  ~ skill-broker.policy.json (already exists, skipped - use -Force to overwrite)"
  }
}

# --- Auto-Sync Hooks ---
Write-Host "Installing knowledge sync hooks..."
if (Test-Path "$MOTTO_SKILLS_HOME\policy\hooks.json") {
  if (-not (Test-Path $TARGET_HOOKS_FILE) -or $Force) {
    Copy-Item -Force "$MOTTO_SKILLS_HOME\policy\hooks.json" $TARGET_HOOKS_FILE
    Write-Host "  + hooks.json (auto-sync on session start/end)"
  } else {
    Write-Host "  ~ hooks.json (already exists, skipped - use -Force to overwrite)"
  }
}

Write-Host ""
Write-Host "=== Done ==="
Write-Host "Skills installed into: $TARGET_SKILLS_DIR"
Write-Host "Knowledge store at:   $TARGET_KNOWLEDGE_DIR"
Write-Host "Hooks at:             $TARGET_HOOKS_FILE"
Write-Host ""
Write-Host "Cross-machine sync:"
Write-Host "  .\sync.ps1 auto      Auto-sync (push + pull)"
Write-Host "  .\sync.ps1 push      Push local knowledge to git"
Write-Host "  .\sync.ps1 pull      Pull shared knowledge from git"
Write-Host ""
Write-Host "Required CLIs to install if missing:"
Write-Host "  - scrapfly (https://scrapfly.io/docs/sdk/python)"
Write-Host "  - wrangler (npm i -g wrangler)"
Write-Host "  - vercel (npm i -g vercel)"
Write-Host "  - smithery (npm i -g @smithery/cli)"
Write-Host "  - doppler (https://docs.doppler.com/docs/install-cli)"
