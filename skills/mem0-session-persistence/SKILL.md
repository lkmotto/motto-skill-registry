---
name: mem0-session-persistence
version: 1.4.0
description: |
  Hermes-first persistent-session workflow with Mem0 fallback. Recalls context at
  session start, logs key decisions during work, and writes end-of-session summaries
  so new Droid sessions can resume with continuity while minimizing Mem0 usage.
when_to_use: |
  Use when work should carry across sessions, especially for ongoing ops, incident
  handling, host management, and multi-step implementation work.
tags: [hermes, mem0, memory, persistence, sessions, continuity]
---

# Session Persistence (Hermes Primary, Mem0 Fallback)

Default identity:
- `user_id: ms01-droid`
- Base metadata: `project=motto-core`, `host=MS01`, `env=prd`
- `source`: `mem0-session-persistence-skill`

## Step 0, Preflight

1. Verify Hermes memory availability with `hermes___memory_recall` (small query, `limit=1`).
2. If Hermes recall succeeds, set `backend=hermes`.
3. If Hermes recall fails, verify Mem0 tool health with `mem0_list_entities`.
4. If Mem0 succeeds, set `backend=mem0`.
5. If both fail, stop and report that persistence is blocked.
6. Never store or echo API keys in memory content.

## Step 1, Session Start Recall

If `backend=hermes`:
1. Run deterministic recalls using anchored queries:
   - `hermes___memory_recall(category="decision", query="[HERMES-PERSIST][decision]", limit=5)`
   - `hermes___memory_recall(category="workflow", query="[HERMES-PERSIST][session_summary]", limit=5)`
   - `hermes___memory_recall(category="workflow", query="[HERMES-PERSIST][session_handoff]", limit=5)`
2. If any anchor query returns empty, run one fallback broad recall:
   - `hermes___memory_recall(query="session continuity decision summary handoff", limit=10)`
3. Prioritize entries tagged for this workflow (`source=mem0-session-persistence-skill`) and current host/project when present.

If `backend=mem0`:
1. Call `mem0_get_memories` with `filters={"AND":[{"user_id":"ms01-droid"}]}` and `page_size=25`.
2. Prioritize entries with `metadata.source="mem0-session-persistence-skill"`.
3. Extract the latest entries by `metadata.type`: `session_handoff`, `session_summary`, `decision`.
4. Run targeted semantic recalls:
   - `mem0_search_memories(query="current objective next actions", top_k=6, threshold=0, filters={"AND":[{"user_id":"ms01-droid"}]})`
   - `mem0_search_memories(query="current blockers and risks", top_k=6, threshold=0, filters={"AND":[{"user_id":"ms01-droid"}]})`

Then produce a short "Memory Brief" with:
- Current objective
- Carry-over tasks
- Known blockers
- Last decision that affects today's work

## Step 1B, Bottleneck Recall Overlay

Before continuing, fetch active bottlenecks so prior failures are visible early.

If mem0 is available:
1. Run targeted recall:
   - `mem0_search_memories(query="active bottlenecks root cause fix verification reuse hint", top_k=8, threshold=0, filters={"AND":[{"user_id":"ms01-droid"}]})`
2. Keep memories where `metadata.type="bottleneck_event"` or content includes `[BOTTLENECK]`.
3. Add a "Known Bottlenecks" subsection to the Memory Brief:
   - signature
   - root cause
   - validated fix
   - reuse hint skill

If mem0 is unavailable:
1. Continue without this overlay and note `bottleneck_recall=skipped`.

## Step 2, Decision Checkpoints (During Session)

Whenever a consequential decision is made, append one memory with one sentence on what was chosen and why.

If `backend=hermes`:
- Use `hermes___memory_store(category="decision", content=..., metadata=...)`
- Metadata should include: `source`, `type=decision`, `scope`, `host`, `project`, `marker`
- Content format should begin with deterministic anchor:
  - `[HERMES-PERSIST][decision] <one-sentence decision>`

If `backend=mem0`:
- Use `mem0_add_memory` with equivalent metadata
- Capture returned `event_id` and poll `mem0_get_event_status` until `SUCCEEDED`, `FAILED`, or timeout

## Step 3, End-of-Session Writeback

Append 2 memories:
1. Session summary (what changed, what remains)
2. Next-step handoff (ordered next actions + owner/context)

Keep each memory concise and searchable.

If `backend=hermes`:
- Write both entries with `hermes___memory_store(category="workflow", ...)`
- Use metadata types `session_summary` and `session_handoff`
- Content format should begin with anchors:
  - `[HERMES-PERSIST][session_summary] <summary text>`
  - `[HERMES-PERSIST][session_handoff] <handoff text>`

If `backend=mem0`:
- Write both entries with `mem0_add_memory`
- Record `event_id` values and poll status before declaring complete

## Output Contract

After running this skill, return:
- Backend used (`hermes` or `mem0`)
- Memory brief used for the session
- Known bottlenecks included in brief (count)
- Count of memories read
- Count of memories written
- Event status summary (`SUCCEEDED` / `PENDING` / `FAILED`) for Mem0 path
- Whether fallback was used and why
- Any persistence errors encountered

## Guardrails

- Never store secrets, tokens, passwords, or raw credentials.
- Prefer concise factual memory text over verbose transcripts.
- Do not duplicate identical memories, update only when state changed.
- Prefer Hermes as primary storage to reduce Mem0 free-tier usage.
