---
name: error-pattern-detector
version: 1.0.0
description: |
  Continuously monitors failures across sessions (auth failures, API errors, build breaks,
  test flakes). Clusters similar failures, identifies root causes, and either auto-patches
  the relevant skill or proposes a new guardrail. Turns every failure into a permanent fix.
when_to_use: |
  Automatically when session-postmortem dispatches a failure_pattern. Also on manual
  "detect error patterns", "why does this keep failing", "find recurring failures".
  Periodically scans sessions-index.json for new failure clusters.
tags: [self-learning, errors, reliability, guardrails, root-cause]
---

# Error Pattern Detector

Failures are free lessons. This skill makes sure we only pay for each one once.

## Activation

- **Auto-trigger**: Receives failure_pattern findings from session-postmortem
- **Periodic scan**: Every 10 sessions, scan `sessions-index.json` for new failure clusters
- **Manual trigger**: "detect error patterns", "find recurring failures", "why does X keep breaking"

## Step 1 — Ingest Failure

Accept a failure finding from session-postmortem:

```json
{
  "session_id": "...",
  "timestamp": "...",
  "error_signature": "Short, normalized description (e.g., 'ntreis_login_stale_session')",
  "raw_error": "What the user/tool actually saw",
  "root_cause": "Why it happened (if known)",
  "resolution": "How we fixed it this time",
  "context": {
    "skill_involved": "mission-orchestrator | neon-ops | ...",
    "step": "Which step in the workflow failed",
    "tool": "Which tool call failed"
  },
  "preventable": true,
  "prevention_strategy": "What would stop this from recurring"
}
```

## Step 2 — Cluster and Match

Normalize the error_signature and search `knowledge/error-patterns.json` for matches:

1. Exact signature match → increment count, add session reference
2. Fuzzy match (same root cause, different surface) → merge as variant
3. No match → create new pattern entry

Pattern entry format:

```json
{
  "id": "pattern-uuid",
  "signature": "normalized_error_signature",
  "first_seen": "ISO-8601",
  "last_seen": "ISO-8601",
  "count": 4,
  "sessions": ["id1", "id2", "id3", "id4"],
  "root_cause": "Known or suspected root cause",
  "severity": "blocker | major | minor | nuisance",
  "status": "active | mitigated | resolved",
  "affected_skills": ["skill-name"],
  "affected_mcps": ["mcp-name"],
  "resolution": {
    "strategy": "auto-patch | guardrail | skill-update | human-required",
    "implemented": false,
    "patch_ref": "link to skill update or guardrail"
  }
}
```

## Step 3 — Action When Threshold Hit

When a pattern reaches count >= 3 and status is "active":

### Auto-patch (low risk, clearly scoped)
- Add retry logic for transient failures
- Add pre-condition check before the failing step
- Add clearer error message referencing the known pattern

### Guardrail (medium risk, structural)
- Update the affected skill's SKILL.md with a "What not to do" section
- Add a pre-flight check to skill-broker policy
- Example: "Before NTREIS capture, force re-auth if session older than 15min"

### Skill update (when existing skill is inadequate)
- Propose specific changes to the skill's instructions
- Add verification steps that catch this pattern
- Document the failure mode so future runs avoid it

### Human-required (high risk or ambiguous)
- Escalate with: pattern summary, recommendation, and explicit question
- Only use when auto-fix would be unsafe

## Step 4 — Prevent Recurrence

After implementing the fix:
1. Mark pattern `status: "mitigated"`, `resolution.implemented: true`
2. Add a note: what was changed, in which file, on what date
3. Monitor: if pattern recurs after mitigation, escalate to human-required

## Periodic Scan Protocol

Every 10 sessions, run:

```bash
# Extract errors from recent sessions
rg '"error"|"failed"|"exception"' ~/.factory/sessions-index.json -B2 -A2

# Cross-reference with existing patterns
# Report: new patterns found, existing patterns that recurred, mitigated patterns that held
```

## Output Contract

- Updated `knowledge/error-patterns.json`
- If auto-patched: updated skill file or guardrail
- If escalated: concise summary to user with recommendation
- Periodic report: pattern health summary

## Guardrails

- Never auto-patch skills that handle credentials, payments, or destructive operations
- Never suppress errors without adding visibility (log, not swallow)
- One pattern = one root cause. Don't conflate unrelated failures
- If unsure whether a fix is safe, escalate to human-required

## Integration Points

- **session-postmortem**: Primary source of failure findings
- **knowledge-distiller**: May extract facts from error clusters
- **environment-drift-monitor**: Errors caused by drift get routed here
- **skill-creation**: Invoked when a new skill could prevent a class of errors
