---
description: "Comprehensive quality audit and design critique — evaluates accessibility, performance, theming, responsive design, anti-patterns, visual hierarchy, and UX effectiveness"
---

<!-- ported-from: https://github.com/pbakaus/impeccable (consolidated /audit + /critique)
     original-author: Paul Bakaus
     port-date: 2026-03-14
     license: Apache 2.0 -->

Conduct a comprehensive quality audit AND design critique in a single pass. This combines systematic technical checks with holistic design evaluation.

**First**: Use the frontend-design skill for design principles and anti-patterns.

## Part 1: Design Critique

Evaluate the interface as a designed experience—not just technically, but as something a human will use.

### 1. AI Slop Detection (CRITICAL)

**This is the most important check.** Does this look like every other AI-generated interface from 2024-2025?

Review the design against ALL the **DON'T** guidelines in the frontend-design skill—they are the fingerprints of AI-generated work. Check for the AI color palette, gradient text, dark mode with glowing accents, glassmorphism, hero metric layouts, identical card grids, generic fonts, and all other tells.

**The test**: If you showed this to someone and said "AI made this," would they believe you immediately? If yes, that's the problem.

### 2. Visual Hierarchy

- Does the eye flow to the most important element first?
- Is there a clear primary action? Can you spot it in 2 seconds?
- Do size, color, and position communicate importance correctly?
- Is there visual competition between elements that should have different weights?

### 3. Information Architecture

- Is the structure intuitive? Would a new user understand the organization?
- Is related content grouped logically?
- Are there too many choices at once? (cognitive overload)
- Is the navigation clear and predictable?

### 4. Emotional Resonance

- What emotion does this interface evoke? Is that intentional?
- Does it match the brand personality?
- Would the target user feel "this is for me"?

### 5. Discoverability & Affordance

- Are interactive elements obviously interactive?
- Would a user know what to do without instructions?
- Are hover/focus states providing useful feedback?

### 6. Composition, Typography, Color

- Does the layout feel balanced or uncomfortably weighted?
- Is whitespace used intentionally or just leftover?
- Does the type hierarchy clearly signal what to read first?
- Is color used to communicate, not just decorate?

### 7. States & Edge Cases

- Empty states: Do they guide users toward action?
- Loading states: Do they reduce perceived wait time?
- Error states: Are they helpful and non-blaming?
- Success states: Do they confirm and guide next steps?

### 8. Microcopy & Voice

- Is the writing clear and concise?
- Are labels and buttons unambiguous?
- Does error copy help users fix the problem?

## Part 2: Technical Audit

Run systematic quality checks across multiple dimensions:

### Accessibility (A11y)

- **Contrast issues**: Text contrast ratios < 4.5:1 (or 7:1 for AAA)
- **Missing ARIA**: Interactive elements without proper roles, labels, or states
- **Keyboard navigation**: Missing focus indicators, illogical tab order, keyboard traps
- **Semantic HTML**: Improper heading hierarchy, missing landmarks, divs instead of buttons
- **Alt text**: Missing or poor image descriptions
- **Form issues**: Inputs without labels, poor error messaging, missing required indicators

### Performance

- **Layout thrashing**: Reading/writing layout properties in loops
- **Expensive animations**: Animating layout properties instead of transform/opacity
- **Missing optimization**: Images without lazy loading, unoptimized assets
- **Bundle size**: Unnecessary imports, unused dependencies
- **Render performance**: Unnecessary re-renders, missing memoization

### Theming

- **Hard-coded colors**: Colors not using design tokens
- **Broken dark mode**: Missing dark mode variants, poor contrast in dark theme
- **Inconsistent tokens**: Using wrong tokens, mixing token types

### Responsive Design

- **Fixed widths**: Hard-coded widths that break on mobile
- **Touch targets**: Interactive elements < 44x44px
- **Horizontal scroll**: Content overflow on narrow viewports
- **Text scaling**: Layouts that break when text size increases

## Generate Report

Structure your feedback as follows:

### Anti-Patterns Verdict

**Start here.** Pass/fail: Does this look AI-generated? List specific tells. Be brutally honest.

### Overall Impression

Brief gut reaction—what works, what doesn't, and the single biggest opportunity.

### What's Working

2-3 things done well. Be specific about why they work.

### Priority Issues (Design + Technical Combined)

The 5-8 most impactful problems, ordered by importance. For each:

- **What**: Name the problem clearly
- **Category**: Design / Accessibility / Performance / Theming / Responsive
- **Severity**: Critical / High / Medium / Low
- **Why it matters**: How this hurts users
- **Fix**: Concrete recommendation
- **Command**: Which command to use (`/design-polish`, or other installed skills)

### Systemic Patterns

Recurring problems across multiple components (e.g., "hard-coded colors in 15+ components").

### Positive Findings

Good practices to maintain and replicate.

### Questions to Consider

Provocative questions that might unlock better solutions.

### Remediation Roadmap

1. **Immediate**: Critical blockers
2. **Short-term**: High-severity issues (this sprint)
3. **Medium-term**: Quality improvements
4. **Long-term**: Nice-to-haves

**Remember**:

- Be direct—vague feedback wastes everyone's time
- Be specific—"the submit button" not "some elements"
- Say what's wrong AND why it matters to users
- Prioritize ruthlessly—if everything is important, nothing is
- This is a review, not a fix. Document issues for `/design-polish` to address.
