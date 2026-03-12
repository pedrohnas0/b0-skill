---
name: neon
description: How to query Neon databases and avoid common pitfalls with @neondatabase/serverless
metadata:
  tags: neon, database, postgres, sql, buildzero
---

## Querying the database

Use the `db` script:

```bash
db ai "SELECT COUNT(*) FROM sessions"
db auth "SELECT email, role FROM users LIMIT 10"
```

Auto-pulls `DATABASE_URL` from Vercel on first use. Uses Neon HTTP API directly (Python urllib, no external deps).

## @neondatabase/serverless pitfalls

The `neon()` function only works as a **tagged template**. Function call syntax does NOT work:

```typescript
const sql = neon(url)

// WORKS — tagged template
const rows = await sql`SELECT * FROM users WHERE id = ${id}`

// BROKEN — throws at runtime
const rows = await sql('SELECT * FROM users WHERE id = $1', [id])
```

### Dynamic conditions

Use the NULL-check pattern instead of building SQL strings:

```typescript
const userFilter = filterByUser ? targetUserId : null
const statusFilter = status || null

const rows = await sql`
  SELECT * FROM sessions
  WHERE parent_session_id IS NULL
    AND (${userFilter}::text IS NULL OR user_id = ${userFilter})
    AND (${statusFilter}::text IS NULL OR status = ${statusFilter})
  ORDER BY last_activity_at DESC NULLS LAST
  LIMIT ${limit} OFFSET ${offset}
`
```

When `$x` is NULL, `($x::text IS NULL)` → TRUE → condition skipped.

### Vercel .env.local quirk

`vercel env pull` wraps values in quotes. Strip them:

```bash
DB_URL=$(grep '^DATABASE_URL=' .env.local | sed 's/^DATABASE_URL=//' | tr -d '"')
```

### Running bun scripts with neon

`@neondatabase/serverless` is installed in `services/web/`. Run from there:

```bash
cd ~/dev/buildzero/services/web && bun script.ts
```
