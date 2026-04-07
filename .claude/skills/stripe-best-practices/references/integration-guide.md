# Stripe Integration Guide

> Loaded by SKILL.md Step 1. Contains the API decision tree, banned/preferred endpoints, and go-live checklist.

## Integration Decision Tree

```
Is this a recurring revenue / subscription model?
  YES → Use Stripe Billing APIs + Checkout Sessions
        See: https://docs.stripe.com/billing/subscriptions/designing-integration
        SaaS pattern: https://docs.stripe.com/saas
  NO  → Is the payment on-session (user present)?
          YES → Use Checkout Sessions (Stripe-hosted or Embedded)
                See: https://docs.stripe.com/payments/checkout
          NO  → Use PaymentIntents API for off-session charges
                See: https://docs.stripe.com/payments/paymentintents/lifecycle
```

**For SaaS products, default to Stripe Billing + Checkout Sessions for all monetization.**

## Frontend Integration Surface

| Option                 | When to Use                                                                 | Priority                                                               |
| ---------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Stripe-hosted Checkout | Default for all flows. Redirect user to Stripe's hosted page.               | FIRST CHOICE                                                           |
| Embedded Checkout      | When checkout must live inside the app's UI.                                | SECOND CHOICE                                                          |
| Payment Element        | Only when advanced customization is required beyond what Checkout supports. | THIRD CHOICE — use with Checkout Sessions API, not raw PaymentIntents. |

Never use the legacy Card Element or Payment Element in card-only mode. If existing code uses Card Element, migrate: https://docs.stripe.com/payments/payment-element/migration

## Banned APIs and Patterns

| Banned                                            | Replacement                                | Migration Guide                                                    |
| ------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------ |
| Charges API                                       | Checkout Sessions or PaymentIntents        | https://docs.stripe.com/payments/payment-intents/migration/charges |
| Sources API                                       | SetupIntents (for saving payment methods)  | https://docs.stripe.com/api/setup_intents                          |
| Tokens API                                        | Payment Element + Checkout Sessions        | Use modern integration surfaces                                    |
| Legacy Card Element                               | Payment Element                            | https://docs.stripe.com/payments/payment-element/migration         |
| `createPaymentMethod` / `createToken` (Stripe.js) | Confirmation Tokens                        | Use when rendering Payment Element before creating intent          |
| Hardcoded `payment_method_types`                  | Dynamic payment methods (dashboard config) | Remove the array; let Stripe choose optimal methods per user       |
| Connect terms: "Standard", "Express", "Custom"    | Controller properties + capabilities       | https://docs.stripe.com/connect/migrate-to-controller-properties   |

## Preferred Patterns

### API Version

Always use the latest Stripe API version and SDK unless the user specifies otherwise.

### Dynamic Payment Methods

Enable dynamic payment methods in the Stripe Dashboard instead of passing `payment_method_types` in API calls. Stripe selects optimal payment methods based on user location, wallets, and preferences.

### Saving Payment Methods

Use the SetupIntents API to save a payment method for later use. Never use Sources API for this purpose.

### Confirmation Tokens

When rendering the Payment Element before creating a PaymentIntent or SetupIntent (e.g., for surcharging or inspecting card details), use Stripe Confirmation Tokens. Do not use `createPaymentMethod` or `createToken`.

### PCI Compliance

If raw PAN data must be sent server-side, the user must prove PCI compliance to access `payment_method_data`. For migrating PAN data from another processor: https://docs.stripe.com/get-started/data-migrations/pan-import

## SaaS Billing Pattern

For subscription billing:

1. **Define Products and Prices** in the Stripe Dashboard (or via API).
2. **Create Checkout Sessions** with `mode: 'subscription'` for new subscribers.
3. **Use Stripe Billing APIs** to manage subscriptions: upgrades, downgrades, cancellations, trials.
4. **Sync state via webhooks** — store subscription status in Prisma, update on `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`.
5. **Use Customer Portal** for self-service subscription management: https://docs.stripe.com/customer-management

Key Stripe Billing resources:

- Subscription use cases: https://docs.stripe.com/billing/subscriptions/use-cases
- SaaS integration: https://docs.stripe.com/saas
- Designing the integration: https://docs.stripe.com/billing/subscriptions/designing-integration

## Stripe Connect (If Applicable)

If the project adds marketplace features:

- **Direct charges:** Platform wants Stripe to bear risk for connected accounts.
- **Destination charges:** Platform accepts liability for negative balances.
- Use `on_behalf_of` parameter to control merchant of record.
- Never mix charge types within a single integration.
- Use controller properties (not legacy "Standard"/"Express"/"Custom" terms): https://docs.stripe.com/connect/migrate-to-controller-properties
- Use capabilities for connected accounts: https://docs.stripe.com/connect/account-capabilities
- Integration recommendations: https://docs.stripe.com/connect/integration-recommendations

## Go-Live Checklist

Before launching billing in production, verify:

- [ ] Stripe API keys are production keys (not test keys)
- [ ] Webhook endpoint is registered in Stripe Dashboard for production
- [ ] Webhook signature verification is enabled and working
- [ ] All test card numbers are removed from any seed/fixture data
- [ ] Error handling covers all Stripe error types (card_error, api_error, etc.)
- [ ] Subscription status synced correctly via webhooks (not just checkout completion)
- [ ] Customer portal configured for self-service management
- [ ] Idempotency keys used for all POST requests that create resources
- [ ] Dynamic payment methods enabled (no hardcoded payment method types)
- [ ] Full checklist: https://docs.stripe.com/get-started/checklist/go-live

## Key Documentation Links

- Integration options overview: https://docs.stripe.com/payments/payment-methods/integration-options
- API tour: https://docs.stripe.com/payments-api/tour
- Checkout Sessions API: https://docs.stripe.com/api/checkout/sessions
- Go-live checklist: https://docs.stripe.com/get-started/checklist/go-live
