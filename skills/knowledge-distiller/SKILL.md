---
name: knowledge-distiller
version: 1.0.0
description: |
  Extracts semantic facts from sessions: tool behavior quirks, domain constraints,
  undocumented requirements. Stores facts in a queryable registry so future sessions
  can reference them instead of re-discovering. Think of it as the AI's second brain.
when_to_use: |
  Automatically when session-postmortem dispatches facts. Manually when user says
  "remember that", "note this fact", "don't forget X". Query when starting work
  in a domain — search facts before guessing about constraints or behavior.
tags: [self-learning, knowledge-management, facts, semantic-memory]
---

# Knowledge Distiller

Procedural skills tell us HOW. This skill remembers WHAT — the facts that every
session needs but nobody writes down.

## Activation

- **Auto-trigger**: Receives fact findings from session-postmortem
- **Manual capture**: "remember this", "note this down", "don't forget that X"
- **Query**: Before starting work, search facts.json for the relevant domain

## Step 1 — Extract Facts

From session-postmortem findings or direct observation, identify durable facts:

**Qualifying facts:**
- Tool behavior quirks: "NTREIS Matrix requires selecting the county dropdown before the address field becomes active"
- Domain constraints: "TaxNet USA county searches require exact address format: '123 Main St' not '123 Main Street'"
- Configuration truths: "Doppler project 'appraisal-pipeline' uses config 'prd' for production secrets"
- Integration specifics: "Comet browser MCP requires a task_uuid for every call"
- Platform limitations: "Smithery free tier limits to 5 concurrent connections"
- Undocumented requirements: "Pipedream Gmail trigger needs explicit label filter, not just inbox"

**Skip:**
- Transient state (e.g., "currently on page 3")
- Obvious or well-documented behavior
- Low-confidence speculation

## Step 2 — Store Fact

Upsert into `~/.factory/knowledge/facts.json`:

```json
{
  "id": "fact-uuid",
  "domain": "ntreis | taxnet | doppler | smithery | comet | pipedream | appraisal | ...",
  "key": "short-lookup-key",
  "fact": "The actual fact, written clearly enough to be actionable",
  "confidence": "high | medium | low",
  "source": "Which session or tool output produced this fact",
  "first_seen": "ISO-8601",
  "last_verified": "ISO-8601",
  "verified_by": "session-id or tool that confirmed it",
  "tags": ["auth", "ui-quirk", "config", "limitation"]
}
```

Upsert logic:
- Same `domain` + `key` → update `fact`, `last_verified`, increment if `confidence` improved
- New `domain` + `key` → create new entry

## Step 3 — Query Before Guessing

When starting work in any domain:

1. Load `knowledge/facts.json`
2. Filter by relevant `domain` and/or `tags`
3. Review high-confidence facts first
4. Note medium/low confidence facts as "verify if relevant"

If the fact prevents a mistake: log it. If the fact turns out wrong: update it.

## Step 4 — Fact Decay and Verification

Facts that rely on external systems (UI behavior, API endpoints, configs) decay:
- `high` confidence: re-verify every 90 days
- `medium` confidence: re-verify every 30 days
- `low` confidence: re-verify before each use

When a fact is contradicted by new evidence:
1. Downgrade confidence to `low`
2. Append contradiction note with source
3. Flag for manual review if critical

## Step 5 — Periodic Distillation

Every 30 days or on "distill knowledge" trigger:

1. Read recent postmortems, sessions-index, and decision-log
2. Identify facts that appear across multiple sessions but aren't in the store
3. Add them with `confidence: medium` and `source: distillation`
4. Report: new facts added, facts due for re-verification, contradictions found

## Output Contract

- Updated `knowledge/facts.json`
- For queries: return relevant facts with confidence levels
- Periodic report: fact health summary

## Guardrails

- Never store secrets, tokens, or credentials as facts
- Keep facts atomic — one fact per entry. Don't combine multiple assertions
- Prefer specificity over generality. "Doppler project X uses config Y" beats "Doppler has configs"

## Integration Points

- **session-postmortem**: Primary source of fact findings
- **decision-log**: Decisions often contain embedded facts
- **environment-drift-monitor**: Uses facts as probe baselines; reports contradictions
- **error-pattern-detector**: Errors may reveal facts we got wrong
