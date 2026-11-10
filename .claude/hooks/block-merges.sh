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

# Surrounding whitespace, including blank lines, never changes what runs, so it
# is trimmed before the exact-match exceptions below.
CMD_TRIM="${COMMAND#"${COMMAND%%[![:space:]]*}"}"
CMD_TRIM="${CMD_TRIM%"${CMD_TRIM##*[![:space:]]}"}"

# Normalize: convert newlines to ;; (treating each line as a separate command)
# then flatten to single line for boundary matching.
FLAT=$(printf '%s' "$CMD_TRIM" | tr '\n' ';')

# Dependabot merge exception. The exempt merge must be the whole command, so
# nothing else in it can change the directory, environment or repository the
# merge runs against, and it must run from inside the project directory.
TRIMMED=$FLAT
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

# Line continuations are removed as Bash removes them. UNQUOTED additionally
# drops quotes, backslashes and $ and joins lines, for plain text checks that
# fail closed: a command that only mentions a merge is blocked too.
BACKSLASH_NEWLINE=$'\\\n'
JOINED=${COMMAND//"$BACKSLASH_NEWLINE"/}
UNQUOTED=$(printf '%s' "$JOINED" | tr -d "'\"\\\\\$" | tr '\n' ' ')

# Shell-aware scan of the command, run in two modes. Mode A builds words the
# way Bash does: single, double and $'...' quoting keep a word whole, $'...'
# escapes are decoded (and cut at \0, as Bash does), command and process
# substitutions are scanned as commands even inside double quotes, and the
# command strings of `sh/bash/zsh/dash/ksh -c` and `eval` are scanned again.
# Mode B treats quote characters as absent, so code inside any quoted string is
# scanned too. In both modes a redirection is an operator plus exactly one
# target word (`-`, a digit, a file or a process substitution), so neither its
# fd nor its target is mistaken for a gh word.
#
# For gh: the first non-option word after a `gh` word (skipping -R/--repo and
# its value) must be `pr` or tracking stops; after `pr`, the next non-option
# word is the subcommand, and anything outside the known non-merge subcommands
# counts as a merge. A computed word (a variable or substitution) in place of
# `pr` or the subcommand fails closed, and a computed command word followed by
# `pr` is treated as gh. Each scan prints four flags: a gh pr merge, a REST
# pulls/<n>/merge path (after %-decoding), a GraphQL merge mutation, and a
# GraphQL request whose body the hook cannot read (a file, stdin or a
# substitution). Out of reach of any text check: gh assembled from pieces at
# run time (eval of variables, base64 and the like), aliases, and other
# languages; branch protection is the backstop.
SCAN_AWK=""
IFS= read -r -d '' SCAN_AWK <<'AWK' || true
BEGIN {
  n = split("checkout checks close comment create diff edit list ls lock new ready reopen review revert status unlock update-branch view", a, " ")
  for (k = 1; k <= n; k++) safe[a[k]] = 1
  n = split("sudo env command exec nohup time timeout nice xargs builtin", a, " ")
  for (k = 1; k <= n; k++) prefix[a[k]] = 1
  n = split("sh bash zsh dash ksh", a, " ")
  for (k = 1; k <= n; k++) shell[a[k]] = 1
  n = split("curl wget http https xh", a, " ")
  for (k = 1; k <= n; k++) api[a[k]] = 1
  n = split("if then else elif do while until ! { ( time coproc", a, " ")
  for (k = 1; k <= n; k++) reserved[a[k]] = 1
  Qn = 1
  begin_scan()
}
# Lines are fed as they arrive and runs of ordinary characters are consumed in
# one step, so the scan stays linear in the size of the command.
{ feed($0 "\n") }
function hexval(h,   v, j) {
  v = 0
  for (j = 1; j <= length(h); j++) v = v * 16 + index("0123456789abcdef", substr(h, j, 1)) - 1
  return v
}
function chr(v) { return (v > 0 && v < 256) ? sprintf("%c", v) : "?" }
function pdec(s,   n, parts, out, j, h) {
  if (index(s, "%") == 0) return s
  n = split(s, parts, "%")
  if (n > 4096) { rest = 1; return s }
  out = parts[1]
  for (j = 2; j <= n; j++) {
    h = tolower(substr(parts[j], 1, 2))
    if (h ~ /^[0-9a-f][0-9a-f]$/) out = out chr(hexval(h)) substr(parts[j], 3)
    else out = out "%" parts[j]
  }
  return out
}
function base(x,   n, parts) { n = split(x, parts, "/"); return parts[n] }
# JSON request bodies may spell names with \uXXXX escapes.
function jdec(s,   n, parts, out, j, h) {
  if (index(s, "\\u") == 0) return s
  n = split(s, parts, "\\\\u")
  if (n > 4096) { mut = 1; return s }
  out = parts[1]
  for (j = 2; j <= n; j++) {
    h = tolower(substr(parts[j], 1, 4))
    if (h ~ /^[0-9a-f][0-9a-f][0-9a-f][0-9a-f]$/) out = out chr(hexval(h)) substr(parts[j], 5)
    else out = out "\\u" parts[j]
  }
  return out
}
# A short-option cluster that reaches -K (config) or -T (upload) reads a file,
# attached value or not (-K f, -Kf, -sSKf, -K-); letters that take a value end
# the cluster (-XPOST).
function shortfile(x,   j, c) {
  if (x !~ /^-[^-]/) return 0
  for (j = 2; j <= length(x); j++) {
    c = substr(x, j, 1)
    if (c == "K" || c == "T") return 1
    if (index("AbcCdDeEFHmoPQrtuUwxXyYz", c) || c !~ /[A-Za-z0-9#:]/) return 0
  }
  return 0
}
function enqueue(s) {
  if (Qn >= 64) found = 1
  else { Qn++; QT[Qn] = s }
}
# An API call (gh api, or curl, wget, http or xh as the command being run) is
# judged per simple command. Its body is hidden when it comes from a file or
# stdin (--input, -T, --upload-file, --post-file, --body-file, @ arguments and
# fields, and for http and xh, which send stdin as the body, stdin fed by < or
# a pipe) or from an expanded variable or substitution (a literal $ inside
# single quotes does not count). Its destination is hidden when the gh api
# endpoint or a curl-family URL is computed. Blocked: a GraphQL call with a
# hidden body; a hidden destination with a hidden body or any write (a write
# method, data or field options, an HTTP method word), since it may name the
# GraphQL or merge endpoint; and a curl config file, which can set both.
function newcmd(   hidden) {
  if (EV[d] != "") enqueue(EV[d])
  if (SCB[d] != "") enqueue(SCB[d])
  if (mode == "A" && AP[d]) {
    hidden = FB[d] || CX[d] > 0 || (HX[d] && (RI[d] || PI[d]))
    if ((GQ[d] && hidden) || (EX[d] && (hidden || MW[d])) || CF[d]) body = 1
  }
  S[d] = 0; SK[d] = 0; TG[d] = 0; NW[d] = 0; PV[d] = ""; EV[d] = ""; EVON[d] = 0; SH[d] = 0; GW[d] = 0
  GQ[d] = 0; FB[d] = 0; CX[d] = 0; AP[d] = 0; EX[d] = 0; RI[d] = 0; PI[d] = 0; HX[d] = 0
  SC[d] = 0; SCB[d] = ""; WR[d] = 0; GHA[d] = 0; CU[d] = 0; CN[d] = ""; MW[d] = 0; CF[d] = 0; PVO[d] = 0; HU[d] = 0; GOFF[d] = 0; EN[d] = 0; ES[d] = 0
}
# One argument of an API call, read by role. An option's value is consumed
# with its role (PVO): 1 harmless (a header, user, output file: an expansion in
# it does not count as a hidden body), 2 a method, 3 a URL, 5 a body, 6 a
# wget -e command, 7 a body whose name@file form reads a file, 8 a form field
# whose =@ or =< form reads a file. Writes, config files and URL files are
# noted, and a computed word that is not an option value is a possible
# destination.
function apiword(x, wc,   v, sep) {
  if (PVO[d]) {
    v = PVO[d]; PVO[d] = 0
    if (v == 1) { if (wc) CX[d]-- }
    else if (v == 2) { if (toupper(x) ~ /^(POST|PUT|PATCH|DELETE)$/) MW[d] = 1 }
    else if (v == 3) { if (wc) { EX[d] = 1; CX[d]-- } else if (x ~ /^@/) EX[d] = 1 }
    else if (v == 6) { if (tolower(x) ~ /(method|post|body|header|input)/) CF[d] = 1 }
    else if (v == 7) { if (index(x, "@")) FB[d] = 1 }
    else if (v == 8) { if (x ~ /=[@<]/) FB[d] = 1 }
    return
  }
  if (x ~ /^--./) { longopt(x, wc); return }
  if (x ~ /^-./) { cluster(x, wc); return }
  # http and xh: an optional method word, the URL, then request items. Data
  # items (=, :=, @, =@, :=@) imply a write and keep an expansion as a body;
  # the @ forms read a file. Headers (:) and query parameters (==) are harmless.
  if (CN[d] ~ /^(http|https|xh)$/) {
    if (!HU[d]) {
      if (x ~ /^[A-Z]+$/) { if (x ~ /^(POST|PUT|PATCH|DELETE)$/) MW[d] = 1; return }
      HU[d] = 1
      if (wc) { EX[d] = 1; CX[d]-- }
      return
    }
    if (match(x, /(==|:=@|:=|=@|=|:|@)/)) {
      sep = substr(x, RSTART, RLENGTH)
      if (sep == "==" || sep == ":") { if (wc) CX[d]--; return }
      MW[d] = 1
      if (index(sep, "@")) FB[d] = 1
      return
    }
    # A computed word that is not an item may be the real URL.
    if (wc) { EX[d] = 1; CX[d]-- }
    return
  }
  if (CU[d] && x ~ /^(POST|PUT|PATCH|DELETE)$/) { MW[d] = 1; return }
  # curl expands {a,b} and [1-9] in URLs unless -g/--globoff, so a globbed URL
  # may name a merge or GraphQL endpoint the text does not show.
  if (CN[d] == "curl" && !GOFF[d] && noipv6(x) ~ /[{[]/) { EX[d] = 1; if (wc) CX[d]--; return }
  if (wc) { EX[d] = 1; CX[d]-- }
}
function longopt(x, wc,   eq, o, val) {
  eq = index(x, "=")
  o = eq ? substr(x, 1, eq - 1) : x
  val = eq ? substr(x, eq + 1) : ""
  if (o == "--request" || o == "--method") {
    if (!eq) PVO[d] = 2
    else if (toupper(val) ~ /^(POST|PUT|PATCH|DELETE)$/) MW[d] = 1
    return
  }
  if (GHA[d]) {
    if (o ~ /^--(field|raw-field|input)$/) { MW[d] = 1; if (!eq) PVO[d] = 5; return }
    if (o ~ /^--(header|jq|template|hostname|preview|cache)$/) { if (!eq) PVO[d] = 1; else if (wc) CX[d]--; return }
    return
  }
  if (o == "--url") { if (!eq) PVO[d] = 3; else if (wc) { EX[d] = 1; CX[d]-- } else if (val ~ /^@/) EX[d] = 1; return }
  if (o == "--globoff") { GOFF[d] = 1; return }
  if (o == "--config") { CF[d] = 1; if (!eq) PVO[d] = 1; return }
  if (o == "--input-file") { EX[d] = 1; if (!eq) PVO[d] = 1; return }
  if (o == "--execute") { if (!eq) PVO[d] = 6; else if (tolower(val) ~ /(method|post|body|header|input)/) CF[d] = 1; return }
  if (o ~ /^--expand-/) { MW[d] = 1; FB[d] = 1; if (!eq) PVO[d] = 5; return }
  if (o == "--data-urlencode" || o == "--variable") {
    if (o != "--variable") MW[d] = 1
    if (!eq) PVO[d] = 7; else if (index(val, "@")) FB[d] = 1
    return
  }
  if (o == "--form" || o == "--form-string") { MW[d] = 1; if (!eq) PVO[d] = 8; else if (val ~ /=[@<]/) FB[d] = 1; return }
  if (o ~ /^--(data|data-raw|data-binary|data-ascii|json|post-data|body-data|post-file|body-file|upload-file)$/) { MW[d] = 1; if (!eq) PVO[d] = 5; return }
  if (o ~ /^--(header|user|user-agent|referer|cookie|cookie-jar|auth|output|output-document|output-file|proxy|proxy-user|dump-header|write-out|cert|cacert|key|max-time|connect-timeout|retry|timeout|tries|password|http-user|http-password)$/) {
    if (!eq) PVO[d] = 1; else if (wc) CX[d]--
    return
  }
  # http and xh options that take a value, so the value is not taken for the URL.
  if (CN[d] ~ /^(http|https|xh)$/) {
    if (o == "--raw") { MW[d] = 1; if (!eq) PVO[d] = 5; return }
    if (o ~ /^--(verify|auth-type|session|session-read-only|print|pretty|style|format-options|cert-key|cert-key-pass|max-redirects|max-headers|default-scheme|ssl|ciphers|boundary|response-charset|response-mime|history-print|bearer|http-version|resolve|interface|unix-socket)$/) {
      if (!eq) PVO[d] = 1; else if (wc) CX[d]--
      return
    }
  }
}
# An IPv6 host in brackets (http://[::1]:3000) is not curl glob syntax.
function noipv6(x) { gsub(/:\/\/\[[0-9A-Za-z.%_]*:[0-9A-Za-z:.%_]*\]/, "://h", x); return x }
# A short-option cluster walked letter by letter for the client: boolean
# letters continue, and the first letter that takes a value ends the cluster
# with the rest of the word, or the next word, as its value.
function cluster(x, wc,   j, n, c, rest) {
  n = length(x)
  for (j = 2; j <= n; j++) {
    c = substr(x, j, 1); rest = substr(x, j + 1)
    if (GHA[d]) {
      if (c == "X") { if (rest == "") PVO[d] = 2; else if (toupper(rest) ~ /^(POST|PUT|PATCH|DELETE)$/) MW[d] = 1; return }
      if (c == "f" || c == "F") { MW[d] = 1; if (rest == "") PVO[d] = 5; return }
      if (index("Hqtp", c)) { if (rest == "") PVO[d] = 1; else if (wc) CX[d]--; return }
    } else if (CN[d] == "wget") {
      if (c == "i") { EX[d] = 1; if (rest == "") PVO[d] = 1; return }
      if (c == "e") { if (rest == "") PVO[d] = 6; else if (tolower(rest) ~ /(method|post|body|header|input)/) CF[d] = 1; return }
      if (index("OoaBPUTtwQlARDXI", c)) { if (rest == "") PVO[d] = 1; else if (wc) CX[d]--; return }
    } else if (CN[d] == "curl") {
      if (c == "X") { if (rest == "") PVO[d] = 2; else if (toupper(rest) ~ /^(POST|PUT|PATCH|DELETE)$/) MW[d] = 1; return }
      if (c == "d" || c == "T") { MW[d] = 1; if (rest == "") PVO[d] = 5; return }
      if (c == "F") { MW[d] = 1; if (rest == "") PVO[d] = 8; else if (rest ~ /=[@<]/) FB[d] = 1; return }
      if (c == "K") { CF[d] = 1; if (rest == "") PVO[d] = 1; return }
      if (c == "g") GOFF[d] = 1
      if (index("AbcCDeEHmoPQrtuUwxyYz", c)) { if (rest == "") PVO[d] = 1; else if (wc) CX[d]--; return }
    } else {
      if (index("aoAps", c)) { if (rest == "") PVO[d] = 1; else if (wc) CX[d]--; return }
    }
  }
}
function word(x, wc,   lx, px, comp, cmdpos, bl, client) {
  px = pdec(x)
  if (tolower(px) ~ /pulls\/[^ \t\n]*\/merge/) rest = 1
  if (px ~ /(^|[^A-Za-z0-9_])(mergePullRequest|enablePullRequestAutoMerge|enqueuePullRequest)/) mut = 1
  if (jdec(px) ~ /(^|[^A-Za-z0-9_])(mergePullRequest|enablePullRequestAutoMerge|enqueuePullRequest)/) mut = 1
  if (tolower(px) ~ /(^|\/)graphql(\/|\?|#|\$|$)/) GQ[d] = 1
  if (x ~ /^@/ || x ~ /=@/ || x ~ /^-[A-Za-z]+@/ || x ~ /^--(input|upload-file|post-file|body-file|config)(=|$)/ || shortfile(x)) FB[d] = 1
  if (wc) CX[d]++
  if (TG[d]) { TG[d] = 0; return }
  lx = tolower(x)
  if (NW[d] == 0 && x ~ /^[A-Za-z_][A-Za-z0-9_]*=/) return
  NW[d]++
  cmdpos = (NW[d] == 1 || (PV[d] in prefix) || (PV[d] in reserved))
  # Every word after `<shell> -c` (options and -- included, each on its own
  # line) and the words after `eval` are scanned again as commands, whatever
  # wrapper (env, sudo, timeout, xargs) precedes them. An API client counts only
  # as the command being run: the first word, a word after a wrapper or a shell
  # keyword (if, while, !, then, do), or any word after a wrapper.
  if (mode == "A") {
    if (SC[d]) SCB[d] = SCB[d] "\n" x
    else if (SH[d] && lx ~ /^-[a-z]*c[a-z]*$/) SC[d] = 1
    if (EVON[d]) EV[d] = EV[d] " " x
    # env -S / --split-string runs a whole command held in one string.
    if (EN[d]) {
      if (ES[d]) { ES[d] = 0; enqueue(x) }
      else if (x ~ /^(-[A-Za-z0-9]*S|--split-string)$/) ES[d] = 1
      else if (x ~ /^-[A-Za-z0-9]*S./) enqueue(substr(x, index(x, "S") + 1))
      else if (x ~ /^--split-string=/) enqueue(substr(x, 16))
    }
    client = 0
    if (length(lx) < 256) {
      bl = base(lx)
      if (bl == "env" && (cmdpos || WR[d])) EN[d] = 1
      if (bl in shell) SH[d] = 1
      if ((cmdpos || WR[d]) && !AP[d] && (bl in api)) {
        AP[d] = 1; CU[d] = 1; CN[d] = bl; client = 1
        if (bl ~ /^(http|https|xh)$/) HX[d] = 1
      }
      if (cmdpos && (bl in prefix)) WR[d] = 1
    }
    if (lx == "eval") EVON[d] = 1
    if ((GHA[d] || CU[d]) && !client) apiword(x, wc)
    if (S[d] == 1 && lx == "api" && !AP[d]) { AP[d] = 1; GHA[d] = 1 }
  }
  PV[d] = lx
  comp = (index(x, "$") || index(x, "`"))
  if (S[d] == 0) {
    if (lx == "gh" || lx ~ /\/gh$/) { S[d] = 1; GW[d] = 1 }
    else if (comp && cmdpos) { S[d] = 1; GW[d] = 2 }
    return
  }
  if (S[d] == 3) return
  if (SK[d]) { SK[d] = 0; return }
  if (lx == "-r" || lx == "--repo") { SK[d] = 1; return }
  if (lx ~ /^-/) return
  if (S[d] == 1) {
    if (lx == "gh" || lx ~ /\/gh$/) { GW[d] = 1; return }
    if (comp) { if (GW[d] == 1) found = 1; else S[d] = 0; return }
    S[d] = (lx == "pr") ? 2 : 0
    return
  }
  if (comp || !(lx in safe)) found = 1
  S[d] = 3
}
function flush() { if (IW[d]) { word(W[d], WC[d]); W[d] = ""; IW[d] = 0; WC[d] = 0 } }
function push(closer) {
  W[d] = W[d] "$("; IW[d] = 1; WC[d] = 1
  QS[d] = q; d++
  W[d] = ""; IW[d] = 0; WC[d] = 0; CL[d] = closer; PD[d] = 0; EV[d] = ""; newcmd(); q = 0
}
function pop() {
  flush(); newcmd()
  d--; q = QS[d]; W[d] = W[d] ")"
}
function begin_scan() {
  d = 0; q = 0; W[0] = ""; IW[0] = 0; WC[0] = 0; CL[0] = ""; PD[0] = 0; EV[0] = ""; newcmd(); nul = 0
}
function end_scan() {
  while (d > 0) pop()
  flush(); newcmd()
}
function feed(t,   L, i, c, nx, e, h, o, mx, v, j) {
  L = length(t)
  for (i = 1; i <= L; i++) {
    c = substr(t, i, 1); nx = substr(t, i + 1, 1)
    if (mode == "B" && (c == "'" || c == "\"")) continue
    if (q == 1) {
      if (c == "'") { q = 0; continue }
      if (match(substr(t, i, 512), /^[^']+/)) { W[d] = W[d] substr(t, i, RLENGTH); i += RLENGTH - 1 }
      continue
    }
    if (q == 3) {
      if (c == "\\") {
        e = nx; i++; v = -1
        if (e == "x") {
          h = ""
          while (length(h) < 2 && tolower(substr(t, i + 1, 1)) ~ /^[0-9a-f]$/) { h = h tolower(substr(t, i + 1, 1)); i++ }
          v = (h == "") ? -1 : hexval(h)
        } else if (e == "u" || e == "U") {
          mx = (e == "u") ? 4 : 8; h = ""
          while (length(h) < mx && tolower(substr(t, i + 1, 1)) ~ /^[0-9a-f]$/) { h = h tolower(substr(t, i + 1, 1)); i++ }
          v = (h == "") ? -1 : hexval(h)
        } else if (e ~ /^[0-7]$/) {
          o = e
          while (length(o) < 3 && substr(t, i + 1, 1) ~ /^[0-7]$/) { o = o substr(t, i + 1, 1); i++ }
          v = 0
          for (j = 1; j <= length(o); j++) v = v * 8 + substr(o, j, 1)
        } else if (e == "c") { i++; v = 1 }
        else if (e == "n") v = 10
        else if (e == "t") v = 9
        else if (e == "r") v = 13
        else if (e == "a") v = 7
        else if (e == "b") v = 8
        else if (e == "e" || e == "E") v = 27
        else if (e == "f") v = 12
        else if (e == "v") v = 11
        else if (e == "\\" || e == "\047" || e == "\"" || e == "?") v = -2
        if (v == 0) nul = 1
        else if (!nul) W[d] = W[d] ((v == -2) ? e : ((v == -1) ? ("\\" e) : chr(v)))
        continue
      }
      if (c == "'") { q = 0; nul = 0; continue }
      if (match(substr(t, i, 512), /^[^'\\]+/)) { if (!nul) W[d] = W[d] substr(t, i, RLENGTH); i += RLENGTH - 1 }
      continue
    }
    if (q == 2) {
      if (c == "\\") { if (index("\"\\$`", nx)) { W[d] = W[d] nx; i++ } else W[d] = W[d] c; continue }
      if (c == "\"") { q = 0; continue }
      if (c == "$" && nx == "(") { push(")"); i++; continue }
      if (c == "`") { push("`"); continue }
      if (match(substr(t, i, 512), /^[^"\\$`]+/)) { W[d] = W[d] substr(t, i, RLENGTH); i += RLENGTH - 1 }
      else { W[d] = W[d] c; if (c == "$") WC[d] = 1 }
      continue
    }
    if (c == "\\") { W[d] = W[d] nx; i++; IW[d] = 1; continue }
    if (c == "'") { q = 1; IW[d] = 1; continue }
    if (c == "\"") { q = 2; IW[d] = 1; continue }
    if (mode == "A" && c == "$" && nx == "'") { q = 3; nul = 0; IW[d] = 1; i++; continue }
    if (mode == "A" && c == "$" && nx == "\"") { q = 2; IW[d] = 1; i++; continue }
    if (c == "$" && nx == "(") { push(")"); i++; continue }
    if (c == "`") { if (CL[d] == "`") pop(); else push("`"); continue }
    if (c == "#" && !IW[d]) { j = index(substr(t, i + 1), "\n"); i = j ? i + j - 1 : L; continue }
    if (c == " " || c == "\t") { flush(); continue }
    if ((c == "<" || c == ">") && nx == "(") { push(")"); i++; continue }
    if (c == "<" || c == ">" || (c == "&" && nx == ">")) {
      if (IW[d] && W[d] ~ /^[0-9]+$/) { W[d] = ""; IW[d] = 0 } else flush()
      if (c == "<") RI[d] = 1
      while (i < L && index("<>&|", substr(t, i + 1, 1))) i++
      TG[d] = 1
      continue
    }
    if (c == "|" && nx != "|" && substr(t, i - 1, 1) != "|") {
      flush(); newcmd(); PI[d] = 1
      if (nx == "&") i++
      continue
    }
    if (c == "(") { flush(); PD[d]++; newcmd(); continue }
    if (c == ")") {
      if (PD[d] > 0) { flush(); PD[d]--; newcmd() }
      else if (CL[d] == ")") pop()
      else { flush(); newcmd() }
      continue
    }
    if (index(";&|\n", c)) { flush(); newcmd(); continue }
    if (match(substr(t, i, 512), /^[^ \t\n\\'"$`#<>&;|()]+/)) { W[d] = W[d] substr(t, i, RLENGTH); IW[d] = 1; i += RLENGTH - 1; continue }
    W[d] = W[d] c; IW[d] = 1
    if (c == "$") WC[d] = 1
  }
}
END {
  end_scan()
  for (qi = 2; qi <= Qn; qi++) { begin_scan(); feed(QT[qi]); end_scan() }
  printf "%d %d %d %d\n", found, rest, mut, body
}
AWK

# A scan that fails or prints anything unexpected counts as finding everything.
scan_flags() {
  local out
  out=$(printf '%s' "$JOINED" | awk -v mode="$1" "$SCAN_AWK" 2>/dev/null) || out=""
  case "$out" in
    [01]\ [01]\ [01]\ [01]) echo "$out" ;;
    *) echo "1 1 1 1" ;;
  esac
}
read -r A_MERGE A_REST A_MUT A_BODY <<< "$(scan_flags A)"
read -r B_MERGE B_REST B_MUT B_BODY <<< "$(scan_flags B)"

# PR merges through the API are blocked. The REST check spares one read form:
# a standalone `gh api <path>/pulls/<number>/merge` (a GET that reports whether
# the PR is merged) with at most --silent or -i/--include; a method flag, a
# field, shell syntax or any other token keeps it blocked. GraphQL names are
# case-sensitive, so read-only fields such as viewerCanEnablePullRequestAutoMerge
# do not match.
API_MERGE_READ_RE='^gh api[[:space:]]+[A-Za-z0-9_.{}/-]*pulls/[0-9]+/merge([[:space:]]+(--silent|-i|--include))*$'
API_MUTATION_RE='(^|[^A-Za-z0-9_])(mergePullRequest|enablePullRequestAutoMerge|enqueuePullRequest)'
if { { [ "$A_REST" = 1 ] || [ "$B_REST" = 1 ] || [ "$(grep_status -iE "pulls/[^[:space:]]*/merge" "$UNQUOTED")" != 1 ]; } && \
     [ "$(grep_status -E "$API_MERGE_READ_RE" "$TRIMMED")" != 0 ]; } || \
   [ "$A_MUT" = 1 ] || [ "$B_MUT" = 1 ] || \
   [ "$(grep_status -E "$API_MUTATION_RE" "$UNQUOTED")" != 1 ]; then
  echo "BLOCKED: merging a PR through the GitHub API is prohibited." >&2
  exit 2
fi

# An API call (gh api, curl, wget, http, xh) whose GraphQL body or whose
# destination the hook cannot read could carry a merge (see the scan's newcmd),
# so it is blocked; write the endpoint, URL and query inline instead.
if [ "$A_BODY" = 1 ] || [ "$B_BODY" = 1 ]; then
  echo "BLOCKED: an API request whose GraphQL body or whose endpoint or URL the hook cannot read is prohibited; write the endpoint, URL and query inline." >&2
  exit 2
fi

# gh pr merge, found by either scan, except the exempt Dependabot merge above.
# Fails closed if the author cannot be confirmed.
if [ "$A_MERGE" = 1 ] || [ "$B_MERGE" = 1 ]; then
  PR_AUTHOR=""
  if [ -n "$EXEMPT_PR_NUMBER" ] && [ "$IN_PROJECT" = "yes" ]; then
    PR_AUTHOR=$(CDPATH='' cd "$HOOK_CWD" && gh pr view "$EXEMPT_PR_NUMBER" --json author --jq '.author.login' 2>/dev/null) || PR_AUTHOR=""
  fi
  if [ "$PR_AUTHOR" != "app/dependabot" ]; then
    echo "BLOCKED: gh pr merge is prohibited. The pipeline stops at PR creation (only a standalone 'gh pr merge <number> [--squash] [--auto] [--delete-branch]' on a Dependabot PR, run from the project directory, is allowed)." >&2
    exit 2
  fi
fi

# Split into segments on && ; || | and check each independently, in one awk
# pass (a per-segment loop of subprocesses took most of a minute on a few
# thousand lines). This prevents "git merge origin/main" in one segment from
# suppressing detection of "git merge main" in another segment. A failed or
# unexpected pass counts as every check matching.
SEG_FLAGS=$(printf '%s\n' "$FLAT" | tr ';&|' '\n\n\n' | awk '
  { sub(/^[[:space:]]+/, ""); s = tolower($0) }
  s ~ /^git merge[[:space:]]+(main|master)/ && s !~ /^git merge[[:space:]]+origin\// { gm = 1 }
  s ~ /^git push[[:space:]].*--force/ || s ~ /^git push[[:space:]]+-f/ { fp = 1 }
  s ~ /^git push[[:space:]]+.*origin[[:space:]]+(main|master|head:(main|master))/ { pm = 1 }
  s ~ /^gh pr review[[:space:]]+--approve/ { ap = 1 }
  END { printf "%d %d %d %d\n", gm, fp, pm, ap }' 2>/dev/null) || SEG_FLAGS=""
case "$SEG_FLAGS" in
  [01]\ [01]\ [01]\ [01]) ;;
  *) SEG_FLAGS="1 1 1 1" ;;
esac
read -r SEG_GIT_MERGE SEG_FORCE_PUSH SEG_PUSH_MAIN SEG_APPROVE <<< "$SEG_FLAGS"

# git merge main/master (but not origin/main)
if [ "$SEG_GIT_MERGE" = 1 ]; then
  echo "BLOCKED: git merge main/master is prohibited. Use 'git merge origin/main' for safe sync." >&2
  exit 2
fi

# git push --force / -f
if [ "$SEG_FORCE_PUSH" = 1 ]; then
  echo "BLOCKED: force push is prohibited." >&2
  exit 2
fi

# git push to main/master (with any flags before origin)
if [ "$SEG_PUSH_MAIN" = 1 ]; then
  echo "BLOCKED: push to main/master is prohibited." >&2
  exit 2
fi

# gh pr review --approve
if [ "$SEG_APPROVE" = 1 ]; then
  echo "BLOCKED: PR auto-approve is prohibited." >&2
  exit 2
fi

exit 0
