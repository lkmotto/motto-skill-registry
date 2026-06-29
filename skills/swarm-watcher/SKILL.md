---
name: swarm-watcher
version: 1.0.0
description: |
  Monitor a swarm of Factory droid sessions to completion. Polls active sessions,
  extracts per-droid outcomes (status, files produced, errors), writes a structured
  Markdown summary, and optionally auto-respawns errored sessions.
when_to_use: |
  Use immediately after spawning a batch of parallel droid sessions (a "swarm") via
  ONA, Perplexity, or any other external trigger. Also use when asked to check on
  outstanding droids or triage swarm results.
tags: [hermes, swarm, sessions, monitoring, factory, polling, triage]
---

# Swarm Watcher

## Purpose

After a spawn_swarm call, droid sessions run asynchronously. This skill closes the
feedback loop: it watches the sessions, extracts outcomes when they go idle, and
produces a structured summary so the next pipeline stage has actionable data.

## Trigger Contract

The canonical trigger is a `swarm-watch.json` file written to:

```
~/workspace/hermes/swarm-watch.json
```

Format:

```json
{
  "label": "human-readable batch name",
  "sessions": ["<session-id-1>", "<session-id-2>", "..."],
  "original_prompt": "the task droids were given (for respawn context)",
  "auto_respawn": false,
  "next_steps": ["optional list of actions to take after swarm completes"]
}
```

ONA or Perplexity should write this file after a `spawn_swarm` call and then
invoke this skill (or start the daemon). The file acts as a durable handoff point.

## Prerequisites

Verify Hermes Factory API connectivity before running:
1. Call `hermes___factory_list_sessions` with `limit=1`. If it fails, stop and
   surface the error - the Factory API key may be missing or expired.
2. Confirm `FACTORY_API_KEY` is set in the Hermes process environment or in
   Doppler `motto-core/prd`.

## Core Loop (AI-driven execution)

Use this procedure when running the skill as an AI agent (e.g., via Hermes driver
or ONA). For daemon-mode execution see the Python daemon section below.

### Step 1, Load Watch List

Read `~/workspace/hermes/swarm-watch.json`. Extract:
- `sessions` array (required)
- `label` (for memory tagging)
- `auto_respawn` flag
- `original_prompt` (for respawn context)

If the file is absent or empty, ask the caller to provide session IDs.

### Step 2, Poll Active Sessions

Every 90 seconds, for each session ID still in the pending set:

1. Call `hermes___factory_get_session` with `session_id=<id>` and `include_messages=false`.
2. Check `session.status`. Mark session as idle when status is one of:
   `idle`, `completed`, `done`, `finished`, `error`, `failed`, `stopped`.
3. For idle sessions, proceed to Step 3.

Use `hermes___factory_list_sessions` to cross-check which sessions are still
showing as active globally. This helps detect sessions that silently terminated
without reaching a known idle status.

### Step 3, Extract Outcome

For each newly-idle session:

1. Call `hermes___factory_get_session` with `include_messages=true` and `message_limit=40`.
2. Classify status from message content:
   - `success` if last messages mention completion, "done", "finished", "success"
   - `error` if messages contain uncaught exceptions, tracebacks, "failed", "fatal"
   - `partial` if messages mention "blocked", "incomplete", "timeout", "stuck"
   - `unknown` otherwise
3. Extract files written by scanning for write-verb patterns:
   `wrote`, `created`, `saved`, `written to` followed by a path.
   Also capture any `~/workspace/` paths mentioned.
4. Collect up to 8 error/blocker lines for the summary.
5. Capture the last assistant message (first 600 chars) as a human-readable summary.

### Step 4, Auto-Respawn (if enabled)

If `auto_respawn=true` and a session has status `error` or `unknown`:

1. Build a corrective prompt:
   ```
   Previous session <id> failed. Errors:
   <error lines>
   Please retry, fixing these issues.
   Original task: <original_prompt>
   ```
2. Spawn a new session (via `droid exec` or Factory mission API).
3. Add the new session ID to the pending set.
4. Record the respawn in the outcome as `respawned_as: <new_id>`.

Limit auto-respawn to 1 retry per original session to prevent infinite loops.

