---
name: environment-drift-monitor
version: 1.0.0
description: |
  Monitors critical touchpoints for silent changes. Skills rot when APIs change,
  websites restructure, or MCPs update. This skill runs lightweight probes against
  key surfaces (NTREIS Matrix, TaxNet, Doppler configs, Smithery connections) and
  detects when skill assumptions no longer hold. Auto-patches or quarantines
  affected skills when drift is detected.
when_to_use: |
  Automatically before any significant task starts (via readiness-gate). Also on
  manual "check for drift", "verify environment", "are my skills still valid",
  "probe health check". Periodic deep scan weekly.
tags: [self-learning, drift, monitoring, probes, reliability, skills-health]
---

# Environment Drift Monitor

The most dangerous failures are the silent ones — where everything looks fine
but the assumptions baked into your skills are now wrong. This skill catches those.

## Activation

- **Auto-trigger**: Called by readiness-gate before significant tasks
- **Periodic deep scan**: Weekly, run full probe suite
- **Manual trigger**: "check for drift", "verify environment", "probe health", "are skills still valid"
- **Event-driven**: After any skill update, re-probe affected surfaces

## Step 1 — Maintain Probe Registry

Probes live in `~/.factory/knowledge/drift-probes.json`. Each probe:

```json
{
  "id": "probe-uuid",
  "name": "ntreis_matrix_login_flow",
  "description": "Verify NTREIS Clareity login redirects to Matrix with correct session",
  "surface": "ntreis",
  "type": "web_page_structure | api_endpoint | mcp_connection | cli_output | config_file",
  "check": {
    "method": "browser_navigation | http_get | mcp_tool_call | cli_command | file_read",
    "target": "https://ntreis.matrix.com/...",
    "expected": {
      "type": "contains | equals | status_code | schema_match",
      "value": "Property Search"
    },
    "timeout_seconds": 30
  },
  "affected_skills": ["mission-orchestrator", "neon-ops"],
  "last_probe": "ISO-8601",
  "last_result": "pass | fail | warn | timeout",
  "last_result_detail": "What was observed vs expected",
  "consecutive_failures": 0
}
```

### Probe Types

**web_page_structure**: Browser automation checks
- Does the login page still have the expected form fields?
- Does the post-login page still contain expected elements?
- Has the DOM structure changed in ways that break selectors?

**api_endpoint**: HTTP checks
- Does the endpoint still respond with expected status codes?
- Has the response schema changed?
- Are required headers still the same?

**mcp_connection**: MCP health checks
- Is the MCP server still reachable?
- Are the expected tools still listed?
- Has authentication state changed?

**cli_output**: Command output checks
- Does `doppler secrets list` still return the expected format?
- Does `smithery mcp list` still show expected connections?

**config_file**: Configuration checks
- Has `mcp.json` lost any expected entries?
- Has `settings.json` changed in ways that affect behavior?

## Step 2 — Define Initial Probes

Seed the probe registry with critical surfaces from your stack:

### NTREIS Matrix
- Login page structure (Clareity form fields present)
- Post-login redirect to Matrix/Realist
- Property search form structure

### TaxNet USA
- County search page availability
- Address search form structure
- Detail page rendering

### Doppler
- Project `appraisal-pipeline` exists with expected configs
- CLI returns expected output format

### Smithery
- All connections in mcp.json are healthy
- `smithery mcp list` returns expected entries

### Comet Browser
- MCP server responds to tool calls
- Extension handoff protocol works

### Auth Runner
- `auth_runner.py` exists and is importable
- Recipe files are valid JSON

## Step 3 — Run Probes

### Lightweight pre-task check (fast, ~30s)
Run only probes for surfaces required by the pending task.

### Deep weekly scan (thorough, ~5-10min)
Run all probes. Check for:
- New probe types needed (surfaces we use but don't monitor)
- Probes that always pass and can be reduced in frequency
- Probes that frequently fail and need better expected values

## Step 4 — Handle Drift

When a probe fails:

### Pass-1: Retry
Retry once after 10s delay (transient network issues).

### Pass-2: Diagnose
If still failing, attempt diagnosis:
- Fetch the page/source and compare to expected
- Check if the change is intentional (API upgrade, redesign) or an outage

### Pass-3: Action

| Change Type            | Action                                                    |
|------------------------|-----------------------------------------------------------|
| Minor UI change        | Auto-update affected skill's selectors/instructions       |
| API schema change      | Update affected skill, note new schema in knowledge-distiller |
| Service outage         | Mark probe `warn`, retry in 1h                            |
| Permanent deprecation  | Quarantine affected skills with deprecation notice        |
| Unknown/ambiguous      | Escalate to user with diff of expected vs actual          |

### Quarantine Protocol

When a skill is quarantined:
1. Add `quarantined: true` and `quarantine_reason` to skill's frontmatter
2. Add quarantine entry to skill-broker policy (prevent auto-activation)
3. Notify: which skill, why, what's needed to fix

## Step 5 — Auto-Patch (Low-Risk Only)

Auto-patching is allowed when:
- The change is a simple selector/text update in a skill file
- The fix has been verified against the live surface
- The skill handles non-destructive operations only

Never auto-patch:
- Credential handling code
- Skills that perform writes, deployments, or destructive ops
- Skills with quarantine history

## Step 6 — Weekly Report

Every 7 days:
1. Probe health summary: passes, failures, warnings
2. New drift detected and how it was handled
3. Probes due for review (unchanged > 90 days)
4. Surfaces not yet monitored that should be

## Output Contract

- Updated `knowledge/drift-probes.json`
- For drift detected: either auto-patch (updated skill file) or quarantine + escalation
- Pre-task result: `{drift_ok: true/false, affected_skills: [...], remediations: [...]}`
- Weekly report: probe health dashboard

## Guardrails

- Never run destructive probes (no DELETE, no form submissions that change state)
- Rate-limit probes against external services (no more than 1 probe/min per service)
- If a surface is returning 5xx errors, don't hammer it — mark `warn` and retry later
- Probe results themselves are facts — feed knowledge-distiller

## Integration Points

- **readiness-gate**: Consumes drift status before allowing task start
- **knowledge-distiller**: Feeds discovered changes as facts; queries facts for expected values
- **error-pattern-detector**: Drift-induced errors get routed to error patterns
- **session-postmortem**: Failed sessions may reveal undetected drift
