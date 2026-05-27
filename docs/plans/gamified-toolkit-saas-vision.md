# Gamified Toolkit SaaS — Vision, Architecture & Naming

**Status:** Strategy / pre-build
**Purpose:** Capture the full thinking from the brainstorming session so a fresh Growth Toolkit Claude Code session can resume work without losing context.
**Source:** Long-form conversation in the LaunchPad repo (cloud session). Plan to be moved into Growth Toolkit and used as the kickoff context for the next session.

---

## 1. The Big-Picture Vision

Build a **gamified SaaS for entrepreneurs** (technical and non-technical) that walks them end-to-end through the journey of starting and scaling a business. Concretely, the product is an **operating system for the founder journey** — wired, gated, hand-holding, and producing markdown artifacts at every step.

### Core mechanics
- The journey is structured as **sequential phases** (Discovery → Mom's Test → Positioning → Offer → Content → Brand → Scale, etc.).
- Each phase has educational material (short explainers, ~5-minute videos, book summaries, reading recommendations) so the user learns the layer they're in before producing an artifact.
- Each phase ends with a **generated artifact** (markdown by default, exportable as PDF / other formats).
- The next phase is **soft-gated / locked** until the current artifact exists. This is the "game" — completing one artifact unlocks the next stage.
- Cross-toolkit gating: when the user reaches a phase in one toolkit that requires another, the system surfaces an upsell prompt (e.g., "to launch your brand, unlock the Marketing Toolkit").

### The five toolkits
1. **Growth Toolkit** — discovery, positioning, mom's test, offer, money model, leads, retention. Already being built in the `growth-toolkit` repo.
2. **Content Toolkit** — strategy and the ~10 layers of content creation (voice, pillars, calendar, etc.).
3. **Studio Toolkit** — split out from Content. ~50 commands to produce creative artifacts (images, videos, branded assets, design deliverables).
4. **Marketing Toolkit** — brand, channels, campaigns, launch.
5. **Scale Toolkit** — late-stage growth: paid acquisition, CAC/LTV, ops, team, systems.

The split of Content into **Content (strategy)** and **Studio (production)** was an explicit decision — they're different jobs done in different mental modes, by different personas, and should be billable separately.

### Why this could work
- The product compresses an enormous body of founder knowledge into a guided, executable sequence — useful for both first-time founders (who don't know what they don't know) and experienced ones (who want speed).
- Markdown-native artifacts integrate cleanly with LaunchPad for technical users.
- Open-source LaunchPad acts as a **funnel and proof point** for the closed-source toolkits SaaS.
- Strong differentiation vs. existing options (YC Startup School, Lenny's, Reforge, generic GPT wrappers) via the **wired end-to-end journey** and **LaunchPad handoff**.

---

## 2. Audience Decision (locked)

**Primary audience: both technical and non-technical founders, served via dual-UX.**

- **Non-technical users** — use the **web UI**. They run the journey in browser, generate artifacts, export as markdown / PDF / other formats. They can hand markdown artifacts to a developer / agency / their builder for technical implementation, but the strategic artifacts (positioning, sales pitch, mom's test results) are valuable on their own without any code execution.
- **Technical users** — use the **Claude Code plugin**. Same journey, same artifacts, executed inside their Claude Code environment. Artifacts can flow directly into LaunchPad for build.

Both audiences share the same backend / project state — a technical cofounder running `/discovery` in Claude Code and their non-technical cofounder viewing in the browser should see the same project and the same artifact.

### Brand feel target
**Crafted + friendly.** Linear + Notion vibes. Not McKinsey-serious, not Duolingo-cartoony, not bro-startup. Approachable for first-time founders, credible for experienced operators.

---

## 3. The "Operating System" Concept

The product IS an operating system in the literal sense — it sequences work, manages project state, abstracts complexity, hand-holds the user, and surfaces what to do next. The naming should convey this even if the word "OS" itself is unavailable (see Section 7 on naming).

### What "wired" means in this product
- The user starts at one end and the program walks them through every step.
- No prior knowledge required — the system teaches the layer before asking for the artifact.
- The system doesn't rely on the user learning — it produces artifacts FOR them and tells them what comes next.
- Cross-references between toolkits are seamless and surface at the right moment.

This is the **central differentiator** vs. courses, communities, or prompt-library products.

---

## 4. Distribution Architecture (decided)

### For technical users: Claude Code plugin → remote MCP server

**Critical research finding:** It is **not possible** to distribute a standard Claude Code plugin while keeping the prompts/commands private from installed users. Claude Code plugins (slash commands, skills, agents, hooks) are installed as plaintext markdown files in `~/.claude/plugins/cache/` and are readable by anyone who installs them. Private repos, encryption, and obfuscation are **not supported** by the plugin system. Source: Claude Code official docs (code.claude.com/docs/en/plugins, plugins-reference, plugin-marketplaces) plus the MCP connector documentation.

**The only architecture that protects prompt IP while integrating into Claude Code:**

1. Ship a **thin Claude Code plugin** with slash command stubs (`/discovery`, `/positioning`, `/mom-test`, etc.).
2. Each stub does one thing: invokes a tool on a **remote MCP server hosted by us**.
3. The MCP server is **auth-gated** (license key / OAuth) — each user authenticates with their paid account.
4. The actual prompts and workflow logic live on the MCP server. The user sees the output in their Claude Code session but never sees the prompt source.
5. Updates ship server-side — no plugin reinstall needed.

### Strategic benefits of the MCP-bridge pattern
- Real IP protection (the prompts are the differentiator and stay server-side)
- Rate-limiting, metering, revocation are clean (expire license → server stops responding)
- Server-side analytics on which phases users complete / drop off
- A/B testing prompts in production
- Updates without user action

### Tradeoffs / open questions
- Real infrastructure required: auth, billing, MCP server uptime, monitoring
- Network hop on every command — if the user is offline, the plugin is dead
- AI cost model unsettled: do we pay the Anthropic API bill server-side, or BYOK? This decision drives unit economics
- Platform dependency on the Claude Code plugin/MCP spec, which Anthropic could change

### For non-technical users: web UI
- Hosted web app, account-based, browser-only
- Same backend state as the MCP path so cross-audience cofounders can share projects
- Built first because (a) larger audience, (b) easier to demo / sell / invest, (c) the MCP bridge becomes a power-user add-on once the web UI is proven

### Why LaunchPad stays open-source
- Open-source LaunchPad = trust, distribution, developer goodwill
- Closed-source toolkits = the paid SaaS where prompts/IP live
- The **integration story** (artifacts flow from toolkit SaaS into LaunchPad) is the moat nobody else has
- **Decision: do NOT release the toolkits as open-source LaunchPad plugins.** That would forfeit the IP. The toolkits remain private repos used internally and exposed only via the MCP bridge.

---

## 5. Pricing & Tiers (open — needs decision)

### Initial thinking from conversation
- 2 or 3 tiers, **not** more (to limit upsell fatigue)
- Tier 1: Growth Toolkit
- Tier 2: Growth + Content
- Tier 3: All five toolkits (Growth, Content, Studio, Marketing, Scale)
- Upsell moments limited to 1–2 across the whole journey, not a constant nag

### Open questions
1. **Subscription vs. one-time?** The journey is finite (3–6 months for most founders). Subscription doesn't fit a finite journey — users will churn at completion. Real options:
   - One-time per toolkit ($79–199 each)
   - Hybrid: one-time unlock + small monthly for AI usage / community / updates
   - Pure SaaS only works if continuous value is added (community, new templates, coaching layer)
2. **AI cost model:** server-pays vs. BYOK. Margins look very different.
3. **License model for the MCP bridge:** per-seat? Per-org? How does the MCP server authenticate the caller?

### Honest critique on the tiering plan
- Gating-by-tier creates an awkward UX: a Tier 1 user reaches the end of Growth Toolkit and sees "upgrade to access Content." That IS an upsell, just packaged. Fine, but recognize it for what it is.
- If the journey is gated by phase AND by tier, you have two gating systems competing. Reconcile them.

---

## 6. Honest Critique (poke-holes pass)

The user explicitly asked for blunt feedback. Captured here so we don't lose the risks.

### Strengths
- LaunchPad (open) → Toolkits (closed) wedge is genuinely defensible
- Splitting Studio out of Content is a sharp instinct
- Markdown-native artifacts fit the technical persona well

### Real risks to manage

1. **Linear gating risk.** Real founders jump around. They arrive with half-finished discovery, pivot mid-journey, want to skim Scale before doing Growth. Hard gating frustrates experienced users and forces fake artifacts. **Recommendation:** soft gating (warning, not block) with a suggested path. Don't ship hard locks.
2. **Markdown vs. non-technical audience tension.** Non-technical founders don't read .md files. They want Notion / Google Docs / a chat UI. If we serve both audiences with the same artifact format, we half-serve both. **Recommendation:** markdown is the canonical format, but the web UI must render artifacts beautifully (not show raw markdown) and export to common formats by default.
3. **"Why pay vs. just use Claude directly?"** A savvy user can prompt Claude with "be a startup coach, walk me through the mom's test" and get 70% of the value for free. The moat isn't the prompts — those are reverse-engineerable in a week. The moat is: curated sequence, artifact schema, LaunchPad integration, educational layer, brand, community. **Be honest that prompts are not the IP. The system is.**
4. **Gamification fatigue.** Duolingo works because language is repetitive long-term skill-building. Entrepreneurship is mostly one-shot decisions per phase — you finish discovery once, you don't grind XP. Gamification here is mostly aesthetic (progress bars, badges, unlock animations), not mechanically addictive. Use it, but don't oversell what it buys you. Don't bolt on streaks and leaderboards that don't fit.
5. **Pricing model unsettled.** As above — subscription may not fit. Decide before launch.
6. **AI cost.** Decide BYOK vs. server-pays before launch. Affects margins fundamentally.
7. **Scope is the actual killer.** Five toolkits × gamified UI × videos × book summaries × community × tiered billing × LaunchPad integration — while running Lighting Agent and BuiltForm. That's three full-time jobs. **Validate with ONE toolkit before building five.**
8. **Competition.** YC Startup School (free), Lenny's, Reforge (premium), Foundr Magazine, Founder OS (founderos.com — 170k+ founders, established competitor), countless founder-GPT wrappers, Notion templates. The LaunchPad integration angle is the strongest differentiator — lean on it hard.

### Recommended MVP path

1. **Growth Toolkit only.** Ten phases. Web app.
2. **One-time price, ~$79.** Get 20 paying users in 60 days.
3. **No videos yet.** Write the explainers. Record video only for phases users get stuck on.
4. **Soft gating** (warn, don't block). Watch where people skip.
5. **Test the LaunchPad handoff** with technical users — does that integration actually delight them, or are they fine with the markdown alone?
6. If 20 people pay and complete it → expand to Content, then Studio, then Marketing, then Scale. If they don't → save nine months and iterate.

---

## 7. Naming Journey (full record)

Naming consumed a significant chunk of the conversation. Captured comprehensively here so we don't redo failed work.

### Names evaluated and **rejected** (with reasons)

| Name | Verdict | Reason |
|---|---|---|
| **Founder OS** (thefounderos.ai / .io / .tech) | ❌ Rejected | `founderos.com` is an active competitor — Toronto-based, founded 2022, 11–50 employees, ~170k founders touched. Direct overlap in product category (founder education, systems). Almost certainly has common-law trademark rights from active commerce. Adding "the" prefix and switching TLD does NOT escape trademark — courts apply a "likelihood of confusion" test. They'd eat our brand searches and SEO. **Drop the entire "Founder OS" namespace, not just the .com.** |
| **foundertoolkit.ai** | ❌ Weak | "Toolkit" is generic — thousands of products use it. Descriptive, not distinctive. Hard to trademark. Two long words = poor verbal handoff. No emotional hook. Placeholder, not a brand. |
| **CACtoLTV.com** | ❌ Rejected | Unpronounceable verbally. Spelling unrecoverable from hearing it. "CAC" rhymes with "hack/cack" phonetically. Acronym filters out non-technical audience. Mismatch with product (CAC/LTV are late-stage metrics; most of our toolkits are early-stage work). Not gamified. Unbrandable visually. Sounds like a Chrome extension, not a $99/mo SaaS. Exit/investor liability. |
| **Foundry** | ❌ Heavily conflicted | Foundry VC, HBS Foundry, Founder Foundry, Carnegie Mellon Foundry, Monad Foundry — multiple direct competitors in founder education and startup acceleration. |
| **Forge** | ❌ Heavily conflicted | Forge Startups (operating-partner model for founders), Forge Global (unicorn data co.), FoundersForge, SaaS Forge. Direct overlap. |
| **Ascent** | ❌ Direct conflict | Ascent Startups (ascentstartups.com) — literally a founder education platform by Gabe Rapoport. Same product category. |
| **Compound** | ❌ Conflicted | Compound Finance (DeFi), Compound Planning (wealth mgmt). Heavy financial brand load. |
| **Climb** | ❌ Direct conflict | CLIMB Factory — "startup studio for non-technical founders," literally our target audience. |
| **Lever** | ❌ Direct conflict | Lever ATS (~$100M+ recruiting SaaS). |
| **Maker OS / makeros.ai** | ❌ Rejected | MakerOS was a real funded company (founded 2015, $2M Series A in 2019, SaaS for 3D printing). Acquired by Shapeways Holdings in March 2022. Shapeways went bankrupt in 2024 — trademark went to whoever bought the assets. Trademark survives website abandonment (10-year USPTO cycles). Cheap-enforcement risk = quiet trademark holder activates after we've built brand equity. Also walks right back into the "X OS" trap we identified. Also "Maker" semantically tilts toward technical builders / 3D printing community, not non-technical founders. |
| **Maker 3.0** | ❌ Rejected for product name | Strong as the title of a **BuiltForm article** about makers in the AI era (the user is writing this article, riffing on Dan Koe's "Human 3.0" and Daniel Miessler's "Human 3.0"). But as a SaaS brand: derivative of Koe (who's actively building the Human 3.0 brand — Master Prompt launched Aug 2025), domain unfriendly (no period in URLs), version numbers age fast. Keep it for the article. |
| **Founder 3.0** | ❌ Rejected | Same problems as Maker 3.0 — derivative of Koe/Miessler, domain unfriendly, version numbers age fast, hard to register as trademark (descriptive + generic version indicator), still in founderos.com's SEO shadow, conceptually unclear. |
| **FounderLoop** | ❌ Rejected by user | "Loop" has negative connotation — feels like being stuck. Sharp catch. |
| **FounderStack** | ❌ Heavily conflicted | `founderstack.pro` (active SaaS bundle), `founderstack.online` (active), and **Accel India runs an accelerator program literally called "Founder Stack" for SaaS founders.** Accel is a top-tier global VC — don't fight that brand. |
| **FounderStudio** | ⚠️ Conflicted | Founder Studio exists as an active venture studio focused on business software. Plus "startup studio" / "venture studio" is a crowded category with potential buyer confusion (investing vs. tooling). |

### BuiltForm as parent brand — also rejected
- User correctly noted that BuiltForm is their AEC/AI (architecture, engineering, construction) brand with a totally different audience.
- Mixing BuiltForm's AEC audience with a founder/SaaS audience would dilute both brands.
- **Decision: BuiltForm stays separate. Don't entangle.**

### Names currently in active vetting

| Name | Initial verdict | Vetting status |
|---|---|---|
| **FounderEngine** | ⚠️ Moderate | No direct "FounderEngine" company found. BUT: **StartEngine** ($113M-funded equity crowdfunding platform, 1M+ users in our audience) is a huge adjacent brand with similar sound. Also "Startup Engine" (2023 SaaS accelerator) exists. Brand confusion risk, not direct trademark. Needs domain + USPTO check. |
| **Foundra** | ✅ Front-runner | No direct competitor surfaced in searches. No brand collision in startup/founder space. Brandable in the Stripe/Vercel sense — short, invented, ownable, evokes "foundry" without inheriting Foundry's trademark traffic. Needs full validation (see checklist below). |

### Foundra — 30-minute validation checklist (action item)

Before committing to Foundra, run these five checks:

1. **Domain availability** — check `foundra.com` and `foundra.ai` at Namecheap / GoDaddy / Instant Domain Search. Takes 30 seconds.
2. **USPTO TESS trademark search** — search "Foundra" in classes **9 (software)**, **35 (business services)**, **41 (education)**. Manual at [uspto.gov/trademarks/search](https://www.uspto.gov/trademarks/search). ~10 minutes for a basic search.
3. **Broad Google search** — make sure "Foundra" isn't a coffee brand, band, non-English company, etc.
4. **LinkedIn company search** — any "Foundra" companies?
5. **Social handles** — `@foundra` on Instagram, X, TikTok? Matters for marketing.

If Foundra passes all five → buy the domain same day, file USPTO intent-to-use application within the month ($350 per class, can DIY via TEAS or use LegalZoom).

If Foundra fails → fall back to **FounderEngine** with the same 5-step check.

### Naming caveats / limits of research done so far
- Could NOT confirm `.com` availability directly via WebFetch (all four candidate domains returned 403 Forbidden — bot-blocked, inconclusive). Human eyes via a registrar will resolve in 30 seconds.
- Could NOT run a USPTO TESS search via the tools available. Manual step at uspto.gov.
- Search-based brand scans miss new/unfunded companies and international brands. A trademark attorney's clearance search ($300–800) would catch what these scans cannot.

---

## 8. Tactical Notes & Side Discussions

### Article being written (separate work)
- User is writing an article for **BuiltForm** titled **"Maker 3.0"** — about designers, builders, and makers becoming better versions of themselves in the wake of AI.
- Riffs on Dan Koe's "Human 3.0" (Master Prompt, launched Aug 2025) and Daniel Miessler's "Human 3.0" essay (note spelling: **Miessler**, not Misley).
- "Maker 3.0" is a good article title, NOT a product name.

### Domain / brand patterns to know
- Single-word `.com` domains for SaaS in the founder space are essentially gone in 2026
- `.ai` is now standard for AI products, well-trusted
- `.io` is fine but a tier below
- `.tech` is the weakest of the three

### Other businesses in the user's portfolio (context)
- **LaunchPad** — open source, stays open. Funnel + proof for the toolkits.
- **BuiltForm** — AEC/AI brand. Separate audience. Don't entangle.
- **Lighting Agent** — mentioned in passing; can be used as a proof case for the toolkit system.

---

## 9. Open Questions Before Building

These should be answered before significant build effort:

1. **Naming:** does Foundra pass the 5-step validation? If yes → lock it. If no → run the same on FounderEngine.
2. **Pricing model:** subscription, one-time, or hybrid? (Strongly recommend hybrid or one-time for MVP — journey is finite.)
3. **AI cost model:** server-pays vs. BYOK? Drives margins.
4. **MVP scope:** confirmed = Growth Toolkit only, web UI first, MCP bridge as v2.
5. **License/auth approach for the eventual MCP bridge:** per-seat? Org? API-key on plugin install?
6. **Hosting / infra choices for the MCP server** (out of scope for now but flagged).

---

## 10. Recommended Next Steps

Order of operations going into the Growth Toolkit session:

1. **Lock the name.** Run the Foundra 5-step validation. Reserve domain + file USPTO intent-to-use.
2. **Lock the MVP scope.** Growth Toolkit, web UI, one-time pricing, ~$79. Soft gating only.
3. **Design the project state model.** Both the web UI and the eventual MCP bridge need to read/write the same project state. This is the foundation for the dual-UX. Decide schema before building either surface.
4. **Build the web UI for Growth Toolkit phases 1–3.** Discovery → Mom's Test → Positioning. End-to-end, including artifact generation, export, soft gating.
5. **Get 5 paying users on phase 1.** Listen.
6. **Only after that — design the Claude Code MCP bridge.** Don't build it before web UI proves the model.

---

## Appendix: Key Decisions Locked

| Decision | Value |
|---|---|
| Audience | Both technical and non-technical, served via dual-UX |
| Brand feel | Crafted + friendly (Linear + Notion vibes) |
| Distribution to technical users | Claude Code plugin → remote auth-gated MCP server (not standard plugin) |
| Distribution to non-technical users | Web UI (browser, account-based) |
| LaunchPad status | Stays open source — funnel + proof, not the paid product |
| Toolkits status | Closed source — prompts/IP live server-side behind MCP bridge |
| BuiltForm relationship | Separate brand, separate audience, do not entangle |
| Studio Toolkit | Split from Content Toolkit — strategy vs. production are different jobs |
| Article "Maker 3.0" | For BuiltForm only, not a product name |
| Name front-runner | **Foundra** (pending 5-step validation) |
| Backup name | **FounderEngine** (StartEngine adjacency risk) |
| MVP scope | Growth Toolkit only, web UI first |
| Pricing approach (tentative) | One-time per toolkit, ~$79, validate before going SaaS |
| Gating | Soft (warn) not hard (block) |

---

## Appendix: References Cited in Research

- [Founder OS — founderos.com](https://www.founderos.com/) (the established competitor)
- [Founder OS — Tracxn profile](https://tracxn.com/d/companies/founderos/__sckAE_rHxzRorlBxjZc0ZeAozkyc29ba5fjBfqsbxwU)
- [Dan Koe — Human 3.0](https://thedankoe.com/letters/a-complete-knowledge-base-of-human-3-0/)
- [Daniel Miessler — The Promise of Human 3.0](https://danielmiessler.com/blog/human-3-creator-revolution)
- [MakerOS — PitchBook](https://pitchbook.com/profiles/company/118156-69) (acquired by Shapeways 2022)
- [Ascent Startups](https://ascentstartups.com/)
- [Forge Startups](https://www.forgestartups.com/)
- [Founder Foundry](https://www.founderfoundry.com/)
- [HBS Foundry](https://www.hbs.edu/foundry)
- [Foundry VC](https://foundry.vc/)
- [CLIMB Factory](https://www.goforvertical.com/climb-ai-1)
- [Accel India Founder Stack program](https://www.seedtoscale.com/blog/deep-dive-into-founder-stack-for-saas)
- [Claude Code Plugin docs](https://code.claude.com/docs/en/plugins)
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)

---

**End of plan.** Move this file into the Growth Toolkit repo, start a fresh Claude Code session there, point it at this file, and continue from Section 10.
