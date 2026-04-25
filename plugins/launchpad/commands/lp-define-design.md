---
name: lp-define-design
description: "Interactively define your design system, app flow, and frontend guidelines with Jobs/Ive quality bar"
---

# Define Design

You are guiding the user through defining their design system, app flow, and frontend guidelines. This command populates three docs through structured Q&A with 17 guided questions and 1 open-ended catch-all:

- `docs/architecture/DESIGN_SYSTEM.md`
- `docs/architecture/APP_FLOW.md`
- `docs/architecture/FRONTEND_GUIDELINES.md`

Every question uses the **guided format**: context explaining WHY the question matters, a dynamically generated options table with "Best When" guidance and examples, a context-aware recommendation based on prior answers, and a TBD escape hatch.

---

## Design Quality Bar (Jobs/Ive Lens)

Throughout this entire definition process, apply the following design philosophy as a quality filter on every answer, recommendation, and generated output. These are not optional aesthetics — they are architectural constraints.

### Core Principles

1. **Simplicity is architecture** — Every element must justify its existence. If it doesn't serve the user's immediate goal, it's clutter. The best interface is the one the user never notices.
2. **Hierarchy drives everything** — Every screen has one primary action. Make it unmissable. Secondary actions support, they never compete. If everything is bold, nothing is bold.
3. **Whitespace is a feature** — Space is not empty. It is structure. Crowded interfaces feel cheap. Breathing room feels premium.
4. **Alignment is precision** — Every element sits on a grid. No exceptions. If something is off by 1-2 pixels, it's wrong.
5. **Consistency is non-negotiable** — The same component must look and behave identically everywhere. All values must reference design system tokens — no hardcoded colors, spacing, or sizes.
6. **Design the feeling** — Premium apps feel calm, confident, and quiet. Every interaction should feel responsive and intentional.

### The Density Principle

> "Remove until it breaks, then add back the last thing."

When defining components, tokens, or layouts during this Q&A, apply this filter: if an element, color role, spacing value, or component variant can be removed without losing meaning, it should not exist in the system.

### Responsive-First Thinking

Mobile is the starting point. Tablet and desktop are enhancements. Every design decision made during this definition must be considered at mobile viewport first, then scaled up. If a design token, component, or layout pattern doesn't work on a phone screen, it needs rethinking — not just resizing.

---

## Step 1: Prerequisite Check

Read `docs/architecture/PRD.md`. Check if it contains real content (not just HTML comments or stubs).

**If PRD.md is still a stub**, tell the user:

