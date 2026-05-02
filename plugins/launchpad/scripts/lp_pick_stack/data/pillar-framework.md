---
generated_by: hand-authored
last_validated: 2026-04-30
purpose: rationale-generation context for /lp-pick-stack
---

# Pillar Framework — v2.0 Stack Taxonomy

This doc is **read-only context** for `/lp-pick-stack` rationale generation.
It is NEVER piped to Claude as instructions — only as data the rationale
template's "why-this-fits" section may quote from. Per HANDSHAKE §2 trust
boundaries, this file is trusted-as-data; user-supplied free text is wrapped
in `<untrusted_user_input>` envelopes upstream.

## The four product pillars

The v2.0 10-stack catalog (HANDSHAKE §11) spans **four product pillars**.
Each pillar groups stacks that share runtime model, deployment shape, and
team-skill prerequisites. The pick-stack engine selects a pillar via Q1
(project shape) + Q3 (AI/ML need) + Q4 (team-language preference); within a
pillar, the engine narrows to a specific stack via the category-patterns.yml
`fits_when` predicates.

### Pillar 1 — Frontend Content/Performance

**Stacks**: astro, eleventy, hugo

**Shape**: Content-heavy sites (blogs, docs, marketing pages) where build
output is mostly static HTML + minimal JavaScript. Read-heavy, edit-rare.

**Shared traits**:

- Markdown-first authoring; frontmatter or content-collection schemas
- Build output is pre-rendered HTML; runtime JS is opt-in (islands or none)
- Lighthouse-optimized by default
- Deploy targets: Cloudflare Pages, Netlify, Vercel, GitHub Pages, S3
- No persistent backend required for the core flow
- 6-month freshness review cadence (BL-105) — flag-set drift is the main risk

**Cross-stack tradeoff axis** (the `static-blog-trio` ambiguity cluster):

- **astro**: TypeScript-first; islands architecture; best when interactive bits
  matter (search, comments, dashboards embedded in content)
- **eleventy**: ESM-only JavaScript; minimal JS surface; best for plain
  Markdown sites without framework overhead
- **hugo**: Go-built; fastest builds (thousands of pages/sec); best for very
  large content corpora (1k+ pages) or non-JS teams

### Pillar 2 — Frontend App

**Stacks**: next

**Shape**: Interactive web apps with auth, dashboards, CRUD, and frequent
state changes. Read+write-heavy; user-action-driven.

**Shared traits**:

- React-based component model
- Server Components / Server Actions for full-stack data flow without separate
  API layer
- App Router file-based routing
- Tailwind v4 + TypeScript-first
- Deploy targets: Vercel (canonical), Cloudflare Workers, Netlify, AWS

**Standalone vs polyglot**:

- **Standalone Next**: when the team is TypeScript-only and Server Actions /
  Route Handlers cover the API surface
- **Next + Hono polyglot**: when end-to-end TypeScript with explicit RPC
  type-inference is preferred (separate `apps/web` + `apps/api`)
- **Next + FastAPI polyglot**: when the backend needs Python ML libraries
  (torch, transformers, langchain) — frontend in TS, backend in Python

### Pillar 3 — Backend (Python / MVC / Managed / Edge-native TS)

**Stacks**: fastapi, django, rails, supabase, hono

**Shape**: Server-side data APIs (REST, GraphQL, RPC) with persistence, auth,
and business logic. May or may not pair with a separate frontend.

**Shared traits**:

- Stateful (database) layer is canonical; even managed backends (supabase) are
  Postgres-backed
- ORM or query-builder pattern (SQLAlchemy, ActiveRecord, Django ORM) — except
  Hono which is unopinionated about persistence
- Migration tooling (alembic, ActiveRecord migrations, Django migrations,
  supabase declarative migrations)
- Testing pyramid: unit + integration with real DB

**Cross-stack tradeoff axis**:

- **fastapi**: Python team + async-first + type-validated request/response.
  Best for ML/data backends, async I/O-heavy workloads.
- **django**: Python team + batteries-included (admin, auth, ORM, templates).
  Best when admin UI is core, async is optional, and team velocity matters.
