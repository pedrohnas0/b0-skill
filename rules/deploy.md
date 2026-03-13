---
name: deploy
description: How to deploy buildzero services using the deploy script
metadata:
  tags: deploy, vercel, cloudflare, wrangler, buildzero
---

## O script deploy

`deploy` roda o pipeline completo: test → deploy (paralelo) → verify.

```bash
deploy                    # full: test → deploy all → verify
deploy auth ai-worker     # deploy serviços específicos
deploy --no-test          # pular unit tests
deploy --dry-run          # mostrar plano sem executar
```

## Ordem de deploy

`observe → auth → ai → ai-worker → telegram → web`

Serviços deployam em **paralelo**. Dependências:
- `auth` precisa estar up antes de `ai` (validates channels)
- `ai` precisa estar up antes de `ai-worker` (gate endpoint)
- Vercel services: `vercel deploy --prod`
- CF Workers: `bunx wrangler deploy` (precisa CF_API_KEY e CF_EMAIL no .env da b0-skill)

## Quando deployar o quê

| Mudou | Deploy |
|-------|--------|
| `services/observe/` | `deploy observe` |
| `services/auth/` | `deploy auth` |
| `services/ai/` | `deploy ai` |
| `services/ai-worker/` | `deploy ai-worker` |
| `services/telegram/` | `deploy telegram` |
| `services/web/` | `deploy web` |
| `packages/sdk/` ou `packages/log/` | `deploy ai-worker telegram` (consumers) |
| `packages/obs/` | `deploy observe ai-worker telegram` (consumers) |
| Múltiplos | `deploy` (todos) |

## Verificação

Após deploy, o script checa health endpoints de todos os serviços.
Usa `User-Agent: b0-deploy/1.0` (Cloudflare bloqueia user-agent padrão do urllib).

Health endpoints:
- observe: `/health`
- auth: `/api/health`
- ai: `/api/health`
- ai-worker: `/health`
- telegram: `/health`
- web: `/` (200 = ok)

## Após deploy

```bash
bun test:smoke                        # contratos API (~3.5s)
bun tests/int/health.ts               # serviços + deps externas
bun tests/e2e/telegram/message.ts     # pipeline completo (~15-25s)
```

## Troubleshooting

- **CF Worker falha**: verificar CF_API_KEY e CF_EMAIL no .env da b0-skill
- **Vercel falha**: rodar `vercel deploy --prod` manualmente no dir do serviço pra ver output completo
- **Health check falha**: cold start — esperar 5s e verificar de novo
- **TS warnings**: deploy reporta; não bloqueiam build mas devem ser corrigidos
