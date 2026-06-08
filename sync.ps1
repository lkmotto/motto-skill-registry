# synck.ps1 — Cross-machine knowledge sync via git
# Pushes learned knowledge to the motto-skills repo so other machines can pull it.
#
# Usage:
#   .\sync.ps1 push          Copy local knowledge into repo, commit, push
#   .\sync.ps1 pull          Pull latest repo, merge knowledge into local
#   .\sync.ps1 auto          Push if local has changes; useful for hooks

param(
  [Parameter(Position=0)]
  [ValidateSet("push", "pull", "auto")]
  [string]$Direction = "auto"
)

$ErrorActionPreference = "Stop"
$REPO_PATH = "$env:USERPROFILE\motto-skills"
$KNOWLEDGE_REPO = "$REPO_PATH\knowledge"
$KNOWLEDGE_LOCAL = "$env:USERPROFILE\.factory\knowledge"

# Shared mergeable files (JSON arrays keyed by id/domain+key — union, don't overwrite)
$MERGEABLE_FILES = @(
  "facts.json",
  "error-patterns.json",
  "workflows.json",
  "capability-gaps.json",
  "credential-health.json"
)

# Append-only files (JSONL — concatenate unique entries by id)
$APPEND_FILES = @("decisions.jsonl")

# Overwrite-only files (single state — use latest timestamp)
$OVERWRITE_FILES = @(
  "autonomy-policy.json",
  "drift-probes.json"
)

function Merge-JsonArrays($repoFile, $localFile) {
  # Union two JSON files that contain array properties keyed by id
  if (-not (Test-Path $repoFile)) { return Get-Content $localFile -Raw }
  if (-not (Test-Path $localFile)) { return Get-Content $repoFile -Raw }
  
  try {
    $repo = Get-Content $repoFile -Raw | ConvertFrom-Json
    $local = Get-Content $localFile -Raw | ConvertFrom-Json
    
    # For each array property, merge by id
    $result = $local | ConvertTo-Json -Depth 10 | ConvertFrom-Json
    $repoProps = $repo.PSObject.Properties
    $localProps = $local.PSObject.Properties
    
    foreach ($prop in $repoProps) {
      $name = $prop.Name
      if ($name -eq "version") { continue }
      
      $repoVal = $prop.Value
      $localVal = $local.$name
      
      if ($repoVal -is [array] -and $localVal -is [array]) {
        $localIds = @{}
        foreach ($item in $localVal) {
          $id = if ($item.id) { $item.id } elseif ($item.signature) { $item.signature } else { $item.name }
          if ($id) { $localIds[$id] = $true }
        }
        foreach ($item in $repoVal) {
          $id = if ($item.id) { $item.id } elseif ($item.signature) { $item.signature } else { $item.name }
          if ($id -and -not $localIds.ContainsKey($id)) {
            $localVal += $item
            $localIds[$id] = $true
          }
        }
        $result.$name = $localVal
      }
    }
    
    return ($result | ConvertTo-Json -Depth 10)
  } catch {
    Write-Warning "Merge failed for $localFile — using local copy"
    return Get-Content $localFile -Raw
  }
}

function Merge-Jsonl($repoFile, $localFile) {
  # Concatenate both JSONL files, dedupe by entry id
  if (-not (Test-Path $repoFile) -and -not (Test-Path $localFile)) { return "" }
  
  $seen = @{}
  $lines = @()
  
  if (Test-Path $repoFile) {
    foreach ($line in (Get-Content $repoFile)) {
      if ($line.Trim() -eq "") { continue }
      try { $obj = $line | ConvertFrom-Json } catch { $lines += $line; continue }
      $id = if ($obj.id) { $obj.id } else { $line }
      if (-not $seen.ContainsKey($id)) { $seen[$id] = $true; $lines += $line }
    }
  }
  if (Test-Path $localFile) {
    foreach ($line in (Get-Content $localFile)) {
      if ($line.Trim() -eq "") { continue }
      try { $obj = $line | ConvertFrom-Json } catch { $lines += $line; continue }
      $id = if ($obj.id) { $obj.id } else { $line }
      if (-not $seen.ContainsKey($id)) { $seen[$id] = $true; $lines += $line }
    }
  }
  
  return ($lines -join "`n")
}

