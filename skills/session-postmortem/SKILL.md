---
name: session-postmortem
version: 1.1.0
description: |
  Automatic lesson extraction at the end of every significant session — whether a
  formal mission, a complex multi-step task, or a long-running interactive session.
  Analyzes what happened, identifies novel decisions, failures, workarounds, and
  successful patterns. Feeds decision-log, error-pattern-detector, and knowledge-distiller.
  Proposes skill updates when warranted.
when_to_use: |
  Automatically at session close when the session exceeds 10 tool calls. Also manually
  when user says "postmortem", "lessons learned", "capture what we learned", "session
  review", or "extract knowledge from this session".
tags: [self-learning, postmortem, knowledge-capture, session-analysis]
---

# Session Postmortem

Extract durable knowledge from every session — mission or not — so nothing is lost.

## Activation

- **Auto-trigger**: At the end of any session exceeding 10 tool calls (missions and regular sessions alike)
- **Manual trigger**: User says "postmortem", "capture lessons", "session review", or "what did we learn"

## Step 1 — Gather Raw Material

Collect from the current session:
1. All tool calls and their outcomes
2. Errors encountered and how they were resolved
3. Decisions made (explicit or implicit)
4. New facts discovered (domain knowledge, tool behavior, constraints)
5. Workflows that were composed or refined
6. Any files created, modified, or deleted

## Step 2 — Analyze

For each category, extract structured findings:

### Novel decisions
- What choice was made?
- What alternatives were considered?
- What constraints drove the decision?
- Outcome: `output_type`: `decision`

### Failures resolved
- What failed?
- Root cause?
- Resolution strategy?
- Can this be prevented in future?
- Outcome: `output_type`: `failure_pattern`

### Domain facts discovered
- What was discovered?
- What domain/scope does it apply to?
- Confidence level (high/medium/low)?
- Source (which tool output or document)?
- Outcome: `output_type`: `fact`

### Successful patterns
- What multi-step workflow worked well?
- Can it be generalized into a template?
- Outcome: `output_type`: `workflow`

### Skill gaps
- Was there something we didn't know how to do?
- Did we have to figure it out from scratch?
- Would a skill have helped?
- Outcome: `output_type`: `skill_gap`

## Step 3 — Dispatch to Downstream Systems

For each finding type, route to the appropriate store:

| Finding Type       | Destination                    | Action                                                 |
|---------------------|-------------------------------|--------------------------------------------------------|
| `decision`          | `knowledge/decisions.jsonl`   | Append entry with timestamp, context, rationale        |
| `failure_pattern`   | `knowledge/error-patterns.json` | Append or increment existing pattern                |
| `fact`              | `knowledge/facts.json`        | Upsert by domain+key                                   |
| `workflow`          | `knowledge/workflows.json`    | Append template if generalizable                       |
| `skill_gap`         | `knowledge/capability-gaps.json` | Append with estimated effort and priority           |

## Step 4 — Propose Skill Updates

If the session repeatedly used a pattern that doesn't exist as a skill:
1. Check if `skill-creation` skill is available
2. If yes, draft a SKILL.md proposal and save to `~/.factory/knowledge/skill-proposals/`
3. Add a note to the postmortem summary pointing to the proposal

If an existing skill had to be worked around or corrected:
1. Note the skill name and the issue
2. Propose the specific change needed
3. Add to postmortem summary

## Step 5 — Produce Postmortem Summary

Write `~/.factory/knowledge/postmortems/{session-id}.json`:

```json
{
  "session_id": "...",
  "timestamp": "...",
  "summary": "One-sentence summary of what happened",
  "session_type": "mission | interactive | task",
  "findings": {
    "decisions": 2,
    "failure_patterns": 1,
    "facts": 3,
    "workflows": 1,
    "skill_gaps": 0
  },
  "skill_proposals": [],
  "updated_stores": ["decisions.jsonl", "facts.json", "error-patterns.json"]
}
```

## Guardrails

- NEVER write raw secrets, tokens, passwords, or API keys to any knowledge store
- Redact credential material before recording decisions about auth flows
- Keep summaries concise — postmortem is a pointer, not a full replay
- Skip trivial sessions (less than 5 tool calls with no errors or decisions)

## Integration Points

- **decision-log**: Receives all `decision` findings
- **error-pattern-detector**: Receives all `failure_pattern` findings
- **knowledge-distiller**: Receives all `fact` findings
- **workflow-library**: Receives all `workflow` findings
- **capability-gap-detector**: Receives all `skill_gap` findings
- **skill-creation**: Invoked when a skill proposal is warranted
