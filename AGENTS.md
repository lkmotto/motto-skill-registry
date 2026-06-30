# AGENTS.md for motto-skill-registry

## Overview
Portable personal Factory skills bundle for fast agent stand-up on new machines. Contains reusable Droid skills for browser automation, Steel sessions, Cloudflare deployment, and more.

## Development

### Setup
```bash
# Install skills to local Factory
bash install.sh
```

### Stand Up (full agent readiness)
```bash
bash standup.sh
```

### Test
Manual verification of skill installation and functionality.

### Lint
```bash
npx prettier --check "**/*.{yml,yaml,md,json}"
```

## Deployment
Deployed as a GitHub repository cloned to agent machines. Skills symlinked into `~/.factory/skills/`.
