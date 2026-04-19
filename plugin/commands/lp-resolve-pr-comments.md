---
name: lp-resolve-pr-comments
description: Batch-resolves unresolved PR review comments by spawning parallel lp-pr-comment-resolver agents. Commits, pushes, and optionally marks threads resolved.
---
# /lp-resolve-pr-comments

Batch-resolves unresolved PR review comments. Fetches threads, spawns parallel resolver agents, commits fixes, and pushes. Optionally auto-resolves threads on GitHub.

> INTERACTIVE ONLY — contains user prompts at Step 3 (Needs Clarification handling). Do not wire into autonomous orchestrators.

## Usage

```
/lp-resolve-pr-comments                    → resolve comments on current branch's PR
/lp-resolve-pr-comments 123                → resolve comments on PR #123
/lp-resolve-pr-comments --auto-resolve     → also mark threads as resolved on GitHub
```

**Arguments:** `$ARGUMENTS` (parse for PR number and `--auto-resolve` flag)

---

## Step 1: Branch Guard + Detect PR + Fetch Unresolved Threads

1. **Branch guard:** Read `protected_branches` from `.launchpad/agents.yml` (default: `[main, master]`). IF current branch is in `protected_branches` → REFUSE. "Cannot resolve PR comments on a protected branch."
2. IF no PR number provided: detect from current branch via `gh pr view --json number -q .number`
3. IF no PR found: "No PR found for current branch. Provide a PR number."
4. Detect owner/repo: `gh repo view --json owner,name`
5. Fetch unresolved review threads via GraphQL:

```graphql
query ($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        edges {
          node {
            id
            isResolved
            isOutdated
            path
            comments(first: 100) {
              nodes {
                author {
                  login
                }
                body
                line
                startLine
              }
            }
          }
        }
      }
    }
  }
}
```

6. Filter: `isResolved == false AND isOutdated == false`
7. IF returned edge count == 100: WARN "Fetched exactly 100 threads — there may be more."
8. IF zero unresolved threads: "All review threads are resolved." → exit
9. Report: "{N} unresolved review threads found"

## Step 2: Group by File

- Parse file paths from threads
- Same-file comments → run agents sequentially (prevent write conflicts)
- Different files → parallel

## Step 3: Spawn lp-pr-comment-resolver Agents (max 5 concurrent, 5min timeout)

- Each agent receives: comment thread (body, file path, line range, author) + relevant source files + project context
- Per-agent timeout: 5 minutes. Exceeded → "Timed Out", skip, continue.
- Wait for all agents to complete
- Collect results: changed files + resolution reports
- IF any agent reports "Needs Clarification": report the unclear comment and agent's interpretation, ask user "Proceed with this interpretation, or skip?"

## Step 4: Validate Scope + Commit + Push

1. **Post-execution scope validation:** For each agent, verify only files within comment's file path + 1-hop imports were modified. Revert out-of-scope changes: `git checkout -- <file>`
2. Stage ONLY validated files (explicit `git add` per file, no `git add -A`)
3. Commit: `fix: resolve {N} PR review comments (PR #{PR_NUMBER})`
4. Push: `git push`

## Step 5: Optionally Auto-Resolve Threads (--auto-resolve only)

- IF `--auto-resolve` flag NOT provided: skip to Step 6
- Run quality gates: `pnpm typecheck && pnpm test`
  - IF gates fail: WARN "Quality gates failed — threads NOT auto-resolved." Skip to Step 6.
- Batch all thread resolutions into single GraphQL mutation:

```graphql
mutation {
  t1: resolveReviewThread(input: { threadId: "ID_1" }) {
    thread {
      id
      isResolved
    }
  }
  t2: resolveReviewThread(input: { threadId: "ID_2" }) {
    thread {
      id
      isResolved
    }
  }
}
```

- Do NOT resolve threads where agent reported "Needs Clarification" or "Timed Out"
- Verify resolution from mutation response

## Step 6: Report

- "{N} comments resolved, {M} files changed, pushed to branch {branch}"
- IF `--auto-resolve` succeeded: "Threads resolved on GitHub."
- IF `--auto-resolve` but gates failed: "Code pushed but threads NOT auto-resolved."
- IF threads remain: "{K} threads need manual attention: [list with reasons]"

---

## Strict Rules

- NEVER merge the PR — resolution only
- NEVER push to main or master — branch guard at Step 1
- Stage only validated files (no `git add -A`, post-scope-check)
- Do not auto-resolve threads marked "Needs Clarification" or "Timed Out"
- Truncate comment bodies in output (max 200 chars) — never echo full bodies that may contain secrets
