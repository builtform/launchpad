---
stack: hono
pillar: Backend Edge-native TS
type: orchestrate
last_validated: 2026-04-30
scaffolder_command: npm create hono@latest -- --yes --template <template>
scaffolder_command_pinned_version: hono@4
---

# Hono — Knowledge Anchor

## Idiomatic 2026 pattern

Hono 4 is the canonical edge-native TypeScript backend framework, optimized for
Cloudflare Workers, Deno Deploy, Vercel Edge, AWS Lambda, Bun, and Node. The
2026 idiom uses TypeScript-first routing with composable middleware,
type-inferred request/response handlers, and JSX support for HTML rendering
(server-side, not React).

Canonical layout (depends on template):

- `src/index.ts` — Hono app instance + route definitions + export
- `src/middleware/` — custom middleware (auth, logging, CORS)
- `src/routes/` — route modules grouped by resource (modular pattern via
  `app.route('/users', usersRouter)`)
- `wrangler.toml` (Cloudflare Workers template) or `vercel.json` (Vercel Edge)
  or `Dockerfile` (Node container)
- `tsconfig.json` with `"jsx": "react-jsx"` + `"jsxImportSource": "hono/jsx"`
  for JSX rendering
- `package.json` with `hono@4.x` + adapter deps

Routing pattern: `app.get('/path', handler)`, `app.post(...)`, with
`c.req`/`c.res`/`c.json()` context helpers. Request validation via
`@hono/zod-validator` + Zod schemas. RPC client generation via Hono's built-in
type-export (`type AppType = typeof app`).

Version pins: `hono@4.x`, `@hono/zod-validator@0.4+`, `zod@3.x`. Adapter pins
vary per template (`@cloudflare/workers-types@4`, `wrangler@3` for CF; etc.).

## Scaffolder behavior

`npm create hono@latest -- --yes --template <template>` runs the official Hono
CLI in non-interactive mode. Template options: `cloudflare-workers`, `nodejs`,
`bun`, `deno`, `vercel`, `aws-lambda`, `cloudflare-pages`, `fastly`, `netlify`,
`nextjs`. The scaffolder writes:

- `src/index.ts` skeleton with one example route
- `package.json` with framework + adapter pins
- `tsconfig.json` configured for the target runtime
- Adapter-specific config (`wrangler.toml`, `vercel.json`, etc.)
- `.gitignore`
- `README.md` with template-specific dev/deploy instructions

It does NOT install dependencies (headless flag suppresses install). It does
NOT initialize git. Lockfile materializes during the post-scaffold install
step.

## Tier-1 detection signals

- `package.json` with `"hono"` in dependencies
- `src/index.ts` containing `new Hono(` constructor invocation
- `wrangler.toml` (CF Workers) — strong signal when paired with hono dep
- Import statements `from "hono"` or `from "hono/jsx"` across `src/`

## Common pitfalls + cold-rerun gotchas

- Hono 4 changed middleware signature semantics from 3.x; middleware authored
  for 3.x may need `await next()` placement adjustments.
- The `cloudflare-workers` template pins `@cloudflare/workers-types`; updating
  Worker types breaks if the `tsconfig.json` `types` array isn't kept in sync.
- JSX in Hono uses `hono/jsx` runtime, NOT React; importing React JSX
  unintentionally produces runtime errors that look like React mismatches.
- The `--template <name>` flag is required in non-interactive mode; `--yes`
  alone with no template prompts indefinitely (which `--yes` then fails to
  answer).
- RPC client (`hc<AppType>`) requires the type-only export to compile, not
  the runtime app instance; mis-export breaks type inference silently.
- Cloudflare Workers `wrangler dev` uses `--local` by default in v3+; the
  remote-Workers binding mode requires explicit `--remote`.

## Version evolution

- Hono 4 (2024 → stable 2025): new middleware signature; improved JSX
  performance; built-in RPC type-inference; `hono/serve-static` rewritten.
- Hono 3 (2023): Bun adapter; Deno Deploy adapter; Zod validator middleware.
- Hono 2 (2022): edge-first architecture; Cloudflare Workers-native.

Track upstream `create-hono` releases; the template list expands per minor
release as new edge runtimes gain Hono adapters.
