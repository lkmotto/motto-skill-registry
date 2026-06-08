# mission-watcher.ps1 — Polls Cloudflare KV for pending missions and dispatches them
#
# Run continuously or via Task Scheduler every 60 seconds:
#   powershell -File mission-watcher.ps1
#
# Requirements:
#   - Cloudflare account with KV namespace for MISSION_QUEUE
#   - CF_API_TOKEN or CF_EMAIL + CF_API_KEY env vars
#   - droid CLI available on PATH
#   - git repos cloned at expected paths

param(
  [int]$PollIntervalSeconds = 60,
  [switch]$Once
)

$ErrorActionPreference = "Continue"
$KV_NAMESPACE_ID = $env:MISSION_KV_NAMESPACE_ID
$CF_ACCOUNT_ID = $env:CF_ACCOUNT_ID
$CF_API_TOKEN = $env:CF_API_TOKEN

if (-not $KV_NAMESPACE_ID -or -not $CF_ACCOUNT_ID -or -not $CF_API_TOKEN) {
  Write-Host "ERROR: Set env vars CF_ACCOUNT_ID, CF_API_TOKEN, MISSION_KV_NAMESPACE_ID"
  exit 1
}

$CF_API_BASE = "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/storage/kv/namespaces/$KV_NAMESPACE_ID"
$CF_HEADERS = @{
  "Authorization" = "Bearer $CF_API_TOKEN"
  "Content-Type"  = "application/json"
}

# Path mapping: repo name → local path
$REPO_PATHS = @{
  "motto-appraisal-pipeline" = "$env:USERPROFILE\motto-appraisal-pipeline"
  "motto-sdr-agent"          = "$env:USERPROFILE\motto-sdr-agent"
  "motto-credential-grabber" = "$env:USERPROFILE\motto-credential-grabber"
  "motto-skills"             = "$env:USERPROFILE\motto-skills"
  "motto-director"           = "$env:USERPROFILE\motto-director"
  "motto-outreach"           = "$env:USERPROFILE\motto-outreach"
  "motto-distribution"       = "$env:USERPROFILE\motto-distribution"
  "motto-social-agent"       = "$env:USERPROFILE\motto-social-agent"
  "appraisalos-bidding"      = "$env:USERPROFILE\appraisalos-bidding"
  "downtime-app"             = "$env:USERPROFILE\downtime-app"
}

function Get-PendingTasks {
  try {
    $response = Invoke-RestMethod -Uri "$CF_API_BASE/values/queue:pending:?prefix=queue:pending:" -Headers $CF_HEADERS -Method Get -TimeoutSec 15
    return $response
  } catch {
    Write-Host "KV list failed: $_"
    return @()
  }
}

function Get-Task($key) {
  try {
    $response = Invoke-RestMethod -Uri "$CF_API_BASE/values/$key" -Headers $CF_HEADERS -Method Get -TimeoutSec 10
    return $response | ConvertFrom-Json
  } catch {
    return $null
  }
}