```
The design docs benefit from knowing your product context (sections, users, features).

docs/architecture/PRD.md - [stub / has content]

I recommend running /lp-define-product first, but I can proceed without it if you prefer.
Would you like to continue or run /lp-define-product first?
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

I'll walk you through 19 questions to define your design across three files:
- Design System (9 questions): brand identity, philosophy, colors, typography, spacing, components, dark mode, icons, animation
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

## Step 4: Gather Design System Information (DS-0 through DS-8)

Ask these questions **one at a time**. Wait for the user's answer before asking the next question. Accept "TBD" for any question.

**IMPORTANT — Guided Format:** For every question, dynamically generate:

1. A brief explanation of WHY this question matters
2. The question itself
3. An options table with columns: Option | Best When | Example
4. A **Recommended** pick with reasoning referencing prior answers
5. A note: **If unsure:** Answer "TBD" — you can fill this in later with `/lp-update-spec`.

The options tables below are starting points. Adapt them based on prior answers and project context.

**IMPORTANT — Design References:** For any visual question (DS-0 through DS-8), the user may provide a **product name** or **URL** instead of (or alongside) a direct answer. Handle each case:

- **Product name** (e.g., "I like Linear's typography" or "Stripe's color palette"): Use your existing knowledge of that product's design language. Propose specific values (hex codes, font names, spacing values) based on what you know, and confirm with the user.
- **URL** (e.g., "https://example.com — I like their color scheme"): Use WebFetch to crawl the page. Extract CSS custom properties (`--color-*`, `--font-*`), `font-family` declarations, hex/rgb color values from stylesheets, and `<meta name="theme-color">` tags. Propose extracted values to the user for confirmation. If extraction is partial, say what was found and ask the user to fill gaps.
- **Multiple references** (e.g., "Linear for typography, Stripe for colors"): Extract from each reference independently and compose the answers. Note the sources in the design system doc for future reference.

Add this note to every visual question (DS-0 through DS-8):

```
You can also name a product you admire (e.g., "Like Linear") or paste a URL and
I'll extract the relevant design values from it.
```

---

### DS-0: Brand Identity

WHY: Brand identity anchors every visual and verbal decision that follows. Without it, color choices are arbitrary, font choices are aesthetic preferences, and UI copy sounds like it was written by five different people. Defining brand personality, voice, and tone BEFORE visual tokens ensures that colors, fonts, spacing, and copy all express a coherent identity.

```
Let's define your brand identity before we make any visual decisions.
This anchors everything that follows — colors, fonts, and UI copy will all flow from these answers.
```

**Part A — Brand Personality**

Pick 1 primary + 1 secondary personality dimension:

| Dimension      | Traits                                     | Brands That Express This      |
| -------------- | ------------------------------------------ | ----------------------------- |
| Sincerity      | Honest, wholesome, cheerful, grounded      | Mailchimp, Basecamp, Notion   |
| Excitement     | Daring, spirited, imaginative, current     | Figma, Arc, Vercel            |
| Competence     | Reliable, intelligent, successful, precise | Linear, Stripe, GitHub        |
| Sophistication | Upper-class, charming, elegant, refined    | Apple, Squarespace, Aesop     |
| Ruggedness     | Outdoorsy, tough, bold, no-nonsense        | Patagonia, Carhartt, Basecamp |

**Recommended:** Generate based on V-3 (target users) from PRD. Developer tools → Competence. Consumer apps → Sincerity or Excitement. B2B SaaS → Competence or Sophistication. AEC/construction → Competence + Ruggedness.

**Part B — Tone Fingerprint**

Place your brand on each spectrum (1-5 scale, or just pick a side):

| Spectrum  | 1 (Left)     | 5 (Right)      |
| --------- | ------------ | -------------- |
| Humor     | Funny        | Serious        |
| Formality | Casual       | Formal         |
| Attitude  | Irreverent   | Respectful     |
| Energy    | Enthusiastic | Matter-of-fact |

**Recommended:** Generate based on Part A. Competence → Serious, Formal, Respectful, Matter-of-fact. Sincerity → Funny-leaning, Casual, Respectful, Enthusiastic. Excitement → Funny-leaning, Casual, Irreverent, Enthusiastic.

**Part C — Voice Attributes**

Pick 3-4 adjectives that describe how your brand speaks. For each, generate a "Write this / Not that" example pair:

```
Example voice attributes with This/Not That:

| Attribute | Write This | Not That |
|-----------|-----------|----------|
| Plainspoken | "Your project was created." | "Your project has been successfully instantiated." |
| Confident | "Here's what to do next." | "You might want to consider possibly trying..." |
| Warm | "Welcome back, let's pick up where you left off." | "Session restored." |
| Precise | "3 tasks remaining, 2 due today." | "You have some tasks to do!" |
```

Ask the user to pick 3-4 attributes or provide their own. Generate the This/Not That pairs for their choices.

**Key rule from research:** In high-stakes moments (payment failure, data loss, security alerts), clarity always trumps personality. Dial personality to zero when the user is stressed.

---

### DS-1: Design Philosophy

WHY: Your design philosophy sets the tone for every visual decision. It's the difference between an app that feels like Apple and one that feels like Craigslist — both valid, but intentionally chosen. Regardless of which aesthetic you pick, the Jobs/Ive quality bar applies: simplicity, hierarchy, whitespace, alignment, consistency, and calm confidence are non-negotiable qualities layered on top of any aesthetic direction.

```
What is your overall design philosophy?

Pick the aesthetic direction that best fits your product and users.
Every option below will be held to the same quality standard: simplicity as architecture,
hierarchy that guides the eye, and whitespace that breathes.
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

