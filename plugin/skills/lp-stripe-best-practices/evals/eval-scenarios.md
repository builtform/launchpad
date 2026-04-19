# Evaluation: stripe-best-practices

> **Purpose:** Test that the skill produces correct, differentiated output across representative scenarios.
> **Minimum:** 3 scenarios (Anthropic guidance: "at least three evaluations created")
> **Test with:** Haiku, Sonnet, and Opus to verify model-agnostic behavior

---

## Scenario 1: Happy Path — Add Subscription Billing

**Description:** User asks to implement subscription billing for a Pro plan.

**Input:**

```
Add Stripe subscription billing for the Pro plan with a 14-day free trial
```

**Expected behavior:**

- [ ] Uses Checkout Sessions with `mode: 'subscription'` (not raw PaymentIntents)
- [ ] Creates a Hono webhook route (not Express) with signature verification using `c.req.text()`
- [ ] Includes Prisma models for Customer, Subscription, and StripeEvent
- [ ] Handles `checkout.session.completed`, `customer.subscription.updated`, and `customer.subscription.deleted` events
- [ ] Implements idempotent event processing (checks for duplicate event IDs)
- [ ] Uses `process.env.STRIPE_SECRET_KEY` (not hardcoded keys)
- [ ] Does not use Charges API, Sources API, or legacy Card Element

**Baseline comparison:** Without this skill, Claude would likely use PaymentIntents directly, might use Express-style middleware (`express.raw()`), might not include idempotency checks, and might suggest raw SQL instead of Prisma models.

---

## Scenario 2: Edge Case — User Asks for Charges API

**Description:** User explicitly requests the Charges API, testing whether the skill correctly redirects to modern alternatives.

**Input:**

```
Create a simple payment using Stripe's Charges API to charge $50
```

**Expected behavior:**

- [ ] Advises against using Charges API with a clear explanation
- [ ] Recommends Checkout Sessions as the replacement for on-session payments
- [ ] Provides migration link: https://docs.stripe.com/payments/payment-intents/migration/charges
- [ ] Implements the payment using Checkout Sessions instead

**Baseline comparison:** Without this skill, Claude would implement the Charges API as requested, producing deprecated code that Stripe discourages.

---

## Scenario 3: Negative Boundary — General API Route (Not Stripe)

**Description:** User asks to build an API route that has nothing to do with payments, testing that the skill does not activate unnecessarily.

**Input:**

```
Create a Hono API route to list all projects for the current user
```

**Expected behavior:**

- [ ] Skill does NOT activate
- [ ] Claude handles the Hono route normally without Stripe references
- [ ] No mention of Stripe, billing, or payment patterns

---

## Scenario 4: Edge Case — Webhook with Express Patterns

**Description:** User pastes Express-style webhook code and asks to integrate it, testing Hono adaptation.

**Input:**

```
I found this Stripe webhook example that uses express.raw() middleware. Can you adapt it for our API?
```

**Expected behavior:**

- [ ] Converts Express patterns to Hono patterns (c.req.text() instead of express.raw())
- [ ] Uses Hono context for responses (c.json() not res.json())
- [ ] Maintains signature verification using stripe.webhooks.constructEvent
- [ ] Adds idempotency via StripeEvent Prisma model

**Baseline comparison:** Without this skill, Claude might attempt a direct translation keeping Express idioms mixed with Hono, or might not know to use `c.req.text()` for raw body access.

---

## Grading

| Scenario | Haiku | Sonnet | Opus |
| -------- | ----- | ------ | ---- |
| 1        |       |        |      |
| 2        |       |        |      |
| 3        |       |        |      |
| 4        |       |        |      |
