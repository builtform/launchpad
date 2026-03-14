---
description: "Interactively define your design system, app flow, and frontend guidelines"
---

# Define Design

You are guiding the user through defining their design system, app flow, and frontend guidelines. This command populates three docs through structured Q&A with 17 guided questions and 1 open-ended catch-all:

- `docs/architecture/DESIGN_SYSTEM.md`
- `docs/architecture/APP_FLOW.md`
- `docs/architecture/FRONTEND_GUIDELINES.md`

Every question uses the **guided format**: context explaining WHY the question matters, a dynamically generated options table with "Best When" guidance and examples, a context-aware recommendation based on prior answers, and a TBD escape hatch.

---

## Step 1: Prerequisite Check

Read `docs/architecture/PRD.md`. Check if it contains real content (not just HTML comments or stubs).

**If PRD.md is still a stub**, tell the user:

```
The design docs benefit from knowing your product context (sections, users, features).

docs/architecture/PRD.md - [stub / has content]

I recommend running /define-product first, but I can proceed without it if you prefer.
Would you like to continue or run /define-product first?
```

If the user wants to continue, proceed without PRD context.

**Also check** `docs/architecture/TECH_STACK.md` for frontend framework info (useful for component library and frontend guidelines questions but not required).

---

## Step 2: Load Context

If PRD.md has content, extract: project name, target users, product sections, and overall product type.

If TECH_STACK.md has content, extract: frontend framework, CSS approach, auth provider, and hosting platform.

Present a brief summary:

```
I have loaded your project context:

- Project: [name]
- Users: [brief description]
- Sections: [list from registry]
- Frontend: [framework + styling if known]

I'll walk you through 18 questions to define your design across three files:
- Design System (8 questions): philosophy, colors, typography, spacing, components, dark mode, icons, animation
- App Flow (6 questions): auth, user journey, pages/routes, navigation, errors, accessibility
- Frontend Guidelines (3 questions): component architecture, state management, responsive strategy
— plus an open-ended catch-all at the end for anything we missed.
```

---

## Step 3: Detect Mode

Read all three target files. For each independently:

- If it contains only HTML comments, stub headers, or placeholder text — **create mode**.
- If it contains real project-specific content — **update mode**.

Report the status:

```
File status:
- DESIGN_SYSTEM.md: [create / update] mode
- APP_FLOW.md: [create / update] mode
- FRONTEND_GUIDELINES.md: [create / update] mode
```

---

## Step 4: Gather Design System Information (DS-1 through DS-8)

Ask these questions **one at a time**. Wait for the user's answer before asking the next question. Accept "TBD" for any question.

**IMPORTANT — Guided Format:** For every question, dynamically generate:

1. A brief explanation of WHY this question matters
2. The question itself
3. An options table with columns: Option | Best When | Example
4. A **Recommended** pick with reasoning referencing prior answers
5. A note: **If unsure:** Answer "TBD" — you can fill this in later with `/update-spec`.

The options tables below are starting points. Adapt them based on prior answers and project context.

---

### DS-1: Design Philosophy

WHY: Your design philosophy sets the tone for every visual decision. It's the difference between an app that feels like Apple and one that feels like Craigslist — both valid, but intentionally chosen.

```
What is your overall design philosophy?

Pick the aesthetic direction that best fits your product and users.
```

| Option                  | Best When                                | Example                    |
| ----------------------- | ---------------------------------------- | -------------------------- |
| Minimal / Clean         | Professional SaaS, developer tools       | Apple, Linear, Vercel      |
| Bold / Striking         | Brand-forward products, creative tools   | Stripe, Figma, Arc         |
| Data-dense              | Dashboards, analytics, admin panels      | GitHub, Grafana, Bloomberg |
| Playful / Friendly      | Consumer apps, onboarding-heavy flows    | Notion, Duolingo, Slack    |
| Enterprise / Structured | B2B, compliance-heavy, form-heavy        | Salesforce, Jira, SAP      |
| Neobrutalist            | Indie tools, creative brands, portfolios | Gumroad, early Notion      |

**Recommended:** Generate based on V-3 (target users) from PRD. Developer tools → Minimal. Consumer apps → Playful. B2B SaaS → Enterprise or Minimal.

