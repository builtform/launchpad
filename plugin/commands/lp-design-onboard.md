---
name: lp-design-onboard
description: "Design or improve onboarding flows, empty states, first-time user experiences, feature discovery, and guided tours"
---
<!-- ported-from: https://github.com/pbakaus/impeccable (/onboard)
     original-author: Paul Bakaus
     port-date: 2026-03-14
     license: Apache 2.0 -->

Create or improve onboarding experiences that help users understand, adopt, and succeed with the product quickly.

## Assess Onboarding Needs

Understand what users need to learn and why:

1. **Identify the challenge**:
   - What are users trying to accomplish?
   - What's confusing or unclear about current experience?
   - Where do users get stuck or drop off?
   - What's the "aha moment" we want users to reach?

2. **Understand the users**:
   - What's their experience level? (Beginners, power users, mixed?)
   - What's their motivation? (Excited and exploring? Required by work?)
   - What's their time commitment? (5 minutes? 30 minutes?)
   - What alternatives do they know? (Coming from competitor? New to category?)

3. **Define success**:
   - What's the minimum users need to learn to be successful?
   - What's the key action we want them to take?
   - How do we know onboarding worked? (Completion rate? Time to value?)

**CRITICAL**: Onboarding should get users to value as quickly as possible, not teach everything possible.

## Onboarding Principles

### Show, Don't Tell

- Demonstrate with working examples, not descriptions
- Provide real functionality in onboarding, not separate tutorial mode
- Use progressive disclosure — teach one thing at a time

### Make It Optional (When Possible)

- Let experienced users skip onboarding
- Don't block access to product
- Provide "Skip" or "I'll explore on my own" options

### Time to Value

- Get users to their "aha moment" ASAP
- Front-load most important concepts
- Teach the 20% that delivers 80% of value
- Save advanced features for contextual discovery

### Context Over Ceremony

- Teach features when users need them, not upfront
- Empty states are onboarding opportunities
- Tooltips and hints at point of use

### Respect User Intelligence

- Don't patronize or over-explain
- Be concise and clear
- Assume users can figure out standard patterns

## Design Onboarding Experiences

### Initial Product Onboarding

**Welcome Screen**: Clear value proposition, what users will accomplish, time estimate, option to skip.

**Account Setup**: Minimal required info (collect more later), explain why you're asking, smart defaults, social login when appropriate.

**Core Concept Introduction**: 1-3 core concepts max, simple language + examples, interactive when possible, progress indication.

**First Success**: Guide users to accomplish something real, pre-populated templates, celebrate completion (don't overdo it), clear next steps.

### Feature Discovery & Adoption

**Empty States** — Instead of blank space, show:

- What will appear here (description + illustration)
- Why it's valuable
- Clear CTA to create first item
- Example or template option

```
No projects yet
Projects help you organize your work and collaborate with your team.
[Create your first project] or [Start from template]
```

**Contextual Tooltips**: Appear at relevant moment (first time user sees feature), point at relevant element, brief explanation + benefit, dismissable with "Don't show again".

**Feature Announcements**: Highlight new features, show what's new and why, let users try immediately, dismissable.

**Progressive Onboarding**: Teach features when encountered, badges on new/unused features, unlock complexity gradually.

### Guided Tours & Walkthroughs

**When to use**: Complex interfaces, significant changes, industry-specific tools.

**How to design**: Spotlight specific elements (dim rest of page), 3-7 steps max, allow free navigation, include "Skip tour", make replayable from help menu.

**Best practices**: Interactive > passive (let users click real buttons), focus on workflow not features ("Create a project" not "This is the project button"), provide sample data.

### Interactive Tutorials

**When to use**: Users need hands-on practice, concepts are complex, high stakes.

**How to design**: Sandbox with sample data, clear objectives, step-by-step guidance, validation, graduation moment.

## Empty State Design

Every empty state needs five things:

1. **What will be here**: "Your recent projects will appear here"
2. **Why it matters**: "Projects help you organize work and collaborate"
3. **How to get started**: [Create project] or [Import from template]
4. **Visual interest**: Illustration or icon (not just text)
5. **Contextual help**: "Need help? [Watch 2-min tutorial]"

**Empty state types**:

- **First use**: Emphasize value, provide template
- **User cleared**: Light touch, easy to recreate
- **No results**: Suggest different query, clear filters
- **No permissions**: Explain why, how to get access
- **Error state**: Explain what happened, retry option

## Implementation Patterns

**Tooltip libraries**: Tippy.js, Popper.js
**Tour libraries**: Intro.js, Shepherd.js, React Joyride
**Modal patterns**: Focus trap, backdrop, ESC to close
**Progress tracking**: LocalStorage for "seen" states
**Analytics**: Track completion and drop-off points

```javascript
// Track onboarding completion
localStorage.setItem("onboarding-completed", "true");
localStorage.setItem("feature-tooltip-seen-reports", "true");
```

**IMPORTANT**: Don't show same onboarding twice. Track completion and respect dismissals.

**NEVER**:

- Force users through long onboarding before they can use product
- Patronize with obvious explanations
- Show same tooltip repeatedly
- Block all UI during tour
- Create separate tutorial mode disconnected from real product
- Overwhelm with information upfront
- Hide "Skip" or make it hard to find
- Forget about returning users

## Verify Onboarding Quality

- **Time to completion**: Can users complete quickly?
- **Comprehension**: Do users understand after completing?
- **Action**: Do users take the desired next step?
- **Skip rate**: Too many skipping? (Maybe too long/not valuable)
- **Completion rate**: Low? Simplify.
- **Time to value**: How long until first value?

Get users to their "aha moment" as quickly as possible. Teach the essential, make it contextual, respect user time and intelligence.
