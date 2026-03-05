---
name: b0-skill
description: Bootstrap toolkit for dev environments. Use this skill whenever you need to run commands with sudo, install packages, interact with the Cloudflare API, copy directories from GitHub, or manage this WSL environment. Also use it when you need to load secrets from .env files in the Bash tool — there's a known quirk documented here.
---

# b0-skill

Dev environment toolkit for WSL. Provides helper scripts, secret management, and operational rules.

**Repo**: https://github.com/pedrohnas0/b0-skill
**Install**: `curl -fsSL buildzero.ai/install | sudo bash`
**Location**: `/home/pedro/dev/.claude/skills/meta/`

## Secrets

All secrets live in `.env` (gitignored). Before using any secret in the Bash tool, read [rules/env.md](rules/env.md) — there's a critical quirk with how `source` works.

## Rules

| File | When to read |
|------|-------------|
| [rules/env.md](rules/env.md) | Loading secrets from `.env` in the Bash tool. Read this FIRST if you need any env var. |
| [rules/system.md](rules/system.md) | Running commands with sudo, installing packages with apt |
| [rules/cloudflare.md](rules/cloudflare.md) | DNS, redirects, or any Cloudflare API operation |
| [rules/self.md](rules/self.md) | Updating this skill itself (commit, push, test) |

## Scripts

| Command | What it does |
|---------|-------------|
| `s <cmd>` | Runs command with sudo (reads password from .env) |
| `ghcp <repo> <path> <dest>` | Copies a directory from GitHub to local |
| `cf <action> [args]` | Cloudflare API helper |
| `b0` | Environment status and health check |

All scripts are in `scripts/` and symlinked to `~/.local/bin/`.
Shared UI module: `scripts/ui.py` — imported by all scripts for consistent output.
