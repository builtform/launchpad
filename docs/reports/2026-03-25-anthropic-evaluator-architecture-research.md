# GAN-Inspired Evaluator Architecture Research Report

**Date:** 2026-03-25
**Source:** Anthropic Engineering Blog -- "Harness design for long-running application development" by Prithvi Rajasekaran (Anthropic Labs)
**Purpose:** Analyze Anthropic's three-agent architecture findings and determine which techniques should be adopted into LaunchPad's compound execution pipeline.
**Outcome:** Four high-value gaps identified. Implementation plan created for adding a GAN-inspired Generator/Evaluator loop with live Playwright testing, sprint contracts, and gradable criteria to LaunchPad's Layer 3.

---

## Article Summary

Anthropic's article (published March 24, 2026) describes a three-agent architecture -- **Planner, Generator, Evaluator** -- inspired by Generative Adversarial Networks (GANs). The core breakthrough: separating the agent that builds code from the agent that judges it dramatically improves output quality for both subjective design and verifiable correctness.

**Planner** takes a 1-4 sentence prompt and expands it to a full product spec. It is prompted to be ambitious about scope and to stay focused on product context rather than granular technical details -- because errors at the planning level cascade through everything downstream.

**Generator** builds one feature at a time. It self-evaluates before handing off to QA, uses git for version control, and works in sprints (v1) or continuous sessions (v2 with Opus 4.6).

**Evaluator** uses Playwright MCP to navigate the running application. It grades against four concrete criteria (Design, Originality, Craft, Functionality). It feeds detailed, actionable bug reports back to the generator. Critically, the evaluator does NOT read code -- it only tests the running app. This caught bugs that code review and static analysis missed entirely: broken interactions, stub-only features, layout regressions, and wiring issues between frontend and backend.

**Results:** A solo agent ($9, 20 min) produced broken core functionality. The full harness ($200, 6 hr) produced a working, polished application. The v2 harness (Opus 4.6, simplified architecture) ran ~4 hours for $124 with 3 build-QA cycles.

---

## Key Findings

### 1. Agents cannot reliably self-evaluate ("confident mediocrity")

When asked to evaluate their own work, agents confidently praise it even when quality is obviously mediocre. This is especially pronounced for subjective tasks like design. Separating the evaluator from the generator is structurally more tractable than making a generator self-critical.

### 2. Live Playwright testing catches a different class of bugs

Static analysis (lint, typecheck, code review) catches syntax and type errors. Live testing catches broken interactions, stub features that look complete in code but don't work, layout regressions, and frontend-backend wiring issues. The article showed specific examples: a `fillRectangle` function that existed but wasn't triggered on `mouseUp`, a delete handler requiring both `selection` AND `selectedEntityId` but only one was set, an API route collision causing 422 errors.

### 3. Gradable criteria convert subjective quality into scorable dimensions

"Is this design good?" is unanswerable. "Does this follow our four criteria?" is gradable. The four dimensions: **Design quality** (coherent whole vs. parts), **Originality** (custom decisions vs. AI slop), **Craft** (typography, spacing, color harmony), **Functionality** (user can complete tasks). Each has a threshold; failing any one fails the sprint.

### 4. Sprint contracts prevent misaligned expectations

Before each sprint, the generator proposes what to build and how success will be verified. The evaluator reviews and challenges vague criteria. This prevents the generator from drifting off-spec or building the wrong interpretation. Contracts were granular -- Sprint 3 alone had 27 criteria.

### 5. Context resets outperform compaction for Sonnet 4.5; Opus 4.6 handles compaction

Sonnet 4.5 exhibited "context anxiety" (wrapping up work prematurely as context grew). Context resets (clearing the window + file-based handoffs) fixed this. Opus 4.6 largely eliminated context anxiety, allowing continuous sessions with automatic compaction.

### 6. Harness components must be re-evaluated as models improve

The article explicitly removed the sprint construct when moving from Opus 4.5 to 4.6 because the model could handle decomposition natively. Key quote: _"every component in a harness encodes an assumption about what the model can't do on its own, and those assumptions are worth stress testing."_ Non-load-bearing pieces should be stripped.

### 7. The evaluator is worth the cost at the capability boundary

For tasks well within the model's solo capability, the evaluator adds unnecessary overhead. For tasks at the edge of what the model handles reliably, the evaluator provides real lift. The boundary shifts outward with each model generation.

