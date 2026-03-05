---
name: vercel
description: Vercel projects, Neon databases, and deployment patterns for the lab monorepo
metadata:
  tags: vercel, neon, deploy, database, lab
---

## Team

- **Scope**: pedrohnas0s-projects
- **Dashboard**: https://vercel.com/pedrohnas0s-projects

## Projects

| Project | Service | Directory |
|---------|---------|-----------|
| auth | Auth (users, JWT) | `~/dev/lab/services/auth` |
| ai | AI (Claude proxy, OAuth, streaming) | `~/dev/lab/services/ai` |

## Neon databases

Cada service tem seu banco Postgres isolado no Neon (gru1 — São Paulo).

| Resource | Project | Region |
|----------|---------|--------|
| lab-auth-db | auth | gru1 (São Paulo) |
| lab-ai-db | ai | gru1 (São Paulo) |

Dashboard: https://vercel.com/d/dashboard/integrations/neon

## Env vars

Gerenciadas pela Vercel. Cada project tem:

- `DATABASE_URL` — connection string pooled (via Neon marketplace)
- `DATABASE_URL_UNPOOLED` — connection direta (pra migrations)
- `JWT_SECRET` — shared entre auth e ai
- `SERVICE_TOKEN` — comunicacao service-to-service

Para puxar envs localmente:

```bash
cd ~/dev/lab/services/<service>
vercel env pull    # cria/atualiza .env.local
```

## Adicionando Neon a um projeto

```bash
cd ~/dev/lab/services/<novo-service>
vercel link --yes                                          # linka o diretorio a um project
vercel integration add neon --name <nome> -m region=gru1   # provisiona Neon em São Paulo
vercel env pull                                            # puxa DATABASE_URL pro .env.local
```

Regiões disponíveis: `cle1` (Cleveland), `iad1` (DC), `pdx1` (Portland), `fra1` (Frankfurt), `lhr1` (London), `syd1` (Sydney), `sin1` (Singapore), `gru1` (São Paulo).

Outras opções úteis: `--name` (nome custom), `-m auth=true` (auth built-in), `--plan launch_v3` (plano pago), `--prefix NEON2_` (prefixo nas env vars).

## Deploy

```bash
# Preview deploy
vercel deploy --cwd ~/dev/lab/services/auth
vercel deploy --cwd ~/dev/lab/services/ai

# Production
vercel deploy --prod --cwd ~/dev/lab/services/auth
vercel deploy --prod --cwd ~/dev/lab/services/ai
```

## Bug: trailing `\n` ao adicionar env vars via pipe

Quando se usa `<<<` ou `echo` pra passar o valor pro `vercel env add`, um `\n` é adicionado ao final do valor. Isso causa bugs silenciosos (tokens inválidos, auth falhando).

```bash
# ERRADO — adiciona \n no final do valor
echo "meu-secret" | vercel env add KEY development
vercel env add KEY development <<< "meu-secret"

# CORRETO — printf sem newline
printf '%s' "meu-secret" | vercel env add KEY development
```

Sempre verificar com `vercel env pull` e `grep` se o valor não tem `\n`.

## Serverless runtime constraints

Vercel `@vercel/node` compila TypeScript pra CommonJS. Configurações ESM crasham silenciosamente (`FUNCTION_INVOCATION_FAILED` sem logs úteis).

### tsconfig.json correto

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "esModuleInterop": true,
    "strict": true,
    "skipLibCheck": true,
    "outDir": "dist"
  }
}
```

### O que NÃO usar

- `"type": "module"` no package.json
- `"module": "ESNext"` ou `"module": "NodeNext"` no tsconfig
- `"moduleResolution": "bundler"` no tsconfig
- Deps ESM-only: `jose`, `@openauthjs/openauth`

### Alternativas CJS

| ESM-only | CJS alternativa |
|----------|----------------|
| jose | jsonwebtoken |
| @openauthjs/openauth/pkce | crypto nativo (inline) |

### Neon error handling

```ts
catch (err: any) {
  const code = err?.code ?? err?.cause?.code
  // Postgres error codes em err.cause, não err
}
```

## CLI útil

```bash
vercel env ls                      # listar env vars do project linkado
vercel env add <KEY> development   # adicionar env var
vercel env pull                    # pull .env.local
vercel integration list            # listar integracoes
vercel logs <url>                  # ver logs de um deploy
```