Reference `docs/ui/ux/design_styles.md` for detailed descriptions of styles like glassmorphism, neobrutalism, neumorphism, bento grid, and kinetic typography if the user wants to explore specific aesthetics.

---

### DS-2: Color Palette

WHY: Color communicates brand, creates hierarchy, and affects accessibility. A well-defined palette prevents inconsistent one-off color choices.

```
What is your color palette?

Define your key colors. You can provide hex values, reference a preset, or describe
the feeling and I'll suggest a palette.
```

| Option                    | Best When                              | Example                                                                      |
| ------------------------- | -------------------------------------- | ---------------------------------------------------------------------------- |
| Generate from brand color | You have a primary brand color         | "Start from #6366F1 (indigo) and generate complementary shades"              |
| Tailwind preset           | Using Tailwind, want consistency       | "Use Tailwind's slate for neutrals, indigo for primary, emerald for success" |
| Radix Colors              | Want accessible, pre-built scales      | "Radix blue + slate + red for errors"                                        |
| Catppuccin                | Developer tools, aesthetic consistency | "Catppuccin Mocha palette"                                                   |
| Custom palette            | Specific brand guidelines              | "Primary: #1a1a2e, Accent: #e94560, Background: #0f3460"                     |

Ask for these specific color roles:

- **Primary** — main brand/action color
- **Secondary** — supporting color
- **Accent** — highlights, badges, callouts
- **Background** — page background
- **Surface** — cards, modals, elevated elements
- **Text** — primary and secondary text colors
- **Semantic** — success (green), warning (amber), error (red), info (blue)

**Recommended:** Generate based on DS-1 philosophy. Minimal → muted neutrals + single accent. Bold → vibrant primary + contrasting accent. Data-dense → high-contrast neutrals.

---

### DS-3: Typography

WHY: Font choice affects readability, personality, and perceived quality. Consistent type scales prevent visual chaos.

```
What fonts and type scale will you use?

Specify heading font, body font, and monospace font (for code/data).
```

| Option               | Best When                        | Example                                       |
| -------------------- | -------------------------------- | --------------------------------------------- |
| Inter                | Clean, versatile, great for UI   | Used by Linear, Vercel, Raycast               |
| Geist                | Modern, designed for code + UI   | Vercel's custom font                          |
| System fonts         | Fastest load, native feel        | `-apple-system, BlinkMacSystemFont, Segoe UI` |
| Plus Jakarta Sans    | Friendly, geometric, modern      | Great for consumer apps                       |
| DM Sans + DM Mono    | Paired heading + mono, geometric | Clean developer tool aesthetic                |
| Custom / Brand fonts | Specific brand identity          | "Heading: Clash Display, Body: Satoshi"       |

Also ask:

- **Base font size**: typically 14px (data-dense), 16px (standard), or 18px (content-focused)
- **Type scale**: how headings relate to body (e.g., 1.25 minor third, 1.333 perfect fourth)

**Recommended:** Generate based on DS-1 and target users. Developer tools → Geist or Inter + JetBrains Mono. Consumer → Plus Jakarta Sans. Enterprise → Inter or system fonts.

---

### DS-4: Spacing & Layout

WHY: Consistent spacing creates visual rhythm and prevents "why does this look off?" debugging. A spacing system makes every layout decision automatic.

```
What spacing system and layout constraints will you use?
```

| Option              | Best When                           | Example                          |
| ------------------- | ----------------------------------- | -------------------------------- |
| 4px base (Tailwind) | Most web apps, fine-grained control | 4, 8, 12, 16, 20, 24, 32, 48, 64 |
| 8px base (Material) | Cleaner math, slightly larger gaps  | 8, 16, 24, 32, 48, 64, 96        |
| Custom base         | Specific design requirements        | "6px base with 1.5x multiplier"  |

Also ask:

- **Max content width**: e.g., 1280px, 1440px, full-width
- **Sidebar width** (if applicable): e.g., 240px collapsed to 64px
- **Container padding**: e.g., 16px mobile, 24px tablet, 32px desktop

**Recommended:** Generate based on DS-1. Minimal → 4px base, 1280px max. Data-dense → 4px base, full-width. Enterprise → 8px base, 1440px max.

---

