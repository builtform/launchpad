# LaunchPad

> The agentic coding harness that installs a persistent governance kernel into your repository, dispatches multi-agent code review with confidence scoring and a P1 floor, and gates autonomous build runs behind an integrity guard plus a content-hash audit log. So your AI ships production-grade code without you becoming the bottleneck.

![License](https://img.shields.io/badge/License-MIT-blue)
![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-1f6feb)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-22.x-339933?logo=node.js&logoColor=white)

![LaunchPad Architectural Outline](.github/assets/hero-image.png)

---

## The cold-session tax

The bottleneck in shipping production code with an AI agent is not the agent's reasoning quality. It is that every new session starts cold. The agent re-learns the repo, re-discovers last week's bugs, and re-introduces conventions you already paid for in review time. The cost is invisible per session and compounding across the project.

The teams shipping production code with Claude Code today are not losing time to bad AI output. They are losing time to the AI starting cold every session. The agent forgets last week's decision, you spend 20 minutes re-explaining the repo, and the third time it happens you stop trusting the agent for anything that touches a real customer.

That is the structural problem. The agent is not the cause. The missing substrate underneath is.

---

## How developers handle agentic coding today

| Approach                                                                                                       | Pros for you                                                                                                                                                                                                                                                              | Cons that cost you weeks                                                                                                                                                                                                                                            |
| -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Status quo:** raw Claude Code, Cursor, or Aider with hand-rolled prompts                                     | Familiar, free, no install; memory primitives (`CLAUDE.md` auto-load + v2.1.59 auto-memory, Cursor Memories, Aider `CONVENTIONS.md`) cover preferences and short notes                                                                                                    | No governance kernel enforced by pre-commit gates; no multi-agent review dispatch with confidence scoring; no audit trail of what got suppressed; structure conventions drift as the project grows                                                                  |
| **Claude Code methodology plugins:** Compound Engineering (Every), Superpowers (obra), BMAD-METHOD             | Compound Engineering ships 20+ confidence-calibrated review agents plus compound-learning files; Superpowers ships methodology-as-skills (TDD, debugging, brainstorming) and is Anthropic-marketplace-blessed; BMAD ships 12+ agile-style agents with dev-loop automation | None installs a governance kernel enforced by pre-commit gates; none ships LaunchPad's specific P1-floor + audit-trailed suppression; none ships an integrity guard against autonomous-build bypass or a status contract that blocks concurrent-work corruption     |
| **First-party platform features:** Anthropic Code Review (launched March 9, 2026), GitHub SpecKit              | Anthropic Code Review ships first-party multi-agent PR review with sub-agent dispatch from the platform vendor; SpecKit ships `/speckit.specify`/`plan`/`tasks`/`analyze` with persistent `constitution.md`                                                               | Anthropic Code Review is cloud-only and post-PR (no local pre-PR run, no in-repo persistence); SpecKit is spec-first only (no autonomous build, no compound-learning solutions corpus, no integrity guard)                                                          |
| **Spec-driven IDEs and platforms:** AWS Kiro, Tessl                                                            | Kiro is a full agentic IDE with spec lifecycle (`requirements.md` / `design.md` / `tasks.md`), hooks for lint/test/secret-scan on save, and a no-auto-merge guarantee; Tessl positions as "spec-first AI-native dev" platform                                             | IDE-shaped (replaces your editor rather than installing into it); no LaunchPad-specific combination of P1 floor + content-hash audit log + integrity guard against autonomous-build bypass                                                                          |
| **Context-engineering and methodology systems:** HumanLayer (CRISPY), Agent OS (Builder Methods), Continue.dev | HumanLayer's CRISPY (2026) reintroduced multi-stage review and `require_approval()` gates; Agent OS ships a 3-layer Standards/Product/Specs kernel; Continue.dev's Continuous AI runs markdown-defined PR-time checks                                                     | None installs a governance kernel enforced by pre-commit gates; none ships LaunchPad's specific combination of confidence-scored review with P1 floor + audit-trailed suppression + integrity guard                                                                 |
| **Autonomous-engineer products:** Devin (Cognition), OpenHands, Factory.ai                                     | Full autonomous-engineer agents that plan, code, test, and open PRs; OpenHands is MIT-licensed and self-hostable; Factory.ai "droids" control browser/terminal/IDE                                                                                                        | Different shape entirely (SaaS agent or sandboxed runner, not a repo-installed kernel); no in-repo governance kernel reloaded every session; no multi-agent specialist review with confidence scoring; you outsource the work rather than augment your own pipeline |
| **Loop and orchestration toolkits:** Ralph Loop, Claude Flow, Codename Goose (Block)                           | Ralph is a Bash-loop pattern that writes state to `AGENTS.md`/`PROMPT.md`/specs between iterations; Claude Flow ships 60+ agents and swarm orchestration; Goose is an Apache-2.0 agent framework                                                                          | Patterns and orchestration runtimes, not installable governance kernels; no multi-agent specialist review with confidence scoring out of the box; no integrity guard or audit log; structure enforcement and review dispatch are still wired by hand                |