### Step 5, Write Summary Report

When all sessions are idle, write the summary to:

```
~/workspace/swarm-results/<TIMESTAMP>-summary.md
```

The summary must include:
- Overall result table (success / error / partial / unknown counts)
- Per-droid section: status, files produced, errors/blockers, last message excerpt
- Recommended next actions
- Configured `next_steps` if present in the watch config

### Step 6, Store to Hermes Memory

After writing the summary:

1. Store outcome to Hermes memory with `hermes___memory_store`:
   ```
   category: workflow
   content: [SWARM-WATCHER] Swarm <label> completed. <success_n> success,
             <error_n> error, <partial_n> partial. Summary: <path>
   metadata:
     source: swarm-watcher
     swarm_label: <label>
     summary_path: <path>
     session_count: <total>
     success_count: <success_n>
     error_count: <error_n>
   ```
2. If any sessions errored, store a separate `learning` entry:
   ```
   content: [SWARM-WATCHER][error] Sessions <ids> failed in swarm <label>.
            Root causes: <top error lines>
   ```

### Step 7, Surface Results

Return a concise summary message to the caller:
- Swarm label and timestamp
- Per-droid status (one line each)
- Path to the full summary file
- Recommended next actions from `next_steps`

## Python Daemon Mode (Autonomous Execution)

The `swarm_watcher.py` script at `~/workspace/hermes/swarm_watcher.py` provides
fully autonomous polling without an AI agent in the loop. Deploy it to the
Hermes VPS or any machine with Python 3.9+ and the `requests` library.

### One-shot execution

```bash
# Watch sessions from the default watch file:
python swarm_watcher.py

# Watch specific session IDs:
python swarm_watcher.py --sessions abc123 def456

# Enable auto-respawn:
python swarm_watcher.py --auto-respawn
```

### Daemon mode (persistent)

```bash
python swarm_watcher.py --daemon
```

The daemon scans `~/workspace/hermes/swarm-watch.json` every 15 seconds.
When new session IDs appear that have not been watched before, it starts a
polling batch automatically. This is the recommended deployment model on the
Hermes VPS: start it once as a background process and let ONA/Perplexity
drop watch files to trigger batches.

### Deploying to Hermes VPS

```bash
# On the Hostinger VPS, inside the hermes container:
docker exec -it hermes-supervisor bash

# Or run alongside the container as a separate process:
scp ~/workspace/hermes/swarm_watcher.py ubuntu@srv1511806.hstgr.cloud:~/
ssh ubuntu@srv1511806.hstgr.cloud "pip install requests && nohup python swarm_watcher.py --daemon > ~/swarm-watcher.log 2>&1 &"
```

Required environment variable on the VPS:
```bash
export FACTORY_API_KEY=<key from Doppler motto-core/prd>
```

## Output Contract

Every run produces:
- `~/workspace/swarm-results/<TIMESTAMP>-summary.md`
- A `workflow` Hermes memory entry tagged `[SWARM-WATCHER]`
- Optional `learning` entries for errored sessions
- Log lines to stdout (daemon: continuous, one-shot: until complete)

## Guardrails

- Do not auto-respawn more than once per original session.
- Do not store session messages verbatim in Hermes memory (size limit).
- Do not expose the FACTORY_API_KEY in log output or summary files.
- If Factory API returns repeated 401s, stop and alert rather than retrying.
- Treat `unknown` status conservatively: flag for review, do not auto-close.

## Integration with ONA / Perplexity

After `spawn_swarm`:

```python
# ONA pseudocode
session_ids = spawn_swarm(tasks)
watch_payload = {
    "label": f"swarm-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}",
    "sessions": session_ids,
    "original_prompt": task_prompt,
    "auto_respawn": False,
}
write_json("~/workspace/hermes/swarm-watch.json", watch_payload)
# The daemon picks it up within 15 seconds. Done.
```

The daemon on the Hermes VPS handles the rest and writes the summary report
autonomously. ONA/Perplexity can poll `~/workspace/swarm-results/` for new
files or call `hermes___memory_recall(query="SWARM-WATCHER", category="workflow")`
to get the outcome.
