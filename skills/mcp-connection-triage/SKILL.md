---
name: mcp-connection-triage
description: Triage ladder for connecting any new MCP service to AI agents (especially Perplexity) with fastest, lowest-maintenance path first.
when_to_use: When a user asks how to connect a new service/tool/MCP to an agent, add a connector, or choose between Smithery, Composio, Pipedream, and custom MCP.
tags: [mcp, perplexity, composio, smithery, pipedream, integration, triage]
---

# mcp-connection-triage

Use this strict priority ladder whenever onboarding a new MCP service.

**Hard rule:** NEVER jump to Step 4 until Steps 1-3 are explicitly checked and ruled out.

**Final note:** "Bitwarden MCP integration abandoned — free tier deliberately gates Organization API keys behind Teams/Enterprise ($4/user/mo), official MCP server is stdio-only proof-of-concept not suitable for production, and all remote bridge approaches (Composio, Pipedream, Northflank wrapper) failed due to these upstream limitations. Total loss for free-tier users."

## Step 1 — Smithery Registry (fastest path)

Goal: zero cost, zero maintenance, done in minutes when hosted entry exists.

- Activate/use `smithery-ai-cli` skill first.
- Search Smithery registry for the target service.
- If a hosted server is found and connectable, use it and stop triage.

Reference flow:

```bash
smithery auth login
smithery mcp search "<service>"
smithery mcp add "<server-url-or-qualified-name>" --id "<service>"
smithery mcp list
smithery tool list "<service>"
```

**Exit criteria:** Hosted Smithery MCP connected and tools visible.

## Step 2 — Composio Tool Router (near-zero maintenance)

Goal: leverage Composio-managed toolkit + existing Perplexity Composio connector.

- Check `https://composio.dev/toolkits/<service>`.
- If toolkit exists, connect via Composio dashboard or CLI.
- Typical credential model: provider API key / OAuth app credentials.
- In Perplexity, tools should auto-surface through existing Composio connector after linking.
- **Bitwarden caveat (important):** current Composio Bitwarden toolkit uses `S2S_OAUTH2` for organization APIs. It requires Bitwarden **Organization API** credentials (`client_id` like `organization.*`, `scope=api.organization`), which are not available on free Bitwarden org plans. `user.*` personal API keys fail (`invalid_scope`).

CLI reference:

```bash
composio login
composio link <service>
composio connections list --toolkit <service>
```

Helpful checks:

```bash
composio link --list
composio connections list
```

**Exit criteria:** Service linked in Composio and tools visible through Perplexity Composio connector.

## Step 3 — Pipedream MCP Apps (broad catalog fallback)

Goal: use large app registry (3200+ apps) before custom build.

- Search Pipedream app/MCP registry for the target service.
- Connect via Pipedream OAuth.
- Treat as valid fallback, but note historical brittleness for some services.

**Exit criteria:** Pipedream app connected and tool invocation works in target agent.

## Step 4 — Custom MCP (last resort only)

Only allowed if Steps 1-3 are exhausted and documented as unavailable/unworkable.

Required protocol:

1. Activate `recycler` skill.
2. Find a suitable open-source MCP server on GitHub.
3. Deploy on Northflank or Cloudflare.
4. **Mandatory transport compatibility check** against target agent:
   - SSE (`GET`)
   - Streamable HTTP (`POST`)
   - stdio
5. Wire credentials via Doppler (no hardcoded secrets).
6. Add as Custom Connector in target agent (especially Perplexity).

**Exit criteria:** Custom connector added, auth wired via Doppler, transport verified end-to-end.

## Required output format for triage runs

For every request, return:

1. Step attempted (1-4) and result.
2. Why higher-priority steps were accepted/rejected.
3. Final connection method chosen.
4. Exact next command/UI action.