None of these are wrong. They are partial. They each address one slice of the cold-session tax and leave the other slices for you to wire up yourself.

---

## What to look for in a harness

Before evaluating LaunchPad (or any harness), bring these three criteria with you:

1. **Persistent context across sessions.** The next agent run inherits the previous run's decisions and findings instead of starting cold.
2. **Senior-reviewer-grade quality bar before you read the PR.** Multi-agent review with confidence scoring, a P1 floor that cannot be silently suppressed, and an audit trail for any noise the harness suppresses on your behalf.
3. **Autonomous runs safe to leave unattended.** Every bypass path closed in code rather than in policy. Commands that refuse to run when violated, not guidelines you have to remember.

If any of those three is not on your evaluation list, LaunchPad is probably not the right tool for you and you should keep looking. If all three are, read on.

---

## LaunchPad: an agentic coding harness

LaunchPad is an **agentic coding harness**. It installs a governance kernel into your repository, then runs Claude Code against that kernel. The kernel is what persists between sessions. The agents are productive _because_ the kernel is in place. Without it, recipe-pack plugins regenerate the same boilerplate every session and silently drift away from project conventions.

Works on **brownfield** projects (add the plugin to an existing repo, run `/lp-define`, get the kernel retrofitted) and **greenfield** (run the `/lp-brainstorm` → `/lp-pick-stack` → `/lp-scaffold-stack` → `/lp-define` pipeline for a fresh project with the kernel materialized from scratch).

