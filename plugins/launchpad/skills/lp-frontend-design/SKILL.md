---
name: lp-frontend-design
description: Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, or applications. Generates creative, polished code that avoids generic AI aesthetics. Triggers on: build a landing page, create a dashboard, design a component, style this UI, make it look good, frontend design, build a page.
---

<!-- ported-from: https://github.com/pbakaus/impeccable (consolidated)
     original-authors: Paul Bakaus (Impeccable), Prithvi Rajasekaran & Alexander Bricken (Anthropic)
     port-date: 2026-03-14
     license: Apache 2.0
     consolidation-note: Merges Anthropic's frontend-design skill with Impeccable's 7 enhanced reference files and design philosophy. Concepts from /animate, /colorize, /bolder, /quieter, /delight, /distill, /extract, and /adapt, and /optimize are folded into the core skill and reference files. -->

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Implement real working code with exceptional attention to aesthetic details and creative choices.

## Design Direction

Commit to a BOLD aesthetic direction:

- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, etc. There are so many flavors to choose from. Use these for inspiration but design one that is true to the aesthetic direction.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work—the key is intentionality, not intensity.

Then implement working code that is:

- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Frontend Aesthetics Guidelines

### Typography

> _Consult [typography reference](references/typography.md) for scales, pairing, and loading strategies._

Choose fonts that are beautiful, unique, and interesting. Pair a distinctive display font with a refined body font.

**DO**: Use a modular type scale with fluid sizing (clamp)
**DO**: Vary font weights and sizes to create clear visual hierarchy
**DON'T**: Use overused fonts—Inter, Roboto, Arial, Open Sans, system defaults
**DON'T**: Use monospace typography as lazy shorthand for "technical/developer" vibes
**DON'T**: Put large icons with rounded corners above every heading—they rarely add value and make sites look templated

### Color & Theme

> _Consult [color reference](references/color-and-contrast.md) for OKLCH, palettes, and dark mode._

Commit to a cohesive palette. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Apply the 60-30-10 rule: 60% neutral, 30% secondary, 10% accent. Accent colors work _because_ they're rare—overuse kills their power.

**DO**: Use modern CSS color functions (oklch, color-mix, light-dark) for perceptually uniform, maintainable palettes
**DO**: Tint your neutrals toward your brand hue—even a subtle hint creates subconscious cohesion
**DO**: Use strategic color to communicate meaning (status, hierarchy, categories)—not just decoration
**DON'T**: Use gray text on colored backgrounds—it looks washed out; use a shade of the background color instead
**DON'T**: Use pure black (#000) or pure white (#fff)—always tint; pure black/white never appears in nature
**DON'T**: Use the AI color palette: cyan-on-dark, purple-to-blue gradients, neon accents on dark backgrounds
**DON'T**: Use gradient text for "impact"—especially on metrics or headings; it's decorative rather than meaningful
**DON'T**: Default to dark mode with glowing accents—it looks "cool" without requiring actual design decisions

### Layout & Space

> _Consult [spatial reference](references/spatial-design.md) for grids, rhythm, and container queries._

Create visual rhythm through varied spacing—not the same padding everywhere. Embrace asymmetry and unexpected compositions. Break the grid intentionally for emphasis.

**DO**: Create visual rhythm through varied spacing—tight groupings, generous separations
**DO**: Use fluid spacing with clamp() that breathes on larger screens
**DO**: Use asymmetry and unexpected compositions; break the grid intentionally for emphasis
**DON'T**: Wrap everything in cards—not everything needs a container
**DON'T**: Nest cards inside cards—visual noise, flatten the hierarchy
**DON'T**: Use identical card grids—same-sized cards with icon + heading + text, repeated endlessly
**DON'T**: Use the hero metric layout template—big number, small label, supporting stats, gradient accent
**DON'T**: Center everything—left-aligned text with asymmetric layouts feels more designed
**DON'T**: Use the same spacing everywhere—without rhythm, layouts feel monotonous

### Visual Details

**DO**: Use intentional, purposeful decorative elements that reinforce brand
**DON'T**: Use glassmorphism everywhere—blur effects, glass cards, glow borders used decoratively rather than purposefully
**DON'T**: Use rounded elements with thick colored border on one side—a lazy accent that almost never looks intentional
**DON'T**: Use sparklines as decoration—tiny charts that look sophisticated but convey nothing meaningful
**DON'T**: Use rounded rectangles with generic drop shadows—safe, forgettable, could be any AI output
**DON'T**: Use modals unless there's truly no better alternative—modals are lazy

### Motion

> _Consult [motion reference](references/motion-design.md) for timing, easing, and reduced motion._

