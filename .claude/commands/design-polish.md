---
description: "Pre-ship refinement pass — fixes alignment, spacing, copy, design system consistency, interaction states, resilience, and edge cases"
---

<!-- ported-from: https://github.com/pbakaus/impeccable (consolidated /polish + /normalize + /clarify + /harden)
     original-author: Paul Bakaus
     port-date: 2026-03-14
     license: Apache 2.0 -->

Perform a comprehensive pre-ship refinement pass. This combines visual polish, design system normalization, UX copy improvement, and interface hardening into one systematic sweep.

**First**: Use the frontend-design skill for design principles and anti-patterns.

**CRITICAL**: Polish is the last step, not the first. Don't polish work that's not functionally complete.

## Scope Constraint

Only modify files within `apps/web/src/` and `packages/ui/src/`. Do NOT modify files outside these directories (no API routes, no database schemas, no scripts, no config). If an improvement requires changes outside these directories, report it as a suggestion instead of implementing it.

## Pre-Polish Assessment

1. **Check completeness**: Is it functionally done? What's the quality bar (MVP vs flagship)?
2. **Discover the design system**: Read `docs/architecture/DESIGN_SYSTEM.md`, UI guidelines, component libraries, style guides. Understand tokens, patterns, and conventions.
3. **Identify scope**: Visual inconsistencies, spacing issues, copy problems, missing states, edge cases.

## Phase 1: Design System Normalization

Align the feature with the design system:

- **Typography**: Replace hard-coded font sizes/weights with typographic tokens or classes
- **Color & Theme**: Apply design system color tokens. Remove one-off colors. Ensure dark mode works.
- **Spacing & Layout**: Use spacing tokens for all margins, padding, gaps. Align with grid patterns.
- **Components**: Replace custom implementations with design system equivalents where they exist
- **Motion**: Match animation timing and easing to established patterns
- **Tinted neutrals**: No pure gray or pure black—add subtle color tint (0.01 chroma)
- **Gray on color**: Never put gray text on colored backgrounds—use a shade of that color

**NEVER**: Create new one-off components when design system equivalents exist. Hard-code values that should use tokens.

## Phase 2: Visual Polish

Work through these dimensions methodically:

### Alignment & Spacing

- Pixel-perfect alignment at all breakpoints
- Consistent spacing using the spacing scale (no random 13px gaps)
- Optical alignment adjustments (icons may need offset for visual centering)

### Typography Refinement

- Hierarchy consistency: same elements use same sizes/weights throughout
- Line length: 45-75 characters for body text
- No widows/orphans (single words on last line)
- Font loading: no FOUT/FOIT flashes

### Interaction States

Every interactive element needs ALL states:

- **Default** → **Hover** → **Focus** → **Active** → **Disabled** → **Loading** → **Error** → **Success**
- Missing states create confusion. Check every button, link, input, toggle.

### Transitions

- All state changes animated (150-300ms)
- Consistent easing: ease-out-quart/quint/expo (never bounce/elastic)
- 60fps animations, only animate transform and opacity
- Respects `prefers-reduced-motion`

### Icons & Images

- All icons from same family or matching style
- Proper optical alignment with adjacent text
- All images have descriptive alt text
- No layout shift on image load (aspect-ratio set)

## Phase 3: UX Copy Improvement

Systematically improve interface text:

### Error Messages

Every error answers: (1) What happened? (2) Why? (3) How to fix it?

- "Email addresses need an @ symbol. Try: name@example.com" NOT "Invalid input"
- Don't blame the user. Suggest corrections. Include examples.

### Button & CTA Text

- Specific verb + object: "Save changes" NOT "Submit" or "OK"
- For destructive actions, name the destruction: "Delete 5 items" NOT "Yes"

### Empty States

- Acknowledge briefly, explain value, provide clear action
- "No projects yet. Create your first one to get started." NOT "No items"

### Form Labels

- Clear, specific labels (not generic placeholders)
- Show format expectations with examples
- Explain why you're asking (when not obvious)

### Consistency

- Same things called same names throughout (Delete, not Remove/Trash/Delete interchangeably)
- Consistent capitalization (Title Case vs Sentence case — pick one)
- No redundant copy (if the heading explains it, don't repeat in body text)

## Phase 4: Hardening

Strengthen against real-world usage:

### Text Overflow

```css
/* Single line ellipsis */
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Multi-line clamp */
.line-clamp {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Flex/grid overflow prevention */
.flex-item {
  min-width: 0;
  overflow: hidden;
}
```

### Internationalization Prep

- Add 30-40% space budget for translations
- Use logical CSS properties (`margin-inline-start` not `margin-left`)
- Use `Intl` API for dates, numbers, currency
- Test with long text (German), CJK characters, emoji

### Error Handling

- Network failures: clear message + retry button
- API errors: handle 400, 401, 403, 404, 429, 500 distinctly
- Form validation: inline errors near fields with `aria-describedby`
- Preserve user input on error

### Edge Cases

- **Long content**: 100+ character names, descriptions
- **No content**: empty states with clear next actions
- **Large datasets**: pagination or virtual scrolling
- **Concurrent operations**: prevent double-submission (disable button while loading)
- **Offline**: appropriate handling if applicable

### Accessibility Resilience

- All functionality keyboard-accessible
- Screen reader support (ARIA labels, live regions)
- `prefers-reduced-motion` respected
- Contrast ratios meet WCAG AA (4.5:1 for text)

## Polish Checklist

Go through systematically before marking as done:

- [ ] Design tokens used consistently (no hard-coded colors, spacing, fonts)
- [ ] Visual alignment perfect at all breakpoints
- [ ] Typography hierarchy consistent
- [ ] All interactive states implemented (8 states per element)
- [ ] All transitions smooth (60fps, consistent easing)
- [ ] Copy is clear, consistent, and non-redundant
- [ ] Error messages explain what happened + how to fix
- [ ] Empty states are welcoming with clear actions
- [ ] Touch targets are 44x44px minimum
- [ ] Color contrast >= 4.5:1 (WCAG AA)
- [ ] Keyboard navigation works with visible focus indicators
- [ ] Text overflow handled (truncation, wrapping, min-width: 0)
- [ ] No console errors, warnings, or dead code
- [ ] No layout shift on load
- [ ] Respects reduced motion preference
- [ ] Forms properly labeled and validated

## Clean Up

After polishing:

- Consolidate any new reusable components into the shared UI path
- Remove orphaned code, unused styles, commented-out code
- Verify quality: lint, type-check, test
- Ensure DRYness: look for duplication and consolidate

**NEVER**: Polish before functionally complete. Introduce bugs while polishing. Perfect one area while leaving others rough.

Remember: Polish until it feels effortless, looks intentional, and works flawlessly. The details matter.
