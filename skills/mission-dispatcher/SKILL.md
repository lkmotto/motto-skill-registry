---
name: mission-dispatcher
description: |
  Receives webhook-triggered mission tasks from the Cloudflare KV queue and
  dispatches them as autonomous droid exec --mission sessions. Maps issue
  labels to mission types, runs readiness checks, posts progress updates
  as GitHub comments, and handles the complete dispatch→execution→feedback loop.
when_to_use: |
  Invoked by mission-watcher.ps1 when a task is pulled from the KV queue.
  Not user-invocable — this is an automated pipeline skill.
tags: [automation, missions, webhook, dispatch, github]
user-invocable: false
---

# Mission Dispatcher

Turns GitHub webhook events into autonomous Droid missions. This is the bridge
between "something happened on GitHub" and "a Droid handled it."

## Activation

Called by `mission-watcher.ps1` with a task payload from the Cloudflare KV queue.

## Step 1 — Receive Task

Task payload from webhook:

```json
{
  "id": "task-uuid",
  "type": "issue_open | issue_labeled | pr_merged",
  "trigger": "mission | mission:fix | mission:review | mission:refactor",
  "owner": "lkmotto",
  "repo": "motto-appraisal-pipeline",
  "issue_number": 42,
  "title": "[mission] Fix NTREIS login timeout",
  "body": "The NTREIS login times out after 30s when the Clareity page loads slowly...",
  "labels": ["mission:fix", "bug"],
  "sender": "lkmotto",
  "received_at": "2026-06-08T12:00:00Z"
}
```

## Step 2 — Determine Mission Type

Map the trigger label to a mission configuration:

| Trigger            | Mission Type       | Auto Level | Template                                     |
|--------------------|--------------------|------------|----------------------------------------------|
| `mission` (bare)   | General task       | high       | Issue body as mission brief                  |
| `mission:fix`      | Bug fix            | high       | Fix described bug, create PR                 |
| `mission:review`   | Code review        | medium     | Review described scope, no commits           |
| `mission:refactor` | Refactor           | medium     | Refactor described component, PR with tests  |
| `mission:docs`     | Documentation      | high       | Update docs per description, create PR       |
| `mission:investigate` | Investigation  | medium     | Research + report, no code changes           |
| `pr_merged` (main) | Post-merge validation | high   | Run tests, verify deploy, report             |

## Step 3 — Build Mission Brief

Construct a concise mission brief from the GitHub issue:

```
MISSION: {title}

Source: github.com/{owner}/{repo}/issues/{issue_number}
Type: {mission_type}
Requested by: @{sender}

{body}

---
Auto-dispatched by mission-webhook. Execute with autonomy: {auto_level}.
Report results back to the issue when done.
```

## Step 4 — Execute Mission

Run the mission via `droid exec --mission`:

```powershell
droid exec --mission `
  --auto {auto_level} `
  --cwd "{repo_path}" `
  --tag "dispatch:{task_id}" `
  --tag "repo:{owner}/{repo}" `
  --tag "issue:{issue_number}" `
  "{mission_brief}"
```

Capture:
- Exit code (0 = success, non-0 = failure)
- Session ID (from output)
- Summary (last N lines of output)

## Step 5 — Report Results

### On Success
Post GitHub comment:
```
✅ **Mission complete** — {one-line summary}

Session: `{session_id}`
Files changed: {count}
PR created: {link or "none"}

Key changes:
- {bullet 1}
- {bullet 2}
```

Update labels: remove `mission:queued`, add `mission:done`.

Close issue if mission type is `fix`, `docs`, or `refactor` (the PR handles the rest).

### On Failure
Post GitHub comment:
```
❌ **Mission failed** — {error summary}

Session: `{session_id}`

What went wrong: {root cause from error}
Attempted fix: {what was tried}

Next step: review session logs or re-trigger with more context.
```

Update labels: remove `mission:queued`, add `mission:blocked`.

Re-open issue if it was closed.

### On Readiness Gate Block
Post GitHub comment:
```
🛑 **Mission blocked at readiness gate**

{reasons from readiness-gate output}

Fix these issues and re-label the issue `mission` to retry.
```

Update labels: remove `mission:queued`, add `mission:blocked`.

## Step 6 — Remove from Queue

After reporting (regardless of outcome):
- Delete the KV key `queue:pending:{repo}:{issue_number}`
- This signals the watcher to pick up the next task

## Integration Points

- **readiness-gate**: Runs before mission starts; blocks if environment is unhealthy
- **session-postmortem**: Runs after mission completes; extracts learnings
- **knowledge-distiller**: Captures any new facts from the mission
- **error-pattern-detector**: Captures failures for pattern analysis

## Guardrails

- Never execute a mission type higher than `medium` autonomy unless the trigger label explicitly authorizes it
- Never commit to `main` directly — always create a PR
- Never close an issue without posting results
- If the same issue triggers twice (duplicate), skip with a comment
- Respect rate limits: max 1 concurrent mission, sequential only
