---
name: mcp-hub
description: Unified multi-registry MCP discovery and provisioning. Use to search for MCP servers/tools across Smithery, the official MCP Registry, Glama, MCP Market, Pipedream, and Composio (Rube) in one pass, rank results, and install the best one by source, routing execution through the Smithery Toolbox to keep thousands of services reachable without bloating context.
metadata: { "openclaw": { "requires": { "bins": ["pwsh", "smithery"] } } }
---

# MCP Hub

One command surface over every major MCP publisher. Discovery and provisioning are
unified; runtime execution stays on the Smithery Toolbox (`search_toolbox` + `execute`)
plus each backend's own search-then-hydrate so schemas never flood model context.

## Architecture

- **Discovery + provisioning**: `~/.factory/bin/mcp-discovery.ps1`, driven by
  `~/.factory/mcp-discovery.policy.json` (sources, ranking, routing).
- **Runtime hubs** (context-lean, search-then-hydrate):
  - `smithery-toolbox` — `search_toolbox(query)` + `execute(code)` over everything installed.
  - `composio-rube` (https://rube.app/mcp) — `RUBE_SEARCH_TOOLS` / `RUBE_CREATE_PLAN` over ~1000+ toolkits.
  - `pipedream-all` (https://remote.mcp.pipedream.net) — sub-agent / app-discovery over 3000+ apps.
- Backends + routing live in `~/.factory/mcp.json` and `~/.factory/mcp-routing.policy.json`.

## Sources searched

| Source        | How                                                             | Auth env                  |
|---------------|-----------------------------------------------------------------|---------------------------|
| smithery      | `smithery --json mcp search`                                    | smithery auth login       |
| mcp_registry  | `registry.modelcontextprotocol.io/v0/servers?search=`           | none                      |
| glama         | Glama API (key) else HTML scrape                                | GLAMA_API_KEY             |
| mcp_market    | `MCP_MARKET_API` template                                       | MCP_MARKET_API            |
| pipedream     | `api.pipedream.com/v1/connect/apps?q=` (exhaustive only)        | PIPEDREAM_API_KEY         |
| composio      | `backend.composio.dev/api/v3.1/toolkits?search=` (exhaustive)   | COMPOSIO_API_KEY          |

Keys resolve via env or Doppler (`-UseDoppler`, project `motto-core`, config `prd`).
Pipedream + Composio are gated behind `-Exhaustive` by default (huge catalogs); flip
`routingRule.queryAggregatorsWhenExhaustiveOnly` to `false` to always include them.

## Workflow

```powershell
$hub = "$env:USERPROFILE\.factory\bin\mcp-discovery.ps1"

# 1. Search (smithery + registry + glama). Add -Exhaustive for pipedream + composio.
& $hub -Command search -Query "gmail" -Exhaustive -Limit 20

# 2. Top-5 recommendation (same flags)
& $hub -Command recommend -Query "gmail" -Exhaustive

# 3. Provision the winner by source (-WhatIf to preview, idempotent)
& $hub -Command add -Source smithery -ServerUrl "https://server.smithery.ai/<ns>/<name>" -Id "<service>"
& $hub -Command add -Source composio                       # adds composio-rube (OAuth at first use)
& $hub -Command add -Source pipedream -QualifiedName "gmail" # realizes pipedream-all (needs creds)
```

### Provisioning routing
- **smithery / glama / mcp_registry / mcp_market**: `smithery mcp add <url> --id <id>` into the toolbox namespace (stays behind `search_toolbox`).
- **composio**: adds/enables `composio-rube` http server in `mcp.json`; complete OAuth in client.
- **pipedream**: adds `pipedream-all` http server; enabled only when `PIPEDREAM_PROJECT_ID`, `PIPEDREAM_EXTERNAL_USER_ID`, and `PIPEDREAM_API_KEY` are present (else added disabled).

## Output shape

`search`/`recommend` emit JSON with `counts` per source, `broadenedSearchUsed`,
`aggregatorsQueried`, and ranked `results`/`recommendations`
(`{source,name,qualifiedName,description,url,score}`). `add` emits an action report.

## Guardrails
- Never hardcode keys; use env or Doppler references only.
- Adapters fail soft (return empty) so one dead registry never breaks a search.
- `add` writes are idempotent; use `-WhatIf` first for anything you're unsure about.
- Vet OSS servers via `recycler` before connecting untrusted sources.