### 8. Criteria wording directly shapes output character

Including phrases like "the best designs are museum quality" pushed designs toward a particular visual convergence. The criteria aren't just measurement instruments -- they're implicit instructions that steer the generator's behavior even before evaluator feedback arrives.

---

## Gap Analysis -- LaunchPad vs. Anthropic's Harness

### A. Missing from LaunchPad (4 items -- should add)

| Gap                                | Article's Solution                                                                          | LaunchPad Today                                                                       | Impact                                                                                                         |
| ---------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Live application evaluation**    | Playwright MCP: navigate, click, test, grade the running app                                | All gates static: lint, typecheck, structure, Codex code review                       | **Critical** -- broken interactions, stub features, layout regressions go undetected until human opens browser |
| **Generator/Evaluator separation** | Separate agents with fresh contexts; evaluator has no ego investment in the code            | Single agent builds AND self-evaluates in execution loop                              | **High** -- self-evaluation bias means the generator marks its own homework                                    |
| **Gradable criteria framework**    | Four dimensions (Design, Originality, Craft, Functionality) with 1-10 scales and thresholds | Design skills guide the generator but no structured grading rubric                    | **High** -- no way to objectively measure output quality                                                       |
| **Sprint contracts**               | Pre-build agreement: generator proposes, evaluator challenges, both iterate until agreed    | One-way flow: PRD -> tasks -> execute. No evaluator reviews criteria before execution | **Medium** -- generator writes its own test plan and grades itself against it                                  |

### B. Already Doing Differently (4 items -- update opportunity)

| Area                           | Article's Approach                                                                                               | LaunchPad's Approach                                                                                                         | Update Opportunity                                                                                                              |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Planner ambition**           | Takes 1-4 sentence prompt, expands to 16-feature spec. Prompted to be ambitious and weave AI features            | Guided Q&A extracts what user defines. Conservative, thorough, but not expansive                                             | Add "ambition mode" for autonomous PRD generation -- expand scope, suggest AI integrations                                      |
| **Context management**         | v1: context resets with file handoffs. v2: Opus 4.6 compaction                                                   | 4-tier document hierarchy (architecture docs -> section specs -> PRDs -> prd.json). Each session starts fresh from documents | LaunchPad's approach is architecturally superior. Minor gap: no explicit checkpoint-and-reset within loop.sh for very long runs |
| **Iteration feedback quality** | Code-level findings from live Playwright testing: "fillRectangle function exists but isn't triggered on mouseUp" | Lint errors, type errors, Codex code review comments                                                                         | Wire Playwright evaluation into existing iteration loop for richer feedback                                                     |
| **Quality gate layers**        | One dynamic gate: Playwright-based functional testing                                                            | Four static gates: pre-commit hooks -> CI -> Codex review -> PR monitoring                                                   | Add Playwright as a fifth gate between execution loop and quality sweep                                                         |

### C. Untouched by the Article (7 items -- keep as-is)

| Area                                         | Why It's Untouched                                             | LaunchPad Advantage                                                                                       |
| -------------------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Skill infrastructure (Tier 0)**            | Article has no concept of domain-specific reasoning amplifiers | Meta-Skill Forge (8-phase pipeline), skill lifecycle tracking, skill auditing, skill-evaluator agent      |
| **Document-driven state machine**            | Article uses ad-hoc file communication                         | Formalized 4-tier hierarchy with explicit status transitions (defined -> shaped -> planned -> built)      |
| **Compound learning (Layer 6)**              | Article mentions no institutional memory                       | Learnings extraction from progress.txt -> docs/solutions/, pattern promotion to CLAUDE.md                 |
| **Cross-file consistency (/update-spec)**    | Article writes specs once, never validates                     | Entity-name, section-name, tech-stack, status, and copy-gap scanners across 7+ docs                       |
| **Report-driven prioritization**             | Article takes raw user prompts                                 | analyze-report.sh reads reports, algorithmically selects highest priority, avoids re-picking recent fixes |
| **Multi-provider support**                   | Claude-only                                                    | auto-compound.sh supports claude/codex/gemini via config.json                                             |
| **Human-in-the-loop architecture decisions** | Fully autonomous end-to-end                                    | Guided Q&A (/shape-section, /define-design) with MCQ format for critical decisions                        |

