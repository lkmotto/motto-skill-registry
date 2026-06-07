---
name: recycler
description: Mandatory pre-coding protocol to discover, security/license/compatibility-gate, and safely reuse open-source code before building new atomic functions.
when_to_use: Before writing any new code for an atomic function in appraisal automation or adjacent Python services.
tags: [python, dependencies, licensing, security, compatibility, open-source, appraisal, code-reuse]
---

# recycler

The agent MUST complete all 12 steps below before writing new code for any atomic function.

## 1) DEFINE (atomic function contract)
- Write exactly one sentence in `input -> output` form.
- Keep scope atomic (single responsibility only, no orchestration concerns).
- Example format: `Raw comp address list -> normalized + deduplicated comp matches`.

## 2) SEARCH (MCP-first, 5 surfaces + hybrid GitHub fallback)
Record candidates in a short table (`source`, `package/repo`, `link`, `why_relevant`, `pattern_evidence`, `fallback_used`):
1. **PyPI exact-match**: search package names matching the function purpose.
2. **Curated Awesome Lists**: find high-signal domain libraries.
3. **Grep MCP (primary)**: run structured pattern/snippet hunting over public GitHub for expected signatures and usage ergonomics.
4. **GitHub MCP (primary GitHub path)**: gather repo metadata and file-level evidence using PAT header mode.
5. **GitHub Topics**: use for breadth expansion after initial signal.
- If Grep MCP was not used successfully, set `fallback_used=true` and include fallback evidence.
- If GitHub MCP auth/connectivity fails, immediately switch to Pipedream GitHub tools (`pipedream-all___github-get-repository`, `pipedream-all___github-get-repository-content`, `pipedream-all___github-list-commits`) and record:
  - `github_access_mode = mcp | pipedream_fallback`
  - `fallback_reason`

## 3) MCP METADATA PRE-FILTER (GitHub MCP primary -> Pipedream fallback)
For each candidate repo, fetch before expensive gates (GitHub MCP first, then Pipedream fallback if needed):
- `stars`
- `last_commit` / `pushed_at`
- `default_branch`
- `license_spdx`
- `topics`

Drop candidates early if any are true:
- stars `< 50`
- no commit in last 12 months
- blocked/unknown license

## 4) LICENSE GATE (hard policy)
- **Block**: `GPL-*`, `AGPL-*`, `UNLICENSED`.
- **Allow**: `MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`.
- Determine SPDX from GitHub MCP metadata first; verify with license file when uncertain.
- If SPDX cannot be confidently identified (including `NOASSERTION`), treat as blocked.

## 5) SECURITY GATE (hard policy)
- Check known vulnerabilities for shortlisted candidates using:
  - OSV (`osv.dev`) package queries
  - GitHub Security Advisories / Dependabot alerts metadata (if available)
- **Block** candidate versions with unresolved `critical`/`high` advisories unless a pinned non-vulnerable version is available.
- Record: `vuln_count`, `max_severity`, `safe_version`.

## 6) COMPATIBILITY GATE (hard policy)
- Verify:
  - Python version support matches target runtime(s)
  - Platform compatibility (Windows/Linux/macOS if relevant)
  - Dependency footprint is acceptable for the repo (`transitive deps`, binary/native build requirements)
- Reject candidates requiring unsupported runtimes or high-friction native toolchains unless explicitly approved.

## 7) QUALITY CHECK (minimum bar)
Candidate is acceptable only if all checks pass:
- `>= 50` GitHub stars
- At least one commit within the last 12 months
- README present
- Tests present OR `py.typed` marker OR published type stubs

## 8) BALANCED SCORING + ADAPTATION COST DECISION
- Score candidates **after** hard gates (`license`, `security`, `compatibility`, `quality`) pass:
  - `security_score` (40%): advisories severity, vuln density, safe-version availability
  - `maintainer_health_score` (30%): recency, release cadence, issue/PR closure velocity, contributor continuity proxy
  - `api_ergonomics_score` (30%): API clarity, snippet quality, typed/docs/tests/examples signal
- Compute deterministic total:
  - `total_score = 0.40*security_score + 0.30*maintainer_health_score + 0.30*api_ergonomics_score`
- Minimum pass threshold:
  - `total_score >= 70`
  - and each pillar score `>= 60`
- If adaptation cost is `< 2 hours` and thresholds pass -> **REUSE**.
- If no clean dependency exists and rebuild is `~1-2 days` -> **BUILD**.
- Document the decision call in a short rationale block: `options considered`, `estimated effort`, `final call`.

