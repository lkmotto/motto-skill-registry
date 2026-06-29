---
name: bottleneck-posterity
version: 1.0.0
description: |
  Captures resolved blockers as durable bottleneck records, recalls them before work,
  and nudges the right skills so repeated failures become one-time events.
  Mem0 is the primary memory backend for recall and reuse.
when_to_use: |
  Automatically after any resolved blocker, workaround, or repeated tool failure.
  Also before significant work to recall known bottlenecks by domain, tools, and objective.
  Manual trigger: "capture bottleneck", "recall bottlenecks", "posterity check".
tags: [self-learning, posterity, bottlenecks, mem0, reliability, reuse]
---

# Bottleneck Posterity

Capture every costly blocker once, then reuse the fix forever.

## Activation

- **Auto-trigger (capture)**: After any resolved failure or workaround
- **Auto-trigger (recall)**: Before mission start, readiness checks, or tool-heavy execution
- **Manual trigger**: "capture bottleneck", "posterity check", "what keeps failing"

## Step 0, Mem0 Preflight

1. Verify mem0 availability with `mem0_list_entities`.
2. If mem0 is unavailable, return `backend_unavailable` and skip writes.
3. Never store secrets, raw credentials, or tokens.

## Step 1, Normalize the Bottleneck Event

Build one atomic record per resolved blocker:
- `where`: host/project/session context
- `symptom`: what failed
- `root_cause`: why it failed
- `fix`: exact corrective action taken
- `verification`: how success was confirmed
- `reuse_hint`: best skill/tool to invoke next time

Also derive:
- `signature`: normalized cause signature, stable across sessions
- `status`: `active | mitigated | resolved`

## Step 2, Store in Mem0

Write with `mem0_add_memory` using:
- `user_id: ms01-droid`
- concise text:
  - `[BOTTLENECK][<signature>] symptom=<...>; root=<...>; fix=<...>; verify=<...>; reuse=<...>`
- metadata:
  - `type=bottleneck_event`
  - `signature`, `status`, `domain`, `skill`, `tool`, `host`, `project`
  - `source=bottleneck-posterity-skill`

After write, poll `mem0_get_event_status` until `SUCCEEDED`, `FAILED`, or timeout.

## Step 3, Recall Before Execution

Before significant work:
1. Build query from objective + domain + expected tools.
2. Run `mem0_search_memories(query=..., top_k=8, threshold=0, filters={"AND":[{"user_id":"ms01-droid"}]})`.
3. Keep only entries with `metadata.type=bottleneck_event`.
4. Rank by recency and signature frequency.
5. Return a short "Known Bottlenecks" block with:
   - signature
   - root cause
   - reuse hint
   - verification shortcut

## Step 4, Skill Nudge Logic

If a recalled bottleneck has `reuse_hint`, proactively recommend that skill before retrying.

Examples:
- privilege/UAC bottleneck -> suggest elevated launcher/runbook path
- repeated auth expiry -> suggest `credential-escrow` or relevant auth skill
- MCP connect failures -> suggest `mcp-connection-triage`

## Step 5, Posterity Metrics

Track and report:
- `capture_rate`
- `reuse_rate`
- `repeat_failure_rate`
- `skill_nudge_conversion`

Metrics can be emitted in summaries and consumed by `capability-gap-detector`.

## Output Contract

- Mode: `capture | recall`
- Mem0 status: `available | unavailable`
- For capture:
  - signature, write result, event status
- For recall:
  - matched bottlenecks and prioritized reuse hints
- Metric snapshot (if available)

## Guardrails

- One bottleneck per record, do not bundle unrelated issues.
- Redact all credentials and secrets.
- Do not mark `resolved` without a concrete verification signal.
- Deduplicate near-identical records by signature and context window.

## Integration Points

- **session-postmortem**: source of resolved failures
- **readiness-gate**: preflight recall of known blockers
- **error-pattern-detector**: signature-level clustering and recurrence status
- **capability-gap-detector**: underused-skill and recurrence correlation
- **mem0-session-persistence**: include bottleneck brief in session continuity