Focus on high-impact moments: one well-orchestrated page load with staggered reveals creates more delight than scattered micro-interactions. Animate with purpose—every motion needs justification.

**DO**: Use motion to convey state changes—entrances, exits, feedback
**DO**: Use exponential easing (ease-out-quart/quint/expo) for natural deceleration
**DO**: For height animations, use grid-template-rows transitions instead of animating height directly
**DO**: Always respect `prefers-reduced-motion` — vestibular disorders affect ~35% of adults over 40
**DON'T**: Animate layout properties (width, height, padding, margin)—use transform and opacity only
**DON'T**: Use bounce or elastic easing—they feel dated and tacky; real objects decelerate smoothly

### Interaction

> _Consult [interaction reference](references/interaction-design.md) for forms, focus, and loading patterns._

Make interactions feel fast. Use optimistic UI—update immediately, sync later. Design every interactive state (default, hover, focus, active, disabled, loading, error, success).

**DO**: Use progressive disclosure—start simple, reveal sophistication through interaction (basic options first, advanced behind expandable sections; hover states that reveal secondary actions)
**DO**: Design empty states that teach the interface, not just say "nothing here"
**DO**: Make every interactive surface feel intentional and responsive
**DO**: Add micro-interactions that provide satisfying feedback (button presses, toggle animations, success celebrations)—but keep them purposeful, never decorative
**DON'T**: Repeat the same information—redundant headers, intros that restate the heading
**DON'T**: Make every button primary—use ghost buttons, text links, secondary styles; hierarchy matters

### Responsive

> _Consult [responsive reference](references/responsive-design.md) for mobile-first, fluid design, and container queries._

**DO**: Use container queries (@container) for component-level responsiveness
**DO**: Adapt the interface for different contexts—don't just shrink it. Rethink the experience per device.
**DO**: Use `@media (pointer: coarse)` for touch targets, not just screen width
**DON'T**: Hide critical functionality on mobile—adapt the interface, don't amputate it

### UX Writing

> _Consult [ux-writing reference](references/ux-writing.md) for labels, errors, and empty states._

**DO**: Make every word earn its place
**DO**: Use specific verb + object for buttons ("Save changes" not "OK")
**DO**: Write error messages that explain what happened, why, and how to fix it
**DON'T**: Repeat information users can already see
**DON'T**: Use jargon, blame the user, or add humor to error messages

---

## The AI Slop Test

**Critical quality check**: If you showed this interface to someone and said "AI made this," would they believe you immediately? If yes, that's the problem.

A distinctive interface should make someone ask "how was this made?" not "which AI made this?"

Review the DON'T guidelines above—they are the fingerprints of AI-generated work from 2024-2025.

---

## Design Intensity Controls

When the user asks for bolder or quieter designs, apply these principles:

**To amplify (make bolder):** Increase typographic contrast (3-5x size jumps), use one bold color dominating 60% of design, break grids asymmetrically, add dramatic shadows, use extreme spacing (100-200px gaps). Bold means genuinely distinctive—NOT more effects, gradients, or glassmorphism.

**To tone down (make quieter):** Shift saturation from 100% to 70-85%, increase whitespace, thin borders or remove them, reduce animation distances (10-20px instead of 40px), use gentler easing. Quiet design is confident design—it doesn't need to shout.

**To add delight:** Focus on success states, empty states, loading periods, and hover moments. Micro-interactions with satisfying physics, personality-driven copy, and subtle celebrations. But: animations should be under 1 second, skippable, and never delay core functionality.

**To simplify (distill):** Find the 20% that delivers 80% of value. Every element must justify its existence. Remove obstacles between users and their goals. Simplify information architecture, reduce visual noise, flatten unnecessary hierarchy.

---

## Implementation Principles

Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices across generations.

## Component Architecture

When building components, follow extraction principles:

- Extract only what's clearly reusable NOW, not everything that might someday be reusable
- Create clear props APIs with sensible defaults and proper TypeScript types
- Build proper variants rather than one-off overrides
- Include accessibility features (ARIA, keyboard nav, focus management) from the start

## Performance Awareness

Every design decision has a performance cost:

- Use modern image formats (WebP, AVIF) with responsive srcset
- Code-split routes and lazy-load heavy components
- Use CSS animations over JS when possible (GPU-accelerated transform + opacity)
- Target Core Web Vitals: LCP < 2.5s, INP < 200ms, CLS < 0.1
- Measure before optimizing—premature optimization wastes time

---

## Related Commands

- `/lp-design-review` — Comprehensive quality audit + honest design critique
- `/lp-design-polish` — Pre-ship refinement: alignment, copy, consistency, resilience, edge cases
- `/lp-design-onboard` — Design onboarding flows, empty states, and first-time experiences