### DS-5: Component Library

WHY: Starting from a component library saves weeks of building buttons, modals, and form inputs. The choice affects your entire frontend development speed.

```
What component library will you use?
```

| Option              | Best When                                                         | Example                                       |
| ------------------- | ----------------------------------------------------------------- | --------------------------------------------- |
| shadcn/ui           | Tailwind-based, copy-paste into your project, highly customizable | Most popular for Next.js + Tailwind           |
| Radix UI            | Unstyled accessible primitives, you own the styling               | When you want full design control             |
| Material UI (MUI)   | Google Material Design, comprehensive                             | Enterprise apps, rapid prototyping            |
| Chakra UI           | Accessible, themeable, good DX                                    | Small-to-medium React apps                    |
| Headless UI         | Unstyled, from Tailwind team                                      | When using Tailwind, want minimal abstraction |
| Mantine             | Feature-rich, batteries-included                                  | Complex forms, date pickers, rich text        |
| Custom from scratch | Unique brand, full control                                        | When off-the-shelf doesn't fit                |

**Recommended:** Generate based on TS-1 (frontend framework) and TS-2 (CSS approach) from TECH_STACK. If Next.js + Tailwind → strongly recommend shadcn/ui. If Vue/Nuxt → suggest PrimeVue or Vuetify. If Svelte → suggest Skeleton or Melt UI.

---

### DS-6: Dark Mode

WHY: Dark mode is a user expectation in modern apps. Deciding now prevents painful retrofitting later — you'll design all colors, shadows, and borders with both modes in mind.

```
Will your app support dark mode?
```

| Option                   | Best When                                           | Example                                  |
| ------------------------ | --------------------------------------------------- | ---------------------------------------- |
| Light only               | Simple app, corporate branding requires light       | Marketing sites, some B2B tools          |
| Dark only                | Developer tools, creative tools, media apps         | Terminal apps, video editors, IDEs       |
| System preference        | Respects user's OS setting automatically            | Most modern SaaS apps                    |
| Manual toggle            | User can override system preference                 | Apps where users work in varied lighting |
| System + manual override | Best of both: defaults to system, user can override | Linear, GitHub, VS Code                  |

**Recommended:** Generate based on V-3 (users) and DS-1 (philosophy). Developer tools → Dark only or System + manual. Consumer → System preference. Enterprise → Light only or System + manual.

---

### DS-7: Icons & Imagery

WHY: Consistent iconography prevents the "mix of 5 different icon styles" problem. Choosing an icon set upfront ensures visual coherence.

```
What icon set will you use? Any imagery guidelines?
```

| Option       | Best When                                       | Example                                |
| ------------ | ----------------------------------------------- | -------------------------------------- |
| Lucide       | Clean, consistent, huge library, React-friendly | Most popular for modern apps           |
| Heroicons    | By Tailwind team, two styles (outline/solid)    | Pairs perfectly with Tailwind          |
| Phosphor     | Flexible (6 weights), large library             | When you need weight variety           |
| Tabler Icons | Over 4000 icons, consistent stroke              | Data-heavy apps needing many icons     |
| Custom SVGs  | Unique brand identity                           | When off-the-shelf doesn't match brand |

Also ask about imagery:

- **Illustrations**: hand-drawn, geometric, 3D, none
- **Photos**: real, stock, AI-generated, none
- **Avatar style**: initials, Gravatar, custom upload, boring avatars