- **rails**: Ruby team + batteries-included (Hotwire, ActiveRecord, Solid
  Queue). Best for MVP velocity in a Ruby shop.
- **supabase**: managed Postgres + Auth + Storage + Realtime. Best when the
  team wants to skip backend infra entirely and focus on frontend; pairs
  naturally with next or astro.
- **hono**: edge-native TypeScript. Best for low-latency edge APIs, RPC-style
  type-inference between client and server, and Cloudflare Workers /
  Vercel Edge deployments.

### Pillar 4 — Frontend Mobile

**Stacks**: expo

**Shape**: Cross-platform iOS + Android apps (and optionally web via React
Native Web). Native UI primitives + React component model.

**Shared traits**:

- TypeScript-first
- Expo Router for file-based routing
- EAS Build for cloud-based native builds (avoids local Xcode/Android Studio)
- New Architecture (Fabric + TurboModules) enabled by default in SDK 52+
- Deploy targets: App Store, Play Store, Expo Go (dev/preview)

**Standalone vs polyglot**:

- **Standalone expo**: client-only mobile app (no backend), or pairs with an
  existing API
- **expo + hono polyglot**: edge-native API for the mobile app — common when
  the team wants TypeScript end-to-end across mobile + backend

## Cross-pillar tradeoff axes

When a project shape spans pillars, the pick-stack engine prefers the smallest
viable composition. The following axes drive the decision:

| Axis                       | Pulls toward                         | Pulls toward                                            |
| -------------------------- | ------------------------------------ | ------------------------------------------------------- |
| Read/write balance         | Frontend Content (read-heavy)        | Frontend App (write-heavy)                              |
| Team language              | Python → Django/FastAPI              | TypeScript → Next/Hono/Astro                            |
| Backend infra preference   | Self-managed (FastAPI/Django/Rails)  | Managed (Supabase)                                      |
| Build-time vs request-time | Frontend Content (build-time render) | Frontend App + Backend (request-time render)            |
| Latency sensitivity        | Edge-native (Hono on Workers)        | Container-deployed (FastAPI/Django/Rails on Render/Fly) |
| Mobile target              | Frontend Mobile (Expo)               | Frontend App (Next via PWA)                             |

## Anti-patterns (what NOT to do in 2026)

These shape the rationale's "alternatives" section when surfacing why a
candidate stack was NOT chosen:

- **Express for new APIs**: Hono or FastAPI is the modern path; Express is
  legacy unless the team has institutional ESM/middleware investment
- **Remix as a separate framework**: Remix v2 became React Router v7 (2024); a
  new Remix project today writes itself as React Router v7 inside a Next or
  standalone Vite shell
- **Webpack for new bundling**: Vite (Astro/SvelteKit/Vite-projects) or
  Turbopack (Next 15) are the modern paths
- **psycopg2 instead of psycopg3**: psycopg3 (`psycopg`) is the 2026 idiom;
  psycopg2 is in maintenance-only mode
- **Pages Router for new Next projects**: App Router is the canonical paradigm
  in Next 15; Pages Router is legacy support for migration only
- **Webpacker / Sprockets for new Rails**: Propshaft + importmap is the Rails 8
  default; Webpacker was sunset in Rails 7

## Notes on the v2.0 catalog (10 stacks)

Per HANDSHAKE §11, v2.0 ships **exactly 10 stacks**. The Layer 3 catalog cut
deferred 10 candidate stacks to v2.2 BL entries (BL-100 through BL-104 +
BL-212): cloudflare-workers, tauri, nestjs, laravel, vite, sveltekit, elysia,
phoenix-liveview, convex, flutter. The pick-stack engine refuses gracefully
when a user's project shape best matches a deferred stack, surfacing a v2.2
roadmap pointer rather than silently substituting a different stack.

The 6-month post-v2.0 freshness review (BL-105) revisits the 10-entry catalog
for drift; the v2.1 documentation-only release does NOT add stacks. Stack
restorations land at v2.2 alongside the operational/security infrastructure
deferrals.