LaunchPad ships under the **BuiltForm** marketplace at [github.com/builtform](https://github.com/builtform).

For the full pipeline narrative, see [HOW_IT_WORKS.md](docs/guides/HOW_IT_WORKS.md). For the architecture and design principles behind the kernel, see [METHODOLOGY.md](docs/guides/METHODOLOGY.md).

---

**Contents:** [Install](#install) · [What you get](#what-you-get) · [Proof](#proof-you-can-verify-this-yourself) · [First 15 Minutes](#first-15-minutes) · [What's Inside](#whats-inside) · [Security](#security) · [Who this is for](#who-this-is-for-and-who-it-isnt) · [Methodology](#methodology) · [Companions](#companions) · [Links](#links)

---

## Install

### Path 1: Add to any repo (Best for Brownfield)

Inside Claude Code, in the project where you want the commands, register the BuiltForm marketplace and install the plugin. Copy-paste the two commands below into a fresh Claude Code session:

```
/plugin marketplace add github:builtform/marketplace
/plugin install launchpad@builtform
```

Restart Claude Code. All `/lp-*` commands are now available. Run `/lp-kickoff` to start.

The marketplace registration step is required today because BuiltForm is awaiting confirmation in the Anthropic public plugin registry. Once Anthropic confirms BuiltForm, `/plugin install launchpad@builtform` will work on its own and the `marketplace add` line above will no longer be necessary. Until then, run both lines.

### Path 2: Fresh monorepo (Best for Greenfield)

LaunchPad detects greenfield vs brownfield by **inspecting your project folder**. An empty folder (or one containing only `.gitignore`, a short `README.md`, `LICENSE`, or a fresh `git init`) reads as greenfield. Anything else (a `package.json`, `pyproject.toml`, any other dependency manifest, or even a stray `.DS_Store` from opening the folder in Finder) flips detection and the four-command pipeline will refuse to scaffold.

**Step 1.** Create a new, empty folder for your project and `cd` into it:

```bash
mkdir my-project && cd my-project
```

Don't `npm init`, don't drop in a `pyproject.toml`, don't open the folder in Finder before you're ready. Keep it clean.

**Step 2.** Open Claude Code in that folder and install the plugin using the same two commands from Path 1:

```
/plugin marketplace add github:builtform/marketplace
/plugin install launchpad@builtform
```

Restart Claude Code.

**Step 3.** Run the four-command greenfield pipeline:

```
/lp-brainstorm  →  /lp-pick-stack  →  /lp-scaffold-stack  →  /lp-define
```

The pipeline scaffolds a fresh monorepo with `package.json`, `lefthook.yml`, the architecture docs, and project config rendered natively by the plugin's kernel renderer. No `git clone` step is required; the plugin is the canonical source for all scaffold content.

---

## What you get

Three outcomes, working together.

### 1. Agent context that survives between sessions

Your AI's next session inherits the previous session's decisions, findings, and resolved problems instead of starting cold. A governance kernel installed in your repo is what persists; a compound-learning corpus is what makes the agent sharper over time. You stop paying the "explain the repo to the AI again" tax on every session, and the marginal cost of session N+1 stays flat instead of climbing as the project grows.

### 2. Every PR clears a senior-reviewer-grade quality bar before you read it

Multiple specialist review agents run in parallel against every diff. Findings carry confidence scores; critical findings (P1) cannot fall below the floor and get silently dropped; everything the harness suppresses lands in an in-repo audit trail you can review. You stop being the only line of defense, and rework rate per PR drops because the agent fixes its own findings before asking you to look.

### 3. Autonomous runs you can leave unattended

`/lp-build` plans, codes, tests, opens PRs, and captures learnings without supervision. Code-level guards refuse to merge to `main`, refuse to commit leaked secrets, and refuse to run if their own authorization was smuggled in by the same commit. You can run it overnight without the "I shouldn't have left it running" feeling, because the safeguards are commands that refuse when violated, not policies you have to remember.

### How LaunchPad compares to the alternatives

Nine criteria that matter when picking a coding harness. Each row is an actual competing tool, evaluated honestly against each criterion. **LaunchPad is the only row that ships all nine.** Most peers ship 1 to 3 of them. Compound Engineering (the closest peer) ships 3 Yes plus 1 Partial. AWS Kiro ships 2 Yes plus 2 Partial on the safety axis. Both are credited here, not erased.

| Approach                                        | Greenfield scaffolding | Brownfield retrofit | Governance kernel | Stack adapter | Multi-agent review | P1 floor + audit | Compound learning | Merge refusal | Open source |
| ----------------------------------------------- | ---------------------- | ------------------- | ----------------- | ------------- | ------------------ | ---------------- | ----------------- | ------------- | ----------- |
| Compound Engineering Plugin (Every)             | No                     | No                  | No                | No            | Yes                | Partial          | Yes               | No            | Yes         |
| Superpowers (obra), BMAD-METHOD                 | No                     | No                  | No                | No            | Yes                | No               | Yes               | No            | Yes         |
| Claude Code multi-agent code review (Anthropic) | No                     | No                  | No                | No            | Yes                | Partial          | No                | No            | Yes         |
| GitHub SpecKit                                  | Partial                | No                  | No                | No            | No                 | No               | No                | No            | Yes         |
| AWS Kiro                                        | Yes                    | No                  | Partial           | No            | Yes                | No               | No                | Partial       | No          |
| CodeLayer (HumanLayer), Continue.dev            | No                     | No                  | No                | No            | Yes                | No               | No                | No            | Yes         |
| Devin (Cognition), OpenHands                    | Yes                    | No                  | No                | No            | No                 | No               | No                | No            | Partial     |
| ScaffoldHub                                     | Yes                    | No                  | No                | No            | No                 | No               | No                | No            | No          |
| **LaunchPad**                                   | **Yes**                | **Yes**             | **Yes**           | **Yes**       | **Yes**            | **Yes**          | **Yes**           | **Yes**       | **Yes**     |

**What each criterion means:**

- **Greenfield scaffolding:** the tool produces a fresh working monorepo (package.json, gates, docs), not just a spec doc or generated code without a kernel.
- **Brownfield retrofit:** the tool detects existing repo state and installs into existing repos without nuking what's already there.
- **Governance kernel:** a specific kernel file set (whitelist + lefthook + config + runtime + architecture docs) enforced by pre-commit gates in your repo. Not memory files alone.
- **Stack adapter:** auto-detects your stack at install time (TS / Python / polyglot) and filters which review agents run, which test/lint commands fire, which templates render.
- **Multi-agent review:** multiple specialist review agents dispatched per PR or diff (security, performance, architecture, etc.) rather than a single generalist.
- **P1 floor + audit:** critical/P1 findings cannot be auto-suppressed; suppression decisions land as auditable artifacts in your repo. (Confidence scoring alone is no longer differentiating; Claude Code's open-source review plugin ships that half since March 2026.)
- **Compound learning:** structured solutions or skills captured from resolved problems get reloaded by future agent runs.
- **Merge refusal:** three-layer hard refusal of automated merge to `main`/`master` (command refusal + PreToolUse hook + branch protection, all three layers required to fail before a merge happens).
- **Open source:** MIT, Apache, or similar permissive license; source code available for audit.

**The honest picture.**

**LaunchPad is two things working together: a governance kernel installed into your repository, and the orchestrators that drive the brainstorm → scaffold → plan → build → review → ship → learn loop against it.** The kernel persists between agent sessions; the orchestrators run the loop. No tool in this table ships both.

**vs. Compound Engineering Plugin (closest peer).** LaunchPad's review agents and skills are CE's, ported natively at fork point. The difference is the substrate: CE ships none, so sessions restart cold; LaunchPad installs the 5-file kernel above, enforced by pre-commit gates, plus three capabilities CE has nothing for: greenfield/brownfield auto-detection, per-stack agent dispatch, and a P1 floor with repo-resident audit trail. You don't choose between LaunchPad and CE; LaunchPad is CE's recipes plus the substrate that makes them productive across sessions.

**vs. AWS Kiro (strongest on autonomous-build + safety).** Kiro is the closest tool on the safe-autonomous axis: greenfield scaffolding from specs, multi-agent reference architecture, on-save lint/test/secret-scan hooks, single-layer "never auto-merges" guarantee. Two gaps: shape (Kiro is an IDE you adopt as your editor; LaunchPad is a plugin in the editor you already use) and substrate (no compound-learning corpus, no per-stack agent dispatch, no P1 floor with audit trail, single-layer merge refusal vs three, AWS-proprietary). Kiro asks you to switch editors; LaunchPad ships with the editor you already chose.

**vs. ScaffoldHub (greenfield-scaffolder category).** ScaffoldHub is a one-shot form-driven generator: fill in a data model, get a working Next.js + Prisma + Hono codebase, then you are on your own. LaunchPad scaffolds from a brainstorm conversation, keeps a governance kernel alive for the lifetime of the project, and adds review, build, and compound-learning loops on top. ScaffoldHub is a generator; LaunchPad is a harness with scaffolding as one phase.

**Why the combination matters.** Each peer addresses one slice of the cold-session tax: CE the review recipes, Kiro the autonomous-build safety, ScaffoldHub the cold start. LaunchPad addresses all three structurally because the kernel, multi-agent review with P1 floor, and three-layer merge refusal are designed against each other. That coherence is what no competitor ships, regardless of how many individual criteria they cover.

---

## Proof (you can verify this yourself)

LaunchPad is MIT-licensed and open-source. Every claim above maps to a file you can read in the repo.

| Claim                                | Verify by                                                                                                                                                                                                                   |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 5-file governance kernel             | Open `docs/architecture/REPOSITORY_STRUCTURE.md`, `lefthook.yml`, `.launchpad/config.yml`, `.harness/`, `docs/architecture/`. Tests verify the file set materializes on `/lp-define`.                                       |
| Compound learning loop               | Walk `docs/solutions/` and read any entry. 14-category taxonomy with YAML-validated frontmatter.                                                                                                                            |
| 42 commands, 36 agents, 16 skills    | Browse `plugins/launchpad/commands/`, `plugins/launchpad/agents/`, `plugins/launchpad/skills/`.                                                                                                                             |
| Multi-agent review dispatch          | Read `.launchpad/agents.yml` and the 13 review agents in `plugins/launchpad/agents/review/`. Dispatch logic is in the `/lp-review` command file.                                                                            |
| 0.60 confidence threshold + P1 floor | Specified in the `/lp-review` command file and enforced in code. Suppression audit trail at `.harness/observations/`.                                                                                                       |
| Stack-aware dispatch                 | `stack_scope:` frontmatter on every agent file. Test coverage: `test_define` + `test_pipeline_matrix` (1,457 passing as of v2.1.3).                                                                                         |
| Content-hash audit log               | Open `.launchpad/audit.log` and read an entry. Schema: ISO timestamp, git user, commit SHA, command, content hash.                                                                                                          |
| Integrity guard refusal              | Code-level check in `/lp-build`. Regression test arms the hostile-PR pattern and asserts the refusal.                                                                                                                       |
| Three-layer merge prevention         | Layer 1: refusal strings in `plugins/launchpad/commands/lp-ship.md` and `plugins/launchpad/commands/lp-commit.md`. Layer 2: PreToolUse hook. Layer 3: GitHub branch protection rules. All three visible in the public repo. |
| Compounding prior art                | Compound Engineering Plugin (Kieran Klaassen / Every) ported natively at fork point, credited in [METHODOLOGY.md](docs/guides/METHODOLOGY.md). The kernel layer is LaunchPad's addition on top.                             |

---

## First 15 Minutes

LaunchPad is organized around four **meta-orchestrators** that chain an idea all the way to a shipped PR:

```
/lp-kickoff  →  /lp-define  →  /lp-plan  →  /lp-build
 brainstorm     spec the       design +     build, review,
                product        plan         resolve, ship, learn
```

Each orchestrator checks a section's status before proceeding. You can run them in sequence for a whole feature, or invoke any one independently when resuming work.

- **`/lp-kickoff`**: collaborative brainstorming with codebase research, writes a design doc to `docs/brainstorms/`, hands off to `/lp-define`.
- **`/lp-define`**: seeds your architecture docs (PRD, tech stack, design system, app flow, backend, CI/CD) and section specs. Stack-aware: detects TypeScript / Python / polyglot projects and seeds `.launchpad/agents.yml` and `.launchpad/config.yml` accordingly.
- **`/lp-plan`**: design workflow (when UI is involved) → `/lp-pnf` (Plan Next Feature) → `/lp-harden-plan` (multi-agent plan stress-test) → human approval gate.
- **`/lp-build`**: fully autonomous. `/lp-inf` (execute the plan) → `/lp-review` (multi-agent review with confidence scoring and FP suppression) → `/lp-resolve-todo-parallel` (fix findings) → `/lp-test-browser` → `/lp-ship` (opens PR, never merges) → `/lp-learn` (captures learnings).
- **`/lp-update-identity`**: update sealed identity (project rename, license change, copyright holder, email, repo URL fill-in) without re-scaffolding. Re-renders the 7 kernel files via `KernelRenderer.refresh()`.

Full workflow guide: [HOW_IT_WORKS.md](docs/guides/HOW_IT_WORKS.md).

---

## What's Inside

LaunchPad ships as a Claude Code plugin with:

| Component       | Count     | What it covers                                                                          |
| --------------- | --------- | --------------------------------------------------------------------------------------- |
| Slash commands  | 38        | The brainstorm, define, plan, build, review, resolve, ship, and learn lifecycle         |
| Sub-agents      | 36        | 6 namespaces: research, review, resolve, design, skills, document-review                |
| Skills          | 16        | Reusable instruction sets for design, planning, review, compound docs                   |
| Runtime scripts | several   | Stack detector, polyglot adapter, Jinja2 doc generator, install scripts                 |
| Test suite      | 12 suites | Adapters, config loader, stack detector, pipeline integration, install-paths regression |

<details>
<summary>Plugin structure</summary>

```
LaunchPad/
├── .claude-plugin/
│   └── marketplace.json        # name=launchpad
├── plugins/launchpad/          # the plugin itself
│   ├── .claude-plugin/
│   │   └── plugin.json         # name=launchpad, version=2.1.3
│   ├── commands/               # /lp-* slash commands
│   ├── agents/                 # 36 sub-agents across 6 namespaces
│   ├── skills/                 # reusable instruction sets
│   └── scripts/                # runtime scripts + stack adapters
├── .launchpad/                 # project-local harness config
└── docs/                       # architecture, reports, releases
```

</details>

---

## Security

LaunchPad runs agents with elevated permissions. `/lp-build` creates branches, runs tests, commits, pushes, and opens PRs without asking.

Safeguards are layered:

- **PRs, not direct merges.** `/lp-ship` hard-refuses to run `gh pr merge` or `git merge main/master`.
- **Multi-agent review with confidence scoring.** `/lp-review` dispatches code + design + DB + copy agents in parallel; findings below a 0.60 confidence threshold are suppressed with an audit trail. P1 floor prevents silent suppression of critical issues.
- **Autonomous-build acknowledgment file.** `.launchpad/autonomous-ack.md` must exist before `/lp-build` will run, making autonomous authorization visible in git blame and PR diffs.
- **Content-hash audit log.** `.launchpad/audit.log` records every command invocation with ISO timestamp, git user, commit SHA, and a hash of the canonical commands section, so auditors can see what the harness ran and at what plugin state.
- **Integrity guard.** `/lp-build` refuses to run if the section spec and `autonomous-ack.md` were introduced in the same commit (the pattern a hostile PR would use to bypass review).

LaunchPad's autonomous loops pass `--dangerously-skip-permissions` to Claude Code so the loop can run unattended. To close the gap that flag opens (destructive shell commands like `rm -rf` or `git reset --hard` that the built-in merge-block hook does not cover) pair LaunchPad with [Destructive Command Guard (dcg)](https://github.com/Dicklesworthstone/destructive_command_guard), a third-party Rust `PreToolUse` hook. Strongly recommended for any unattended `/lp-build` run. Full threat model and the recommended companions: [SECURITY.md](SECURITY.md).

Detailed threat model and safeguard list: [HOW_IT_WORKS.md → Security](docs/guides/HOW_IT_WORKS.md#security-considerations).

---

## Who this is for (and who it isn't)

**LaunchPad is built for** solo developers and small-team tech leads (1 to 5 engineers) who:

- Are already using Claude Code as their primary AI coding tool (the dependency is hard; LaunchPad is a Claude Code plugin).
- Work in a production-grade repository where shipped bugs have a real cost.
- Have felt the pain of agent-context-loss between sessions and can name a specific instance.
- Have had at least one near-miss with an AI commit: leaked secret, broken migration, file-structure drift, hallucinated API.
- Are willing to invest about 30 minutes to install a kernel into their repo for a payoff measured in weeks.
- Work in TypeScript, Python, or a polyglot mix (the stacks the v2.1 adapter set supports first-class).

**LaunchPad is not for:**

- **Engineering managers shopping for team-wide tooling.** Wrong sale, wrong evaluation criteria. LaunchPad ships a kernel and slash commands for the hands-on operator. If you want SSO, dashboards, and admin policies, evaluate compliance-first tools instead.
- **Pure greenfield "vibe coders" who don't care about quality.** The kernel will feel like friction. The value of a kernel only shows up once the codebase is large enough to drift, and if you don't care, you don't need it yet.
- **Enterprise security teams looking for SOC2 or vendor risk reviews.** LaunchPad is MIT-licensed and open-source; the entire surface is auditable in the GitHub repo. If your evaluation criterion is SOC2, this is not the tool.
- **Developers not on Claude Code.** LaunchPad is a Claude Code plugin. Cursor, Copilot, Aider users: this is a future conversation, not a today one.

Surfacing the anti-fit up front is intentional. If any of the above describes you, do not install. There are tools better suited to those problems, and the 30 minutes of install friction will pay off poorly.

---

## Methodology

LaunchPad organizes AI-assisted development into six layers (Scaffold, Definition, Planning, Execution, Quality, Learning) with design principles (status contract, fresh-context loops, confidence scoring, compound learning) designed to keep agents honest.

Full architecture, design principles, and credits: [METHODOLOGY.md](docs/guides/METHODOLOGY.md).

LaunchPad stands on the shoulders of:

- **[Compound Engineering Plugin](https://github.com/EveryInc/compound-engineering-plugin)** by Kieran Klaassen / [Every](https://every.to/), ported natively at fork point. LaunchPad's addition is the kernel underneath.
- **[Compound Product](https://github.com/snarktank/compound-product)** by Ryan Carson: autonomous pipeline from report to PR.
- **[Ralph Loop](https://ghuntley.com/ralph/)** by Geoffrey Huntley: fresh-context execution loop (a Bash loop pattern).
- **[HumanLayer](https://github.com/humanlayer/humanlayer)**: SDK plus Claude Code commands for context engineering (Research → Plan → Implement, locator/analyzer pairs, `require_approval()`).
- **Spec-Driven Development**: SpecKit and Agent OS (Builder Methods) philosophy (specify before building).

---

## Companions

LaunchPad is intentionally narrow in scope. Two third-party tools pair well with it for users who want extra capabilities:

- **[Destructive Command Guard (dcg)](https://github.com/Dicklesworthstone/destructive_command_guard)** by [@Dicklesworthstone](https://github.com/Dicklesworthstone): pattern-based shell-command guard that closes the `--dangerously-skip-permissions` gap by intercepting `rm -rf`, `git reset --hard`, `DROP TABLE`, and similar destructive operations before they execute. Strongly recommended for any unattended `/lp-build` run. See [SECURITY.md](SECURITY.md#recommended-companion-destructive-command-guard-dcg) for context.
- **[MemPalace](https://github.com/MemPalace/mempalace)**: local vector store + MCP server giving Claude Code verbatim recall of past sessions. Adds a fourth tier (raw transcript retrieval) on top of LaunchPad's three-tier knowledge system. Setup cookbook: [docs/guides/MEMPALACE_INTEGRATION.md](docs/guides/MEMPALACE_INTEGRATION.md).

LaunchPad does not bundle either tool, does not auto-install them, and does not depend on them at runtime. They're recommended pairings, not requirements.

---

## Next step

Install LaunchPad and run `/lp-kickoff` in the repo you are actively shipping from:

```
/plugin marketplace add github:builtform/marketplace
/plugin install launchpad@builtform
```

Restart Claude Code, then run `/lp-kickoff`.

What happens next:

1. `/lp-kickoff` runs a collaborative brainstorm with codebase research, writes a design doc to `docs/brainstorms/`, and hands off to `/lp-define`.
2. `/lp-define` seeds the architecture docs (PRD, tech stack, design system, app flow, backend, CI/CD) and section specs. Stack-aware: detects TypeScript, Python, or polyglot and seeds `.launchpad/agents.yml` and `.launchpad/config.yml` accordingly.
3. After `/lp-define`, the Tier 1 reveal panel prints. You see the 5-component kernel listed with the one-line "why it matters" for each component.
4. From there, run `/lp-plan` and `/lp-build` on a real section and feel the difference within an hour.

Cost: about 30 minutes of install plus the first `/lp-define`. Plugin is MIT and free. No quote, no demo gate, no contact form.

---

## Links

- [How It Works](docs/guides/HOW_IT_WORKS.md): day-to-day operator's manual
- [Methodology](docs/guides/METHODOLOGY.md): architecture, design principles, credits
- [Repository structure](docs/architecture/REPOSITORY_STRUCTURE.md): file-placement decision tree
- [Release notes](docs/releases/v2.1.3.md)
- [Contributing](CONTRIBUTING.md)

---

## License

MIT. See [LICENSE](LICENSE).
