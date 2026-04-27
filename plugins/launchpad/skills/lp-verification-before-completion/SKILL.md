---
name: lp-verification-before-completion
description: >
  Enforces evidence-before-claims for all completion assertions. Requires running
  verification commands (test, typecheck, lint, build) and confirming output
  before claiming work is done, fixed, or passing. Prevents false completion
  claims, premature commits, and trust-breaking assertions without proof.
  Triggers on: claiming work is complete, about to commit, creating PRs, marking
  tasks done, expressing satisfaction about code changes.
---

<!-- Adapted from obra/superpowers — skills/verification-before-completion/SKILL.md
     original-author: obra (superpowers)
     license: MIT -->

**Run verification commands and confirm their output before making any completion claim. No exceptions.**

## Trigger

Activate this skill automatically when:

- About to claim work is complete, fixed, passing, or done
- About to commit, push, or create a PR
- About to express satisfaction about code changes ("Great!", "Perfect!", "Done!")
- About to move to the next task after making changes
- Delegating to or receiving results from sub-agents
- Making any positive assertion about code state ("tests pass", "build succeeds", "no lint errors")

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If the verification command has not been run in the current message, the claim cannot be made.

## The Gate

Before claiming any status or expressing satisfaction:

1. **Identify the command.** What command proves this claim? Map it to the verification commands below.
2. **Run the full command.** Execute it fresh and complete — not a partial run, not a cached result.
3. **Read the full output.** Check exit code, count failures, read every error line.
4. **Confirm the output matches the claim.** If it does not, state the actual status with evidence. If it does, state the claim with the evidence attached.
5. **Only then make the claim.**

Skipping any step is fabrication, not verification.

## Verification Commands

The examples below show pnpm-based commands typical of TypeScript projects. For other stacks (Python, Go, Django, polyglot), the commands are whatever LaunchPad's project-level `.launchpad/config.yml` declares under `commands.test`, `commands.typecheck`, `commands.lint`, and `commands.build` — these are dispatched via `${CLAUDE_PLUGIN_ROOT}/scripts/plugin-build-runner.py --stage=<stage>`. The skill's contract is the same regardless of stack: identify the right stage, run it fresh, attach the output.

| Claim                  | Required Command (TS example)                | What Confirms It             |
| ---------------------- | -------------------------------------------- | ---------------------------- |
| Tests pass             | `pnpm test`                                  | Exit 0, 0 failures in output |
| Types are correct      | `pnpm typecheck`                             | Exit 0, no type errors       |
| No lint errors         | `pnpm lint`                                  | Exit 0, 0 errors in output   |
| Build succeeds         | `pnpm build`                                 | Exit 0, all workspaces built |
| Bug is fixed           | `pnpm test` + reproduce original symptom     | Test for the bug passes      |
| Definition of Done met | `pnpm test` + `pnpm typecheck` + `pnpm lint` | All three exit 0             |

## Red Flags — STOP Immediately

Stop and run verification if about to:

- Use "should", "probably", "seems to", "looks correct"
- Express satisfaction before running commands ("Great!", "All good!", "Done!")
- Commit, push, or create a PR without verification output in the current message
- Trust a sub-agent's success report without independent verification
- Rely on partial verification (linter passing does not mean types are correct)
- Claim completion based on code reading alone ("I changed the code so it should work")

## Rationalization Prevention

| Excuse                                        | Response                                         |
| --------------------------------------------- | ------------------------------------------------ |
| "Should work now"                             | Run the command                                  |
| "I'm confident"                               | Confidence is not evidence                       |
| "Just this once"                              | No exceptions                                    |
| "Linter passed"                               | Linter is not typecheck is not test is not build |
| "Agent said success"                          | Verify independently                             |
| "Partial check is enough"                     | Partial proves nothing about the whole           |
| "Different wording so the rule doesn't apply" | Spirit over letter — always                      |

## Correct Patterns

**Tests:**

```
RUN:  pnpm test
SEE:  Tests: 34 passed, 0 failed
THEN: "All 34 tests pass — output above."
```

**Definition of Done:**

```
RUN:  pnpm test && pnpm typecheck && pnpm lint
SEE:  All three exit 0
THEN: "Definition of Done met — test/typecheck/lint all pass. Output above."
```

**Bug fix (red-green cycle):**

```
1. Write regression test
2. RUN: pnpm test — SEE: new test FAILS (confirms it catches the bug)
3. Apply fix
4. RUN: pnpm test — SEE: all tests pass including the new one
5. THEN: "Bug fixed — regression test confirmed red-green cycle. Output above."
```

**Sub-agent delegation:**

```
1. Agent reports success
2. RUN: git diff to inspect actual changes
3. RUN: pnpm test && pnpm typecheck && pnpm lint
4. SEE: All pass
5. THEN: "Agent changes verified — test/typecheck/lint pass. Output above."
```

## What This Skill Does NOT Handle

- **Choosing which tests to write** — this skill enforces running verification, not test design.
- **Code review quality** — this skill checks that claims are backed by evidence, not that the code itself is good.
- **CI/CD pipeline configuration** — this skill governs local verification behavior, not deployment gates.

## Verification

- [ ] Every completion claim in the conversation is preceded by a fresh command run with visible output
- [ ] All three Definition of Done commands (test, typecheck, lint) are run before marking a task complete
- [ ] No "should pass" / "looks correct" / "seems to work" language appears without command evidence
- [ ] Sub-agent results are independently verified before being reported as successful
- [ ] Red-green cycle is demonstrated for bug fix claims (test fails before fix, passes after)

**Run verification commands and confirm their output before making any completion claim. No exceptions.**
