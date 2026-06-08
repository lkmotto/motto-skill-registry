---
name: decision-log
version: 1.0.0
description: |
  Lightweight append-only log of consequential decisions made during sessions.
  Records what was chosen, alternatives considered, rationale, and constraints.
  Future sessions query this log before re-litigating past decisions.
  Feeds self-calibrating-autonomy with approval/rejection patterns.
when_to_use: |
  Automatically when session-postmortem dispatches a decision. Manually when user
  says "log this decision", "remember why we chose X", or "record this choice".
  Also query this skill when starting work that may have been decided before.
tags: [self-learning, decisions, knowledge-management, autonomy]
---

# Decision Log

Never re-litigate the same choice twice. Every consequential decision is recorded
once and queried forever.

## Activation

- **Auto-trigger**: Called by session-postmortem when decisions are detected
- **Query trigger**: Before making a consequential choice, search decisions.jsonl for similar contexts
- **Manual trigger**: "log this decision", "remember this choice"

## Step 1 — Write a Decision Entry

Append to `~/.factory/knowledge/decisions.jsonl`:

```json
{
  "timestamp": "ISO-8601",
  "session_id": "...",
  "domain": "auth | deployment | library-choice | architecture | workflow | tooling | other",
  "context": "What were we doing when this decision came up?",
  "question": "What specific question were we trying to answer?",
  "alternatives": [
    {"option": "Option A", "pros": ["..."], "cons": ["..."]},
    {"option": "Option B", "pros": ["..."], "cons": ["..."]}
  ],
  "chosen": "Option B",
  "rationale": "Why this option won. Include constraints, tradeoffs accepted.",
  "constraints": ["Must work on Windows", "No GPL dependencies", "Under 2h integration time"],
  "reversible": true,
  "review_date": "ISO-8601 (if decision should be revisited, e.g. 3 months out)"
}
```

## Step 2 — Query Before Deciding

Before making any consequential choice:

1. Search `~/.factory/knowledge/decisions.jsonl` for the same domain
2. Search `~/.factory/sessions-index.json` for sessions where similar choices were discussed
3. If a prior decision exists:
   - Check if it's still valid (constraints unchanged? review date passed?)
   - If still valid: adopt it without re-litigation
   - If stale: note what changed and proceed with new decision

## Step 3 — What Qualifies as Consequential

Log decisions when:
- Choosing between 2+ libraries, frameworks, or tools
- Making an architecture or design tradeoff
- Accepting a known limitation or technical debt
- Choosing a workaround over a proper fix
- Setting a policy or convention that affects future work
- User explicitly approves or rejects a proposed approach

Skip when:
- Trivial or obvious choices (e.g., using `httpx` over `requests` because it's already in the project)
- Temporary debugging decisions

## Step 4 — Periodic Review

Every 30 days (or on manual "review decisions" trigger):
1. Scan decisions.jsonl for entries past their `review_date`
2. For each overdue decision: check if it still holds
3. If outdated: append a revision entry referencing the original

## Output Contract

- Decision appended to `knowledge/decisions.jsonl`
- No other files modified

## Guardrails

- Never log raw credentials, tokens, or secrets
- Be specific in `context` and `question` — vague entries are useless for future queries
- Record the real rationale, not the post-hoc justification

## Integration Points

- **session-postmortem**: Dispatches decisions here
- **self-calibrating-autonomy**: Reads decisions to learn approval patterns
- **knowledge-distiller**: May extract facts from decision entries