**Quality lens follow-up:** After the user picks a philosophy, confirm how the Jobs/Ive principles map to their choice:

```
Your choice: [philosophy]

Here's how the premium quality bar applies to [philosophy]:
- Hierarchy: [how hierarchy manifests in this style]
- Whitespace: [how breathing room works in this style]
- Density: [what "remove until it breaks" means for this style]
- Feeling: [what calm/confident/quiet looks like in this style]
```

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

**Quality lens:** Apply color restraint — color should guide attention, not scatter it. Ask: "Is each color role earning its place? Could two roles be merged without losing meaning?" Fewer colors used with purpose always beats a large palette used inconsistently. Ensure contrast ratios meet WCAG AA minimum (4.5:1 for text, 3:1 for large text/UI elements).

**Brand lens:** Reference DS-0 brand personality to guide palette direction:

| Personality    | Color Direction                                       | Why                                           |
| -------------- | ----------------------------------------------------- | --------------------------------------------- |
| Sincerity      | Warm tones, earth tones, soft blues                   | Conveys trust, approachability, honesty       |
| Excitement     | Vibrant primaries, bold contrasts, saturated accents  | Conveys energy, daring, imagination           |
| Competence     | Blues, cool neutrals, precise accents                 | Conveys reliability, intelligence, precision  |
| Sophistication | Deep purples, blacks, muted golds, restrained palette | Conveys elegance, refinement, premium quality |
| Ruggedness     | Earth tones, deep greens, warm grays, high contrast   | Conveys strength, durability, no-nonsense     |

Ask: "Does this palette express your [primary personality] brand? A user should feel [personality traits] when they see these colors."

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

**Quality lens:** Typography establishes hierarchy before the user reads a single word. Apply the density principle: how many distinct type sizes are truly needed? Most premium apps use 5-7 sizes total. If there are more than 3 font weights in regular use, the hierarchy is competing with itself. Type should feel calm, not chaotic — too many sizes or weights fighting for attention is a design failure.

**Brand lens:** Reference DS-0 brand personality to guide font category:

| Personality    | Font Category                                          | Why                                  |
| -------------- | ------------------------------------------------------ | ------------------------------------ |
| Sincerity      | Humanist sans-serif (Plus Jakarta Sans, Source Sans)   | Warm, approachable, natural curves   |
| Excitement     | Geometric sans-serif (Space Grotesk, Clash Display)    | Modern, precise, forward-looking     |
| Competence     | Geometric or neo-grotesque (Inter, Geist, DM Sans)     | Clean, reliable, technical precision |
| Sophistication | Serif or refined sans-serif (Playfair Display, Outfit) | Established, elegant, authoritative  |
| Ruggedness     | Slab serif or bold sans-serif (Roboto Slab, Work Sans) | Grounded, confident, no-frills       |

Ask: "Does this font feel like your brand speaking? If your brand were a person using [primary personality] voice, would they write in this typeface?"

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

**Quality lens:** Whitespace is a feature, not wasted space. When in doubt, add more space, not more elements. The spacing scale should create visual rhythm — a harmonious vertical flow where elements breathe. Consider responsive container padding carefully: mobile screens need tighter but still intentional spacing, not cramped afterthoughts. Every spacing value in the system must be from the scale — no magic numbers, no one-off padding values.

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

**Quality lens — Jobs Filter for Components:** When the user selects a library, apply these questions to their component strategy before moving on:

```
Before we continue, let's apply the design quality filter to your component choices:

1. "Would a user need to be told this exists?" — Every interactive element should be
   obviously interactive. If a button doesn't look pressable, it needs redesign.
2. "Can this be removed without losing meaning?" — Which component variants
   (sizes, styles) do you actually need? Start with the minimum set and add only
   when a real use case demands it.
3. "Does this feel inevitable?" — When a user sees your components, they should
   feel like no other design was possible. This means consistent border radius,
   consistent shadow depth, consistent padding — across every component.

How many component variants do you anticipate needing? (e.g., Button: primary,
secondary, ghost, destructive — or can we start with fewer?)
```

Record the user's answer. Use it to constrain the component section in DESIGN_SYSTEM.md.

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

