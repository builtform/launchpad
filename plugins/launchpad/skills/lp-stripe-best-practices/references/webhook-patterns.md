# Stripe Webhook Patterns for Hono

> Loaded by SKILL.md Step 3. Contains Hono-specific webhook route implementation, signature verification, and idempotent event processing.

## Webhook Route in Hono

This project's API uses Hono (not Express). The critical difference: Hono does not use `express.raw()` middleware. Use `c.req.text()` to get the raw body for signature verification.

```typescript
// apps/api/src/routes/stripe-webhooks.ts
import { Hono } from "hono";
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET!;

const app = new Hono();

app.post("/webhooks/stripe", async (c) => {
  // 1. Get raw body for signature verification
  const rawBody = await c.req.text();
  const signature = c.req.header("stripe-signature");

  if (!signature) {
    return c.json({ error: "Missing stripe-signature header" }, 400);
  }

  // 2. Verify webhook signature
  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(rawBody, signature, webhookSecret);
  } catch (err) {
    console.error("Webhook signature verification failed:", err);
    return c.json({ error: "Invalid signature" }, 400);
  }

  // 3. Process event idempotently
  try {
    await processStripeEvent(event);
  } catch (err) {
    console.error(`Error processing event ${event.id}:`, err);
    // Return 200 anyway to prevent Stripe from retrying
    // Log the error for manual investigation
  }

  // 4. Return 200 promptly — Stripe times out after 20 seconds
  return c.json({ received: true }, 200);
});

export default app;
```

## Idempotent Event Processing

Every webhook handler must be idempotent. Stripe may deliver the same event multiple times.

```typescript
// apps/api/src/services/stripe-event-processor.ts
import { prisma } from "@repo/db";
import type Stripe from "stripe";

export async function processStripeEvent(event: Stripe.Event): Promise<void> {
  // Check if event was already processed
  const existing = await prisma.stripeEvent.findUnique({
    where: { stripeEventId: event.id },
  });

  if (existing) {
    console.log(`Event ${event.id} already processed, skipping`);
    return;
  }

  // Process based on event type
  switch (event.type) {
    case "checkout.session.completed":
      await handleCheckoutCompleted(event.data.object as Stripe.Checkout.Session);
      break;
    case "customer.subscription.updated":
      await handleSubscriptionUpdated(event.data.object as Stripe.Subscription);
      break;
    case "customer.subscription.deleted":
      await handleSubscriptionDeleted(event.data.object as Stripe.Subscription);
      break;
    case "invoice.paid":
      await handleInvoicePaid(event.data.object as Stripe.Invoice);
      break;
    case "invoice.payment_failed":
      await handleInvoicePaymentFailed(event.data.object as Stripe.Invoice);
      break;
    default:
      console.log(`Unhandled event type: ${event.type}`);
  }

  // Record that this event was processed
  await prisma.stripeEvent.create({
    data: {
      stripeEventId: event.id,
      type: event.type,
      processedAt: new Date(),
    },
  });
}
```

## Critical Webhook Events for SaaS Billing

These events must be handled for subscription billing:

| Event                           | When It Fires                                        | Action                                      |
| ------------------------------- | ---------------------------------------------------- | ------------------------------------------- |
| `checkout.session.completed`    | Customer completes checkout                          | Create/activate subscription in Prisma      |
| `customer.subscription.updated` | Subscription changes (upgrade, downgrade, trial end) | Update subscription status in Prisma        |
| `customer.subscription.deleted` | Subscription canceled (after grace period)           | Mark subscription as inactive in Prisma     |
| `invoice.paid`                  | Recurring payment succeeds                           | Update billing period, reset usage counters |
| `invoice.payment_failed`        | Recurring payment fails                              | Flag account, send dunning notification     |

## Webhook Security Rules

1. **Always verify signatures.** Never process unverified webhook payloads.
2. **Use the raw request body** for verification — not parsed JSON. In Hono, use `c.req.text()`.
3. **Return 200 quickly.** Move heavy processing to background jobs if it takes more than a few seconds.
4. **Handle duplicates.** Store processed event IDs in the `StripeEvent` Prisma model.
5. **Do not trust client-side data.** Always fetch the authoritative object from Stripe's API if you need additional fields beyond what the webhook payload provides.

## Local Development

Use the Stripe CLI to forward webhooks to your local Hono server:

```bash
stripe listen --forward-to localhost:3001/webhooks/stripe
```

The CLI outputs a webhook signing secret (`whsec_...`) — use it as `STRIPE_WEBHOOK_SECRET` in `.env.local` during development.
