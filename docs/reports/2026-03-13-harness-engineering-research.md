# Harness Engineering Research Report

**Date:** 2026-03-13
**Purpose:** Determine whether LaunchPad should adopt "harness" terminology and position itself as an AI coding harness.
**Outcome:** Yes -- LaunchPad maps to all 9 defining characteristics of a harness. Terminology adopted across README.md, HOW_IT_WORKS.md, and METHODOLOGY.md.

---

## What Is Harness Engineering?

Harness engineering is the discipline of designing the **environment, constraints, feedback loops, and infrastructure** that wrap around an AI agent to make it reliable, productive, and steerable at scale. The metaphor is drawn from horse tack -- reins, saddle, bit -- the complete equipment for channeling a powerful but unpredictable animal in the right direction. The AI model is the horse; the harness is everything that ensures it runs where you need it to go.

The most cited definition comes from **Martin Fowler's Thoughtworks article** (by Birgitta Bockeler, Feb 17, 2026): harness engineering is _"the tooling and practices we can use to keep AI agents in check."_

**Philipp Schmid** offers a more structural definition: _"the infrastructure that wraps around an AI model to manage long-running tasks... a software system governing agent operations while ensuring reliability, efficiency, and steerability -- but notably, it is not the agent itself."_

---

## Who Coined It and When Did It Emerge?

The term has **three independent origin threads** that converged in early 2026:

### A. Dex Horthy (HumanLayer) -- Mid-2025 (earliest known usage)

Dex Horthy, founder of HumanLayer (YC-backed), posted on X: _"there's a new concept I'm seeing emerging in AI Agents (especially coding agents), which I'll call 'harness engineering' -- applying context engineering principles to how you use an existing agent."_ His framing positioned it as the next evolution beyond context engineering: while context engineering manages what information reaches the model, harness engineering manages the **integration points** -- how you structure the entire surrounding system.

### B. Mitchell Hashimoto (HashiCorp co-founder) -- February 5, 2026

In his blog post "My AI Adoption Journey," Hashimoto described the practice of systematically engineering solutions whenever an agent makes a mistake so it never makes that mistake again. He called this "harness engineering." His concrete practices included AGENTS.md files documenting project conventions (each line addressing a known bad agent behavior) and custom programmatic tools (screenshot scripts, filtered test runners).

### C. OpenAI Codex Team -- February ~20, 2026

OpenAI published "Harness engineering: leveraging Codex in an agent-first world," describing how a 3-person team used Codex agents to produce ~1 million lines of code across ~1,500 PRs over five months with **zero human-written code**. This post caused the term to go viral across the AI engineering community.

### Convergence Timeline

- **2022-2024**: Prompt engineering era (single-shot interactions)
- **Mid-2025**: Context engineering gains prominence (Andrej Karpathy emphasizes context over prompts; Dex Horthy begins using "harness engineering")
- **November 2025**: Anthropic publishes "Effective Harnesses for Long-Running Agents" (Justin Young) -- uses the "harness" concept without the "engineering" compound term
- **February 2026**: Hashimoto's blog post, then OpenAI's Codex blog, then Fowler/Thoughtworks, then LangChain's benchmark results -- the term explodes in ~2 weeks

---

## The Three Nested Layers

Multiple sources converge on this framing:

| Layer                   | Scope                                                                                   | Analogy                                                                           |
| ----------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **Prompt engineering**  | Crafting the right instruction for a single interaction                                 | The command "turn right"                                                          |
| **Context engineering** | Managing what information reaches the model at the right time                           | The map, road signs, and visible terrain                                          |
| **Harness engineering** | Designing the entire runtime environment: constraints, tools, feedback loops, lifecycle | The reins, saddle, fence, and road itself -- so ten horses can run safely at once |

Context engineering is a **subset** of harness engineering. The harness includes context but extends to architectural constraints, CI/CD integration, linting rules, mechanical enforcement, observability, and agent lifecycle management.

