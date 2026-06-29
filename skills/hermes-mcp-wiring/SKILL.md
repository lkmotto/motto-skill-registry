---
name: hermes-mcp-wiring
description: Wire and manage Hermes ↔ Factory bidirectional MCP communication. Use when connecting, verifying, or debugging Hermes MCP from Factory, or when setting up Hermes on a new host.
---

# Hermes ↔ Factory MCP Wiring

Hermes is a persistent meta-layer agent acting as project manager, running on a Docker container. It communicates with Factory bidirectionally via MCP and REST.

## Hosting

| Detail | Value |
|---|---|
| Current host | Hostinger VPS 1511806 (`srv1511806.hstgr.cloud`) |
| Port | 8150 (HTTP MCP) |
| Code repo | `https://github.com/lkmotto/hermes-supervisor` |
| Source | `C:\Users\lkmot\projects\hermes` |
| Secrets | Doppler `motto-core/prd` |

## Connection Commands

### Connect Hermes to Factory (Factory → Hermes MCP)
```bash
droid mcp add hermes https://srv1511806.hstgr.cloud:8150 --type http
```
If MCP auth is enabled on Hermes, add the auth header:
```bash
droid mcp add hermes https://srv1511806.hstgr.cloud:8150 --type http --header "Authorization: Bearer <MOTTO_MCP_AUTH_TOKEN>"
```

### Remove Hermes from Factory
```bash
droid mcp remove hermes
```

### Verify connection
```bash
droid mcp list
```
Look for `hermes  http  enabled  [user]` in the output.

## Tools Hermes Exposes to Factory

When connected via MCP, Factory can call these Hermes tools:

### Research & Planning
| Tool | Description | Risk |
|---|---|---|
| `research` | Deep research via Perplexity Sonar Pro with citations | read-only |
| `plan` | Generate structured execution plan using Perplexity, stores in memory | memory write |

### VPS Management (Hostinger-specific)
| Tool | Description | Risk |
|---|---|---|
| `vps_info` | VPS state, resources, IPs, config | read-only |
| `vps_metrics` | CPU/RAM/disk usage over N days | read-only |
| `vps_projects` | List all Docker Compose projects | read-only |
| `vps_project_logs` | Recent logs from a Docker project | read-only |
| `vps_restart_project` | Restart a Docker project | hermes-scoped mutation |
| `vps_stop_project` | Stop a Docker project | dangerous-global |
| `vps_start_project` | Start a Docker project | hermes-scoped mutation |
| `vps_deploy` | Deploy/redeploy a Docker project | hermes-scoped mutation |
| `vps_snapshot` | Create VPS snapshot (overwrites existing) | dangerous-global |
| `vps_restart` | Full VPS restart | dangerous-global |

### Memory & Knowledge
| Tool | Description | Risk |
|---|---|---|
| `memory_store` | Store fact/decision/knowledge in SQLite | memory write |
| `memory_recall` | Search memory by category + query | read-only |

### Fleet & Business Ops
| Tool | Description | Risk |
|---|---|---|
| `fleet_get_run_details` | Retrieve fleet run details and artifacts | read-only |
| `business_management_cycle` | Full fleet cycle: record, signal, learn | memory write |
| `business_pm_loop` | Perceive/recall/plan/propose/learn cycle | memory write |
| `business_status_report` | High-level ops status with focus/risks/next steps | read-only |

### Perplexity Integration
| Tool | Description | Risk |
|---|---|---|
| `perplexity_ingest` | Push Perplexity research context into Hermes memory | memory write |
| `perplexity_shadow_status` | Retrieve recent Perplexity shadow observations | read-only |

### Factory API (v2.2+, requires FACTORY_API_KEY env var)
| Tool | Description | Risk |
|---|---|---|
| `factory_list_sessions` | List recent Factory Droid sessions | read-only |
| `factory_get_session` | Get session by ID with optional messages | read-only |
| `factory_create_mission` | Create new Factory mission from Hermes | memory write |

### Tool Risk Levels
- **read-only**: Always allowed, no confirmation needed
- **memory write**: Allowed, writes to Hermes SQLite only
- **hermes-scoped mutation**: Requires `confirm=true` + `project="hermes"` + `validation_evidence` + `approval`
- **dangerous-global**: Requires `confirm=true` + explicit `approval`

## Reverse Direction: Hermes → Factory

Hermes calls Factory through two channels:

### 1. Fleet MCP Client (built-in)
Hermes connects to Factory's MCP endpoint as a client via `FleetClient` (see `src/fleet.ts`). Configuration:
- `MOTTO_MCP_URL` — Factory MCP endpoint
- `MOTTO_MCP_AUTH_TOKEN` — auth token for Factory MCP

Fleet tools Hermes calls on Factory:
- `register_agent`, `heartbeat`, `record_run_start`, `record_run_end`
- `record_event`, `record_artifact_content`, `get_run`
- `signal_intent`, `consume_open_intents`
- `queue_local_task`, `get_local_task`, `list_local_tasks`
- `request_capability`

### 2. Factory REST API (v2.2+)
Hermes can call Factory's REST API for sessions and missions:
- `GET /api/v0/sessions` — list sessions
- `GET /api/v0/sessions/:id` — get session
- `GET /api/v0/sessions/:id/messages` — get session messages
- `POST /api/v0/missions` — create mission

Requires `FACTORY_API_KEY` env var. Client code at `src/factory-client.ts`.

## Doppler Secrets Used

All in Doppler `motto-core/prd`:
- `HOSTINGER_API_TOKEN` — Hostinger API
- `PERPLEXITY_API_KEY` — Perplexity Sonar API
- `MOTTO_MCP_AUTH_TOKEN` — Hermes MCP auth + Fleet MCP auth
- `FACTORY_API_KEY` — Factory REST API
- `TELEGRAM_BOT_TOKEN` (or `HERMES_TELE_BOT_TOKEN`) — Telegram bot

## Migration to New Host

When moving Hermes to a new machine (e.g., ms01):

1. **Copy the database**: Extract `hermes.db` from the Docker volume `hermes_data` on the old host
2. **Deploy compose-vps.yml** on the new host — it auto-clones from GitHub and auto-builds
3. **Set env vars**: `HOSTINGER_API_TOKEN`, `PERPLEXITY_API_KEY`, `MOTTO_MCP_AUTH_TOKEN`, `FACTORY_API_KEY`, `HERMES_MCP_AUTH_TOKEN`
4. **Reconnect Factory**: `droid mcp add hermes https://<new-host>:8150 --type http`
5. **Replace VPS tools**: The `vps_*` tools target Hostinger API. Replace with local machine management for non-Hostinger hosts.

## Verification Checklist

After any wiring change, verify:
1. `droid mcp list` shows `hermes http enabled`
2. From a Factory session, call `vps_info` or `memory_recall` — should return data
3. Check Hermes health: `curl https://srv1511806.hstgr.cloud:8150/health`
4. Check VPS Docker status via Hostinger API for hermes project
5. Run `hermes doctor` on the VPS if accessible
