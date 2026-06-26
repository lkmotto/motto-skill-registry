---
name: capability-gap-detector
version: 1.1.0
description: |
  Periodically scans session history, skill graph, and MCP inventory to identify
  missing tools and skills. Produces a prioritized build queue with effort estimates.
  Finds concrete gaps like "no appraisal PDF parser exists despite 4 sessions
  extracting PDF data" and proposes scaffolding. Feeds tool-auto-provisioner.
when_to_use: |
  Automatically after every 5 significant sessions or on weekly cadence. Manual
  trigger: "find capability gaps", "what am I missing", "skill audit", "capability
  review", "what should I build next".
tags: [self-learning, gaps, audit, skills, mcp, planning, strategy]
---

# Capability Gap Detector

Know what you don't have before you need it. This skill identifies missing tools
and skills before they become blockers.

## Activation

- **Auto-trigger**: Every 5 significant sessions or weekly
- **Manual trigger**: "find capability gaps", "what am I missing", "skill audit"
- **Feeds**: tool-auto-provisioner for gap closure

## Step 1 — Build Capability Map

Assemble the current capability landscape:

### Skills Inventory
Scan `~/.factory/skills/` and `~/.factory/skills-disabled/` for all SKILL.md files.
Extract: name, description, domain, when_to_use triggers.

### MCP Inventory
From `~/.factory/mcp.json` and Smithery connections:
- Connected MCP servers and their tools
- Core-local MCPs from mcp-routing.policy.json
- Toolbox-preferred services

### Droid Inventory
From `~/.factory/droids/`: available specialized agents.

### Session History
From `~/.factory/sessions-index.json` and `~/.factory/missions/`:
- Domains worked in
- Tools and skills used per session
- Failure points and manual interventions

## Step 2 — Detect Gaps

Four gap detection strategies:

### Usage-Based Gaps
Sessions repeatedly do X manually or with workarounds, but no skill exists for X.
- Scan session postmortems for `skill_gap` entries
- Scan sessions for repeated "figure it out from scratch" patterns
- Look for error patterns where the resolution was "we need a tool for Y"

### Stack Gaps
Your stack covers domains A, B, C. Domain D is absent. Is it needed?
- Map your session domains to capability domains
- Compare with common agent capability matrices
- Flag domains with no coverage

### Integration Gaps
You have service X connected, but no skill/tool that leverages it.
- Cross-reference MCP inventory with skill inventory
- Flag connected services with zero or minimal skill usage

### Pattern Gaps
Sessions follow a recurring pattern but lack a reusable template.
- Cross-reference workflow-library templates with actual session patterns
- Flag recurring patterns not yet templated

## Step 3 — Classify and Prioritize

For each gap detected:

```json
{
  "id": "gap-uuid",
  "type": "missing_skill | missing_mcp | missing_template | missing_integration",
  "domain": "appraisal | auth | deployment | monitoring | communication | ...",
  "description": "What's missing, in concrete terms",
  "evidence": {
    "source": "session-postmortem | session-analysis | stack-audit | pattern-analysis",
    "occurrences": 4,
    "last_encountered": "ISO-8601",
    "sessions_affected": ["id1", "id2"]
  },
  "priority": "critical | high | medium | low",
  "priority_rationale": "Why this priority level",
  "estimated_effort": "30min | 2h | 1d | 1w",
  "dependencies": ["skill-name or mcp-name needed before this"],
  "proposed_solution": "What would close this gap",
  "auto_buildable": true,
  "build_plan": "If auto-buildable: what to create and how"
}
```

Priority logic:
- **critical**: Blocking active missions, causing repeated failures
- **high**: Would significantly reduce manual work, used in 3+ sessions
- **medium**: Would improve efficiency, used in 1-2 sessions
- **low**: Nice to have, speculative

## Step 4 — Produce Build Queue

Output `~/.factory/knowledge/capability-gaps.json` with prioritized queue.

Also produce a human-readable summary:

```
CAPABILITY GAP REPORT — 2026-06-08
==================================

CRITICAL (0)
(none)

HIGH (2)
1. appraisal-pdf-parser: Skill for extracting structured data from appraisal PDFs
   Evidence: 4 missions, 12+ manual extractions
   Effort: ~2h, Auto-buildable: yes (pdfplumber + pydantic schema)
   
2. ntreis-session-health-check: Probe for NTREIS session freshness
   Evidence: 3 auth failures due to stale sessions
   Effort: ~30min, Auto-buildable: yes (add to drift-monitor probes)

MEDIUM (3)
3. ...
```

## Step 5 — Handoff to Tool Auto-Provisioner

For high-priority gaps marked `auto_buildable: true`:
1. Pass the gap to `tool-auto-provisioner` skill
2. Include the proposed solution and estimated effort
3. Tool-auto-provisioner handles build/search/install

For gaps requiring human decision:
1. Include in the summary report
2. Ask one question: "Build, search, or skip?"

## Periodic Review

Every 30 days:
1. Re-scan: have any gaps been closed since last check?
2. Re-prioritize: have usage patterns changed?
3. Remove gaps that are no longer relevant
4. Report: closed gaps, new gaps, remaining queue

## Output Contract

- Updated `knowledge/capability-gaps.json`
- Human-readable gap report
- Handoff to tool-auto-provisioner for auto-buildable gaps
- Decision prompts for non-auto-buildable gaps

## Guardrails

- Don't propose gaps for domains we never work in
- Don't propose building skills that duplicate existing capabilities
- Respect the recycler protocol: search before build
- One gap = one capability. Don't combine unrelated needs

## Integration Points

- **session-postmortem**: Source of skill_gap findings
- **workflow-library**: Missing templates indicate gaps
- **tool-auto-provisioner**: Consumer of auto-buildable gaps
- **knowledge-distiller**: May suggest capabilities based on fact patterns
- **error-pattern-detector**: Recurring manual fixes indicate gaps