---

## OpenAI's Five Harness Engineering Principles

From the OpenAI Codex team's report:

1. **What the agent can't see doesn't exist** -- Push every decision into the repository as markdown, schemas, and execution plans. Knowledge in Google Docs, Slack threads, or people's heads is invisible to the system.

2. **Ask what capability is missing, not why the agent is failing** -- Diagnose gaps in the environment rather than blaming model performance. Instrument better tools rather than rewriting prompts.

3. **Mechanical enforcement over documentation** -- Enforce invariant rules through custom linters and structural tests, not prose. Paradoxically, constraining the solution space makes agents more productive.

4. **Give the agent eyes** -- Integrate Chrome DevTools Protocol, DOM snapshots, screenshots, observability stacks. Let agents apply fixes in feedback loops against real runtime data.

5. **A map, not a manual** -- Provide brief architectural overviews (ARCHITECTURE.md) that highlight structure and boundaries, not exhaustive documentation.

---

## Harness vs. Framework vs. Scaffold -- The Distinctions

| Term                                    | Definition                                                                                                                                                                                                                                                                | LaunchPad?                   |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| **Scaffold**                            | The assembly that happens **before the first prompt**. Constructs the agent: system prompt, tool schemas, sub-agent registry. Static setup.                                                                                                                               | Layer 1 only                 |
| **Framework** (e.g., LangChain, CrewAI) | Provides **building blocks** at a lower level. Implements the agentic loop, tool interfaces, composable primitives. You assemble your own system.                                                                                                                         | No -- too opinionated        |
| **Harness**                             | The **runtime orchestration layer** that wraps the core reasoning loop. Coordinates everything after the first prompt: tool dispatch, context compaction, safety enforcement, state persistence, lifecycle hooks, error recovery, verification loops. Batteries included. | **Yes -- this is LaunchPad** |
| **Orchestrator**                        | Controls _when_ and _how_ to invoke models (logic and control flow).                                                                                                                                                                                                      | Partial overlap              |

### Philipp Schmid's Computer Analogy

- **Model = CPU** (raw processing power)
- **Context window = RAM** (limited working memory)
- **Harness = Operating System** (manages context, initialization, tool handling)
- **Agent = Application** (specific user logic running on top)

---

## Quantitative Evidence That Harnesses Matter

**LangChain's benchmark results** (Feb 17, 2026): By only modifying the harness (keeping the model fixed), they improved their coding agent from **52.8% to 66.5% on Terminal Bench 2.0** -- a 13.7-point gain that moved them from outside the top 30 to the top 5.

**MorphLLM's finding**: Swapping models changed benchmark scores by ~1%. Swapping the harness changed them by **22%**. A mid-tier model in a great harness beats a frontier model in a bad one.

**OpenAI Codex**: 3 engineers, 5 months, ~1,500 PRs merged, ~1M lines of code, averaging 3.5 PRs per engineer per day -- with zero human-written code.

---

## LaunchPad as a Harness: 9-Point Mapping

| Harness Characteristic               | LaunchPad Feature                                                        | Match? |
| ------------------------------------ | ------------------------------------------------------------------------ | ------ |
| 1. Runtime, not just setup           | Compound loops, fresh-context cycles, progress.txt                       | Yes    |
| 2. Wraps the model                   | CLAUDE.md, skills, sub-agents all shape how the AI operates              | Yes    |
| 3. Manages lifecycle                 | Git-based state persistence, prd.json, progress tracking across sessions | Yes    |
| 4. Mechanical enforcement            | check-repo-structure.sh, pre-commit hooks, CI quality gates              | Yes    |
| 5. Feedback loops                    | Layer 6 learnings feed back into all layers, compound pipeline           | Yes    |
| 6. Context engineering as subsystem  | 6 architecture docs, two-wave orchestration (Layer 2)                    | Yes    |
| 7. Opinionated + batteries-included  | 7 layers pre-wired, not a pick-your-own-adventure framework              | Yes    |
| 8. Model-agnostic                    | Works with Claude Code, Codex, Gemini                                    | Yes    |
| 9. Designed for autonomous operation | Humans design the harness, agents execute within it                      | Yes    |

