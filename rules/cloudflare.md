---
name: cloudflare
description: Cloudflare API patterns for DNS, redirects, and zone management
metadata:
  tags: cloudflare, dns, redirect, api
---

## Authentication

Every Cloudflare API request needs these headers:

```
X-Auth-Email: <CF_EMAIL>
X-Auth-Key: <CF_API_KEY>
Content-Type: application/json
```

Use the `cf` helper script when possible. For manual curl, load vars per [rules/env.md](env.md).

## Helper script

```bash
cf zones                              # list zones
cf dns list                           # list DNS records for buildzero.ai
cf dns create <type> <name> <content> # create DNS record
cf pagerule list                      # list page rules
cf pagerule create <match> <url>      # create redirect page rule
```

## Manual curl pattern

```bash
CF_EMAIL=$(grep CF_EMAIL /home/pedro/dev/.claude/skills/meta/.env | cut -d= -f2)
CF_KEY=$(grep CF_API_KEY /home/pedro/dev/.claude/skills/meta/.env | cut -d= -f2)
CF_ZONE=$(grep CF_ZONE_ID /home/pedro/dev/.claude/skills/meta/.env | cut -d= -f2)

curl -s "https://api.cloudflare.com/client/v4/zones/$CF_ZONE/dns_records" \
  -H "X-Auth-Email: $CF_EMAIL" \
  -H "X-Auth-Key: $CF_KEY" \
  -H "Content-Type: application/json"
```

## Current setup

- **Domain**: buildzero.ai
- **Zone ID**: stored in `.env` as `CF_ZONE_ID`
- **Page Rules**:
  - `buildzero.ai/install` → 302 → GitHub raw install.sh