function Delete-Task($key) {
  try {
    Invoke-RestMethod -Uri "$CF_API_BASE/values/$key" -Headers $CF_HEADERS -Method Delete -TimeoutSec 10 | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Post-GitHubComment($owner, $repo, $issueNumber, $body) {
  $token = $env:GITHUB_TOKEN
  if (-not $token) { return }

  try {
    $ghHeaders = @{
      "Authorization" = "Bearer $token"
      "Accept"        = "application/vnd.github+json"
      "Content-Type"  = "application/json"
    }
    $ghBody = @{ body = $body } | ConvertTo-Json
    Invoke-RestMethod -Uri "https://api.github.com/repos/$owner/$repo/issues/$issueNumber/comments" `
      -Headers $ghHeaders -Method Post -Body $ghBody -TimeoutSec 15 | Out-Null
  } catch {
    Write-Host "Failed to post comment: $_"
  }
}

function Update-GitHubLabels($owner, $repo, $issueNumber, $addLabels, $removeLabels) {
  $token = $env:GITHUB_TOKEN
  if (-not $token) { return }

  try {
    $ghHeaders = @{
      "Authorization" = "Bearer $token"
      "Accept"        = "application/vnd.github+json"
      "Content-Type"  = "application/json"
    }

    if ($removeLabels) {
      foreach ($label in $removeLabels) {
        Invoke-RestMethod -Uri "https://api.github.com/repos/$owner/$repo/issues/$issueNumber/labels/$label" `
          -Headers $ghHeaders -Method Delete -TimeoutSec 10 | Out-Null
      }
    }
    if ($addLabels) {
      $body = @{ labels = $addLabels } | ConvertTo-Json
      Invoke-RestMethod -Uri "https://api.github.com/repos/$owner/$repo/issues/$issueNumber/labels" `
        -Headers $ghHeaders -Method Post -Body $body -TimeoutSec 10 | Out-Null
    }
  } catch {
    Write-Host "Failed to update labels: $_"
  }
}

function Invoke-Mission($task) {
  $repo = $task.repo
  $repoPath = $REPO_PATHS[$repo]
  if (-not $repoPath) {
    Write-Host "WARNING: No local path for repo $repo — skipping"
    return $false
  }
  if (-not (Test-Path $repoPath)) {
    Write-Host "WARNING: Repo path $repoPath does not exist — cloning..."
    git clone "https://github.com/$($task.owner)/$repo.git" $repoPath 2>$null
    if (-not (Test-Path $repoPath)) {
      Write-Host "ERROR: Failed to clone $repo"
      return $false
    }
  }

  # Pull latest
  Set-Location $repoPath
  git pull 2>$null

  # Determine mission type
  $trigger = $task.trigger
  $missionType = switch -Wildcard ($trigger) {
    "mission:fix"         { "bug-fix" }
    "mission:review"      { "code-review" }
    "mission:refactor"    { "refactor" }
    "mission:docs"        { "docs-update" }
    "mission:investigate" { "investigation" }
    "pr_merged"           { "post-merge-validation" }
    default               { "general" }
  }
  $autoLevel = switch ($missionType) {
    "bug-fix"              { "high" }
    "code-review"          { "medium" }
    "refactor"             { "medium" }
    "docs-update"          { "high" }
    "investigation"        { "medium" }
    "post-merge-validation" { "high" }
    default                { "high" }
  }

  # Build mission brief
  $brief = @"
MISSION: $($task.title)

Source: github.com/$($task.owner)/$($task.repo)/issues/$($task.issue_number)
Type: $missionType
Requested by: @$($task.sender)

$($task.body)

---
Auto-dispatched by mission-webhook. Execute with autonomy: $autoLevel.
Report results back to issue #$($task.issue_number) when done.
"@

  # Announce start
  Post-GitHubComment $task.owner $task.repo $task.issue_number `
    "🔧 **Mission started** — Type: `$missionType`, Autonomy: `$autoLevel`"

  Update-GitHubLabels $task.owner $task.repo $task.issue_number `
    @("mission:in-progress") @("mission:queued")

  # Execute mission
  Write-Host "Dispatching mission: $($task.title)"
  Write-Host "  Repo: $repo"
  Write-Host "  Type: $missionType"
  Write-Host "  Auto: $autoLevel"

  $briefFile = [System.IO.Path]::GetTempFileName() + ".md"
  Set-Content -Path $briefFile -Value $brief

  try {
    $output = droid exec --mission --auto $autoLevel --cwd $repoPath --file $briefFile 2>&1
    $exitCode = $LASTEXITCODE
    $outputText = ($output | Out-String).Trim()

    # Extract session ID from output (droid exec prints it)
    $sessionId = ""
    if ($outputText -match 'session[:\s]+([a-f0-9-]{36})') {
      $sessionId = $matches[1]
    }

    if ($exitCode -eq 0) {
      $summary = ($outputText -split "`n" | Select-Object -Last 5) -join "`n"
      $comment = @"
✅ **Mission complete** — $missionType finished successfully

Session: ``$sessionId``
Type: `$missionType`

$summary
"@
      Post-GitHubComment $task.owner $task.repo $task.issue_number $comment
      Update-GitHubLabels $task.owner $task.repo $task.issue_number `
        @("mission:done") @("mission:in-progress")
      Write-Host "MISSION SUCCESS: $($task.title)"
      return $true
    } else {
      $comment = @"
❌ **Mission failed** — exit code $exitCode

Session: ``$sessionId``
Type: `$missionType`

Check session logs for details. Fix the issue and re-label `mission` to retry.
"@
      Post-GitHubComment $task.owner $task.repo $task.issue_number $comment
      Update-GitHubLabels $task.owner $task.repo $task.issue_number `
        @("mission:blocked") @("mission:in-progress", "mission:queued")
      Write-Host "MISSION FAILED: $($task.title)"
      return $false
    }
  } catch {
    $comment = @"
❌ **Mission error** — $($_.Exception.Message)

This may be a transient infrastructure issue. Re-label `mission` to retry.
"@
    Post-GitHubComment $task.owner $task.repo $task.issue_number $comment
    Update-GitHubLabels $task.owner $task.repo $task.issue_number `
      @("mission:blocked") @("mission:in-progress", "mission:queued")
    Write-Host "MISSION ERROR: $_"
    return $false
  } finally {
    Remove-Item $briefFile -Force -ErrorAction SilentlyContinue
  }
}

# --- Main Loop ---
Write-Host "mission-watcher started at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Polling every ${PollIntervalSeconds}s — Ctrl+C to stop"

do {
  $tasks = Get-PendingTasks
  if ($tasks -and $tasks.result) {
    foreach ($entry in $tasks.result) {
      $key = $entry.name
      Write-Host "Found pending task: $key"

      $task = Get-Task $key
      if (-not $task) {
        Write-Host "  Failed to fetch task, skipping"
        continue
      }

      $success = Invoke-Mission $task

      # Remove from queue regardless of outcome
      Delete-Task $key
      Write-Host "  Removed from queue: $key"
    }
  } else {
    Write-Host "No pending tasks at $(Get-Date -Format 'HH:mm:ss')"
  }

  if (-not $Once) {
    Start-Sleep -Seconds $PollIntervalSeconds
  }
} while (-not $Once)

Write-Host "mission-watcher stopped"
