---
stack: hono
pillar: Backend Edge-native TS
type: orchestrate
last_validated: 2026-08-01
scaffolder_command: npm create hono@latest <target-dir> -- --template <template> --pm npm
scaffolder_command_pinned_version: create-hono@0.19 (framework: hono@4)
---

# Hono — Knowledge Anchor

## Idiomatic 2026 pattern

Hono 4 (current 4.12.x; no v5 exists) is the canonical edge-native TypeScript
backend framework, optimized for
Cloudflare Workers, Deno Deploy, Vercel Edge, AWS Lambda, Bun, and Node. The
2026 idiom uses TypeScript-first routing with composable middleware,
type-inferred request/response handlers, and JSX support for HTML rendering
(server-side, not React).

Canonical layout (depends on template):

- `src/index.ts` — Hono app instance + route definitions + export
- `src/middleware/` — custom middleware (auth, logging, CORS)
- `src/routes/` — route modules grouped by resource (modular pattern via
  `app.route('/users', usersRouter)`)
- `wrangler.jsonc` (Cloudflare Workers template; the template no longer ships
  `wrangler.toml`) or `vercel.json` (Vercel Edge) or `Dockerfile` (Node
  container)
- `tsconfig.json` with `"jsx": "react-jsx"` + `"jsxImportSource": "hono/jsx"`
  for JSX rendering
- `package.json` with `hono@4.x` + adapter deps

Routing pattern: `app.get('/path', handler)`, `app.post(...)`, with
`c.req`/`c.res`/`c.json()` context helpers. Request validation via
`@hono/zod-validator` + Zod schemas, or `@hono/standard-validator` when the
schema library should stay swappable (Standard Schema: zod / valibot / arktype).
RPC client generation via Hono's built-in type-export
(`type AppType = typeof app`).

Version pins: `hono@4.12.x`, `@hono/zod-validator@0.9.x` (requires
`hono >=4.11.2`; peers `zod ^3.25 || ^4`), `zod@4.x`. Adapter pins vary per
template: Node uses `@hono/node-server@2.0.x` (Node 20+ required; the `/vercel`
adapter was removed in v2). Cloudflare uses `wrangler@4.x` and generates Worker
types with `wrangler types` into `worker-configuration.d.ts` rather than
depending on `@cloudflare/workers-types` (now v5, date-versioned, and no longer
the recommended path).

## Scaffolder behavior

`npm create hono@latest <target-dir> -- --template <template>` runs the official
Hono CLI. There is NO `--yes` flag; non-interactivity comes from supplying the
`[target]` positional plus `-t/--template`. Supported flags: `-t, --template`,
`-i, --install`, `-p, --pm <pnpm|bun|deno|npm|yarn>` (defaults to npm),
`-o, --offline`.

Template options (13, enforced via commander `.choices()`, so an unlisted name
hard-errors): `aws-lambda`, `bun`, `cloudflare-workers`,
`cloudflare-workers+vite`, `deno`, `fastly`, `lambda-edge`, `netlify`, `nextjs`,
`nodejs`, `vercel`, `cloudflare-pages`, `x-basic`. The scaffolder writes:

- `src/index.ts` skeleton with one example route
- `package.json` with framework + adapter pins
- `tsconfig.json` configured for the target runtime
- Adapter-specific config (`wrangler.jsonc` for Workers, `vercel.json`, etc.)
- `.gitignore`
- `README.md` with template-specific dev/deploy instructions

It does NOT install dependencies unless `-i/--install` is passed; install is
opt-in, not suppressed by a headless flag. It does NOT initialize git. Lockfile
materializes during the post-scaffold install step. Only `src/index.ts` is
emitted under `src/`; `src/routes/` and `src/middleware/` above are convention
you add, not scaffolder output.

## Tier-1 detection signals

- `package.json` with `"hono"` in dependencies
- `src/index.ts` containing `new Hono(` constructor invocation
- `wrangler.jsonc` / `wrangler.json` / `wrangler.toml` (CF Workers), a strong
  signal when paired with a hono dep; current templates emit `wrangler.jsonc`
- `@hono/node-server` in dependencies, the strongest signal for Node-hosted Hono
- Import statements `from "hono"` or `from "hono/jsx"` across `src/`

## Common pitfalls + cold-rerun gotchas

- v3 to v4 breaking changes, per the upstream `docs/MIGRATION.md`: `c.req` is a
  `HonoRequest` (use `c.req.raw` for the raw `Request`); the old validator
  middleware is gone; serve-static moved to per-runtime adapters; the `Hono`
  constructor generics are `{ Bindings, Variables }`. Rarely encountered in 2026
  but still bites vendored or long-dormant code.
- The `cloudflare-workers` template no longer depends on
  `@cloudflare/workers-types` and its tsconfig has no `types` array. Worker
  types come from `npm run cf-typegen` (`wrangler types --env-interface
  CloudflareBindings`) writing `worker-configuration.d.ts`. Forgetting to re-run
  cf-typegen after changing bindings or `compatibility_date` is the modern
  failure mode.
- JSX in Hono uses `hono/jsx` runtime, NOT React; importing React JSX
  unintentionally produces runtime errors that look like React mismatches.
- Both the `[target]` positional and `-t/--template` are required for a truly
  non-interactive run; omitting either drops into a prompt. Passing `--yes`
  errors out as an unknown option: `create-hono` has no such flag.
- RPC client (`hc<AppType>`) requires the type-only export to compile, not
  the runtime app instance; mis-export breaks type inference silently.
- Cloudflare `wrangler` is v4.x. `wrangler dev` runs locally by default;
  `--local` and `--remote` both default to false, `--local` force-disables all
  remote bindings, and individual bindings opt into remote access with
  `remote: true` in the Wrangler config.

## Version evolution

- Hono 4 (Jan 2024, still the current major at 4.12.x): `HonoRequest`; improved
  JSX performance; built-in RPC type-inference; `hono/serve-static` rewritten.
- Hono 3 (2023): Bun adapter; Deno Deploy adapter; Zod validator middleware.
- Hono 2 (2022): edge-first architecture; Cloudflare Workers-native.

Track upstream `create-hono` releases; the template list expands per minor
release as new edge runtimes gain Hono adapters.
