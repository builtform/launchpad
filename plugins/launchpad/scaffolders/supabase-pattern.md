---
stack: supabase
pillar: Backend Managed
type: orchestrate
last_validated: 2026-04-30
scaffolder_command: supabase init
scaffolder_command_pinned_version: supabase-cli@2
---

# Supabase — Knowledge Anchor

## Idiomatic 2026 pattern

Supabase is a managed Postgres + Auth + Storage + Realtime + Edge Functions
platform. The 2026 idiom uses the Supabase CLI v2 for local-first development
(local Postgres + Studio via Docker), declarative SQL migrations stored in
`supabase/migrations/`, Row Level Security (RLS) enabled by default on every
exposed table, and TypeScript-generated types via `supabase gen types
typescript`.

Canonical layout from `supabase init`:

```
supabase/
  config.toml         # project config (db port, studio port, edge functions)
  seed.sql            # optional initial data
  migrations/         # timestamped SQL migrations
  functions/          # Edge Functions (Deno)
    <name>/
      index.ts
  .gitignore          # ignores .branches, .temp
.env.local            # SUPABASE_URL + SUPABASE_ANON_KEY for local stack
```

Production-grade pattern adds:

- `lib/supabase/client.ts` — browser client (`createBrowserClient`)
- `lib/supabase/server.ts` — server client (`createServerClient` with cookie
  handling for SSR auth)
- `lib/supabase/middleware.ts` — Next.js middleware for session refresh
- `database.types.ts` — generated types committed to git
- RLS policies in `supabase/migrations/` declaring access rules per table

Version pins:

- `supabase` CLI v2.x (binary, not npm)
- `@supabase/supabase-js@2.45+` (JS client)
- `@supabase/ssr@0.5+` (SSR adapters for Next, Remix, etc.)
- Local Docker: `supabase/postgres:15.x` (CLI manages this)

## Scaffolder behavior

`supabase init` creates the `supabase/` directory with `config.toml`,
empty `migrations/`, empty `functions/`, and `seed.sql`. It is **interactive**
in default mode: prompts for "Generate VS Code settings for Deno?", "Generate
IntelliJ Settings for Deno?". This is the `mixed-prompts` flavor — the
LaunchPad scaffolder pipes canned `n\nn\n` answers via stdin to suppress both
prompts, OR uses `supabase init --workdir .` with an answer-file (CLI v2.x
supports `SUPABASE_INIT_*` env vars to skip prompts non-interactively).

**Pre-bootstrap requirement**: `supabase init` does NOT require auth (no
`supabase login` needed for init alone). Local stack startup (`supabase
start`) requires Docker running; remote project linking (`supabase link
--project-ref <ref>`) requires `supabase login`.

After `supabase init`, the canonical follow-ups (LaunchPad emits these as
post-scaffold customization):

1. `supabase start` — boots local Docker stack (Postgres + Studio + Auth +
   Storage). Skipped at scaffold time; user runs manually when ready.
2. Install JS clients: `pnpm add @supabase/supabase-js @supabase/ssr`
3. Materialize `lib/supabase/{client,server,middleware}.ts` per pattern
4. Generate types: `supabase gen types typescript --local > database.types.ts`

No lockfile from supabase init itself; lockfile from sibling Next.js install.

## Tier-1 detection signals

- `supabase/config.toml` at repo root or under `supabase/`
- `supabase/migrations/` directory with `.sql` files
- `package.json` with `@supabase/supabase-js` or `@supabase/ssr` in deps
- `.env.local` with `SUPABASE_URL=` or `NEXT_PUBLIC_SUPABASE_URL=`
- `database.types.ts` generated types file at repo root or `lib/`

## Common pitfalls + cold-rerun gotchas

- `supabase init` interactive prompts are the #1 scaffolder snag; non-
  interactive answer-passing is required for CI/headless flows. The CLI v2.x
  `--workdir` flag does NOT suppress prompts; prompts must be answered via
  stdin pipe or env vars (CLI changes behavior here per minor release).
- `supabase start` requires Docker running and ~3 GB free disk; first start
  pulls multi-GB images.
- RLS is OFF by default on tables created via raw SQL migration; the CLI
  supports `alter table ... enable row level security;` but doesn't add it
  automatically. Forgetting RLS exposes data to anon-key clients — a frequent
  security incident.
- `@supabase/ssr` (v0.5+) replaced the deprecated `@supabase/auth-helpers-*`
  packages; pre-2024 Next.js + Supabase tutorials reference deprecated APIs.
- Anon key vs service-role key: anon key is safe for client-side; service-role
  key BYPASSES RLS and must NEVER be exposed client-side.
- Local stack auth emails go to Inbucket (http://localhost:54324) by default;
  not real email delivery until configured.
- Edge Functions run on Deno runtime; Node.js syntax compatibility is partial.

## Version evolution

- Supabase CLI v2 (2024): renamed many subcommands; `supabase functions deploy`
  no longer requires `--no-verify-jwt` for public routes; declarative database
  schema diffing improvements.
- Supabase CLI v1 (2023): first stable; introduced declarative migrations.
- `@supabase/ssr` (2024): replaces auth-helpers-nextjs/remix/sveltekit;
  cookie-based session refresh.

Track upstream Supabase CLI releases; the scaffolder's prompt flow has shifted
twice in v2.x and is the most-likely freshness-drift surface.
