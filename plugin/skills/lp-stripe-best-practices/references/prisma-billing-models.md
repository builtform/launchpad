# Prisma Billing Models for Stripe

> Loaded by SKILL.md Step 4. Contains recommended Prisma schema patterns for storing Stripe billing state.

## Core Principle

Stripe is the source of truth for billing state. Prisma stores a synchronized copy for fast queries and access control. Webhooks keep the two in sync. Never derive subscription status from Checkout Session completion alone.

## Recommended Prisma Models

```prisma
// packages/db/prisma/schema.prisma

model Customer {
  id               String   @id @default(cuid())
  userId           String   @unique
  stripeCustomerId String   @unique
  createdAt        DateTime @default(now())
  updatedAt        DateTime @updatedAt

  subscriptions Subscription[]
  user          User @relation(fields: [userId], references: [id])

  @@index([stripeCustomerId])
}

model Subscription {
  id                   String             @id @default(cuid())
  customerId           String
  stripeSubscriptionId String             @unique
  stripePriceId        String
  status               SubscriptionStatus
  currentPeriodStart   DateTime
  currentPeriodEnd     DateTime
  cancelAtPeriodEnd    Boolean            @default(false)
  trialEnd             DateTime?
  createdAt            DateTime           @default(now())
  updatedAt            DateTime           @updatedAt

  customer Customer @relation(fields: [customerId], references: [id])

  @@index([stripeSubscriptionId])
  @@index([customerId])
}

enum SubscriptionStatus {
  ACTIVE
  PAST_DUE
  CANCELED
  INCOMPLETE
  INCOMPLETE_EXPIRED
  TRIALING
  UNPAID
  PAUSED
}

model StripeEvent {
  id             String   @id @default(cuid())
  stripeEventId  String   @unique
  type           String
  processedAt    DateTime
  createdAt      DateTime @default(now())

  @@index([stripeEventId])
}
```

## Sync Patterns

### On `checkout.session.completed`

```typescript
async function handleCheckoutCompleted(session: Stripe.Checkout.Session) {
  if (session.mode !== "subscription") return;

  const stripeSubscription = await stripe.subscriptions.retrieve(session.subscription as string);

  // Find or create the Customer record
  let customer = await prisma.customer.findUnique({
    where: { stripeCustomerId: session.customer as string },
  });

  if (!customer) {
    customer = await prisma.customer.create({
      data: {
        userId: session.client_reference_id!, // Pass user ID when creating checkout session
        stripeCustomerId: session.customer as string,
      },
    });
  }

  // Create the Subscription record
  await prisma.subscription.upsert({
    where: { stripeSubscriptionId: stripeSubscription.id },
    create: {
      customerId: customer.id,
      stripeSubscriptionId: stripeSubscription.id,
      stripePriceId: stripeSubscription.items.data[0].price.id,
      status: mapStripeStatus(stripeSubscription.status),
      currentPeriodStart: new Date(stripeSubscription.current_period_start * 1000),
      currentPeriodEnd: new Date(stripeSubscription.current_period_end * 1000),
      trialEnd: stripeSubscription.trial_end ? new Date(stripeSubscription.trial_end * 1000) : null,
    },
    update: {
      status: mapStripeStatus(stripeSubscription.status),
      currentPeriodStart: new Date(stripeSubscription.current_period_start * 1000),
      currentPeriodEnd: new Date(stripeSubscription.current_period_end * 1000),
    },
  });
}
```

### On `customer.subscription.updated`

```typescript
async function handleSubscriptionUpdated(subscription: Stripe.Subscription) {
  await prisma.subscription.update({
    where: { stripeSubscriptionId: subscription.id },
    data: {
      status: mapStripeStatus(subscription.status),
      stripePriceId: subscription.items.data[0].price.id,
      currentPeriodStart: new Date(subscription.current_period_start * 1000),
      currentPeriodEnd: new Date(subscription.current_period_end * 1000),
      cancelAtPeriodEnd: subscription.cancel_at_period_end,
      trialEnd: subscription.trial_end ? new Date(subscription.trial_end * 1000) : null,
    },
  });
}
```

### On `customer.subscription.deleted`

```typescript
async function handleSubscriptionDeleted(subscription: Stripe.Subscription) {
  await prisma.subscription.update({
    where: { stripeSubscriptionId: subscription.id },
    data: {
      status: "CANCELED",
    },
  });
}
```

## Status Mapping

```typescript
function mapStripeStatus(status: Stripe.Subscription.Status): SubscriptionStatus {
  const mapping: Record<string, SubscriptionStatus> = {
    active: "ACTIVE",
    past_due: "PAST_DUE",
    canceled: "CANCELED",
    incomplete: "INCOMPLETE",
    incomplete_expired: "INCOMPLETE_EXPIRED",
    trialing: "TRIALING",
    unpaid: "UNPAID",
    paused: "PAUSED",
  };
  return mapping[status] ?? "INCOMPLETE";
}
```

## Access Control Pattern

Use the Prisma subscription data for feature gating:

```typescript
async function hasActiveSubscription(userId: string): Promise<boolean> {
  const customer = await prisma.customer.findUnique({
    where: { userId },
    include: {
      subscriptions: {
        where: {
          status: { in: ["ACTIVE", "TRIALING"] },
        },
      },
    },
  });

  return (customer?.subscriptions.length ?? 0) > 0;
}
```

Do not call the Stripe API for access control on every request. Use the cached Prisma data, kept in sync by webhooks.
