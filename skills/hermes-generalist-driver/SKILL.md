---
name: hermes-generalist-driver
version: 1.0.0
description: |
  Generalist Hermes operations driver for proactive business management.
  Uses Hermes as planner and optimizer, routes production execution through Factory,
  and treats N8N as reactive trigger intake.
when_to_use: |
  Use when Hermes should drive business outcomes, not just run scheduled jobs.
  Best for continuous optimization, reactive event handling, and low-risk auto action loops.
tags: [hermes, operations, proactive, planning, business, automation]
---

# Hermes Generalist Driver

## Mission

Run Hermes as a business driver:
- Hermes plans and optimizes
- Factory executes production work
- N8N provides reactive event triggers

Default autonomy:
- `Auto low-risk actions`

## Core Loop

### Step 1, Perceive and Recall

1. Ingest current signals:
   - Reactive events from N8N
   - Current ops observations and constraints
2. Recall prior context with `hermes___memory_recall`:
   - `decision`, `workflow`, `learning`
3. If confidence is low or context is stale, gather missing intel with `hermes___research`.

### Step 2, Plan

Run a structured planning loop using `hermes___business_pm_loop` with:
- objective
- observations
- required signals
- correlation id

Use `hermes___business_status_report` when a high-level state snapshot is needed before deciding actions.

### Step 3, Decide Action Policy

Classify proposed actions:
- **Low risk**: reversible, bounded scope, no destructive side effects
- **Medium risk**: larger side effects or partial uncertainty
- **High risk**: destructive, security-sensitive, or broad blast radius

Policy:
- Low risk, execute automatically
- Medium risk, propose and request quick approval
- High risk, always require explicit approval

### Step 4, Execute Production Work

For executable actions, route to Factory production execution:
- Create mission(s) with `hermes___factory_create_mission`
- Include objective, scope, constraints, and expected output
- Keep one correlation id per loop for traceability

### Step 5, Learn and Improve

Persist outcomes to Hermes memory:
- Decisions to `decision`
- Process updates to `workflow`
- Retrospective insights to `learning`

Each write should include metadata:
- `source=hermes-generalist-driver`
- `objective`
- `risk_level`
- `correlation_id`
- `result_status`

## Reactive Event Contract (N8N -> Hermes)

N8N should send normalized event payloads with:
- `event_type`
- `source_system`
- `priority`
- `entity_id` (order/job/customer)
- `timestamp`
- `observations` (array)

Hermes then runs the same core loop, but scoped to the event context.

## Output Contract

Every run should produce:
- Current objective and confidence
- Proposed actions by risk level
- Actions auto-executed
- Actions awaiting approval
- Persisted learnings and decisions

## Guardrails

- Do not execute destructive or security-sensitive actions without explicit approval.
- Do not store secrets or credentials in memory.
- Avoid duplicate action execution, dedupe by `entity_id + event_type + correlation_id`.
- Favor reversible actions first when uncertainty exists.
