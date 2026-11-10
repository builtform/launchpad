#!/usr/bin/env bash
set -euo pipefail
# PreToolUse hook: blocks merge, force-push, and approve commands.
# One exception: Dependabot PRs may be merged by number (see EXEMPT_MERGE_RE).
# Claude Code passes tool input as JSON on stdin.
# Exit 0 = allow, Exit 2 = block.

INPUT=$(cat) || true

# Fail closed: if jq is missing or input is empty
if ! command -v jq >/dev/null 2>&1 || [ -z "$INPUT" ]; then
  echo "BLOCKED: Could not parse hook input (jq missing or empty stdin). Failing closed." >&2
  exit 2
fi

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || true

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Normalize: convert newlines to ;; (treating each line as a separate command)
# then flatten to single line for boundary matching.
FLAT=$(printf '%s' "$COMMAND" | tr '\n' ';')

# Dependabot merge exception. The exempt merge must be the whole command, so
# nothing else in it can change the directory, environment or repository the
# merge runs against, and it must run from inside the project directory.
TRIMMED=$(printf '%s' "$FLAT" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
EXEMPT_MERGE_RE='^gh pr merge[[:space:]]+([0-9]+)([[:space:]]+(--squash|--auto|--delete-branch))*$'
EXEMPT_PR_NUMBER=$(printf '%s' "$TRIMMED" | sed -nE "s/$EXEMPT_MERGE_RE/\1/p")
HOOK_CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null) || HOOK_CWD=""
HOOK_CWD=${HOOK_CWD:-${CLAUDE_PROJECT_DIR:-}}
IN_PROJECT=no
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -n "$HOOK_CWD" ]; then
  PROJECT_REAL=$(CDPATH='' cd "$CLAUDE_PROJECT_DIR" 2>/dev/null && pwd -P) || PROJECT_REAL=""
  CWD_REAL=$(CDPATH='' cd "$HOOK_CWD" 2>/dev/null && pwd -P) || CWD_REAL=""
  if [ -n "$PROJECT_REAL" ] && [ -n "$CWD_REAL" ]; then
    case "$CWD_REAL/" in "$PROJECT_REAL"/*) IN_PROJECT=yes ;; esac
  fi
fi

# Merge detection runs on the whole command with line continuations removed (as
# Bash does), then quotes, backslashes and $ removed and newlines joined, so
# quoting, continuations, redirections and command prefixes cannot hide a
# merge. It fails closed: a command that only mentions a merge is blocked too.
# Text matching cannot see through variables or eval; GitHub branch protection
# is the server-side backstop for those.
BACKSLASH_NEWLINE=$'\\\n'
JOINED=${COMMAND//"$BACKSLASH_NEWLINE"/}
UNQUOTED=$(printf '%s' "$JOINED" | tr -d "'\"\\\\\$" | tr '\n' ' ')

# PR merges through the API are blocked. The REST check spares one read form:
# a standalone `gh api <path>/pulls/<number>/merge` (a GET that reports whether
# the PR is merged) with at most --silent or -i/--include; a method flag, a
# field, shell syntax or any other token keeps it blocked. GraphQL names are
# case-sensitive, so read-only fields such as viewerCanEnablePullRequestAutoMerge
# do not match.
API_MERGE_READ_RE='^gh api[[:space:]]+[A-Za-z0-9_.{}/-]*pulls/[0-9]+/merge([[:space:]]+(--silent|-i|--include))*$'
if { printf '%s' "$UNQUOTED" | grep -qiE "pulls/[^[:space:]]*/merge" && \
     ! printf '%s' "$TRIMMED" | grep -qE "$API_MERGE_READ_RE"; } || \
   printf '%s' "$UNQUOTED" | grep -qE "(^|[^A-Za-z0-9_])(mergePullRequest|enablePullRequestAutoMerge)"; then
  echo "BLOCKED: merging a PR through the GitHub API is prohibited." >&2
  exit 2
fi

# gh pr merge anywhere in the command, except the exempt Dependabot merge
# above. Fails closed if the author cannot be confirmed. Each simple command
# is split into words (redirections and brace syntax also split), and a merge
# is a `gh` word followed later by `pr` and then exactly `merge`, so options
# or redirections between them (gh --repo x pr merge, gh > f pr merge) cannot
# hide it. Command separators start a new search, so `gh pr view && git merge
# origin/main` and `gh pr list --state merged` still pass.
is_gh_pr_merge() {
  printf '%s' "$JOINED" | tr -d "'\"\\\\\$" | tr ';&|()\140' '\n\n\n\n\n\n' | tr '<>{},' '     ' | awk '
    { s = 0
      for (i = 1; i <= NF; i++) {
        w = tolower($i)
        if (w == "gh" || w ~ /\/gh$/) { s = 1; continue }
        if (s == 1 && w == "pr") { s = 2; continue }
        if (s == 2 && w == "merge") { found = 1; exit }
      } }
    END { exit found ? 0 : 1 }'
}
if is_gh_pr_merge; then
  PR_AUTHOR=""
  if [ -n "$EXEMPT_PR_NUMBER" ] && [ "$IN_PROJECT" = "yes" ]; then
    PR_AUTHOR=$(CDPATH='' cd "$HOOK_CWD" && gh pr view "$EXEMPT_PR_NUMBER" --json author --jq '.author.login' 2>/dev/null) || PR_AUTHOR=""
  fi
  if [ "$PR_AUTHOR" != "app/dependabot" ]; then
    echo "BLOCKED: gh pr merge is prohibited. The pipeline stops at PR creation (only a standalone 'gh pr merge <number> [--squash] [--auto] [--delete-branch]' on a Dependabot PR, run from the project directory, is allowed)." >&2
    exit 2
  fi
fi

# Split into segments on && ; || and check each independently.
# This prevents "git merge origin/main" in one segment from suppressing
# detection of "git merge main" in another segment.
while IFS= read -r seg; do
  seg=$(echo "$seg" | sed 's/^[[:space:]]*//')
  [ -z "$seg" ] && continue

  # git merge main/master (but not origin/main)
  if echo "$seg" | grep -qiE "^git merge[[:space:]]+(main|master)" && \
     ! echo "$seg" | grep -qiE "^git merge[[:space:]]+origin/"; then
    echo "BLOCKED: git merge main/master is prohibited. Use 'git merge origin/main' for safe sync." >&2
    exit 2
  fi

  # git push --force / -f
  if echo "$seg" | grep -qiE "^git push[[:space:]].*--force|^git push[[:space:]]+-f"; then
    echo "BLOCKED: force push is prohibited." >&2
    exit 2
  fi

  # git push to main/master (with any flags before origin)
  if echo "$seg" | grep -qiE "^git push[[:space:]]+.*origin[[:space:]]+(main|master|HEAD:(main|master))"; then
    echo "BLOCKED: push to main/master is prohibited." >&2
    exit 2
  fi

  # gh pr review --approve
  if echo "$seg" | grep -qiE "^gh pr review[[:space:]]+--approve"; then
    echo "BLOCKED: PR auto-approve is prohibited." >&2
    exit 2
  fi

done <<< "$(echo "$FLAT" | tr ';&' '\n' | sed 's/|/\n/g')"

exit 0