**Quality lens:** Transitions should feel like physics, not decoration. Every animation must have a purpose: guide attention, explain a state change, or provide feedback. If an animation exists for no functional reason, remove it. The density principle applies here too — fewer, more intentional animations always beat many decorative ones.

---

## Step 5: Write DESIGN_SYSTEM.md

Write `docs/architecture/DESIGN_SYSTEM.md`:

```markdown
# [Project Name] — Design System

**Last Updated**: [YYYY-MM-DD]
**Status**: Draft
**Version**: 1.0

## Brand Identity

### Personality

- **Primary dimension**: [DS-0 Part A — e.g., Competence]
- **Secondary dimension**: [DS-0 Part A — e.g., Sophistication]

### Tone Fingerprint

| Spectrum  | Position                             | Notes     |
| --------- | ------------------------------------ | --------- |
| Humor     | [1-5: Funny ↔ Serious]               | [context] |
| Formality | [1-5: Casual ↔ Formal]               | [context] |
| Attitude  | [1-5: Irreverent ↔ Respectful]       | [context] |
| Energy    | [1-5: Enthusiastic ↔ Matter-of-fact] | [context] |

### Voice Attributes

| Attribute | Write This | Not That          |
| --------- | ---------- | ----------------- |
| [attr 1]  | [example]  | [counter-example] |
| [attr 2]  | [example]  | [counter-example] |
| [attr 3]  | [example]  | [counter-example] |

### Tone by Context

How voice adapts to user emotional state (clarity always trumps personality in high-stakes moments):

| UI Context       | Tone Shift                   | Example                         |
| ---------------- | ---------------------------- | ------------------------------- |
| Onboarding       | [warmer, more encouraging]   | [example from voice attributes] |
| Success          | [celebratory but restrained] | [example]                       |
| Error            | [empathetic, clarity-first]  | [example]                       |
| Empty state      | [action-oriented, warm]      | [example]                       |
| Payment/security | [serious, zero personality]  | [example]                       |
| Tooltip/helper   | [concise, informative]       | [example]                       |

## Design References

_Products and URLs that inspired this design system. Not copied — used as directional reference._

| Aspect                | Reference                   | What We Took                                         |
| --------------------- | --------------------------- | ---------------------------------------------------- |
| [e.g., Typography]    | [e.g., Linear]              | [e.g., Clean geometric sans-serif, tight type scale] |
| [e.g., Color palette] | [e.g., https://example.com] | [e.g., Muted blue primary, warm neutral backgrounds] |

## Design Philosophy

[DS-1 answer — chosen philosophy with reasoning]

### Quality Principles

These principles apply to every design decision, regardless of aesthetic direction:

- **Simplicity is architecture** — Every element justifies its existence. Complexity is a design failure.
- **Hierarchy drives everything** — Every screen has one primary action. Visual weight matches functional importance.
- **Whitespace is a feature** — Space is structure. When in doubt, add more space, not more elements.
- **Alignment is precision** — Every element sits on a grid. No exceptions.
- **Consistency is non-negotiable** — All values reference design system tokens. No hardcoded one-offs.
- **Density test** — Remove until it breaks, then add back the last thing.
- **Responsive-first** — Mobile is the starting point. Desktop is the enhancement.

### Jobs Filter (Component Validation)

Before adding any new component or variant, ask:

1. "Would a user need to be told this exists?" — if yes, redesign until obvious
2. "Can this be removed without losing meaning?" — if yes, remove it
3. "Does this feel inevitable, like no other design was possible?" — if no, keep refining
4. "Say no to 1,000 things" — cut good ideas to keep great ones

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
- **Motion rule**: Transitions feel like physics, not decoration. No animation without purpose.
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

**Quality lens:** Error states, empty states, and loading states are design surfaces, not afterthoughts. A blank screen should feel intentional, not broken. Error messages should feel helpful and clear, never hostile or technical. These "edge" states are where premium apps separate from adequate ones — the back of the fence must be painted too.

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

**Quality lens:** Regardless of which strategy the user picks, responsive design is the real design. Every screen must feel intentional at every viewport — not just resized. Design for thumbs first, then cursors. Touch targets must be sized for thumbs on touch devices (minimum 44x44px). The layout should adapt fluidly across all viewport sizes, not just snap at breakpoints. No screen size should feel like an afterthought. If it looks "off" at any size, it's not done.

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

If the user says "No" or "We're good", proceed to the design quality validation.

---

## Step 10b: Design Quality Validation

Before writing final files, silently run the Jobs Filter across all collected answers. Present the results to the user:

```
Design Quality Check (Jobs/Ive Lens):