---

## Linked Article Summaries

### 1. "Improving Frontend Design through Skills" (Anthropic)

**Problem:** LLMs default to safe, generic designs (Inter font, purple gradients, stock card layouts) -- "distributional convergence."

**Solution:** Skills as ~400-token just-in-time context injection. Right-altitude prompting: above hex values, below vague platitudes. Four design levers: typography (distinctive fonts, extreme weight contrasts), color/theme (CSS variables, dominant + accent palettes), motion (staggered reveals), backgrounds (layered gradients).

**Relevance:** LaunchPad's frontend-design skill already implements this pattern.

### 2. "Effective Harnesses for Long-Running Agents" (Anthropic, earlier work)

The predecessor to the current article. Described an initializer -> coding agent -> context reset architecture. Key finding: context resets (fresh agent + file handoffs) outperformed compaction for Sonnet 4.5. Established the one-feature-at-a-time approach and structured artifacts for context carryover.

**Relevance:** LaunchPad's loop.sh already implements fresh-context-per-iteration based on this work.

### 3. "Effective Context Engineering for AI Agents" (Anthropic)

Defines context engineering as _"strategically curating all tokens available to an LLM during inference."_ Key concept: context rot -- performance degrades as token volume grows (n-squared attention relationships). Primary techniques: system prompt organization, tool design (minimize redundancy), just-in-time retrieval, sub-agent architectures.

**Relevance:** LaunchPad's progressive disclosure table and on-demand doc loading already follow these patterns.

### 4. "Building Effective Agents" (Anthropic)

Distinguishes **workflows** (predefined code paths) from **agents** (dynamically direct their own processes). Five workflow patterns: prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer. Core finding: successful implementations use simple, composable patterns -- not complex frameworks. Key quote: _"find the simplest solution possible, and only increase complexity when needed."_

**Relevance:** LaunchPad's pipeline is the evaluator-optimizer pattern. The article validates adding a formal evaluator.

### 5. "Introducing Claude Opus 4.6" (Anthropic)

1M token context window, adaptive extended thinking, effort controls, context compaction (beta). Agent-relevant: parallel subagent orchestration (9+ subagents, 100+ tool calls), improved long-context retrieval (76% MRCR v2 vs Sonnet's 18.5%). Key quote: _"[Opus 4.6] plans more carefully, sustains agentic tasks for longer, operates more reliably in larger codebases, and has better code review and debugging skills."_

**Relevance:** Opus 4.6's improved capabilities mean some harness complexity (sprint decomposition) is no longer load-bearing. The evaluator remains load-bearing because it addresses self-evaluation bias, not model capability.

---

## Recommendation

Implement the GAN-inspired evaluator architecture as an **opt-in enhancement** to LaunchPad's Layer 3 (Compound Execution). Specifically:

1. **Add a live application evaluator** to the auto-compound.sh pipeline (Step 6.5) -- starts the dev server, runs an evaluator agent via Playwright MCP (or static fallback), grades against four dimensions, feeds actionable fixes back to the generator for iterative improvement.

2. **Add sprint contract negotiation** (Step 5.5) -- before the execution loop, the generator proposes what to build and how to verify it, and the evaluator challenges vague or untestable criteria.

3. **Define a gradable criteria framework** -- four dimensions (Design, Originality, Craft, Functionality) with configurable thresholds, calibrated scoring rubrics, and evidence collection guidance.

4. **Add an ambition mode** to the PRD skill -- when enabled, the planner expands brief prompts into ambitious, feature-rich specs that include AI integration suggestions.

All changes are opt-in via config.json. The existing pipeline continues to work unchanged. The evaluator gracefully degrades when Playwright MCP is unavailable (falls back to curl, HTML inspection, code quality assessment, and test suite execution).

**Implementation plan:** See `docs/reports/2026-03-25-evaluator-architecture-implementation-plan.md`.

---

## Sources

- [Harness design for long-running application development -- Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- Improving Frontend Design through Skills -- Anthropic
- Effective Harnesses for Long-Running Agents -- Anthropic
- [Effective Context Engineering for AI Agents -- Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Building Effective Agents -- Anthropic](https://www.anthropic.com/research/building-effective-agents)
- [Introducing Claude Opus 4.6 -- Anthropic](https://www.anthropic.com/news/claude-opus-4-6)