function Push-Knowledge {
  Write-Host "Pushing local knowledge to repo..."
  
  # 1. Pull latest first to avoid conflicts
  Set-Location $REPO_PATH
  git pull --rebase 2>$null
  
  # 2. Copy local knowledge files into repo
  foreach ($file in $MERGEABLE_FILES) {
    Copy-Item -Force "$KNOWLEDGE_LOCAL\$file" "$KNOWLEDGE_REPO\$file"
  }
  foreach ($file in $APPEND_FILES) {
    $merged = Merge-Jsonl "$KNOWLEDGE_REPO\$file" "$KNOWLEDGE_LOCAL\$file"
    if ($merged) { Set-Content -Path "$KNOWLEDGE_REPO\$file" -Value $merged -NoNewline }
  }
  foreach ($file in $OVERWRITE_FILES) {
    if (Test-Path "$KNOWLEDGE_LOCAL\$file") {
      Copy-Item -Force "$KNOWLEDGE_LOCAL\$file" "$KNOWLEDGE_REPO\$file"
    }
  }
  
  # 3. Commit and push if changes
  Set-Location $REPO_PATH
  git add knowledge/
  $status = git status --porcelain knowledge/
  if ($status) {
    $hostname = hostname
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    git commit -m "sync($hostname): knowledge push at $timestamp"
    git push
    Write-Host "Pushed knowledge from $hostname"
  } else {
    Write-Host "No knowledge changes to push"
  }
}

function Pull-Knowledge {
  Write-Host "Pulling shared knowledge from repo..."
  
  # 1. Pull latest
  Set-Location $REPO_PATH
  git pull --rebase
  
  # 2. Merge repo knowledge into local
  foreach ($file in $MERGEABLE_FILES) {
    if (Test-Path "$KNOWLEDGE_REPO\$file") {
      $merged = Merge-JsonArrays "$KNOWLEDGE_REPO\$file" "$KNOWLEDGE_LOCAL\$file"
      if ($merged) { Set-Content -Path "$KNOWLEDGE_LOCAL\$file" -Value $merged }
    }
  }
  foreach ($file in $APPEND_FILES) {
    $merged = Merge-Jsonl "$KNOWLEDGE_REPO\$file" "$KNOWLEDGE_LOCAL\$file"
    if ($merged) { Set-Content -Path "$KNOWLEDGE_LOCAL\$file" -Value $merged -NoNewline }
  }
  foreach ($file in $OVERWRITE_FILES) {
    # Only overwrite if repo file is newer
    if ((Test-Path "$KNOWLEDGE_REPO\$file") -and (Test-Path "$KNOWLEDGE_LOCAL\$file")) {
      $repoTime = (Get-Item "$KNOWLEDGE_REPO\$file").LastWriteTime
      $localTime = (Get-Item "$KNOWLEDGE_LOCAL\$file").LastWriteTime
      if ($repoTime -gt $localTime) {
        Copy-Item -Force "$KNOWLEDGE_REPO\$file" "$KNOWLEDGE_LOCAL\$file"
        Write-Host "  Updated $file (repo newer)"
      }
    } elseif (Test-Path "$KNOWLEDGE_REPO\$file") {
      Copy-Item -Force "$KNOWLEDGE_REPO\$file" "$KNOWLEDGE_LOCAL\$file"
      Write-Host "  Created $file from repo"
    }
  }
  
  Write-Host "Knowledge pulled from repo"
}

# --- Main ---
if ($Direction -eq "push") {
  Push-Knowledge
} elseif ($Direction -eq "pull") {
  Pull-Knowledge
} elseif ($Direction -eq "auto") {
  # Pull first to get any remote changes, then push local changes
  Pull-Knowledge
  Push-Knowledge
}
