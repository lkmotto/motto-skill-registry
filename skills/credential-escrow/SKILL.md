---
name: credential-escrow
version: 1.0.0
description: |
  Proactive auth lifecycle management. Scans Smithery connections, Doppler configs,
  and Bitwarden items for token/credential expiry. Before missions, checks if any
  credential will expire mid-task. Attempts auto-renewal via api-credential-acquisition
  before escalating to the user. Maintains a credential health dashboard.
when_to_use: |
  Automatically before any significant task starts (via readiness-gate). Also on
  manual "check credential health", "auth status", "are my tokens fresh", "rotate tokens".
  Periodic scan every 24 hours.
tags: [self-learning, auth, credentials, tokens, doppler, smithery, bitwarden, proactive]
---

# Credential Escrow

Don't let missions fail because a token expired at step 7 of 12. Know the state of
every credential before work begins.

## Activation

- **Auto-trigger**: Called by readiness-gate before significant tasks
- **Periodic scan**: Every 24 hours, scan all credential sources
- **Manual trigger**: "credential health", "auth status", "check tokens", "rotate credentials"

## Step 1 — Inventory Credential Sources

Scan all three sources:

### Smithery Connections
```bash
smithery mcp list --json
```
For each connection, check:
- `status`: connected | auth_required | error
- `last_connected`: when it was last healthy
- Inferred expiry: OAuth tokens typically 1h-24h; API keys indefinite

### Doppler Secrets
```bash
doppler secrets list --project <project> --config <config> --json
```
For each secret that looks like a credential (key contains `token`, `key`, `secret`, `password`, `api`):
- Check if format suggests expiry (JWT tokens have `exp` claim)
- Note last rotation date if tracked

### Bitwarden Items
Use Bitwarden CLI or MCP to enumerate items tagged as API credentials.
For each item:
- Note type: API key, OAuth token, password, TOTP seed
- Check if the item has an `expiry` field or notes about rotation schedule

## Step 2 — Assess Health

For each credential, determine:

```json
{
  "source": "smithery | doppler | bitwarden",
  "id": "unique-identifier",
  "type": "oauth | api_key | password | totp | token",
  "service": "github | gmail | figma | ntreis | taxnet | ...",
  "status": "healthy | expiring_soon | expired | unknown | unreachable",
  "expires_at": "ISO-8601 or null",
  "last_verified": "ISO-8601",
  "auto_renewable": true,
  "renewal_method": "api-credential-acquisition | smithery-reconnect | manual-only",
  "blocking_tasks": ["task-id-1", "task-id-2"],
  "notes": "Any known quirks or special instructions"
}
```

Status logic:
- `healthy`: Verified within last 24h, no expiry within 48h
- `expiring_soon`: Expiry within 48h
- `expired`: Known or suspected expired
- `unknown`: Can't determine status (no JWT to decode, no expiry metadata)
- `unreachable`: Can't connect to the credential source

## Step 3 — Remediate

For each credential with status `expiring_soon` or `expired`:

### Auto-renewable via api-credential-acquisition
1. Invoke `api-credential-acquisition` skill with the service name
2. Run the auth recipe
3. Verify new credential works
4. Update credential-health.json with new expiry and verification timestamp

### Smithery reconnect
1. Run `smithery mcp list` to get connection details
2. If `auth_required`: open setupUrl, poll until connected
3. Update credential-health.json

### Manual-only
1. Add to escalation list with:
   - Service name
   - What's needed (e.g., "Log into NTREIS and complete Clareity challenge")
   - Which missions are blocked
2. Report to user before task start

## Step 4 — Pre-Task Check

When called by readiness-gate:

1. Load `knowledge/credential-health.json`
2. Cross-reference with the task's required services
3. For each required credential:
   - `healthy` or `unknown`: proceed
   - `expiring_soon`: flag as warning, attempt auto-renewal
   - `expired` or `unreachable`: attempt auto-renewal, escalate if fails
4. Return: `{go: true/false, warnings: [...], blockers: [...], remediated: [...]}`

## Step 5 — Periodic Scan

Every 24 hours:
1. Run full inventory (Step 1)
2. Assess health (Step 2)
3. Remediate any `expiring_soon` or `expired` (Step 3)
4. Write updated `credential-health.json`
5. Report changes since last scan

## Output Contract

- Updated `knowledge/credential-health.json`
- Pre-task check result: go/no-go with details
- Periodic report: health delta since last scan
- Escalation list for manual-only renewals

## Guardrails

- NEVER log raw tokens, secrets, or passwords to any file
- Only store masked proofs (hash, length, last-4-chars) in credential-health.json
- Never attempt auto-renewal for credentials marked `manual-only`
- If renewal fails 3 times for the same credential, escalate to user with context

## Integration Points

- **api-credential-acquisition**: Invoked for auto-renewable credentials
- **readiness-gate**: Consumes health data before task start
- **knowledge-distiller**: May extract renewal patterns as facts
- **error-pattern-detector**: Repeated auth failures feed pattern detection
