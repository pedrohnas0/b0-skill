---
name: planning
description: How to plan, develop, test, and explore codebases with Pedro
metadata:
  tags: planning, tdd, testing, exploration, monorepo
---

# ── Ciclo de Desenvolvimento ───────────────────────────────

3 fases: Planejar → Construir → Corrigir.
A Fase 3 só existe quando E2E falha.
O ciclo termina quando todos os E2E passam.

Regra zero: se não consigo VER o erro, o primeiro fix é na observabilidade, não no código.

## Fase 1 · Planejar

Antes de escrever qualquer código.

```
┌ CONTEXTO
│  → ler plano atual                projects/<projeto>/plans/
│  → ler referências relevantes      references/
│  → ler erros conhecidos            discoveries.md
│
├ DECISÕES
│  → definir abordagem
│  → comparar com referências (OpenCode, OpenClaw, etc.)
│  → registrar no plano: por que essa abordagem
│
├ CONTRATOS
│  → interfaces, types, assinaturas de função
│  → critérios de aceitação E2E (numerados)
│  → TDD por módulo: inputs, outputs esperados
│
└ PLANO FINAL
   → estrutura de diretórios com [NOVO] [EDIT] [MANTER]
   → banco com markers por campo
   → passos de implementação ordenados
   → comandos de verificação exatos
```

## Fase 2 · Construir

Módulo por módulo, nunca tudo de uma vez.

```
┌ TESTE (RED)
│  → escrever unit test do módulo
│  → NÃO rodar pra ver falhar (economia de contexto)
│
├ CÓDIGO (GREEN)
│  → implementação mínima
│  → bun test → GREEN
│  → rodar TODOS os unit tests → sem regressão
│
├ PRÓXIMO MÓDULO
│  → repetir RED → GREEN até todos os módulos prontos
│
├ BUILD
│  → wrangler deploy --dry-run (cada worker)
│
├ DEPLOY
│  → secrets se necessário (wrangler secret put)
│  → wrangler deploy
│
├ E2E
│  → bun run e2e/run.ts
│  ✓ todos passam                     → FINALIZAR
│  ✗ falhou                           → Fase 3
│
└ FINALIZAR
   → git add (arquivos específicos, nunca -A)
   → git commit
   → git push
   → atualizar plano em .memory
```

## Fase 3 · Corrigir

Só entra aqui quando E2E falha. Nunca editar código no escuro.

```
┌ OBSERVAR
│  ✓ erro descritivo e claro          → pula pra ENTENDER
│  ✗ erro genérico / timeout / sem info
│     ├─ adicionar mensagem descritiva no código
│     │  "[erro: gate] 401 unauthorized"
│     │  "[erro: blob] 413 payload too large"
│     │  "[erro: bus] 429 rate limited"
│     ├─ deploy só da observabilidade
│     └─ re-rodar E2E → agora vejo o erro
│
├ ENTENDER
│  → ler o texto do erro (ele é a documentação)
│  → identificar módulo + causa raiz
│  → checar discoveries.md (já conhecido?)
│
├ CONTRATAR (RED)
│  → escrever/ajustar unit test que reproduz
│  → bun test → RED (confirma reprodução)
│
├ CORRIGIR (GREEN)
│  → alterar só o módulo afetado
│  → bun test → GREEN
│  → rodar TODOS os unit tests → sem regressão
│
├ DEPLOY
│  → wrangler deploy --dry-run
│  → wrangler deploy
│
└ E2E
   → bun run e2e/run.ts
   ✓ todos passam                     → FINALIZAR (Fase 2)
   ✗ outro erro                       → volta pro OBSERVAR
```

# ── Regras ──────────────────────────────────────────────────

- Um módulo por vez — não mexer em 3 coisas esperando que "alguma resolva"
- Observabilidade é pré-requisito — se não vejo o erro, o primeiro fix é no log, não no código
- Erros descritivos no código > docs sobre erros — o erro se explica sozinho quando bem escrito
- Deploy só depois que unit tests passam — E2E é validação final, não ambiente de debug
- Commit só quando todos os layers do E2E passam

# ── Formato de planos ──────────────────────────────────────

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
4. **Banco — schema visual** com markers por campo:
   ```
   users (ALTERADO)
     id              text primary key           [MANTER]
     email           text unique                [EDIT] nullable
     account_token   text unique not null       [NOVO]

   sessions (NOVO)
     id              text primary key           [NOVO]

   api_keys                                     [MANTER] sem alterações
   ```
   Markers: `[NOVO]` campo/tabela criado, `[EDIT]` campo alterado, `[MANTER]` sem mudança.
   Se o plano não altera banco, incluir nota "Nenhuma alteração de banco" com tabelas `[MANTER]`.
5. **E2E — critérios de aceitação** numerados, agrupados por domínio
6. **TDD por módulo** — contratos (funções, inputs, outputs)
7. **Passos de implementação** — ordem de execução
8. **Verificação** — comandos exatos

Planos salvos em `.memory/projects/<projeto>/plans/plan-XX.md`. Incrementais.

# ── Testes ──────────────────────────────────────────────────

- **Co-location**: `file.test.ts` ao lado de `file.ts`
- **E2E na raiz do monorepo**: único `e2e/`, cresce plano a plano
- **Unitários co-located** dentro de cada service
- **Runner**: `bun test`

# ── Monorepo ────────────────────────────────────────────────

- `services/` — deploys independentes com bancos próprios
- `packages/` — libs compartilhadas (quando necessário)
- Cada service: `package.json` + `tsconfig.json` (extends raiz) + banco separado

# ── Exploração de codebases ────────────────────────────────

1. `ls` primeiro
2. Ler MDs da raiz (README, CONTRIBUTING, AGENTS)
3. Apresentar resumo
4. Seguir camada por camada sob ordem do user
5. Destacar padrões e termos técnicos quando encontrar

SEMPRE carregar os arquivos-chave diretamente com Read no chat. Subagentes (Explore) servem pra descobrir onde as coisas estão, mas não substituem leitura direta — decisões e comparações saem do contexto carregado via Read.

Subagentes de exploração podem usar Sonnet ou Haiku — são mais rápidos e a diferença em navegação de código é marginal.

# ── Serverless-first ───────────────────────────────────────

- Vercel pra serviços HTTP
- Neon (Postgres serverless) pra banco
- Cloudflare Workers pra long-running (futuro)
- SQLite NÃO funciona em serverless
