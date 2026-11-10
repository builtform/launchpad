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

# grep_status <grep flags> <ERE> <text> prints 0 (match), 1 (no match) or 2
# (error). grep reads all of its input (no -q), so an early exit can never
# raise SIGPIPE upstream and turn a match into a miss under pipefail. Block
# checks treat anything but 1 as a match, so they fail closed.
grep_status() {
  local rc=0
  printf '%s' "$3" | grep "$1" -- "$2" >/dev/null || rc=$?
  echo "$rc"
}

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
if { [ "$(grep_status -iE "pulls/[^[:space:]]*/merge" "$UNQUOTED")" != 1 ] && \
     [ "$(grep_status -E "$API_MERGE_READ_RE" "$TRIMMED")" != 0 ]; } || \
   [ "$(grep_status -E "(^|[^A-Za-z0-9_])(mergePullRequest|enablePullRequestAutoMerge)" "$UNQUOTED")" != 1 ]; then
  echo "BLOCKED: merging a PR through the GitHub API is prohibited." >&2
  exit 2
fi

# gh pr merge anywhere in the command, except the exempt Dependabot merge
# above. Fails closed if the author cannot be confirmed. Each simple command
# is split into words (redirections and brace syntax also split). After a `gh`
# word and a later `pr` word, the first word that is not an option (skipping
# -R/--repo and its value) is the subcommand, and anything outside a list of
# known non-merge subcommands counts as a merge. Options or redirections
# between words (gh --repo x pr merge, gh 2>&1 pr merge) and leftovers of
# quoting or expansion in the subcommand (merge$'\0', merg?, mer{g,}e) cannot
# hide it. Redirections that contain & or | (2>&1, <&0, &>, >|) are folded
# into a plain > first, so only real separators (; & && | || parentheses,
# backticks) start a new search; `gh pr view && git merge origin/main` and
# `gh pr list --state merged` still pass. awk reads all input and prints a
# verdict, and any pipeline failure counts as a merge. A `gh` or `pr` word
# that is itself encoded or computed (escapes, variables, eval) is out of
# reach of any text check; branch protection is the backstop.
GH_PR_MERGE=$(printf '%s' "$JOINED" | tr -d "'\"\\\\\$" | sed -e 's/>|/>/g' -e 's/[<>]&/>/g' -e 's/&>/>/g' | tr ';&|()\140' '\n\n\n\n\n\n' | tr '<>{},' '     ' | awk '
  BEGIN {
    n = split("checkout checks close comment create diff edit list ls lock new ready reopen review revert status unlock update-branch view", a, " ")
    for (k = 1; k <= n; k++) safe[a[k]] = 1
  }
  { s = 0; skip = 0
    for (i = 1; i <= NF; i++) {
      w = tolower($i)
      if (s < 2) {
        if (w == "gh" || w ~ /\/gh$/) s = 1
        else if (s == 1 && w == "pr") s = 2
        continue
      }
      if (skip) { skip = 0; continue }
      if (w == "-r" || w == "--repo") { skip = 1; continue }
      if (w ~ /^-/) continue
      if (!(w in safe)) found = 1
      s = 0
    } }
  END { print (found ? "yes" : "no") }') || GH_PR_MERGE=yes

# A second, quote-aware scan builds words the way Bash does (single, double and
# $'...' quoting keep a word whole, so `gh pr -R "x view" merge` is read
# right) and fails closed on what it cannot resolve: a redirection, command
# substitution or computed word between `gh` and the subcommand (gh pr >view
# merge, gh pr $(echo merge)). The first scan still catches merges hidden in
# quoted command substitutions; a merge found by either scan counts.
if [ "$GH_PR_MERGE" = "no" ]; then
  GH_PR_MERGE=$(printf '%s' "$JOINED" | awk '
    BEGIN {
      n = split("checkout checks close comment create diff edit list ls lock new ready reopen review revert status unlock update-branch view", a, " ")
      for (k = 1; k <= n; k++) safe[a[k]] = 1
    }
    function word(x,   lx) {
      lx = tolower(x)
      if (s == 1 && (index(x, "$(") || index(x, "`"))) { found = 1; return }
      if (s < 2) {
        if (lx == "gh" || lx ~ /\/gh$/) s = 1
        else if (s == 1 && lx == "pr") s = 2
        return
      }
      if (s == 2) {
        if (skip) { skip = 0; return }
        if (lx == "-r" || lx == "--repo") { skip = 1; return }
        if (lx ~ /^-/) return
        if (!(lx in safe)) found = 1
        s = 3
      }
    }
    function flush() { if (inw) { word(w); w = ""; inw = 0 } }
    { buf = buf $0 "\n" }
    END {
      L = length(buf); q = 0; w = ""; inw = 0; s = 0; skip = 0
      for (i = 1; i <= L; i++) {
        c = substr(buf, i, 1); nx = substr(buf, i + 1, 1)
        if (q == 1) { if (c == "\047") q = 0; else w = w c; continue }
        if (q == 3) { if (c == "\\") { w = w c nx; i++ } else if (c == "\047") q = 0; else w = w c; continue }
        if (q == 2) { if (c == "\\") { w = w nx; i++ } else if (c == "\"") q = 0; else w = w c; continue }
        if (c == "\\") { w = w nx; i++; inw = 1; continue }
        if (c == "\047") { q = 1; inw = 1; continue }
        if (c == "\"") { q = 2; inw = 1; continue }
        if (c == "$" && nx == "\047") { q = 3; inw = 1; i++; continue }
        if (c == "$" && nx == "\"") { q = 2; inw = 1; i++; continue }
        if (c == "#" && !inw) { while (i < L && substr(buf, i + 1, 1) != "\n") i++; continue }
        if (c == " " || c == "\t") { flush(); continue }
        if (c == "<" || c == ">" || (c == "&" && nx == ">")) {
          if (inw && w ~ /^[0-9]+$/) { w = ""; inw = 0 } else flush()
          while (i < L && index("<>&|-", substr(buf, i + 1, 1))) i++
          if (s == 1 || s == 2) found = 1
          continue
        }
        if (index(";&|()`\n", c)) {
          flush()
          if ((c == "(" || c == "`") && (s == 1 || s == 2)) found = 1
          s = 0; skip = 0
          continue
        }
        w = w c; inw = 1
      }
      flush()
      print (found ? "yes" : "no")
    }') || GH_PR_MERGE=yes
fi
if [ "$GH_PR_MERGE" != "no" ]; then
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
  if [ "$(grep_status -iE "^git merge[[:space:]]+(main|master)" "$seg")" != 1 ] && \
     [ "$(grep_status -iE "^git merge[[:space:]]+origin/" "$seg")" != 0 ]; then
    echo "BLOCKED: git merge main/master is prohibited. Use 'git merge origin/main' for safe sync." >&2
    exit 2
  fi

  # git push --force / -f
  if [ "$(grep_status -iE "^git push[[:space:]].*--force|^git push[[:space:]]+-f" "$seg")" != 1 ]; then
    echo "BLOCKED: force push is prohibited." >&2
    exit 2
  fi

  # git push to main/master (with any flags before origin)
  if [ "$(grep_status -iE "^git push[[:space:]]+.*origin[[:space:]]+(main|master|HEAD:(main|master))" "$seg")" != 1 ]; then
    echo "BLOCKED: push to main/master is prohibited." >&2
    exit 2
  fi

  # gh pr review --approve
  if [ "$(grep_status -iE "^gh pr review[[:space:]]+--approve" "$seg")" != 1 ]; then
    echo "BLOCKED: PR auto-approve is prohibited." >&2
    exit 2
  fi

done <<< "$(echo "$FLAT" | tr ';&' '\n' | sed 's/|/\n/g')"

exit 0
