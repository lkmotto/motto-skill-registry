---
name: frontier-search
description: Use Tavily and Perplexity for high-value frontier research in spec mode, mission kickoff, and solution exploration. Route spec-mode search through Tavily with dedupe, then run WebSearch plus Perplexity deep research before mission planning.
user-invocable: true
disable-model-invocation: false
---

# Frontier Search

Use this skill when frontier web intelligence materially improves planning quality.

## Use when

- Entering spec mode for a complex initiative
- Starting a mission
- Comparing solution approaches or improvement paths
- Researching regulations, company intel, fast-moving best practices, or recent vendor docs

## Do not use when

- The task is local-only (small refactor, direct bugfix, formatting)
- Existing repository context is already sufficient

## Execution policy

### Spec mode policy (all spec-mode work)

1. Treat Tavily as the default search engine for spec mode.
2. Route baseline search through `tavily_search` (1 query by default).
3. Minimize redundancy:
   - keep a running set of seen URLs and domains during the spec pass
   - avoid repeating near-identical queries
   - only extract pages that add new evidence
4. If Tavily MCP tools are unavailable, use native `WebSearch` as fallback.
5. Escalate to Perplexity only when decision risk or source conflict requires deeper validation:
   - `perplexity_search`, then `perplexity_ask`
   - `perplexity_research` only when unresolved or high-impact

### Mission preflight policy (before starting a mission)

1. Run native `WebSearch` to get broad current coverage.
2. Run `perplexity_research` for deep, decision-grade synthesis.
3. Merge and deduplicate findings into a single plan-ready brief.
4. Prefer official docs, primary sources, and recent authoritative references.

## Required output format

### Intel Brief

- Decision-ready summary
- Key findings (bullets)
- Recommended next action
- Sources with links

### Cost and Latency

- Modes used: `tavily`, `websearch`, `search`, `ask`, `research`
- Query count by mode
- Elapsed time per query
- Citation quality note
- Cost estimate:
  - if token usage is returned, provide estimate
  - otherwise output: `cost: unavailable from tool response` and assign spend-risk (`low`, `medium`, `high`) based on mode mix

## Guardrails

- Do not state nontrivial facts without citations.
- Call out uncertainty and conflicting sources explicitly.
- Keep Tavily as the mandatory default in spec mode unless unavailable.
- Before mission kickoff, require both `WebSearch` and `perplexity_research`.
- Keep research proportional to decision impact.
