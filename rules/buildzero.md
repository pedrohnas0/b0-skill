---
name: buildzero
description: BuildZero monorepo — services, deploy, testing, and operational patterns
metadata:
  tags: buildzero, monorepo, vercel, cloudflare, ai, auth, deploy
---

## Arquitetura

```
~/dev/buildzero/
  services/
    auth/       Vercel  — users, JWT (signup, login, validate)
    ai/         Vercel  — OAuth PKCE, token mgmt, gate (~100ms)
    ai-worker/  CF Worker — streaming direto pro client (AI SDK + masquerading)
    telegram/   CF Worker — webhook, commands, media, backpressure
    sandbox/    CF Containers — execução de código isolada
    web/        Next.js 16 / Vercel — landing page, signup
  e2e/          testes de integração (por plano)
```

### Fluxo de request (direct connect)

```
Client → POST ai/api/chat (Vercel, ~100ms)
  → valida JWT via auth/api/validate
  → busca claude_tokens do Neon
  → refresh se expirado
  → retorna { workerUrl, sessionToken, accessToken }

Client → POST ai-worker (Cloudflare, conexão longa)
  → valida sessionToken (jose/jwtVerify, 5min TTL)
  → masquerading fetch (OAuth headers, ?beta=true)
  → streamText (AI SDK v6)
  → streaming direto pro client
```

## URLs

| Serviço | Produção |
|---------|----------|
| auth | https://auth-lilac-five-97.vercel.app |
| ai | https://ai-three-pi.vercel.app |
| ai-worker | https://b0-ai-worker.pedrohnas0.workers.dev |
| telegram | https://b0-telegram.pedrohnas0.workers.dev |
| sandbox | https://b0-sandbox.pedrohnas0.workers.dev |

## Deploy

```bash
# Auth e AI — Vercel
cd ~/dev/buildzero/services/auth && vercel deploy --prod
cd ~/dev/buildzero/services/ai && vercel deploy --prod

# Workers — Cloudflare (precisa do token)
CF_TOKEN=$(grep CF_WORKER_TOKEN /home/pedro/dev/.claude/skills/b0-skill/.env | cut -d= -f2)
cd ~/dev/buildzero/services/ai-worker && CLOUDFLARE_API_TOKEN="$CF_TOKEN" bunx wrangler deploy
cd ~/dev/buildzero/services/telegram && CLOUDFLARE_API_TOKEN="$CF_TOKEN" bunx wrangler deploy

# Sandbox — precisa Global API Key (R2 permissions)
CF_KEY=$(grep CF_API_KEY /home/pedro/dev/.claude/skills/b0-skill/.env | cut -d= -f2)
CF_EMAIL=$(grep CF_EMAIL /home/pedro/dev/.claude/skills/b0-skill/.env | cut -d= -f2)
cd ~/dev/buildzero/services/sandbox && CLOUDFLARE_API_KEY="$CF_KEY" CLOUDFLARE_EMAIL="$CF_EMAIL" bunx wrangler deploy
```

Regra: deploy e validar e2e em cloud ANTES de commit.

## Testes

```bash
# Unitários (co-located, por service)
cd ~/dev/buildzero/services/auth && bun test src/
cd ~/dev/buildzero/services/ai && bun test src/
cd ~/dev/buildzero/services/ai-worker && bun test src/

# E2E (contra cloud)
cd ~/dev/buildzero && bun run e2e/run.ts
```

## Env vars

Gerenciadas pela Vercel (auth, ai) e Cloudflare (workers). Pull local:

```bash
# Vercel services
cd ~/dev/buildzero/services/<service> && vercel env pull

# Workers — secrets em .dev.vars (local) e wrangler secret (cloud)
```

| Var | Onde | Propósito |
|-----|------|-----------|
| DATABASE_URL | auth, ai | Neon connection string |
| JWT_SECRET | auth, ai | Compartilhado pra validar tokens |
| SERVICE_TOKEN | ai, worker | Auth service-to-service |
| AUTH_URL | ai | URL do auth service |
| WORKER_URL | ai | URL do worker |

## Vercel runtime constraints

Ver [rules/vercel.md](vercel.md) seção "Serverless runtime constraints" pra detalhes completos.

Resumo:
- `"module": "commonjs"` no tsconfig, SEM `"type": "module"` no package.json
- Deps ESM-only não funcionam: `jose` → `jsonwebtoken`, `@openauthjs` → crypto inline
- Neon errors: código Postgres em `err.cause.code`, não `err.code`

## OAuth Claude (masquerading)

Referência: `~/.memory/references/opencode-anthropic-auth/index.mjs`

### Headers obrigatórios (no Worker)

```
Authorization: Bearer <access_token>
anthropic-beta: oauth-2025-04-20,interleaved-thinking-2025-05-14
anthropic-version: 2023-06-01
user-agent: claude-cli/2.1.2 (external, cli)
URL: /v1/messages?beta=true
```

### Fluxo OAuth PKCE

1. `POST ai/api/oauth-start` → gera PKCE, salva verifier no DB, retorna URL do Claude
2. User autoriza no browser → recebe `code#state`
3. `POST ai/api/oauth-callback` com code → exchange por access_token + refresh_token
4. Tokens salvos no Neon, refresh automático quando expiram

### Renovar tokens

Se refresh_token ainda válido: automático no `chat.ts`.
Se ambos inválidos: precisa refazer OAuth (gerar link, user autoriza).

## Cloudflare Worker

- Account: `8261c0647800836894a376e98a5c4bfc` (Pedrohnas0)
- `wrangler.toml` já tem `account_id`
- Secrets via `wrangler secret put` (precisa `CLOUDFLARE_API_TOKEN`)
- AI SDK v5: `ai@5.0.124`, `@ai-sdk/anthropic@2.0.65`
- Model: `claude-sonnet-4-6`

## Novo service checklist

1. `mkdir ~/dev/buildzero/services/<name>` + `package.json` + `tsconfig.json` (commonjs!)
2. `vercel link --yes` → linka ao projeto Vercel
3. `vercel integration add neon --name b0-<name>-db -m region=gru1` → banco
4. `vercel env pull` → env vars locais
5. Escrever e2e primeiro, depois TDD módulo a módulo
6. Deploy + e2e em cloud → commit
