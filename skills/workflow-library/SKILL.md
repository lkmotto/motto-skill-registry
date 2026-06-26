---
name: workflow-library
version: 1.1.0
description: |
  Extracts recurring multi-step patterns from session history — missions and regular
  tasks alike — generalizes them, and stores as composable workflow templates. New
  tasks can reference templates instead of re-specifying steps. Reduces specification
  burden for known patterns.
when_to_use: |
  Automatically when session-postmortem dispatches a workflow finding. Manually
  when user says "save this workflow", "template this process", "make this reusable".
  Query when planning any significant task — search for matching templates first.
tags: [self-learning, workflows, patterns, templates, automation]
---

# Workflow Library

When you've done something twice, the third time should be a template call, not a
re-specification.

## Activation

- **Auto-trigger**: Receives workflow findings from session-postmortem
- **Manual capture**: "save this workflow", "template this", "make this pattern reusable"
- **Query**: When planning any significant task or mission, search workflows.json for applicable templates

## Step 1 — Identify Workflow Candidates

A workflow is worth templating when:
- It spans 3+ distinct steps
- It has been used in 2+ different sessions or missions
- Its structure is general enough to apply to different contexts (same shape, different content)
- The steps have a clear ordering or dependency

Examples from your stack:
- "Auth preflight → capture → QC → PDF write" (the foundational capture pattern)
- "Connect MCP → verify tools → test call → wire to mission"
- "Search Smithery → fallback to Glama → fallback to MCP Market → custom build"

## Step 2 — Generalize

For each candidate, extract the template:

```json
{
  "id": "workflow-uuid",
  "name": "auth-gated-capture",
  "description": "Authenticate against a data source, capture content, validate, and persist",
  "version": 1,
  "parameters": [
    {"name": "source", "type": "string", "description": "Data source name (ntreis, taxnet, etc.)"},
    {"name": "auth_skill", "type": "skill_ref", "description": "Skill that handles auth for this source"},
    {"name": "capture_skill", "type": "skill_ref", "description": "Skill that performs the capture"},
    {"name": "output_format", "type": "string", "default": "pdf", "description": "Output format"}
  ],
  "steps": [
    {
      "order": 1,
      "name": "Preflight auth",
      "action": "Run {auth_skill} preflight. If fail, retry once. If still fail, abort.",
      "guard": "Must pass before proceeding"
    },
    {
      "order": 2,
      "name": "Capture content",
      "action": "Run {capture_skill} against {source}",
      "depends_on": [1]
    },
    {
      "order": 3,
      "name": "Validate output",
      "action": "Run hybrid QC: check for source anchor, verify content not login/error page",
      "depends_on": [2]
    },
    {
      "order": 4,
      "name": "Persist",
      "action": "Write validated content to {output_format}",
      "depends_on": [3]
    }
  ],
  "failure_policy": "fail_fast",
  "retry_policy": "retry_auth_once",
  "extracted_from": ["session-id-1", "session-id-2"],
  "created": "ISO-8601"
}
```

## Step 3 — Store Template

Append or update in `~/.factory/knowledge/workflows.json`:

- Same `name` → update version, steps, parameters
- New `name` → create new entry

## Step 4 — Compose Workflows

Workflows can reference other workflows as steps:

```json
{
  "name": "full-appraisal-pipeline",
  "steps": [
    {"order": 1, "workflow_ref": "auth-gated-capture", "params": {"source": "ntreis"}},
    {"order": 2, "workflow_ref": "auth-gated-capture", "params": {"source": "taxnet"}},
    {"order": 3, "name": "Merge and cross-reference", "action": "..."}
  ]
}
```

## Step 5 — Use Templates in Missions

When planning any significant task:
1. Load `knowledge/workflows.json`
2. Search by name, description, or tags for matching templates
3. If a template fits: instantiate with parameters rather than re-specifying steps
4. If no template fits: note the gap for post-session extraction

## Periodic Housekeeping

Every 30 days:
1. Check if any workflow templates reference deprecated skills or MCPs
2. Update step instructions if the underlying tools changed
3. Remove templates that haven't been used in 90 days (or mark `deprecated`)

## Output Contract

- Updated `knowledge/workflows.json`
- For queries: return matching templates with instantiation instructions
- For manual captures: confirmation of template saved

## Guardrails

- Templates should be parameterized, not hardcoded to specific values
- Steps should describe what to do, not how to do it (let skills handle implementation)
- Keep templates at the right abstraction level — too specific = useless, too general = confusing

## Integration Points

- **session-postmortem**: Primary source of workflow findings
- **mission-orchestrator**: Consumes templates for mission planning
- **capability-gap-detector**: Missing templates may indicate capability gaps
