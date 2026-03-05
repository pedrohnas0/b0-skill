---
name: planning
description: How to plan, develop, test, and explore codebases with Pedro
metadata:
  tags: planning, tdd, testing, exploration, monorepo
---

## TDD adaptado pra AI

### Red (contratos + testes)
1. Reler arquivos de referência (contexto fresco — essencial em sessões longas)
2. Escrever contratos (types, interfaces, assinaturas)
3. Escrever testes unitários
4. NÃO rodar pra ver falhar (economia de contexto e tokens)

### Green (implementação mínima)
1. Escrever código mínimo
2. Rodar `bun test`

### Refactor
Normal TDD tradicional.

## Formato de planos

Todo plano deve conter:

1. **Context** — por que, problema, resultado esperado
2. **Referências** — paths completos dos arquivos relevantes
3. **Estrutura de diretórios** com marcadores:
   ```
   services/
     auth/
       src/
         db.ts              [NOVO] schema Drizzle
         jwt.ts             [EDIT] adicionar refresh
         old.ts             [DELETE] absorvido
       api/
         login.ts           [MANTER]
   ```
4. **E2E — critérios de aceitação** numerados, agrupados por domínio
5. **TDD por módulo** — contratos (funções, inputs, outputs)
6. **Passos de implementação** — ordem de execução
7. **Verificação** — comandos exatos

Planos salvos em `.memory/projects/<projeto>/plans/plan-XX.md`. Incrementais.

## Testes

- **Co-location**: `file.test.ts` ao lado de `file.ts`
- **E2E na raiz do monorepo**: único `e2e/`, cresce plano a plano
- **Unitários co-located** dentro de cada service
- **Runner**: `bun test`

## Monorepo

- `services/` — deploys independentes com bancos próprios
- `packages/` — libs compartilhadas (quando necessário)
- Cada service: `package.json` + `tsconfig.json` (extends raiz) + banco separado

## Exploração de codebases

1. `ls` primeiro
2. Ler MDs da raiz (README, CONTRIBUTING, AGENTS)
3. Apresentar resumo
4. Seguir camada por camada sob ordem do user
5. Destacar padrões e termos técnicos quando encontrar

## Serverless-first

- Vercel pra serviços HTTP
- Neon (Postgres serverless) pra banco
- Cloudflare Workers pra long-running (futuro)
- SQLite NÃO funciona em serverless
