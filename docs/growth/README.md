# Growth (Internal)

This folder holds **internal positioning, sales-pitch, and copy strategy work** for LaunchPad and the broader BuiltForm product line. Everything inside is gitignored except this README — the artifacts here are produced by the [Growth Toolkit](https://github.com/builtform/marketplace) plugin and consumed by maintainers when rewriting marketing surfaces.

## Why this folder exists

LaunchPad ships under the BuiltForm marketplace, which lists two plugins:

- **LaunchPad** — the public, MIT-licensed agentic coding harness you're reading the source of.
- **Growth Toolkit** — a separate **paid** plugin that produces strategic and conversion-optimized go-to-market work: customer positioning, sales-pitch storyboards, lead-generation plans, money-model blueprints, and page copy.

Growth Toolkit is built on the same agentic-harness pattern as LaunchPad but applied to a different domain: instead of helping you ship code, it helps you ship the words and offers that sell what the code does.

## Where to get Growth Toolkit

Growth Toolkit lives in the BuiltForm marketplace alongside LaunchPad:

```
/plugin marketplace add github:builtform/marketplace
/plugin install growth-toolkit@builtform
```

Install requires repository access. Growth Toolkit is a private repo; request access via the BuiltForm marketplace issue tracker.

## What this folder contains (when populated)

The `.gitignore` in this folder hides every file except this README, so contributors cloning LaunchPad won't see the live strategy artifacts. Maintainers running `/growth-positioning`, `/growth-sales-pitch`, `/growth-offer`, `/growth-leads`, `/growth-moneymodel`, or `/growth-page-copy` from inside this repo write their outputs here.

The artifacts produced are:

- `positioning.md` — Dunford 5-component positioning (competitive alternatives, unique capabilities, differentiated value, best-fit customers, market category).
- `sales-pitch-storyboard.md` — Dunford 8-step storyboard (Insight → Alternatives → Perfect World → Introduction → Differentiated Value → Proof → Objections → The Ask).
- `offer-blueprint.md` — Hormozi Grand Slam Offer with Value Equation scoring.
- `lead-generation-plan.md` — Hormozi $100M Leads roadmap and Core Four prioritization.
- `money-model-blueprint.md` — Hormozi $100M Money Models pricing architecture.
- `copy/` — Veloso conversion copy for landing, pricing, about, and feature pages.

These artifacts are inputs to public-facing surfaces (README, landing page, pricing page). The artifacts themselves stay internal.