## 9) THIN ADAPTER PATTERN (mandatory abstraction)
- Never call third-party library APIs directly from business logic.
- Wrap each selected dependency behind an internal interface module:
  - `adapters/<lib>.py`
- Keep adapter surface minimal and swappable.
- Business modules import only the adapter interface, not vendor internals.

```python
# adapters/shapely_geom.py
"""Internal wrapper around Shapely. If we swap geometry libs, only this file changes."""
from shapely.geometry import shape
from shapely.ops import unary_union

def merge_flood_zones(geojson_polygons: list[dict]) -> dict:
    shapes = [shape(p) for p in geojson_polygons]
    return unary_union(shapes).__geo_interface__
```

- Business logic imports ONLY from `adapters/`, never directly from third-party packages.

## 10) FILE-LEVEL FOLLOW-UP (GitHub MCP primary -> Pipedream fallback)
- Use GitHub MCP to inspect candidate repo files before integration; if unavailable, use Pipedream GitHub content endpoints:
  - adapter-relevant source files
  - tests/examples
  - minimal integration points
- Record `files_reviewed` and `why_each_file_mattered` for adapter API shape decisions.

## 11) PATCH BUNDLE OUTPUT (default behavior)
- Produce a ready-to-apply implementation bundle:
  - dependency file diff (`requirements.txt` / `pyproject.toml`)
  - adapter module(s) under `adapters/`
  - minimal call-site integration diff
- Include provenance:
  - Grep MCP snippet references
  - GitHub MCP file references
- Include rollback note (`remove dep + swap adapter import`) in the rationale.

## 12) ATTRIBUTION & COMPLIANCE
- Run:
  - `pip-licenses --format=markdown`
- Append/update:
  - `THIRD_PARTY_LICENSES.md`
- For each `Apache-2.0` dependency, add/update `NOTICE` entries.

## Real Estate Appraisal Automation Reference (Vetted Libraries)

| Library | Primary Use | Typical SPDX | Notes |
|---|---|---|---|
| HomeHarvest | Realtor/MLS-style listing scrape workflows | MIT | Candidate for property/listing ingestion |
| shapely | Geometry ops, parcel boundaries, flood polygon intersection | BSD-3-Clause | Spatial feature engineering and geofencing |
| pdfplumber | Parse appraisal PDFs and extract tabular/text fields | MIT | Useful for form-driven report extraction |
| xgboost | AVM modeling and structured regression/classification | Apache-2.0 | Add NOTICE attribution requirements |
| rapidfuzz | Address/comp fuzzy matching and dedupe | MIT | Fast edit-distance style matching |
| httpx | External API client and service integrations | BSD-3-Clause | Prefer async where pipeline benefits |
| pydantic (v2) | Schema validation + parsing at boundaries | MIT | Keep strict models for ingestion/output |
| tenacity | Retry/backoff around flaky IO | Apache-2.0 | Add NOTICE attribution requirements |

## MCP Suggestions (for live discovery inside Droid)
- **Grep MCP (`https://mcp.grep.app`)**: primary pattern/snippet hunting.
- **Official GitHub MCP (`https://api.githubcopilot.com/mcp/`)**: metadata enrich, license checks, file-level follow-up.

## Output Contract
- Candidate table (source, package/repo, link, SPDX license, stars, last commit, max_severity, compatibility, `security_score`, `maintainer_health_score`, `api_ergonomics_score`, `total_score`, decision)
- Discovery chain trace: `grep_mcp_used`, `github_access_mode`, `github_mcp_used`, `fallback_used`, `fallback_reason`
- Metadata prefilter output: `stars`, `last_commit`, `default_branch`, `license_spdx`, `topics`
- Balanced score block: `security_score`, `maintainer_health_score`, `api_ergonomics_score`, `total_score`, `threshold_passed`
- Chosen path: REUSE | BUILD | WAIT/FORK (with rationale)
- Adapter filename created (e.g. `adapters/rapidfuzz_matcher.py`)
- Patch bundle summary (dependency diff + adapter diff + call-site diff + rollback note)
- Evidence list: Grep MCP snippet refs + GitHub MCP file refs
- THIRD_PARTY_LICENSES.md diff summary
- NOTICE file updates (if any Apache-2.0 added)
- JSON artifact (`recycler_report.json`) with machine-readable fields:
  - `contract`
  - `candidates[]`
  - `discovery_chain`
  - `github_access_mode`
  - `fallback_reason`
  - `metadata_prefilter`
  - `gates` (`license`, `security`, `compatibility`, `quality`)
  - `score` (`security`, `maintainer_health`, `api_ergonomics`, `total`)
  - `signal_evidence[]`
  - `decision`
  - `patch_bundle`
  - `compliance`