**Recommended:** Generate based on TS-2 and DS-5. If using Tailwind → Heroicons or Lucide. If using shadcn/ui → Lucide (it's the default).

---

### DS-8: Animation Philosophy

WHY: Animation can make your app feel polished or distracting. An intentional philosophy prevents both under- and over-animation.

```
What is your approach to animation and motion?
```

| Option             | Best When                                                  | Example                                        |
| ------------------ | ---------------------------------------------------------- | ---------------------------------------------- |
| None / minimal     | Data-dense apps, accessibility-first, performance-critical | Bloomberg, admin panels                        |
| Subtle transitions | Professional feel without distraction                      | Linear (smooth page transitions, hover states) |
| Purposeful motion  | Guides attention, explains state changes                   | Stripe (card animations, loading states)       |
| Rich animations    | Brand differentiator, delightful UX                        | Framer, Apple (complex interactions)           |

**Important:** Regardless of choice, always respect `prefers-reduced-motion` — users who set this OS preference should get minimal or no animation.

Also ask:

- **Transition duration**: fast (150ms), medium (300ms), slow (500ms)
- **Easing**: ease-out (most UI), spring (playful), linear (progress bars)
- **Library preference**: CSS transitions only, Framer Motion, GSAP, none

**Recommended:** Generate based on DS-1 and V-3. Minimal → Subtle transitions. Playful → Purposeful motion. Enterprise → None/minimal. Developer tools → Subtle transitions.

---

## Step 5: Write DESIGN_SYSTEM.md

Write `docs/architecture/DESIGN_SYSTEM.md`:

```markdown
# [Project Name] — Design System

**Last Updated**: [YYYY-MM-DD]
**Status**: Draft
**Version**: 1.0

## Design Philosophy

[DS-1 answer — chosen philosophy with reasoning]

## Color Palette

### Core Colors

| Role             | Value | Usage               |
| ---------------- | ----- | ------------------- |
| Primary          | [hex] | [usage description] |
| Secondary        | [hex] | [usage description] |
| Accent           | [hex] | [usage description] |
| Background       | [hex] | [usage description] |
| Surface          | [hex] | [usage description] |
| Text (primary)   | [hex] | [usage description] |
| Text (secondary) | [hex] | [usage description] |

### Semantic Colors

| Role    | Value | Usage                           |
| ------- | ----- | ------------------------------- |
| Success | [hex] | Confirmations, positive states  |
| Warning | [hex] | Caution states, pending actions |
| Error   | [hex] | Errors, destructive actions     |
| Info    | [hex] | Informational messages          |

## Typography

- **Heading font**: [DS-3 answer]
- **Body font**: [DS-3 answer]
- **Monospace font**: [DS-3 answer]
- **Base size**: [px]
- **Type scale**: [ratio]

## Spacing & Layout

- **Base unit**: [DS-4 answer]
- **Scale**: [computed values]
- **Max content width**: [value]
- **Sidebar width**: [value if applicable]
- **Container padding**: [responsive values]

## Component Library

- **Library**: [DS-5 answer]
- **Customization approach**: [how components are styled/themed]

## Dark Mode

- **Strategy**: [DS-6 answer]
- **Implementation**: [how theme switching works]

## Icons & Imagery

- **Icon set**: [DS-7 answer]
- **Illustrations**: [style or "none"]
- **Photos**: [approach or "none"]
- **Avatars**: [style]

## Animation & Motion

- **Philosophy**: [DS-8 answer]
- **Transition duration**: [value]
- **Easing**: [value]
- **Library**: [choice or "CSS only"]
- **Reduced motion**: Always respect `prefers-reduced-motion`
```

**In update mode:** Only modify sections the user chose to update. Preserve everything else.

---

## Step 6: Gather App Flow Information (AF-1 through AF-6)

Introduce the section, then ask these questions **one at a time**, waiting for each answer. Accept "TBD" for any question. In update mode, show the current value and ask "Keep this or change it?"

**IMPORTANT — Guided Format:** For every question, dynamically generate options table, recommendation referencing prior answers, and TBD escape hatch.

---

### AF-1: Auth Flow

WHY: Authentication is the first thing users experience. A well-defined auth flow prevents security gaps and UX confusion.

```
How should authentication work in your app?

Describe the login, signup, and password reset flows.
```

| Option               | Best When                         | Example                                                             |
| -------------------- | --------------------------------- | ------------------------------------------------------------------- |
| Email + password     | Simple, traditional               | "Sign up with email/password, verify email, login, forgot password" |
| OAuth only           | Developer tools, quick onboarding | "Sign in with GitHub/Google, no password, auto-create account"      |
| Email + OAuth hybrid | Flexibility for users             | "Email/password or Google/GitHub OAuth, link accounts"              |
| Magic link           | Passwordless, modern              | "Enter email, receive login link, no password needed"               |
| SSO / SAML           | Enterprise, B2B                   | "SAML SSO for enterprise customers, email/password for free tier"   |

**Recommended:** Generate based on auth provider from TECH_STACK and target users from PRD.

---

### AF-2: Main User Journey

WHY: The primary user journey defines the "happy path" — the core experience your app delivers. Everything else supports this flow.

```
What is the primary user journey after logging in?

Walk me through the main workflow step by step.
```

Do NOT provide a generic options table. Instead, generate a **worked example** based on the user's product sections and features:

```
Based on your product sections ([list]), here's a possible journey:

1. User lands on [first section] showing [relevant data]
2. User navigates to [core section] to [primary action]
3. User [creates/configures/views] [key entity]
4. System [processes/displays/confirms] the result
5. User can [next logical action]

Does this match your vision? Adjust as needed.
```

---

### AF-3: Pages and Routes

WHY: A route map prevents duplicate pages, naming conflicts, and ensures every section has a home.

```
What are the main pages/routes?

List each with its path and a one-line description.
```

Pre-populate from the section registry:

```
Based on your product sections, here's a starting route map:

| Route | Page | Description | Auth Required |
|-------|------|-------------|---------------|
| / | Landing | [public marketing page or redirect to dashboard] | No |
| /login | Login | Authentication | No |
| /dashboard | Dashboard | [from section registry] | Yes |
| /[section] | [Section] | [from section registry] | Yes |
| /settings | Settings | [from section registry] | Yes |

Confirm, adjust, or add routes.
```

---

### AF-4: Navigation Pattern

WHY: Navigation pattern affects layout, responsive behavior, and how users discover features.

```
What navigation pattern will you use?
```

| Option                      | Best When                        | Example                    |
| --------------------------- | -------------------------------- | -------------------------- |
| Top navbar + sidebar        | Feature-rich SaaS, many sections | Linear, Notion, GitHub     |
| Top navbar only             | Simple apps, few sections        | Stripe Dashboard, Vercel   |
| Sidebar only                | Data-heavy apps, deep navigation | Slack, Discord, VS Code    |
| Bottom tabs                 | Mobile-first, < 5 sections       | Most mobile apps           |
| Minimal (no persistent nav) | Single-purpose tools, wizards    | Typeform, onboarding flows |
| Command palette + minimal   | Developer tools, keyboard-first  | Raycast, VS Code, Linear   |

**Recommended:** Generate based on section count and target users. Many sections → sidebar. Few sections → top navbar. Developer tools → command palette.

Also ask: What goes in the nav? Does it collapse on mobile? Breadcrumbs?

---

### AF-5: Error States

WHY: Users spend more time in error states than you'd expect. Well-designed error handling prevents confusion, data loss, and support tickets.

```
How should errors be handled?

Cover: 404, 500, network offline, unauthorized (expired session), and empty states.
```

| Option                  | Best When              | Example                                                     |
| ----------------------- | ---------------------- | ----------------------------------------------------------- |
| Friendly error pages    | Consumer apps          | Custom illustration + "Something went wrong" + retry button |
| Technical error details | Developer tools        | Error code, stack trace, copy-to-clipboard                  |
| Toast notifications     | Non-critical errors    | Brief notification that auto-dismisses                      |
| Inline validation       | Form errors            | Red border + message under the field                        |
| Error boundaries        | React apps             | Catch component crashes, show fallback UI                   |
| Retry with backoff      | Network-dependent apps | Auto-retry 3 times, then show error                         |

**Recommended:** Generate based on target users and frontend framework. Consumer → friendly pages. Developer tools → technical details. React → error boundaries.

---

### AF-6: Accessibility Patterns

WHY: Accessibility ensures your app works for everyone — including users with disabilities, users on slow connections, and users navigating with keyboards. Building it in from the start is 10x cheaper than retrofitting.

```
What accessibility patterns will you implement?
```

| Option                 | Best When                           | Example                                      |
| ---------------------- | ----------------------------------- | -------------------------------------------- |
| Keyboard navigation    | All web apps (should always be yes) | Tab order, focus rings, keyboard shortcuts   |
| Screen reader support  | Public-facing, compliance-required  | ARIA labels, semantic HTML, live regions     |
| Focus management       | SPAs, modal-heavy apps              | Trap focus in modals, restore focus on close |
| Skip navigation        | Content-heavy pages                 | "Skip to main content" link                  |
| Reduced motion         | Apps with animation                 | Respect prefers-reduced-motion               |
| High contrast          | Data-dense, enterprise              | Support prefers-contrast, WCAG AA ratios     |
| WCAG 2.1 AA compliance | Public-facing, legal requirements   | Full audit, automated testing                |

**Recommended:** At minimum, always recommend keyboard navigation + focus management + reduced motion. For public-facing apps, recommend WCAG 2.1 AA.

---

## Step 7: Write APP_FLOW.md

Write `docs/architecture/APP_FLOW.md` with: header (project name, date, Draft status, version 1.0), then sections for Authentication Flow (numbered steps), Main User Journey (numbered steps), Pages and Routes (table: Route, Page, Description, Auth Required), Navigation (description + responsive behavior), Error Handling (table: Scenario, Behavior for each error type), Accessibility (chosen patterns with implementation notes).

In update mode, only modify sections the user chose to change.

---

## Step 8: Gather Frontend Guidelines Information (FG-1 through FG-3)

Tailor questions to the frontend framework and CSS approach from TECH_STACK.md. Reference DESIGN_SYSTEM.md (just written in Step 5).

**Note:** Component library choice is already defined in DS-5. Reference it here.

---

### FG-1: Component Architecture

WHY: Consistent component organization prevents "where do I put this?" decisions and makes the codebase navigable.

```
How should components be organized?
```

| Option                    | Best When                           | Example                                                             |
| ------------------------- | ----------------------------------- | ------------------------------------------------------------------- |
| Feature-based             | Medium-to-large apps, many features | `components/dashboard/`, `components/auth/`, `components/projects/` |
| Atomic design             | Design-system-heavy apps            | `atoms/Button`, `molecules/SearchBar`, `organisms/Header`           |
| Hybrid (shared + feature) | Most SaaS apps                      | `components/ui/` for generic + `features/dashboard/` for specific   |
| Flat with clear naming    | Small apps, < 20 components         | Single `components/` directory with descriptive names               |
| Co-located (Next.js)      | Next.js App Router                  | Components alongside routes in `app/[route]/_components/`           |

Also ask:

- Naming conventions? (PascalCase files, barrel exports, co-located tests)
- Where do hooks go? (co-located, shared `hooks/`, feature-level)

**Recommended:** Generate based on frontend framework and app size. Next.js App Router → co-located or hybrid. Many sections → feature-based.

---

### FG-2: State Management

WHY: State management strategy affects data freshness, performance, and developer experience. Getting it wrong leads to prop drilling, stale data, and unnecessary re-renders.

```
What state management approach?
```

| Option                | Best When                             | Example                                     |
| --------------------- | ------------------------------------- | ------------------------------------------- |
| React state + Context | Simple apps, few shared state needs   | Built-in, zero dependencies                 |
| Zustand               | Lightweight global state              | Simple API, minimal boilerplate             |
| Jotai                 | Atomic state, fine-grained reactivity | Bottom-up approach, great for derived state |
| Redux Toolkit         | Complex state, time-travel debugging  | Enterprise apps, large teams                |
| TanStack Query        | Server state (API data)               | Caching, refetching, optimistic updates     |
| SWR                   | Server state, simpler API             | Vercel ecosystem, stale-while-revalidate    |
| Nuxt/Pinia            | Vue ecosystem                         | Composable stores, SSR-friendly             |

Most apps combine **server state** (TanStack Query / SWR) + **client state** (Zustand / React state).

**Recommended:** Generate based on frontend framework and data complexity. Next.js + many entities → TanStack Query + Zustand. Simple app → React state only.

---

### FG-3: Responsive Strategy

WHY: Responsive design decisions affect every component. Deciding upfront prevents inconsistent breakpoint usage and mobile afterthoughts.

```
What is your responsive design strategy?
```

| Option                      | Best When                          | Example                                                     |
| --------------------------- | ---------------------------------- | ----------------------------------------------------------- |
| Mobile-first                | Consumer apps, high mobile traffic | Start with mobile layout, add complexity for larger screens |
| Desktop-first               | SaaS dashboards, data-heavy apps   | Start with full layout, simplify for mobile                 |
| Desktop-only                | Internal tools, admin panels       | No mobile layout, minimum 1024px                            |
| Responsive with breakpoints | Most web apps                      | Tailwind defaults: sm 640, md 768, lg 1024, xl 1280         |
| Adaptive (separate layouts) | Very different mobile vs desktop   | Different component trees for mobile and desktop            |

Also ask:

- Minimum supported width?
- Tablet-specific layouts needed?
- Mobile-specific behavior? (bottom sheets, swipe gestures, simplified views)

**Recommended:** Generate based on target users and product type. Consumer → mobile-first. SaaS dashboard → desktop-first. Internal tool → desktop-only.

---

## Step 9: Write FRONTEND_GUIDELINES.md

Write `docs/architecture/FRONTEND_GUIDELINES.md` with: header block, then sections for:

**Design System Reference** — Add:

```markdown
## Design System Reference

See [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) for visual design decisions:
component library, color palette, typography, spacing, icons, and animation.
```

Then: Component Architecture (with Directory Structure code block showing example tree and Naming Conventions subsection), State Management (with Server State, Client State, URL State subsections), Responsive Design (bullet points: approach, breakpoints, minimum width, plus additional notes).

In update mode, only modify sections the user chose to change.

---

## Step 10: Open-Ended Catch-All

After all three files' questions are complete, ask:

```
Is there anything about your design, app flow, or frontend guidelines that we haven't covered?
Any brand guidelines, accessibility requirements, UX patterns, or frontend preferences?

If not, just say "No, we're good" and I'll finalize the output files.
```

**No options table** — purely open-ended.

**CRITICAL behavior:** If the user provides additional information, parse it and integrate it into the appropriate doc section. Do NOT create a separate "Other Notes" section. Examples:

- "We need WCAG 2.1 AA compliance" → add to APP_FLOW.md Accessibility section
- "Our brand color is #FF6B35" → integrate into DESIGN_SYSTEM.md Color Palette section
- "No gradients anywhere" → add as a constraint in DESIGN_SYSTEM.md Design Philosophy section
- "We're using a monorepo" → add to FRONTEND_GUIDELINES.md

If the user says "No" or "We're good", proceed directly to the summary.

---

## Step 11: Summary and Next Step

After all files are written, present a summary:

```
Done. Here is what was written:

**docs/architecture/DESIGN_SYSTEM.md**
- Philosophy: [choice]
- Colors: [primary color] + [N] semantic colors
- Typography: [heading font] / [body font]
- Components: [library]
- Dark mode: [strategy]
- Icons: [set]
- Animation: [philosophy]

**docs/architecture/APP_FLOW.md**
- Auth: [flow type]
- Pages: [count] routes
- Navigation: [pattern]
- Error handling: [approach]
- Accessibility: [patterns]

**docs/architecture/FRONTEND_GUIDELINES.md**
- Components: [architecture]
- State: [management approach]
- Responsive: [strategy]

Recommended next step: Run `/define-architecture` to define your backend structure
and CI/CD pipeline.

After that, use `/shape-section [name]` to deep-dive into each product section.
```

---

## Behavioral Rules

1. **Ask one question at a time.** Never batch multiple questions into a single message.
2. **Wait for an answer before proceeding.** Do not assume or fill in answers.
3. **Accept "TBD" gracefully.** Write it literally into the docs. Do not push for decisions.
4. **In update mode, show current values.** Let the user confirm or change each field.
5. **Do not invent information.** Only write what the user explicitly told you.
6. **Use exact answers provided.** Do not rephrase or editorialize unless the user asks you to clean up their wording.
7. **Generate guided format dynamically.** Options tables and recommendations must reference prior answers. Adapt, add, or remove options based on context.
8. **Handle files in order: DESIGN_SYSTEM, APP_FLOW, FRONTEND_GUIDELINES.** Visual foundation → UX flows → implementation patterns (natural dependency chain).
9. **Reference design_styles.md when relevant.** If the user asks about specific aesthetics (glassmorphism, bento grid, etc.), reference `docs/ui/ux/design_styles.md` for detailed descriptions.
10. **Integrate open-ended answers.** Parse the catch-all response and place information in the appropriate document sections.
11. **Allow skipping.** If the user wants to skip a file, accept it, write "TBD" for all its sections, and move on.
