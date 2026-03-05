---
name: env
description: How to load secrets from .env in the Bash tool
metadata:
  tags: env, secrets, source, bash
---

## The problem

In Claude Code's Bash tool, `source .env` does NOT reliably make variables available to subsequent commands in the same line. This fails silently or causes auth errors:

```bash
# BROKEN — do NOT use
source /home/pedro/dev/.claude/skills/b0-skill/.env && echo "$SUDO_PASSWORD" | sudo -S whoami
```

## The solution

Use `grep | cut` to load individual variables:

```bash
MY_VAR=$(grep MY_VAR /home/pedro/dev/.claude/skills/b0-skill/.env | cut -d= -f2)
```

For multiple variables:

```bash
CF_EMAIL=$(grep CF_EMAIL /home/pedro/dev/.claude/skills/b0-skill/.env | cut -d= -f2)
CF_KEY=$(grep CF_API_KEY /home/pedro/dev/.claude/skills/b0-skill/.env | cut -d= -f2)
CF_ZONE=$(grep CF_ZONE_ID /home/pedro/dev/.claude/skills/b0-skill/.env | cut -d= -f2)
```

## Available variables

| Variable | Purpose |
|----------|---------|
| `SUDO_PASSWORD` | Password for sudo (used by `s` script) |
| `CF_API_KEY` | Cloudflare Global API Key |
| `CF_EMAIL` | Cloudflare account email |
| `CF_ZONE_ID` | Cloudflare zone ID for buildzero.ai |

## Prefer helper scripts

When possible, use the helper scripts (`s`, `cf`) instead of loading vars manually. They handle .env loading internally in Python where there's no quirk.