SIMPLICITY
- Total color roles defined: [N] — [OK if ≤10 / REVIEW if >10: "Can any roles be merged?"]
- Total type sizes in scale: [N] — [OK if ≤7 / REVIEW if >7: "Consider reducing"]
- Component variants requested: [N] — [OK / REVIEW: "Start with fewer, add when needed"]

HIERARCHY
- Primary action clarity: [Does every screen description imply a single primary action?]
- Navigation pattern: [Does it support clear hierarchy or flatten everything equally?]

DENSITY
- Any element, token, or variant that could be removed without losing meaning? [List if found]

RESPONSIVENESS
- Mobile consideration: [Are all layout decisions mobile-aware?]
- Touch targets: [Noted in component strategy? Yes/No]

[Any specific recommendations for the user to consider before finalizing]
```

If issues are found, present them and ask: "Would you like to adjust any of these before I write the files?" Accept the user's decision — do not push.

---

## Step 10c: Enrich harness.local.md

After quality validation, write or update the `## Design Context` section in `.harness/harness.local.md`. This provides compact project-specific design context to design agents (`design-iterator`, `figma-design-sync`, `design-ui-auditor`, `design-responsive-auditor`, `design-alignment-checker`, `/lp-design-review`, `/lp-design-polish`).

Extract values from the Q&A answers in Steps 4-9 (DS-0 through FG-3) and condense into:

```markdown
## Design Context

<!-- Enriched by /lp-define-design. -->

**Brand:** [primary personality] + [secondary personality]. Voice: [attributes].
**Philosophy:** [chosen design philosophy] — [one-line description].
**Density:** [data-dense / minimal / balanced] — [context for why].
**Colors:** [primary hex] primary, [background approach], [dark mode strategy].
**Typography:** [heading font] / [body font] at [base size].
**Components:** [library choice] with [customization approach].
**Responsive:** [strategy] — [critical breakpoints and why].
**Accessibility:** [WCAG level target] — [chosen patterns].

### Domain Design Constraints

- [Project-specific constraint extracted from Q&A]
- [Project-specific constraint extracted from Q&A]
- [Project-specific constraint extracted from Q&A]
```

This parallels the existing enrichment hooks: `/lp-define-product` Step 6b writes `## Review Context`, `/lp-define-architecture` Step 4b appends to `## Review Context`. Design agents read `## Design Context`; review agents read `## Review Context`.

---

## Step 11: Summary and Next Step

After all files are written, present a summary:

```
Done. Here is what was written:

**docs/architecture/DESIGN_SYSTEM.md**
- Brand: [primary personality] + [secondary personality], [N] voice attributes
- Philosophy: [choice]
- Colors: [primary color] + [N] semantic colors (aligned with brand personality)
- Typography: [heading font] / [body font] (aligned with brand voice)
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

Recommended next step: Run `/lp-define-architecture` to define your backend structure
and CI/CD pipeline.

After that, use `/lp-shape-section [name]` to deep-dive into each product section.
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
12. **Apply the quality lens, not enforce it.** Present the Jobs/Ive principles as guidance in recommendations and quality checks. If the user chooses differently, respect their decision. The quality bar informs — the user decides.
13. **No cosmetic suggestions without structural reasoning.** Never say "add more padding" without explaining what the spacing change does to rhythm. Never say "make this blue" without explaining what the color change accomplishes in hierarchy. Every recommendation must have a design reason, not just a preference.
14. **Premium means calm, confident, quiet.** When generating recommendations or defaults, bias toward restraint. Fewer colors, fewer type sizes, fewer component variants, more whitespace. Less but better.