**Result: 9/9 match.** LaunchPad is a textbook AI coding harness.

---

## Adoption Status of the Term

As of early 2026, "harness engineering" is **rapidly becoming canonical**. Adopted by:

- **OpenAI** (official blog post)
- **Anthropic** (engineering blog, pre-dating the term)
- **LangChain** (research + blog post)
- **Martin Fowler / Thoughtworks** (industry analysis)
- **Philipp Schmid** (former Hugging Face, now AWS)
- **Multiple X/Twitter threads** with thousands of engagements

It is being discussed as a **job title** ("harness engineer"), an **organizational capability**, and a **platform problem**. Multiple sources predict it will be one of the defining concepts of 2026 in AI engineering.

---

## Terminology Changes Applied

### New tagline

> The harness your AI agent didn't know it needed. With best practices pre-wired for AI coding.

### Files updated

| File                          | Change                                                                                                                                      |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `README.md`                   | Tagline updated; "opinionated project scaffold" -> "AI coding harness"; "wired into a single scaffold" -> "pre-wired into a single harness" |
| `docs/guides/HOW_IT_WORKS.md` | "a 7-layer system" -> "a 7-layer AI coding harness"                                                                                         |
| `docs/guides/METHODOLOGY.md`  | Tagline updated; "a monorepo template" -> "an AI coding harness"                                                                            |

### Preserved terminology

"Scaffold" is preserved where it specifically refers to Layer 1 (the file structure layer). The harness contains the scaffold; the scaffold is not the harness.

---

## Sources

- [Harness engineering: leveraging Codex in an agent-first world -- OpenAI](https://openai.com/index/harness-engineering/)
- [Effective harnesses for long-running agents -- Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Harness Engineering -- Martin Fowler / Birgitta Bockeler](https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html)
- [Improving Deep Agents with harness engineering -- LangChain](https://blog.langchain.com/improving-deep-agents-with-harness-engineering/)
- [The importance of Agent Harness in 2026 -- Philipp Schmid](https://www.philschmid.de/agent-harness-2026)
- [What is an agent harness in the context of large-language models? -- Parallel AI](https://parallel.ai/articles/what-is-an-agent-harness)
- [Dex Horthy's original tweet coining "harness engineering"](https://x.com/dexhorthy/status/1985699548153467120)
- [OpenAI Introduces Harness Engineering -- InfoQ](https://www.infoq.com/news/2026/02/openai-harness-engineering-codex/)
- [How OpenAI Built 1M Lines of Code: 5 Harness Engineering Principles -- Tony Lee](https://tonylee.im/en/blog/openai-harness-engineering-five-principles-codex)
- [Harness Engineering: Complete Guide -- NxCode](https://www.nxcode.io/resources/news/harness-engineering-complete-guide-ai-agent-codex-2026)
- [2025 Was Agents. 2026 Is Agent Harnesses -- Aakash Gupta (Medium)](https://aakashgupta.medium.com/2025-was-agents-2026-is-agent-harnesses-heres-why-that-changes-everything-073e9877655e)
- [My AI Adoption Journey -- Mitchell Hashimoto](https://mitchellh.com/writing/my-ai-adoption-journey)
- [Best AI Model for Coding: Harness Changed Scores 22% -- MorphLLM](https://www.morphllm.com/best-ai-model-for-coding)
- [The Emerging Harness Engineering Playbook -- Ignorance.ai](https://www.ignorance.ai/p/the-emerging-harness-engineering)
- [Beyond Prompts and Context: Harness Engineering -- MadPlay](https://madplay.github.io/en/post/harness-engineering)
- [Building AI Coding Agents for the Terminal (arXiv paper)](https://arxiv.org/html/2603.05344v1)
