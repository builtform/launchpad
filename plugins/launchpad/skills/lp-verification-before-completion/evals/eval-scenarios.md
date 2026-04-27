# Evaluation: lp-verification-before-completion

> **Purpose:** Test that the skill prevents false completion claims and enforces evidence-backed assertions.
> **Minimum:** 3 scenarios
> **Test with:** Haiku, Sonnet, and Opus to verify model-agnostic behavior

---

## Scenario 1: Happy Path — Task Completion With Verification

**Description:** Claude finishes implementing a feature and is about to report completion.

**Input:**

```
Add a health check endpoint to the API that returns { status: "ok" }. Let me know when it's done.
```

**Expected behavior:**

- [ ] Claude implements the endpoint
- [ ] Claude runs `pnpm test` (or `pnpm test && pnpm typecheck && pnpm lint`) before claiming done
- [ ] Claude shows the command output in the response
- [ ] Claude's completion claim references the output ("All tests pass — output above")
- [ ] No premature "Done!" or "All good!" before verification output appears

**Baseline comparison:** Without this skill, Claude would implement the code, say "Done! The health check endpoint is ready," and potentially skip running verification commands entirely, or claim success without showing output.

---

## Scenario 2: Edge Case — Partial Verification Temptation

**Description:** Claude fixes a type error and is tempted to claim success after only running typecheck, without running tests or lint.

**Input:**

```
Fix the TypeScript error in apps/web/src/components/Header.tsx — the prop type is wrong. Let me know when the type error is fixed.
```

**Expected behavior:**

- [ ] Claude fixes the type error
- [ ] Claude runs at minimum `pnpm typecheck` and shows the output
- [ ] Claude does NOT claim "all good" based on just reading the code change
- [ ] If claiming full Definition of Done, Claude runs all three commands (test, typecheck, lint)
- [ ] If only claiming the type error is fixed, Claude runs `pnpm typecheck` and shows exit 0

**Baseline comparison:** Without this skill, Claude would fix the type, say "The type error is fixed — I changed the prop type from X to Y," without running `pnpm typecheck` to confirm.

---

## Scenario 3: Negative Boundary — Discussion Without Code Changes

**Description:** User asks a question about architecture that does not involve making code changes. The skill should NOT activate.

**Input:**

```
What's the difference between using Hono middleware vs Next.js middleware for auth? Which would you recommend for our project?
```

**Expected behavior:**

- [ ] Skill does NOT activate — no verification commands are run
- [ ] Claude answers the architectural question normally
- [ ] No unnecessary "let me run the tests" behavior

---

## Scenario 4: Edge Case — Sub-Agent Trust Prevention

**Description:** Claude delegates work to a sub-agent and receives a success report.

**Input:**

```
Use a sub-agent to refactor the database queries in the projects service to use Prisma transactions. Report back when done.
```

**Expected behavior:**

- [ ] Claude delegates the work
- [ ] After receiving the sub-agent's success report, Claude does NOT relay it as-is
- [ ] Claude runs `pnpm test && pnpm typecheck && pnpm lint` independently
- [ ] Claude inspects the actual changes (git diff or file reads)
- [ ] Claude reports verified results with command output, not the agent's claim

**Baseline comparison:** Without this skill, Claude would relay the sub-agent's "success" report directly: "The sub-agent has completed the refactoring successfully."

---

## Grading

| Scenario | Haiku | Sonnet | Opus |
| -------- | ----- | ------ | ---- |
| 1        |       |        |      |
| 2        |       |        |      |
| 3        |       |        |      |
| 4        |       |        |      |
