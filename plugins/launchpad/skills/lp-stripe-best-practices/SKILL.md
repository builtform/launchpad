---
name: lp-stripe-best-practices
description: >
  Stripe integration patterns for SaaS billing. Enforces Checkout Sessions over
  raw PaymentIntents, modern API usage over deprecated endpoints, webhook security with Hono,
  Prisma-backed subscription state, and Connect platform best practices. Covers the full
  lifecycle: checkout, subscriptions, webhooks, error handling, and go-live readiness.
  Triggers on: implementing payments, adding Stripe checkout, building subscription billing,
  writing webhook handlers, integrating Stripe Connect.
---

<!-- ported-from: anthropics/claude-plugins-official/external_plugins/stripe/skills/stripe-best-practices
     original-author: Anthropic (Stripe plugin)
     port-date: 2026-04-06
     upstream-version: unversioned
     license: Apache 2.0 / MIT
     note: Adapted for generic monorepo use (Hono API + Prisma). Downstream projects should adjust package imports. -->

**Use Checkout Sessions and Stripe Billing APIs for all payment flows. Never use the Charges API, Sources API, or legacy Card Element.**

## Prerequisites

This skill requires the following when billing is implemented:

- **npm:** `stripe` package | Install: `pnpm add stripe` (in `apps/api/`)
- **npm:** `@stripe/stripe-js` + `@stripe/react-stripe-js` | Install: `pnpm add @stripe/stripe-js @stripe/react-stripe-js` (in `apps/web/`)
- **Environment variables in `.env.local`:**
  - `STRIPE_SECRET_KEY` — Server-side API key (starts with `sk_`)
  - `STRIPE_PUBLISHABLE_KEY` — Client-side key (starts with `pk_`)
  - `STRIPE_WEBHOOK_SECRET` — Webhook endpoint signing secret (starts with `whsec_`)
- **Stripe CLI** (for local webhook testing) | Install: `brew install stripe/stripe-cli/stripe`

## Trigger

Activate this skill when:

- Implementing payment processing, checkout flows, or billing
- Building subscription management (create, update, cancel, trial)
- Writing Stripe webhook handlers in the Hono API
- Adding Stripe Connect for marketplace or platform features
- Storing payment/subscription state in Prisma models
- Preparing for go-live with Stripe

Example invocations:

- "Add Stripe checkout for the Pro plan"
- "Build webhook handler for subscription events"
- "Set up Stripe billing with free trial"

## The Job

1. **Choose the correct integration surface.** Read [references/integration-guide.md](mdc:references/integration-guide.md) for the decision tree. Default to Stripe-hosted Checkout or Embedded Checkout. Use PaymentIntents only for off-session payments. Use Stripe Billing APIs for any recurring revenue model.

2. **Implement with modern APIs only.** Apply the banned/preferred API rules from the integration guide. Never use Charges, Sources, Tokens, or legacy Card Element. Use `payment_method_types: undefined` (dynamic payment methods via dashboard) instead of hardcoding payment method types.

3. **Build webhook handlers using Hono patterns.** Read [references/webhook-patterns.md](mdc:references/webhook-patterns.md) for the Hono-specific webhook route, signature verification, and idempotent event processing. Every webhook handler must verify signatures, handle events idempotently, and return 200 promptly.

4. **Store subscription state in Prisma.** Read [references/prisma-billing-models.md](mdc:references/prisma-billing-models.md) for the recommended Prisma schema patterns. Sync Stripe state via webhooks — never rely solely on client-side session data for subscription status.

5. **Produce a compliance checklist.** After implementation, verify against the go-live checklist in the integration guide. List which items are complete and which remain.

## What This Skill Does NOT Handle

- **UI/UX design of pricing pages** — Use the `frontend-design` skill for layout, typography, and visual design of pricing components.
- **Authentication and authorization** — This skill covers Stripe API auth (API keys, webhook secrets), not user auth (Clerk, NextAuth, etc.).
- **Tax calculation details** — Stripe Tax configuration is mentioned but detailed tax compliance is outside scope.
- **Stripe Connect onboarding flows** — Mentioned at a high level; detailed Connect account onboarding requires dedicated implementation.

## Verification

- [ ] All payment flows use Checkout Sessions or Stripe Billing APIs (no raw Charges or PaymentIntents for on-session payments)
- [ ] No references to deprecated APIs (Charges, Sources, Tokens, legacy Card Element)
- [ ] Webhook handler verifies signatures using `stripe.webhooks.constructEvent`
- [ ] Webhook processing is idempotent (checks for duplicate event IDs before processing)
- [ ] Subscription state is stored in Prisma and synced via webhooks, not client-side only
- [ ] Dynamic payment methods enabled (no hardcoded `payment_method_types` array)
- [ ] Environment variables loaded from `.env.local` via `process.env`, never hardcoded

**Use Checkout Sessions and Stripe Billing APIs for all payment flows. Never use the Charges API, Sources API, or legacy Card Element.**
