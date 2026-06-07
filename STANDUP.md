# Agent Standup Checklist

Get a fresh machine/agent online fast with the full motto-skills kit.

## Prerequisites

- `git` — to clone this repo
- `gh` authenticated (`gh auth status`) — for GitHub-aware skills
- `node` + `npm` — for `wrangler` and `vercel`
- `python3` + `pip` — for `scrapfly-sdk` and the Python tools
- `doppler` — secrets are pulled from Doppler/Bitwarden at runtime (never committed)

## One-liner

```bash
git clone https://github.com/lkmotto/motto-skills.git "$HOME/motto-skills" \
  && cd "$HOME/motto-skills" \
  && bash standup.sh
```

`standup.sh` is idempotent — safe to re-run. It installs skills, then installs
`scrapfly-sdk`, `wrangler`, and `vercel` only if missing.

## Verify

```bash
ls ~/.factory/skills        # should show 11 skills
wrangler --version
vercel --version
python3 -c "import scrapfly; print(scrapfly.__version__)"
```

Expected 11 skills:
`api-credential-acquisition`, `cloudflare-browser`, `cloudflare-deploy`,
`docs-audit-worker`, `github-code-awareness`, `github-issues`,
`mcp-connection-triage`, `recycler`, `scrapfly`, `smithery-ai-cli`,
`vercel-deployment`.

## Secrets

Keep all tokens in Doppler/Bitwarden. Never commit tokens or live recipe
files (`*.live-*.json` is gitignored).
