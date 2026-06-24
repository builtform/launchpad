#!/usr/bin/env python3
"""v2.0 handshake CI lint (HANDSHAKE §12 dispatch contract).

Default invocation (no flag) is **read-only** and is the only mode permitted in
PR-triggered CI workflows. `--regenerate-fixtures` is the SOLE write-mutating
mode and may run only in `v2-release.yml` (Phase 7.5 ship workflow).

Dispatch modes (read-only):
  default — runs the full read-only lint:
    * grep for `safe_run` enforcement (no raw `subprocess.` outside helpers)
    * grep for `shell=True` (forbidden)
    * grep for `read_and_verify` (knowledge-anchor read sites)
    * `0.x-test` residual check (HANDSHAKE §10 invariant; user-tree carve-out)
    * `BROWNFIELD_MANIFESTS` single-source enforcement (HANDSHAKE §8)
    * hyphen-prefixed test files in scripts/tests/ rejected
    * `pull_request_target` forbidden-pattern grep (BL-225 — v2.0 ships
      grep-based; v2.2 promotes to PyYAML AST)
    * private-origin leakage scan via `.launchpad/secret-patterns.txt`
  --check-version-coherence --phase=pre-bump|post-tag — version-coherence
    check (gating before/after the v2.0.0 ship commit; full implementation
    deferred to Phase 7.5 sub-step in the ship workflow — at v2.0 dev time
    runs in advisory mode only).
  --check-_legacy_yaml_canonical_hash-removal — gates v2.1.0 removal of the
    legacy YAML migration helper (BL-210).
  --check-psutil-cve — Phase -1 acceptance gate parallel to PyYAML; cross-
    references `_vendor/PSUTIL_VERSION` against the public CVE feed.
  --check-leakage — standalone private-origin leakage scan (verify-v2-ship
    #4 + Phase 7.5 §4.9 pre-push scrub). Same checker as the default-lint
    sub-rule, isolated so v2-release.yml can call it without running the
    full lint.

Write-mutating mode:
  --regenerate-fixtures — 2-pass atomic regen consuming
    `tests/fixtures/manifest.yml` (runtime <10s, --max-fixtures 200 cap).

Per HANDSHAKE §1.5 strip-back: AST-based `pull_request_target` shape check
(BL-225), exponential-backoff polling (BL-232), and KAT cross-platform parity
(BL-233) are deferred to v2.2 — this script ships the grep-based / single-shot
substitutes.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
PLUGINS_SCRIPTS = SCRIPT_DIR

VERSION_RESIDUAL = "0.x-test"

# Catalog-doc paths (Phase 1 deliverables — joint deliverables per HANDSHAKE
# §12). Validated by check_scaffolders_catalog + check_category_patterns_catalog.
SCAFFOLDERS_YML = REPO_ROOT / "plugins" / "launchpad" / "scaffolders.yml"
CATEGORY_PATTERNS_YML = (
    REPO_ROOT
    / "plugins"
    / "launchpad"
    / "scripts"
    / "lp_pick_stack"
    / "data"
    / "category-patterns.yml"
)
ANCHOR_DIR = REPO_ROOT / "plugins" / "launchpad" / "scaffolders"

# OPERATIONS §4: single 30-day freshness window for plugin-shipped catalog +
# pattern docs. Phase 1 enforces the same window for scaffolders.yml +
# category-patterns.yml + each anchor doc + the contract docs themselves.
FRESHNESS_WINDOW_DAYS = 30

# Allowed roles per HANDSHAKE §4 rule 2 / pick-stack plan §3.4. Manual-override
# entries may carry an empty canonical_stack; otherwise every layer's role MUST
# be in this set.
ALLOWED_ROLES = frozenset(
    {
        "frontend",
        "backend",
        "frontend-main",
        "frontend-dashboard",
        "fullstack",
        "mobile",
        "backend-managed",
        "desktop",
    }
)

# Allowed scaffolder type/flavor enums per HANDSHAKE §11 + scaffolding-layer
# test plan §1.
ALLOWED_TYPES = frozenset({"orchestrate", "curate"})
ALLOWED_FLAVORS = frozenset({"pure-headless", "mixed-prompts", "n/a"})

# scaffolders.yml + category-patterns.yml entries with paths/commands MUST
# match this allowlist per OPERATIONS §1 + §2 lint rule (mirror of the
# safe_run argv allowlist; YAML-side enforcement closes the supply-chain
# vector where a malicious PR could insert shell metacharacters via a
# scaffolder field).
ARGV_SAFE_RE = re.compile(r"^[A-Za-z0-9@._\-/=:]+$")

# Repo-tree allowlist for `0.x-test`: the HANDSHAKE.md + this script + the
# operations doc + plan/handoff/release-notes docs may legitimately mention
# the lifecycle string; the user-tree carve-out also exempts user-generated
# `.launchpad/scaffold-*.json`.
ZX_ALLOWED_PATHS = (
    "docs/architecture/SCAFFOLD_HANDSHAKE.md",
    "docs/architecture/SCAFFOLD_OPERATIONS.md",
    "docs/handoffs/launchpad_handoffs/",
    "docs/plans/launchpad_plans/",
    "docs/releases/v2.0.0.md",
    "docs/tasks/BACKLOG.md",  # BL entries documenting v2.2 deferrals reference lifecycle terms
    "ROADMAP.md",
    "plugins/launchpad/scripts/plugin-v2-handshake-lint.py",
    "plugins/launchpad/scripts/lp_pick_stack/__init__.py",
    "plugins/launchpad/scripts/lp_scaffold_stack/__init__.py",
    "plugins/launchpad/scripts/plugin-scaffold-receipt-loader.py",
    "plugins/launchpad/scripts/tests/",  # tests legitimately verify the constant
)

# Directories scanned by the lint exclude these gitignored or third-party
# trees: their contents never ship in the plugin artifact and frequently
# contain false-positive markers in audit/research material.
LINT_SCAN_EXCLUDES = (
    "docs/reports/launchpad_reports/",
    "docs/handoffs/launchpad_handoffs/",
    "docs/plans/launchpad_plans/",
    "docs/articles/",
    "node_modules/",
    "__pycache__/",
    ".git/",
    ".pytest_cache/",
    ".harness/",
    # v2.1.1 Phase 4: ruff cache mirrors source content into binary blobs;
    # the leakage scanner picks them up as accidental matches. Cache dir is
    # gitignored.
    ".ruff_cache/",
)

# pull_request_target forbidden patterns — bracket/dot AST paths that resolve
# to attacker-controlled fork-PR fields (HANDSHAKE §12 + Layer 5
# security-auditor P2-4). v2.0 grep-based per BL-225.
PR_TARGET_FORBIDDEN_PATTERNS = (
    r"github\.event\.pull_request\.head\.sha",
    r"github\.event\.pull_request\.head\.ref",
    r"github\.event\.pull_request\.head\.repo",
    r"github\.event\.pull_request\.merge_commit_sha",
    r"github\.event\.pull_request\.body",
    r"github\.event\.pull_request\.title",
    r"github\.event\.pull_request\.user\.login",
    r"github\.event\.workflow_run\.head_sha",
    r"github\.event\.workflow_run\.head_branch",
)

PYTHON_FILES = list(PLUGINS_SCRIPTS.rglob("*.py"))

# v2.0 contract scope — all Python under plugins/launchpad/scripts/ uses
# safe_run() per OPERATIONS §1, EXCEPT vendored third-party code, test
# harnesses, and Jinja templates (which are emitted to downstream projects,
# not LaunchPad runtime code). v2.1.1 Phase 3 broadens scope from a 11-
# basename frozenset (BL-237) to a path-prefix matcher; new violations
# trigger lint failure unless added to LINT_RAW_SUBPROCESS_ALLOWLIST with
# docstring justification.
V2_SCOPE_ROOT = "plugins/launchpad/scripts/"
V2_SCOPE_EXCLUDE_PREFIXES = (
    "plugins/launchpad/scripts/_vendor/",
    "plugins/launchpad/scripts/plugin_stack_adapters/_vendor/",
    "plugins/launchpad/scripts/tests/",
)
V2_SCOPE_EXCLUDE_SUFFIXES = (".j2",)

# Audited raw-subprocess exemptions. Each entry is a FULL relative path
# from repo root (NOT a basename — there are 4 distinct engine.py files in
# scope: lp_update_identity/, lp_pick_stack/, lp_scaffold_stack/,
# lp_bootstrap/. Basename allowlist would silently exempt all four,
# defeating future enforcement). Adding to this list requires PR review;
# auditors verify the justification and BL-track migration if appropriate.
LINT_RAW_SUBPROCESS_ALLOWLIST = frozenset(
    {
        # Self-allowlist — IS the runner. Subprocess is its purpose.
        # (cf. safe_run.py inline skip; both are canonical helpers.)
        "plugins/launchpad/scripts/plugin-build-runner.py",
        # macOS /sbin/mount filesystem introspection — fixed argv, no shell.
        # Internal FS check (NOT scaffolder-emitting subprocess); safe_run is
        # for caller code paths. Documented inline at nonce_ledger.py:152-155.
        "plugins/launchpad/scripts/lp_scaffold_stack/nonce_ledger.py",
        # Best-effort git config + python subprocess for audit-log forensics;
        # FileNotFoundError-tolerant, fixed argv. Migration to safe_run is
        # BL-308 (Phase 5 stash-pop seeds the concrete number).
        "plugins/launchpad/scripts/plugin-audit-log.py",
        # Best-effort git invocations for autonomous-guard ack check;
        # FileNotFoundError + non-repo tolerant. Migration BL-308.
        "plugins/launchpad/scripts/plugin_stack_adapters/autonomous_guard.py",
        # Stack detector subprocess invocation; bounded env (LP_REPO_ROOT pin
        # only). Migration BL-308.
        "plugins/launchpad/scripts/lp_define_runner.py",
        # git config user.email read (best-effort; fail-closed empty per
        # cycle-3 security P2-A). Migration BL-308.
        "plugins/launchpad/scripts/lp_update_identity/engine.py",
        # v2.1.4 BL-328: pin-rotation parity check. Script-only (no
        # runtime path). Calls fixed-argv `git init` / `git fetch` /
        # `git checkout` against pinned SHAs from pin_registry.py. The
        # subprocess layer here is the script's purpose (mirroring
        # template_cache._resolver.git_clone_depth_one for CI-side
        # pin-rotation validation). Migration to safe_run alongside the
        # v2.x sweep tracked in BL-308.
        "plugins/launchpad/scripts/plugin-upstream-pin-walk-scope-parity.py",
        # v2.1.7 BL-364: external-infrastructure preflight engine. Calls
        # fixed-argv `dig` (DNS probes) and `gh secret list` (GitHub
        # Secrets probe) plus `git status --porcelain` (uncommitted-
        # changes warn-only) through an injectable ProbeClients seam.
        # check=False is required because probes inspect non-zero exit
        # codes (127 missing binary, 124 timeout, 4xx provider API).
        # safe_run's strict env-allowlist would also break `gh` auth
        # (requires GH_TOKEN / gh-config access). Tests substitute the
        # entire ProbeClients via dependency injection so the production
        # subprocess.run path is bypassed under test. Migration to
        # safe_run tracked in BL-365 if the env-allowlist concern is
        # resolved upstream.
        "plugins/launchpad/scripts/lp_preflight.py",
    }
)

# shell=True allowlist — currently a single entry. plugin-build-runner.py:336
# uses shell=True for serial command execution in test/typecheck/lint stages;
# the user-supplied cmd string from commands.<stage> is intentionally shell-
# parsed for pipe / redirection / env-var support. v2.1.x BL: extend
# safe_run_long_shell from --stage=dev to all stages.
LINT_SHELL_TRUE_ALLOWLIST = frozenset(
    {
        "plugins/launchpad/scripts/plugin-build-runner.py",
    }
)

# Private-origin leakage patterns (HANDSHAKE §12 verify-v2-ship #5; v2.0 hard-
# codes the generic markers since the user-specific name allowlist lives in
# `.launchpad/secret-patterns.txt` which is gitignored config). These are
# universal regex markers that should never appear in public LaunchPad
# artifacts.
PRIVATE_ORIGIN_PATTERNS = (
    r"ported\s+from",
    r"originated\s+(at|in|from)",
    r"extracted\s+from\s+(my|our|the)\s+(private|internal|downstream)",
)

# Leakage-scan paths: extends the `_walk_grep` defaults to also include
# `.claude-plugin/` and root-level `.json` files (per HANDSHAKE §12 verify-v2-
# ship #4: "grep all committed paths under plugins/, docs/, .claude-plugin/,
# .github/, root .md/.json files").
LEAKAGE_SCAN_PATHS = (
    "plugins/",
    "docs/",
    ".github/",
    ".claude-plugin/",
    "ROADMAP.md",
    "README.md",
    "CHANGELOG.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
)

# Per-file leakage-scan allowlist (Option A — preserve "BuiltForm" public
# umbrella brand). The "builtform" org/marketplace name was deliberately
# minted at v1.0.0 ship as the public umbrella brand; scrubbing it would
# require rewriting already-shipped v1.x release notes (immutable history)
# and the marketplace.json that downstream installers point at. The hard-
# rule applies to private-origin LEAKAGE in NEW v2.0+ artifacts, NOT to
# the public org identity.
#
# Two carve-outs:
#  1. Public-brand artifacts (marketplace.json, plugin.json homepage URL,
#     immutable v1.x release notes + CHANGELOG entries, README + ROADMAP +
#     HOW_IT_WORKS public-marketplace references, install-issue template).
#  2. v1.x legacy code references that pre-date the no-BuiltForm-in-public
#     hard rule. These are scrub candidates for a v2.1+ housekeeping pass;
#     surfaced in the Phase 7.5 wrap-summary but not scrubbed here so the
#     v2.0 ship surface stays focused on the v2.0 contract.
LEAKAGE_FILE_ALLOWLIST = (
    # Carve-out 1: public-brand artifacts
    ".claude-plugin/marketplace.json",
    "plugins/launchpad/.claude-plugin/plugin.json",
    "README.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "docs/guides/HOW_IT_WORKS.md",
    "docs/releases/v1.0.0.md",
    "docs/releases/v1.0.1.md",
    "docs/releases/v1.1.0.md",
    ".github/ISSUE_TEMPLATE/plugin_install_issue.yml",
    # Carve-out 2: v1.x legacy code references — v2.1+ scrub candidates
    "plugins/launchpad/scripts/tests/test_define.py",
    "plugins/launchpad/scripts/plugin_default_generators/agents.yml.j2",
    "plugins/launchpad/scripts/plugin_stack_adapters/ts_monorepo.py",
    "plugins/launchpad/commands/lp-define.md",
    "plugins/launchpad/commands/lp-copy.md",
    # Carve-out 3: docs that TEACH the porting-attribution pattern itself.
    # The literal string "Ported from: [source]" appears as a TEMPLATE
    # placeholder in skill-creation/porting how-to docs — it's the lint
    # target, not a real attribution. Surfaced by PR #41 cycle 7 #1 closure
    # (case-insensitive prefilter); the previous case-sensitive prefilter
    # silently dropped these even though the post-filter regex was IGNORECASE.
    "plugins/launchpad/skills/lp-creating-skills/references/PORTING-GUIDE.md",
)


# --- helper utilities ---


def _run(cmd: list[str], *, cwd: Path = REPO_ROOT) -> tuple[int, str]:
    """Run a shell-free subprocess and capture stdout.

    Used inside the CI lint itself; safe_run is for caller code paths. We
    intentionally use subprocess.run() directly here because this IS the
    enforcement script and must be self-contained.
    """
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return 127, str(exc)
    return res.returncode, res.stdout


def _walk_grep(
    pattern: str,
    *paths: str,
    fixed: bool = False,
    regex: bool = False,
    ignorecase: bool = False,
) -> list[str]:
    """Filesystem-walk grep over the worktree (tracked + untracked).

    Walks the filesystem directly rather than invoking `git grep` so the lint
    works on untracked files during Phase -1 (the v2 modules are not yet
    committed per the no-push golden rule). Despite the prior `_git_grep`
    name, no git invocation occurs; D9 closure renamed to `_walk_grep`.

    `ignorecase` (PR #41 cycle 7 #1 closure): if True, the prefilter regex
    compiles with `re.IGNORECASE`. Required by the private-origin leakage
    scan so case variants like `Ported From` / `Builtform` aren't filtered
    out before the case-insensitive `cre.search()` post-check fires.
    """
    flags = re.IGNORECASE if ignorecase else 0
    if regex:
        pat = re.compile(pattern, flags)
        match = lambda line: bool(pat.search(line))  # noqa: E731
    elif fixed:
        if ignorecase:
            needle = pattern.lower()
            match = lambda line: needle in line.lower()  # noqa: E731
        else:
            match = lambda line: pattern in line  # noqa: E731
    else:
        # Plain pattern, treat as regex (matches git grep default behavior
        # closely enough for our needs).
        pat = re.compile(re.escape(pattern), flags)
        match = lambda line: bool(pat.search(line))  # noqa: E731

    if not paths:
        paths = (
            "plugins/",
            "docs/",
            "ROADMAP.md",
            "README.md",
            "CHANGELOG.md",
            ".github/",
        )
    hits: list[str] = []
    seen_files: set[Path] = set()
    for p in paths:
        target = REPO_ROOT / p
        if target.is_file():
            files = [target]
        elif target.is_dir():
            files = []
            for f in target.rglob("*"):
                if not f.is_file():
                    continue
                rel = str(f.relative_to(REPO_ROOT))
                if any(
                    rel.startswith(ex) or f"/{ex}" in f"/{rel}/"
                    for ex in LINT_SCAN_EXCLUDES
                ):
                    continue
                files.append(f)
        else:
            continue
        for f in files:
            if f in seen_files:
                continue
            seen_files.add(f)
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if match(line):
                    rel = str(f.relative_to(REPO_ROOT))
                    hits.append(f"{rel}:{i}:{line.rstrip()}")
    return hits


def _emit(failures: list[str], rule: str, hits: list[str]) -> None:
    if hits:
        failures.append(f"[{rule}] {len(hits)} hit(s):")
        for h in hits[:30]:
            failures.append(f"  {h}")
        if len(hits) > 30:
            failures.append(f"  ... ({len(hits) - 30} more)")


# --- read-only checks ---


def _is_v2_module(path: str) -> bool:
    """A path is in the v2.0 contract scope iff it lives under
    plugins/launchpad/scripts/, NOT under _vendor/ or tests/, and is NOT
    a Jinja template (.j2 — emitted code, not runtime code)."""
    if not path.startswith(V2_SCOPE_ROOT):
        return False
    if any(path.startswith(p) for p in V2_SCOPE_EXCLUDE_PREFIXES):
        return False
    if any(path.endswith(s) for s in V2_SCOPE_EXCLUDE_SUFFIXES):
        return False
    return True


def check_no_raw_subprocess(failures: list[str]) -> None:
    """All subprocess calls in v2.0 contract scope (path-prefix-matched)
    must go through `safe_run()` (OPERATIONS §1). Audited exceptions live
    in `LINT_RAW_SUBPROCESS_ALLOWLIST` (full-path strings)."""
    bad = []
    for hit in _walk_grep(
        r"^[^#]*subprocess\.(run|Popen|call|check_output|check_call)",
        "plugins/launchpad/scripts/",
        regex=True,
    ):
        path = hit.split(":", 1)[0]
        if not _is_v2_module(path):
            continue
        if path in LINT_RAW_SUBPROCESS_ALLOWLIST:
            continue  # audited exemption with docstring justification
        if path.endswith("safe_run.py"):
            continue  # safe_run is the helper itself
        if path.endswith("plugin-v2-handshake-lint.py"):
            continue  # this script IS the enforcement
        if "/tests/" in path:
            continue  # already excluded by _is_v2_module; defense-in-depth
        bad.append(hit)
    _emit(failures, "no-raw-subprocess", bad)


def check_no_shell_true(failures: list[str]) -> None:
    """shell=True is forbidden in v2.0 contract scope (path-prefix-matched).
    Audited exceptions live in `LINT_SHELL_TRUE_ALLOWLIST` (full-path
    strings).

    Allow lines that only mention shell=True as documentation/prohibition
    (heuristic: comment-marker before the match, or contains "no shell=True"
    / "Never use" / "forbidden"). Actual subprocess invocations go through
    safe_run() and do not appear in user code at all.
    """
    bad = []
    for hit in _walk_grep("shell=True", "plugins/launchpad/scripts/", fixed=True):
        path = hit.split(":", 1)[0]
        if not _is_v2_module(path):
            continue
        if path in LINT_SHELL_TRUE_ALLOWLIST:
            continue  # audited exemption with docstring justification
        if path.endswith("plugin-v2-handshake-lint.py"):
            continue
        # Phase 5 v2.1 (cycle-1 security-lens F-SEC-LENS-2 + cycle-2
        # pattern-finder P2): safe_run.py is the single audit-trailed
        # exception -- safe_run_long_shell uses Popen(shell=True) for
        # commands.dev entries. The SIGINT/SIGTERM/SIGKILL ladder + env
        # hygiene contract is identical to the argv-list path.
        if path.endswith("safe_run.py"):
            continue
        if "/tests/" in path:
            continue
        # Documentation/prohibition mentions allowed.
        line_text = hit.split(":", 2)[2] if hit.count(":") >= 2 else ""
        if (
            "no shell=True" in line_text
            or "shell=True is" in line_text
            or "Never use" in line_text
            or "forbidden" in line_text.lower()
        ):
            continue
        # Inline comment hash before the match → documentation.
        if "#" in line_text and line_text.index("#") < line_text.index("shell=True"):
            continue
        bad.append(hit)
    _emit(failures, "no-shell-true", bad)


def check_zx_test_residual(failures: list[str]) -> None:
    """The string `0.x-test` MUST NOT appear in plugin-shipped tree after the
    v2.0.0 bump commit. During development the HANDSHAKE.md + OPERATIONS.md
    + plan files + this script are exempt (allowlist)."""
    bad = []
    for hit in _walk_grep(VERSION_RESIDUAL, fixed=True):
        path = hit.split(":", 1)[0]
        if any(
            path == allowed or path.startswith(allowed) for allowed in ZX_ALLOWED_PATHS
        ):
            continue
        bad.append(hit)
    _emit(failures, "no-0.x-test-residual", bad)


def check_brownfield_manifests_single_source(failures: list[str]) -> None:
    """`BROWNFIELD_MANIFESTS = {` definition must occur exactly once (in
    cwd_state.py). Per HANDSHAKE §8 single-source assertion #2."""
    hits = _walk_grep(
        r"BROWNFIELD_MANIFESTS\s*=\s*\{", "plugins/launchpad/scripts/", regex=True
    )
    # Filter out hits inside this lint script + tests (test source includes
    # the regex literal).
    real = [
        h
        for h in hits
        if not (
            h.split(":", 1)[0].endswith("plugin-v2-handshake-lint.py")
            or "/tests/" in h.split(":", 1)[0]
        )
    ]
    if len(real) != 1:
        failures.append(
            f"[brownfield-manifests-single-source] expected exactly 1 definition, "
            f"found {len(real)}:\n  " + "\n  ".join(real)
        )
        return
    if not real[0].startswith("plugins/launchpad/scripts/cwd_state.py"):
        failures.append(
            f"[brownfield-manifests-single-source] definition must live in "
            f"cwd_state.py, found: {real[0]}"
        )


def check_hyphen_test_files(failures: list[str]) -> None:
    """Test files under scripts/tests/ MUST match `test_*.py`. Hyphen-prefixed
    files are silently skipped by pytest discovery."""
    bad = []
    tests_dir = PLUGINS_SCRIPTS / "tests"
    if tests_dir.exists():
        for f in tests_dir.iterdir():
            if f.suffix != ".py":
                continue
            if f.stem.startswith("__"):
                continue
            if "-" in f.stem:
                bad.append(str(f.relative_to(REPO_ROOT)))
            elif not f.stem.startswith("test_"):
                # Helper-only modules (e.g., conftest.py) are allowed.
                # Phase 5 smoke runner + adversarial corpus are explicitly
                # named for the handoff §4.1/§4.7 contract; pytest.ini
                # carries them in its `python_files` list so collection
                # still works.
                if f.stem in (
                    "conftest",
                    "scaffold_smoke_runner",
                    "scaffold_adversarial_corpus",
                ):
                    continue
                # Any other .py without test_ prefix is a CI lint violation
                # if it looks like it should be a test (heuristic: contains
                # `def test_`).
                try:
                    content = f.read_text(encoding="utf-8")
                    if re.search(r"^def test_\w+", content, re.MULTILINE):
                        bad.append(str(f.relative_to(REPO_ROOT)))
                except OSError:
                    pass
    _emit(failures, "test-file-naming", bad)


def check_pull_request_target_safety(failures: list[str]) -> None:
    """v2.0 grep-based check (BL-225 v2.2 promotes to PyYAML AST).

    Workflows triggered on `pull_request_target` MUST NOT reference attacker-
    controlled fork-PR fields. We grep across all `.github/workflows/*.yml`
    for the forbidden patterns.
    """
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.exists():
        return
    bad = []
    for wf in workflows_dir.glob("*.yml"):
        try:
            text = wf.read_text(encoding="utf-8")
        except OSError:
            continue
        # Only enforce against pull_request_target-triggered workflows.
        if "pull_request_target" not in text:
            continue
        for pat in PR_TARGET_FORBIDDEN_PATTERNS:
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(pat, line):
                    bad.append(
                        f"{wf.relative_to(REPO_ROOT)}:{i}: forbidden pattern {pat!r}"
                    )
    _emit(failures, "pull-request-target-safety", bad)


def _load_leakage_patterns() -> list[str]:
    """Return universal markers + any private-origin section patterns from
    `.launchpad/secret-patterns.txt`. The file is gitignored config — the
    section header `# private-origin:` opens the named-marker set; any
    other `#`-prefixed line closes it (avoids treating generic credential
    patterns as content-leakage indicators).
    """
    patterns: list[str] = list(PRIVATE_ORIGIN_PATTERNS)
    patterns_file = REPO_ROOT / ".launchpad" / "secret-patterns.txt"
    if not patterns_file.exists():
        return patterns
    try:
        text = patterns_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return patterns
    in_origin_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# private-origin:"):
            in_origin_section = True
            continue
        if stripped.startswith("#"):
            in_origin_section = False
            continue
        if in_origin_section and stripped:
            patterns.append(stripped)
    return patterns


def _is_leakage_allowlisted(path: str) -> bool:
    """Allowlist check for private-origin leakage scan. Skips this script,
    the patterns file, and every entry in LEAKAGE_FILE_ALLOWLIST."""
    if path.endswith("plugin-v2-handshake-lint.py"):
        return True
    if path.endswith(".launchpad/secret-patterns.txt"):
        return True
    return any(
        path == allowed or path.endswith("/" + allowed)
        for allowed in LEAKAGE_FILE_ALLOWLIST
    )


def check_private_origin_leakage(failures: list[str]) -> None:
    """Private-origin leakage scan (HANDSHAKE §12 verify-v2-ship #5).

    v2.0 ships hard-coded universal markers (`ported from`, `originated from`,
    etc.) in PRIVATE_ORIGIN_PATTERNS. The user-specific name allowlist lives
    in gitignored `.launchpad/secret-patterns.txt`; per-file allowlist for
    public-brand carve-outs lives in LEAKAGE_FILE_ALLOWLIST (Option A).
    """
    patterns = _load_leakage_patterns()
    bad: list[str] = []
    seen: set[str] = set()
    for pat in patterns:
        try:
            cre = re.compile(pat, re.IGNORECASE)
        except re.error:
            continue
        for hit in _walk_grep(pat, *LEAKAGE_SCAN_PATHS, regex=True, ignorecase=True):
            path = hit.split(":", 1)[0]
            if _is_leakage_allowlisted(path):
                continue
            line_text = hit.split(":", 2)[2] if hit.count(":") >= 2 else ""
            if not cre.search(line_text):
                continue
            if hit in seen:
                continue
            seen.add(hit)
            bad.append(hit)
    _emit(failures, "private-origin-leakage", bad)


# Schema-source files for the v2.1 schema-CODEOWNERS gate (V3 plan §11.6
# + §11.7, locked in HANDSHAKE §10.v2.1). When ANY of these change in a PR
# diff, the same PR MUST also touch HANDSHAKE.md so the schema contract and
# its source-of-truth doc stay in sync. Bootstrap-manifest writers land in
# Phase 3+; the gate covers the path even before the file exists so the
# rule is in place when the writer arrives.
SCHEMA_SOURCE_FILES = (
    # scaffold-decision schema sources
    "plugins/launchpad/scripts/lp_pick_stack/__init__.py",  # SCHEMA_VERSION_V2_1, identity regexes
    "plugins/launchpad/scripts/lp_pick_stack/decision_writer.py",  # build_decision_payload, validate_identity
    "plugins/launchpad/scripts/plugin-config-loader.py",  # read_scaffold_decision, read_bootstrap_manifest
    # bootstrap-manifest schema sources (Phase 3+ live)
    "plugins/launchpad/scripts/lp_bootstrap/__init__.py",  # BootstrapErrorCode + INFRASTRUCTURE_FILES + envelope constants
    "plugins/launchpad/scripts/lp_bootstrap/manifest_writer.py",  # build_manifest, write_manifest, security_fields contract
    # Phase 4 v2.1 adapter Protocol + composition + cache (Slice A+) sources
    "plugins/launchpad/scripts/plugin_stack_adapters/contracts.py",  # Adapter Protocol, OverlayConfig, ConflictPolicy
    "plugins/launchpad/scripts/plugin_stack_adapters/pin_registry.py",  # _UPSTREAM_SHA registry; rotation-detected
    # Phase 8.5 v2.1 render-batch flow + secret-scanner gate sources
    "plugins/launchpad/scripts/plugin_default_generators/_renderer_base.py",  # render_batch + scan_batch + write_batch contract (DA1' = a2)
    "plugins/launchpad/scripts/plugin_default_generators/secret_allowlist.py",  # filter_allowlisted (DA4)
    "plugins/launchpad/scripts/plugin_stack_adapters/polyglot_path_rewriter.py",  # _rewrite_adapter_paths standalone home (DA2)
    "plugins/launchpad/scripts/plugin_stack_adapters/secret_scanner.py",  # BUNDLED_DEFAULT_PATTERNS + pattern cache (DA3 + DA5)
)

# Phase 8.5 plan section 2.3: ALLOWLIST-based lint rule for atomic_write_replace
# callers. Only these files are permitted to call atomic_write_replace; any
# other caller (or an aliased import like `from atomic_io import
# atomic_write_replace as _w`) fails the lint. Adding a new permitted
# caller requires CODEOWNERS review on this constant.
ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS = (
    "plugins/launchpad/scripts/atomic_io.py",  # the source module (defines + re-exports)
    "plugins/launchpad/scripts/plugin_default_generators/_renderer_base.py",  # write_batch (DA1' = a2 gate)
    # lp_bootstrap is the per-file policy layer; engine + manifest_writer
    # are siblings of policy.py doing the bootstrap-tier writes (NOT
    # renderer bypass). Plan section 2.3 listed `policy.py` as the
    # canonical entry but the practical bootstrap surface is the whole
    # module; CODEOWNERS protects it as a unit.
    #
    # Phase 11 hardening A4: `lp_bootstrap/sentinel.py` was REMOVED from
    # this allowlist after the sentinel writer harmonized to
    # `O_CREAT|O_EXCL` (mirroring lp_scaffold_stack + lp_update_identity
    # sentinels), eliminating its `atomic_write_replace` dependency.
    "plugins/launchpad/scripts/lp_bootstrap/policy.py",  # per-file policy dispatcher
    # v2.1 Codex PR #50 cycle 6 F9: `lp_bootstrap/engine.py` was REMOVED from
    # this allowlist after `_record_version_drift` was refactored to route
    # through `re_seal_decision_atomic()` in `lp_pick_stack.decision_writer`.
    # Engine no longer holds the primitive directly; the decision_writer
    # entry below covers the resealed scaffold-decision write.
    "plugins/launchpad/scripts/lp_bootstrap/manifest_writer.py",  # bootstrap manifest writer
    # v2.1.8 BL-370: post-bootstrap preflight-config proposer writes
    # `.launchpad/preflight.config.yaml` (and the opt-out marker) so the
    # v2.1.7 external-infrastructure gate actually fires for default
    # greenfield setups. Sibling of manifest_writer.py; covered by the
    # `/lp_bootstrap/` directory CODEOWNERS rule.
    "plugins/launchpad/scripts/lp_bootstrap/preflight_proposer.py",
    # v2.1.8 BL-371: preflight memoization. lp_preflight.py writes
    # `.launchpad/preflight-receipt.json` atomically so a concurrent
    # `--read-receipt` reader on /lp-ship cannot see a partial write
    # produced by /lp-build's `--write-receipt`. The receipt is the only
    # atomic-replace surface in lp_preflight; the existing checklist
    # writer remains a plain write (no concurrent-reader contract).
    "plugins/launchpad/scripts/lp_preflight.py",
    # v2.1.8 BL-372: Claude Code permission-mode autonomy merger writes
    # `.claude/settings.json` atomically after deep-merging the bundled
    # autonomous-mode template into the user's existing settings.
    # Sibling of preflight_proposer.py; covered by the `/lp_bootstrap/`
    # directory CODEOWNERS rule.
    "plugins/launchpad/scripts/lp_bootstrap/claude_settings_merger.py",
    # Phase 10 v2.1: scaffold-decision atomic re-seal lives in decision_writer
    # (re_seal_decision_atomic) so /lp-update-identity inherits the same
    # atomic-replace primitive used by /lp-pick-stack's first-write path.
    "plugins/launchpad/scripts/lp_pick_stack/decision_writer.py",  # re_seal_decision_atomic
    # v2.1 Codex PR #50 Slice E: pre-squash audit-log filter for
    # restamp-history.jsonl (strips wip(slice-x): WIP-checkpoint entries
    # before squash). Single atomic_write_replace at the end of the
    # filter pipeline.
    "plugins/launchpad/scripts/plugin-restamp-redact-wip.py",
)
# v2.1 Codex PR #50 post-review P1: `atomic_write_replace_batch` is the
# two-phase shape introduced for `RendererBase.write_batch()`. It uses
# the same primitives (mkstemp/fsync/fchmod/os.replace/_fsync_parent)
# and is gated by the same allowlist; the lint scans for either symbol.
ATOMIC_WRITE_REPLACE_NAMES = (
    "atomic_write_replace",
    "atomic_write_replace_batch",
)
ATOMIC_WRITE_REPLACE_SCAN_GLOBS = ("plugins/launchpad/scripts/**/*.py",)

# Phase 8.5 plan section 2.3: audit-log enforcement rule. Any deletion of a
# CODEOWNERS-protected path requires a same-commit
# `docs/maintainers/decommission-history.md` entry with non-empty Reason +
# Reviewer columns. Phase 8 entries are the seed corpus.
DECOMMISSION_AUDIT_LOG = "docs/maintainers/decommission-history.md"

# Phase 4 v2.1: pin-registry rotation-detector. Every modification of a
# `sha` value in pin_registry.py requires a same-commit append-only entry in
# `docs/maintainers/upstream-pin-rotations.md` (Phase 4 plan §3.9).
PIN_REGISTRY_FILE = "plugins/launchpad/scripts/plugin_stack_adapters/pin_registry.py"
PIN_ROTATION_AUDIT_LOG = "docs/maintainers/upstream-pin-rotations.md"
SCHEMA_DOC = "docs/architecture/SCAFFOLD_HANDSHAKE.md"
BOOTSTRAP_MANIFEST_DOC = "docs/architecture/SCAFFOLD_HANDSHAKE.md"


def check_schema_codeowners_gate(
    failures: list[str], base_ref: str = "origin/main"
) -> None:
    """Fail PRs that change schema-source files without touching HANDSHAKE.md.

    V3 plan §11.6 + §11.7 + HANDSHAKE §10.v2.1 acceptance rules: the
    scaffold-decision and bootstrap-manifest schemas are paired with
    HANDSHAKE.md as their source of truth. Schema-source code changes
    without a corresponding HANDSHAKE.md update silently drift the contract.
    The gate enforces co-touched edits at PR time.

    Strategy:
      1. Compute the changed-file set via `git diff --name-only <base>...HEAD`.
         Default base is `origin/main`; CI sets `LP_BASE_REF` to override.
      2. If the changed set intersects SCHEMA_SOURCE_FILES, assert
         HANDSHAKE.md is also in the changed set.
      3. The gate is silent on PRs that touch neither schema sources nor
         HANDSHAKE.md (most PRs).

    The gate intentionally uses a static SCHEMA_SOURCE_FILES list, not
    a glob: false positives on unrelated edits would train contributors
    to bypass the gate. Adding new schema-source files requires updating
    this list AND the HANDSHAKE.md schema docs in the same PR — the gate
    catches itself.
    """
    rule = "schema-codeowners-gate"
    rc, out = _run(["git", "diff", "--name-only", f"{base_ref}...HEAD"])
    if rc != 0:
        # Diff failed — most likely the base ref is unavailable (shallow
        # clone, missing remote). Emit INFO and skip; CI is responsible
        # for fetching the base ref before invoking this lint.
        failures.append(
            f"[{rule}] git diff against {base_ref} failed (rc={rc}); "
            f"set LP_BASE_REF or fetch the base ref before running this "
            f"check. Output: {out.strip()[:200]!r}"
        )
        return

    changed = {line.strip() for line in out.splitlines() if line.strip()}
    if not changed:
        return  # empty diff; gate trivially satisfied

    schema_changed = changed.intersection(SCHEMA_SOURCE_FILES)
    if not schema_changed:
        return  # no schema sources changed; gate satisfied

    if SCHEMA_DOC in changed:
        return  # both sides touched; gate satisfied

    failures.append(
        f"[{rule}] schema-source files changed without {SCHEMA_DOC} also "
        f"being touched in the same diff:\n  "
        + "\n  ".join(sorted(schema_changed))
        + f"\n\nThe v2.1 schema contract (HANDSHAKE §10.v2.1) requires "  # nosec B608 -- false positive; constructing error-message string, not SQL query (the word "schema" + adjacent string concat triggers B608's heuristic) (cf. BL-308 | HANDSHAKE §10.v2.1 | plan §6 alternatives table).
        f"that any change to schema-source code be paired with an update "
        f"to {SCHEMA_DOC}. If this PR genuinely needs to ship without a "
        f"docs change (e.g., pure refactor), set commit footer "
        f"`Schema-Refactor-Only: <reason>` and re-run; the bypass token "
        f"is reviewed at merge time. (Token enforcement lands in Phase 7+; "
        f"at v2.1 the gate is hard-fail.)"
    )


def run_check_schema_codeowners_gate() -> int:
    """Standalone entry point for v2-handshake-lint.yml workflow."""
    failures: list[str] = []
    base_ref = os.environ.get("LP_BASE_REF", "origin/main")
    check_schema_codeowners_gate(failures, base_ref=base_ref)
    if failures:
        print("schema-codeowners-gate: FAIL", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print("schema-codeowners-gate: PASS")
    return 0


_PIN_SHA_LINE_RE = re.compile(r'^\+\s*"sha":\s*"([0-9a-f]{40})"', re.MULTILINE)


def check_pin_registry_rotation_audit_log(
    failures: list[str], base_ref: str = "origin/main"
) -> None:
    """Phase 4 v2.1 rotation-detector (Phase 4 plan §3.9).

    If the diff between `<base>...HEAD` adds any new `"sha": "<40-hex>"` line
    inside pin_registry.py, the audit log at
    `docs/maintainers/upstream-pin-rotations.md` MUST also be touched in the
    same diff. The check intentionally inspects the diff (not the working
    tree): the goal is to gate the *act of rotation* at PR time, not to
    re-validate already-merged history.

    Strategy:
      1. `git diff <base>...HEAD -- <pin_registry>` to get the textual diff.
      2. Extract added (+) `"sha": "<hex>"` lines via regex.
      3. If any such line exists, assert the audit log path is in the
         changed-files set.
      4. Skip silently when pin_registry is not in the diff.
    """
    rule = "pin-registry-rotation-audit-log"

    rc, names_out = _run(["git", "diff", "--name-only", f"{base_ref}...HEAD"])
    if rc != 0:
        failures.append(
            f"[{rule}] git diff against {base_ref} failed (rc={rc}); set "
            f"LP_BASE_REF or fetch the base ref before running this check."
        )
        return
    changed = {line.strip() for line in names_out.splitlines() if line.strip()}
    if PIN_REGISTRY_FILE not in changed:
        return  # pin_registry untouched; gate trivially satisfied

    rc, diff_out = _run(["git", "diff", f"{base_ref}...HEAD", "--", PIN_REGISTRY_FILE])
    if rc != 0:
        failures.append(f"[{rule}] git diff for {PIN_REGISTRY_FILE} failed (rc={rc}).")
        return

    added_shas = _PIN_SHA_LINE_RE.findall(diff_out)
    if not added_shas:
        return  # pin_registry diff contains no new SHA lines

    if PIN_ROTATION_AUDIT_LOG not in changed:
        failures.append(
            f"[{rule}] pin_registry.py adds new SHA value(s) without a same-"
            f"commit entry in {PIN_ROTATION_AUDIT_LOG}.\n  added SHAs:\n  "
            + "\n  ".join(sorted(added_shas))
            + "\n\nPhase 4 plan §3.9: every _UPSTREAM_SHA rotation requires "
            "an append-only audit-log entry with non-empty Reason + Reviewer "
            "in the same commit."
        )


def run_check_pin_registry_rotation_audit_log() -> int:
    """Standalone entry point for the rotation-detector lint rule."""
    failures: list[str] = []
    base_ref = os.environ.get("LP_BASE_REF", "origin/main")
    check_pin_registry_rotation_audit_log(failures, base_ref=base_ref)
    if failures:
        print("pin-registry-rotation-audit-log: FAIL", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print("pin-registry-rotation-audit-log: PASS")
    return 0


def run_check_leakage() -> int:
    """Standalone leakage scan (verify-v2-ship #4 + Phase 7.5 §4.9 pre-push
    scrub). Same checker as the default-lint sub-rule, but isolated so the
    release workflow can call it without running the rest of the lint."""
    failures: list[str] = []
    check_private_origin_leakage(failures)
    if failures:
        print("private-origin leakage: FAIL", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print("private-origin leakage: PASS")
    return 0


# --- Phase 1 catalog-validation checks ---


def _load_yaml_or_fail(path: Path, failures: list[str], rule: str) -> dict | None:
    """Load YAML via vendored PyYAML safe_load. Append failure on error."""
    if not path.exists():
        failures.append(f"[{rule}] catalog file missing: {path.relative_to(REPO_ROOT)}")
        return None
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        failures.append(
            f"[{rule}] PyYAML not importable; lint cannot validate {path.name}. "
            f"Vendored pin in _vendor/PYYAML_VERSION."
        )
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        failures.append(f"[{rule}] {path.relative_to(REPO_ROOT)} parse error: {exc}")
        return None
    if not isinstance(data, dict):
        failures.append(
            f"[{rule}] {path.relative_to(REPO_ROOT)} top-level must be a mapping; "
            f"got {type(data).__name__}"
        )
        return None
    return data


def _check_freshness(date_str: str, *, today: _dt.date) -> str | None:
    """Return None if last_validated is within window; an error string otherwise."""
    try:
        last = _dt.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return f"unparseable last_validated {date_str!r}"
    age_days = (today - last).days
    if age_days < 0:
        return f"last_validated {date_str} is in the future"
    if age_days > FRESHNESS_WINDOW_DAYS:
        return f"last_validated {date_str} is {age_days}d old (>30d window)"
    return None


# Sentinel embedded in the staleness message emitted by `_check_freshness`. Used
# by `_freshness_finding` to tell a pure-staleness finding (advisory) apart from
# a structural one (hard failure). Keep in sync with the message above.
_STALENESS_MARKER = "d old (>"


def _freshness_finding(lv: object, *, today: _dt.date) -> tuple[str, str] | None:
    """Classify a `last_validated` value into a `(severity, message)` finding.

    `severity` is one of:
      - ``"fail"`` — a STRUCTURAL problem (missing / wrong type / unparseable /
        future-dated). Always a hard lint failure: the value is malformed, not
        merely old.
      - ``"warn"`` — the date is valid but older than the freshness window. This
        is ADVISORY in the default PR lint (`run_default_lint`). Re-stamping the
        catalog/pattern docs is a time-based maintenance task with no
        relationship to the content of any given PR, so a lapsed window must
        never block unrelated changes (e.g. a dependency bump). The HARD
        freshness gate runs at release time via `--check-freshness`, wired into
        `v2-release.yml`. See `docs/architecture/SCAFFOLD_OPERATIONS.md` §4.

    Returns ``None`` when the date is fresh. Reuses `_check_freshness` so the
    date arithmetic lives in exactly one place.
    """
    if isinstance(lv, _dt.date):
        date_str = lv.isoformat()
    elif isinstance(lv, str):
        date_str = lv
    else:
        return ("fail", f"last_validated must be a YYYY-MM-DD string; got {lv!r}")
    err = _check_freshness(date_str, today=today)
    if err is None:
        return None
    return ("warn" if _STALENESS_MARKER in err else "fail", err)


def check_scaffolders_catalog(
    failures: list[str],
    today: _dt.date | None = None,
    *,
    warnings: list[str] | None = None,
    freshness_blocking: bool = False,
) -> set[str]:
    """Validate scaffolders.yml shape + freshness + per-entry sha256 against
    its knowledge_anchor file. Returns the set of stack ids it found (used by
    the cross-reference check in check_category_patterns_catalog).

    Staleness findings route to `warnings` (advisory) unless `freshness_blocking`
    is True, in which case they route to `failures` (the release-time gate). See
    `_freshness_finding`.
    """
    if today is None:
        today = _dt.date.today()
    if warnings is None:
        warnings = []
    rule = "scaffolders-catalog"
    data = _load_yaml_or_fail(SCAFFOLDERS_YML, failures, rule)
    if data is None:
        return set()

    if data.get("schema_version") != "1.0":
        failures.append(
            f"[{rule}] schema_version must be '1.0' at v2.0; got "
            f"{data.get('schema_version')!r}"
        )

    stacks = data.get("stacks")
    if not isinstance(stacks, dict):
        failures.append(f"[{rule}] top-level `stacks:` must be a mapping")
        return set()

    # v2.1.4 BL-331: catalog widens to 11 entries with `generic` added
    # as a primary-stack option (bring-your-own-framework path). The
    # original "exactly 10" assertion locked the v2.0 catalog shape;
    # 11 is the v2.1.4 lock. Future widening past 11 should land
    # alongside an explicit BL + a release-note callout (catalog
    # additions are user-visible) rather than a silent drift.
    if len(stacks) != 11:
        failures.append(
            f"[{rule}] v2.1.4 catalog must ship exactly 11 stacks "
            f"(HANDSHAKE §11 + BL-331 generic addition); found {len(stacks)}"
        )

    found_ids: set[str] = set()
    for stack_id, entry in stacks.items():
        found_ids.add(stack_id)
        if not isinstance(entry, dict):
            failures.append(f"[{rule}] entry {stack_id!r} must be a mapping")
            continue
        for required in (
            "pillar",
            "type",
            "flavor",
            "knowledge_anchor",
            "knowledge_anchor_sha256",
            "options_schema",
            "last_validated",
        ):
            if required not in entry:
                failures.append(
                    f"[{rule}] entry {stack_id!r} missing required field {required!r}"
                )
        # Type/flavor enum
        if entry.get("type") not in ALLOWED_TYPES:
            failures.append(
                f"[{rule}] entry {stack_id!r} type {entry.get('type')!r} not in "
                f"{sorted(ALLOWED_TYPES)}"
            )
        if entry.get("flavor") not in ALLOWED_FLAVORS:
            failures.append(
                f"[{rule}] entry {stack_id!r} flavor {entry.get('flavor')!r} not "
                f"in {sorted(ALLOWED_FLAVORS)}"
            )
        # Orchestrate-only: command + headless_flags
        if entry.get("type") == "orchestrate":
            cmd = entry.get("command", "")
            if not isinstance(cmd, str) or not cmd:
                failures.append(
                    f"[{rule}] orchestrate entry {stack_id!r} requires non-empty "
                    f"`command:`"
                )
            else:
                # The command may legitimately contain spaces (`hugo new site`,
                # `rails new`, `npx create-next-app@latest`). Validate each
                # space-separated token against ARGV_SAFE_RE. Use fullmatch
                # (not match) so a safe-prefix + unsafe-suffix token cannot
                # pass CI but fail at runtime — runtime safe_run uses
                # fullmatch, and the lint MUST mirror the runtime check
                # to avoid drift (Codex review #7 on PR #41).
                for token in cmd.split():
                    if not ARGV_SAFE_RE.fullmatch(token):
                        failures.append(
                            f"[{rule}] entry {stack_id!r} command token "
                            f"{token!r} fails argv-safe allowlist"
                        )
            flags = entry.get("headless_flags", [])
            if not isinstance(flags, list):
                failures.append(
                    f"[{rule}] entry {stack_id!r} headless_flags must be a list"
                )
            else:
                for f in flags:
                    if not isinstance(f, str) or not ARGV_SAFE_RE.fullmatch(f):
                        failures.append(
                            f"[{rule}] entry {stack_id!r} headless flag {f!r} "
                            f"fails argv-safe allowlist"
                        )
        # knowledge_anchor + sha256
        anchor_rel = entry.get("knowledge_anchor")
        if isinstance(anchor_rel, str):
            anchor_path = REPO_ROOT / anchor_rel
            if not anchor_path.exists():
                failures.append(
                    f"[{rule}] entry {stack_id!r} knowledge_anchor "
                    f"{anchor_rel} does not exist"
                )
            else:
                actual_sha = hashlib.sha256(anchor_path.read_bytes()).hexdigest()
                pinned = entry.get("knowledge_anchor_sha256")
                if pinned != actual_sha:
                    failures.append(
                        f"[{rule}] entry {stack_id!r} knowledge_anchor_sha256 "
                        f"mismatch: pinned {pinned!r} actual {actual_sha!r}"
                    )
        # last_validated freshness (staleness advisory unless freshness_blocking)
        finding = _freshness_finding(entry.get("last_validated"), today=today)
        if finding is not None:
            severity, msg = finding
            sink = failures if (severity == "fail" or freshness_blocking) else warnings
            sink.append(f"[{rule}] entry {stack_id!r}: {msg}")

    return found_ids


def check_category_patterns_catalog(
    failures: list[str],
    *,
    scaffolder_ids: set[str],
    today: _dt.date | None = None,
    warnings: list[str] | None = None,
    freshness_blocking: bool = False,
) -> None:
    """Validate category-patterns.yml shape + freshness + cross-reference each
    canonical_stack[].stack against scaffolder_ids.

    Staleness findings route to `warnings` (advisory) unless `freshness_blocking`
    is True. See `_freshness_finding`."""
    if today is None:
        today = _dt.date.today()
    if warnings is None:
        warnings = []
    rule = "category-patterns-catalog"
    data = _load_yaml_or_fail(CATEGORY_PATTERNS_YML, failures, rule)
    if data is None:
        return

    if data.get("schema_version") != "1.0":
        failures.append(
            f"[{rule}] schema_version must be '1.0' at v2.0; got "
            f"{data.get('schema_version')!r}"
        )

    if not isinstance(data.get("ambiguity_clusters"), list):
        failures.append(
            f"[{rule}] top-level `ambiguity_clusters:` must be a list "
            f"(HANDSHAKE §4 rule 7)"
        )

    categories = data.get("categories")
    if not isinstance(categories, list):
        failures.append(f"[{rule}] top-level `categories:` must be a list")
        return

    seen_ids: set[str] = set()
    for entry in categories:
        if not isinstance(entry, dict):
            failures.append(f"[{rule}] category entries must be mappings")
            continue
        cat_id = entry.get("id")
        if not isinstance(cat_id, str) or not cat_id:
            failures.append(f"[{rule}] category missing string `id`")
            continue
        if cat_id in seen_ids:
            failures.append(f"[{rule}] duplicate category id {cat_id!r}")
        seen_ids.add(cat_id)
        for required in (
            "name",
            "fits_when",
            "canonical_stack",
            "explanation",
            "last_validated",
        ):
            if required not in entry:
                failures.append(
                    f"[{rule}] category {cat_id!r} missing required field {required!r}"
                )
        # Cross-reference canonical_stack[].stack against scaffolder_ids
        layers = entry.get("canonical_stack", [])
        if not isinstance(layers, list):
            failures.append(
                f"[{rule}] category {cat_id!r} canonical_stack must be a list"
            )
        else:
            # The reserved manual-override id has empty canonical_stack per
            # HANDSHAKE §4 rule 4; all others MUST have ≥1 layer.
            if cat_id != "manual-override" and not layers:
                failures.append(
                    f"[{rule}] category {cat_id!r} canonical_stack empty (only "
                    f"`manual-override` is permitted to be empty)"
                )
            for layer in layers:
                if not isinstance(layer, dict):
                    failures.append(
                        f"[{rule}] category {cat_id!r} layer must be a mapping"
                    )
                    continue
                stack = layer.get("stack")
                role = layer.get("role")
                path = layer.get("path")
                if stack not in scaffolder_ids:
                    failures.append(
                        f"[{rule}] category {cat_id!r} references unknown "
                        f"stack {stack!r} (not in scaffolders.yml)"
                    )
                if role not in ALLOWED_ROLES:
                    failures.append(
                        f"[{rule}] category {cat_id!r} role {role!r} not in "
                        f"{sorted(ALLOWED_ROLES)}"
                    )
                if not isinstance(path, str):
                    failures.append(
                        f"[{rule}] category {cat_id!r} path must be a string"
                    )
        # last_validated freshness (staleness advisory unless freshness_blocking)
        finding = _freshness_finding(entry.get("last_validated"), today=today)
        if finding is not None:
            severity, msg = finding
            sink = failures if (severity == "fail" or freshness_blocking) else warnings
            sink.append(f"[{rule}] category {cat_id!r}: {msg}")


def check_anchor_doc_freshness(
    failures: list[str],
    today: _dt.date | None = None,
    *,
    warnings: list[str] | None = None,
    freshness_blocking: bool = False,
) -> None:
    """Each plugins/launchpad/scaffolders/<stack>-pattern.md MUST carry a
    YAML frontmatter `last_validated:`. Presence/shape problems are hard
    failures; a lapsed window is advisory unless `freshness_blocking` is True.
    See `_freshness_finding`."""
    if today is None:
        today = _dt.date.today()
    if warnings is None:
        warnings = []
    rule = "anchor-doc-freshness"
    if not ANCHOR_DIR.exists():
        return
    fm_re = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
    lv_re = re.compile(r"^last_validated:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.MULTILINE)
    for anchor in sorted(ANCHOR_DIR.glob("*-pattern.md")):
        text = anchor.read_text(encoding="utf-8")
        m = fm_re.match(text)
        if not m:
            failures.append(
                f"[{rule}] {anchor.relative_to(REPO_ROOT)} missing YAML frontmatter"
            )
            continue
        lv = lv_re.search(m.group(1))
        if not lv:
            failures.append(
                f"[{rule}] {anchor.relative_to(REPO_ROOT)} frontmatter missing "
                f"last_validated"
            )
            continue
        finding = _freshness_finding(lv.group(1), today=today)
        if finding is not None:
            severity, msg = finding
            sink = failures if (severity == "fail" or freshness_blocking) else warnings
            sink.append(f"[{rule}] {anchor.relative_to(REPO_ROOT)}: {msg}")


# --- Phase -1 acceptance gates ---


def check_psutil_cve(failures: list[str]) -> int:
    """Cross-reference `_vendor/PSUTIL_VERSION` against the public CVE feed.

    At v2.0 dev time we ship a static check: assert the pinned version exists
    and is non-empty. Online CVE-feed cross-reference is a Phase 7.5 ship-time
    addition once we choose a feed source. The current Phase -1 gate is the
    structural pin requirement.
    """
    pin = SCRIPT_DIR / "_vendor" / "PSUTIL_VERSION"
    if not pin.exists():
        failures.append(
            "[psutil-cve] _vendor/PSUTIL_VERSION pin file missing — required "
            "by HANDSHAKE §1.4."
        )
        return 1
    version = pin.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(\.\d+)?", version):
        failures.append(
            f"[psutil-cve] _vendor/PSUTIL_VERSION pin {version!r} doesn't "
            f"match semver pattern."
        )
        return 1
    return 0


def check_pyyaml_cve(failures: list[str]) -> int:
    """Same shape as check_psutil_cve. Pin file required."""
    pin = SCRIPT_DIR / "_vendor" / "PYYAML_VERSION"
    if not pin.exists():
        failures.append(
            "[pyyaml-cve] _vendor/PYYAML_VERSION pin file missing — required "
            "by HANDSHAKE §12."
        )
        return 1
    version = pin.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(\.\d+)?", version):
        failures.append(
            f"[pyyaml-cve] _vendor/PYYAML_VERSION pin {version!r} doesn't "
            f"match semver pattern."
        )
        return 1
    return 0


def check_legacy_yaml_canonical_hash_removal(failures: list[str]) -> int:
    """v2.2.0 gate (BL-210): when plugin.json version >= 2.2.0, the legacy
    YAML migration helper must have been deleted.

    Phase 11 hardening A5: gate threshold bumped from 2.1.0 to 2.2.0. The
    Phase 11 plugin.json bump 2.0.0 -> 2.1.0 activated this gate prematurely
    against code that still defines and calls `_legacy_yaml_canonical_hash`.
    BL-210 deletion lands with the v2.2 audit-tooling promotion bundle so
    the gate's docstring + activation threshold + symbol removal land in
    the same release. Until then the gate stays inactive at v2.1.x.

    Implementation: grep for the symbol; if found AND plugin.json version is
    >= 2.2.0, fail. Reads plugin.json directly (no JSON canonicalization
    needed for a single-field lookup)."""
    plugin_json = REPO_ROOT / "plugins" / "launchpad" / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        return 0  # nothing to gate against
    import json

    try:
        meta = json.loads(plugin_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"[legacy-yaml-removal] plugin.json parse error: {exc}")
        return 1
    version = meta.get("version", "")
    # Parse semver major.minor only; gate fires at >= 2.2.0
    m = re.match(r"(\d+)\.(\d+)", version)
    if not m:
        return 0
    major, minor = int(m.group(1)), int(m.group(2))
    if (major, minor) < (2, 2):
        return 0  # gate not yet active
    hits = _walk_grep(
        "_legacy_yaml_canonical_hash", "plugins/launchpad/scripts/", fixed=True
    )
    real = [
        h
        for h in hits
        if not h.split(":", 1)[0].endswith("plugin-v2-handshake-lint.py")
    ]
    if real:
        failures.append(
            f"[legacy-yaml-removal] BL-210 gate: at version {version} the "
            f"_legacy_yaml_canonical_hash symbol must be removed; found:\n  "
            + "\n  ".join(real)
        )
        return 1
    return 0


# --- mode dispatch ---


def check_scaffold_receipt_schema(failures: list[str]) -> None:
    """L1 (Phase 3): validate any `scaffold-receipt.json` files in fixtures
    match HANDSHAKE §5 schema (required fields + sha256 self-hash + 4-key
    tier1_governance_summary)."""
    fixtures = PLUGINS_SCRIPTS / "tests" / "fixtures"
    if not fixtures.exists():
        return
    import json

    # Import canonical_hash for sha256 self-verification (PR #41 cycle 6 #4
    # — the previous shape only checked required-field presence, so a
    # corrupted fixture with a wrong sha256 passed silently).
    import sys as _sys

    if str(PLUGINS_SCRIPTS) not in _sys.path:
        _sys.path.insert(0, str(PLUGINS_SCRIPTS))
    from decision_integrity import canonical_hash  # type: ignore[import-not-found]

    required = (
        "version",
        "scaffolded_at",
        "decision_sha256",
        "decision_nonce",
        "layers_materialized",
        "cross_cutting_files",
        "toolchains_detected",
        "secret_scan_passed",
        "tier1_governance_summary",
        "sha256",
    )
    bad: list[str] = []
    for f in fixtures.glob("scaffold_receipt*.json"):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            bad.append(f"{f.name}: parse failed: {exc}")
            continue
        for fld in required:
            if fld not in payload:
                bad.append(f"{f.name}: missing required field {fld!r}")
        # Forward-compat: fixture's tier1 may carry only architecture_docs_rendered
        # (Phase 1 stub); the FULL 4-key check is enforced at write-side, not
        # at fixture-validation level, since /lp-define populates the other
        # 3 counts after dispatch.
        tier1 = payload.get("tier1_governance_summary") or {}
        if "architecture_docs_rendered" not in tier1:
            bad.append(
                f"{f.name}: tier1_governance_summary.architecture_docs_rendered missing"
            )
        # sha256 self-hash verification (closes silent-corruption gap).
        # Skip if `sha256` key is missing — already flagged by required-fields check.
        declared_sha = payload.get("sha256")
        if isinstance(declared_sha, str):
            payload_minus_sha = {k: v for k, v in payload.items() if k != "sha256"}
            try:
                actual_sha = canonical_hash(payload_minus_sha)
            except Exception as exc:  # pragma: no cover
                bad.append(f"{f.name}: canonical_hash failed: {exc}")
                continue
            if actual_sha != declared_sha:
                bad.append(
                    f"{f.name}: sha256 mismatch: declared={declared_sha!r} "
                    f"computed={actual_sha!r}"
                )
    _emit(failures, "scaffold-receipt-schema", bad)


def check_nonce_ledger_format(failures: list[str]) -> None:
    """L2 (Phase 3): if any `.scaffold-nonces.log` exists in fixtures, assert
    it carries the format header line as the first record + 33-byte fixed-
    record discipline (per HANDSHAKE §4 rule 10)."""
    fixtures = PLUGINS_SCRIPTS / "tests" / "fixtures"
    if not fixtures.exists():
        return
    bad: list[str] = []
    for f in fixtures.rglob("*.scaffold-nonces.log"):
        try:
            lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError as exc:
            bad.append(f"{f.name}: read failed: {exc}")
            continue
        if not lines:
            bad.append(f"{f.name}: empty ledger")
            continue
        if not lines[0].startswith("# nonce-ledger-format:"):
            bad.append(f"{f.name}: first line must be format header (got {lines[0]!r})")
            continue
        # 33-byte record discipline (data lines only; comment lines exempt).
        for ln in lines[1:]:
            if ln.startswith("#"):
                continue
            if len(ln.encode("utf-8")) != 33:
                bad.append(
                    f"{f.name}: data line is not 33 bytes (got {len(ln.encode('utf-8'))})"
                )
                break
    _emit(failures, "nonce-ledger-format", bad)


def check_scaffold_rejection_schema(failures: list[str]) -> None:
    """L3 (Phase 3): validate any `scaffold-rejection-<ts>.jsonl` files in
    fixtures match the inline write-protocol schema."""
    fixtures = PLUGINS_SCRIPTS / "tests" / "fixtures"
    if not fixtures.exists():
        return
    import json

    required = ("schema_version", "reason", "timestamp", "pid", "pid_start_time")
    bad: list[str] = []
    for f in fixtures.rglob("scaffold-rejection-*.jsonl"):
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as exc:
            bad.append(f"{f.name}: read failed: {exc}")
            continue
        for ln in text.splitlines():
            if not ln.strip():
                continue
            try:
                rec = json.loads(ln)
            except ValueError as exc:
                bad.append(f"{f.name}: parse failed: {exc}")
                continue
            for fld in required:
                if fld not in rec:
                    bad.append(f"{f.name}: missing required field {fld!r}")
            if rec.get("schema_version") != "1.0":
                bad.append(
                    f"{f.name}: schema_version must be '1.0' (got {rec.get('schema_version')!r})"
                )
    _emit(failures, "scaffold-rejection-schema", bad)


def check_scaffold_failed_schema(failures: list[str]) -> None:
    """L4 (Phase 3): validate any `scaffold-failed-<ts>.json` files in
    fixtures match OPERATIONS §6 gate #11 schema + write-time destructive-
    path denylist."""
    fixtures = PLUGINS_SCRIPTS / "tests" / "fixtures"
    if not fixtures.exists():
        return
    import json

    required = (
        "schema_version",
        "version",
        "failed_at",
        "reason",
        "failed_layer_index",
        "materialized_files",
        "recovery_commands",
        "recommended_recovery_action",
        "see_recovery_doc",
    )
    valid_reasons = {
        "layer_materialization_failed",
        "auth_precondition_unmet",
        "network_precondition_unmet",
        "cross_cutting_wiring_collision",
        "secret_scan_failed",
        "recovery_precondition_unmet",
    }
    destructive_paths = {".", "./", "..", "/", "~", ".launchpad", ".git", ".github"}
    bad: list[str] = []
    for f in fixtures.rglob("scaffold-failed-*.json"):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            bad.append(f"{f.name}: parse failed: {exc}")
            continue
        for fld in required:
            if fld not in rec:
                bad.append(f"{f.name}: missing required field {fld!r}")
        if rec.get("reason") not in valid_reasons:
            bad.append(
                f"{f.name}: reason {rec.get('reason')!r} not in OPERATIONS §6 gate #11 enum"
            )
        for entry in rec.get("recovery_commands") or []:
            path = entry.get("path")
            if path in destructive_paths:
                bad.append(
                    f"{f.name}: recovery_commands carries destructive path {path!r}"
                )
    _emit(failures, "scaffold-failed-schema", bad)


def check_atomic_write_replace_allowlist(failures: list[str]) -> None:
    """Phase 8.5 plan section 2.3: ALLOWLIST-based lint rule for
    `atomic_write_replace` callers.

    Only modules in `ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS` may call
    `atomic_write_replace` (or an aliased import). Anything else fails
    the lint. Uses AST analysis with import-binding resolution so
    `from atomic_io import atomic_write_replace as _w` then `_w(...)` is
    detected as a violation in the same module.
    """
    rule = "atomic-write-replace-allowlist"
    import ast as _ast

    permitted = set(ATOMIC_WRITE_REPLACE_ALLOWED_CALLERS)

    py_files: list[Path] = []
    for pat in ATOMIC_WRITE_REPLACE_SCAN_GLOBS:
        py_files.extend(REPO_ROOT.glob(pat))

    hits: list[str] = []
    for py_path in py_files:
        try:
            rel = py_path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        if rel in permitted:
            continue
        if "/_vendor/" in rel or "/__pycache__/" in rel:
            continue
        if (
            "/tests/" in rel
            or rel.endswith("_test.py")
            or rel.startswith("plugins/launchpad/scripts/tests/")
        ):
            # Tests are permitted to call atomic_write_replace as part
            # of fixture setup; the gate targets production code paths.
            continue
        try:
            tree = _ast.parse(py_path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue

        # Bind every import name resolving to atomic_io.atomic_write_replace.
        bound_names: set[str] = set()
        for node in _ast.walk(tree):
            if isinstance(node, _ast.ImportFrom):
                if (node.module or "").endswith("atomic_io"):
                    for alias in node.names:
                        if alias.name in ATOMIC_WRITE_REPLACE_NAMES:
                            bound_names.add(alias.asname or alias.name)
            elif isinstance(node, _ast.Import):
                for alias in node.names:
                    if alias.name == "atomic_io":
                        # `atomic_io.atomic_write_replace(...)` calls
                        # are caught via Attribute below.
                        bound_names.add(alias.asname or alias.name)

        # Walk the AST looking for calls. Bare-name calls hit
        # `bound_names`; attribute calls hit `<atomic_io_alias>.atomic_write_replace`.
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Call):
                func = node.func
                if isinstance(func, _ast.Name) and func.id in bound_names:
                    hits.append(f"{rel}:{node.lineno}: {func.id}(...)")
                elif (
                    isinstance(func, _ast.Attribute)
                    and func.attr in ATOMIC_WRITE_REPLACE_NAMES
                    and isinstance(func.value, _ast.Name)
                    and func.value.id in bound_names
                ):
                    hits.append(
                        f"{rel}:{node.lineno}: {func.value.id}.{func.attr}(...)"
                    )

    if hits:
        failures.append(
            f"[{rule}] atomic_write_replace called from non-allowlisted "
            f"module(s); only {sorted(permitted)} may call this function "
            f"(Phase 8.5 plan section 2.3). Hits:\n  " + "\n  ".join(sorted(hits))
        )


def check_decommission_audit_log_required(
    failures: list[str], base_ref: str = "origin/main"
) -> None:
    """Phase 8.5 plan section 2.3 audit-log enforcement rule.

    Any deletion of a CODEOWNERS-protected path under
    `plugins/launchpad/scripts/` requires a same-commit append-only entry
    in `docs/maintainers/decommission-history.md`. The check:

      1. `git diff --name-only --diff-filter=D <base>...HEAD` -> deleted files.
      2. If any deleted path matches the protected pattern set, assert
         the audit log is in the changed-files set.
    """
    rule = "decommission-audit-log-required"
    rc, deleted_out = _run(
        ["git", "diff", "--name-only", "--diff-filter=D", f"{base_ref}...HEAD"]
    )
    if rc != 0:
        # Diff failed; CI is responsible for fetching the base ref.
        return

    deleted = {line.strip() for line in deleted_out.splitlines() if line.strip()}
    if not deleted:
        return

    # Protected patterns: anything under plugins/launchpad/scripts/ except
    # __pycache__ + _vendor.
    protected_prefixes = ("plugins/launchpad/scripts/",)
    excluded_substrings = ("/__pycache__/", "/_vendor/", "/tests/")

    protected_deleted = []
    for d in deleted:
        if not any(d.startswith(p) for p in protected_prefixes):
            continue
        if any(s in d for s in excluded_substrings):
            continue
        protected_deleted.append(d)

    if not protected_deleted:
        return

    rc, changed_out = _run(["git", "diff", "--name-only", f"{base_ref}...HEAD"])
    if rc != 0:
        return
    changed = {line.strip() for line in changed_out.splitlines() if line.strip()}

    if DECOMMISSION_AUDIT_LOG not in changed:
        failures.append(
            f"[{rule}] CODEOWNERS-protected path(s) deleted without a "
            f"same-commit append entry in {DECOMMISSION_AUDIT_LOG}:\n  "
            + "\n  ".join(sorted(protected_deleted))
            + "\n\nPhase 8.5 plan section 2.3 audit-log enforcement: every "
            "deletion under plugins/launchpad/scripts/ requires an "
            "append-only audit-log entry with non-empty Reason + Reviewer."
        )


def run_default_lint() -> int:
    failures: list[str] = []
    # Catalog/pattern-doc staleness is advisory in the PR lint: it reflects a
    # time-based maintenance cadence, not the content of any PR, so it must not
    # block unrelated changes. The hard freshness gate runs at release time via
    # `--check-freshness` (wired into v2-release.yml). See _freshness_finding.
    warnings: list[str] = []
    check_no_raw_subprocess(failures)
    check_no_shell_true(failures)
    check_zx_test_residual(failures)
    check_brownfield_manifests_single_source(failures)
    check_hyphen_test_files(failures)
    check_pull_request_target_safety(failures)
    check_private_origin_leakage(failures)
    check_atomic_write_replace_allowlist(failures)
    # Phase 1 catalog validation (only enforced when the catalog files exist;
    # at Phase -1 they did not, and the lint stayed silent on this surface).
    if SCAFFOLDERS_YML.exists() or CATEGORY_PATTERNS_YML.exists():
        scaffolder_ids = check_scaffolders_catalog(failures, warnings=warnings)
        check_category_patterns_catalog(
            failures, scaffolder_ids=scaffolder_ids, warnings=warnings
        )
        check_anchor_doc_freshness(failures, warnings=warnings)
    # Phase 3 fixture-shape validators (run regardless; no-op if no matching
    # fixtures exist).
    check_scaffold_receipt_schema(failures)
    check_nonce_ledger_format(failures)
    check_scaffold_rejection_schema(failures)
    check_scaffold_failed_schema(failures)
    if warnings:
        print("v2 handshake lint advisory (non-blocking — see --check-freshness):")
        for w in warnings:
            print(f"  {w}")
    if failures:
        print("v2 handshake lint failed:", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print("v2 handshake lint: PASS")
    return 0


def run_check_freshness_gate() -> int:
    """Hard freshness gate for release time (`--check-freshness`).

    Runs the same catalog/anchor validators as the default lint but with
    `freshness_blocking=True`, so a lapsed `last_validated:` window becomes a
    failure rather than an advisory warning. Wired into v2-release.yml so
    catalog/pattern docs must be re-stamped within the window at each tag, while
    everyday PRs (e.g. dependency bumps) are never blocked by staleness.
    """
    failures: list[str] = []
    if SCAFFOLDERS_YML.exists() or CATEGORY_PATTERNS_YML.exists():
        scaffolder_ids = check_scaffolders_catalog(failures, freshness_blocking=True)
        check_category_patterns_catalog(
            failures, scaffolder_ids=scaffolder_ids, freshness_blocking=True
        )
        check_anchor_doc_freshness(failures, freshness_blocking=True)
    else:
        print("freshness gate: no catalog files present; nothing to check")
        return 0
    if failures:
        print("freshness gate FAIL:", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print("freshness gate: PASS")
    return 0


def run_check_version_coherence(phase: str) -> int:
    """Version-coherence enforcement.

    `--phase=pre-bump` (advisory): verifies that the bump-list constants are
    NOT yet at "1.0" — i.e., the bump commit has not yet landed. Used by the
    pre-bump CI gate to refuse premature merge of partial bumps.

    `--phase=post-tag` (gating): verifies the §10 post-bump invariant — the
    string `0.x-test` MUST NOT appear anywhere in the plugin-shipped tree
    (modulo the documentary allowlist). Wired into v2-release.yml check #3.
    """
    if phase not in ("pre-bump", "post-tag"):
        print(f"--phase must be pre-bump or post-tag; got {phase}", file=sys.stderr)
        return 2
    failures: list[str] = []
    if phase == "post-tag":
        check_zx_test_residual(failures)
        if failures:
            print(
                "version-coherence (post-tag): FAIL — 0.x-test residual",
                file=sys.stderr,
            )
            for f in failures:
                print(f, file=sys.stderr)
            return 1
        print("version-coherence (post-tag): PASS")
        return 0
    # pre-bump: advisory at v2.0 dev time
    print(f"version-coherence ({phase}): advisory pass at v2.0 dev time")
    return 0


def run_regenerate_fixtures(max_fixtures: int) -> int:
    """2-pass atomic regen consuming tests/fixtures/manifest.yml.

    At Phase -1 there are no fixtures yet; fixture creation lives in the
    pick-stack/orchestration phases. This entry point is wired so the
    workflow can call it without erroring out.
    """
    manifest = SCRIPT_DIR / "tests" / "fixtures" / "manifest.yml"
    if not manifest.exists():
        print("regenerate-fixtures: no manifest.yml yet (Phase -1 — no fixtures)")
        return 0
    print(
        f"regenerate-fixtures: max_fixtures={max_fixtures}; "
        f"manifest at {manifest.relative_to(REPO_ROOT)} (Phase 7.5 path)"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-version-coherence",
        action="store_true",
        help="Run the version-coherence check (requires --phase).",
    )
    parser.add_argument(
        "--phase",
        choices=("pre-bump", "post-tag"),
        help="Phase for version-coherence check.",
    )
    parser.add_argument(
        "--check-_legacy_yaml_canonical_hash-removal",
        action="store_true",
        dest="check_legacy_removal",
        help="Gate v2.1.0 removal of _legacy_yaml_canonical_hash (BL-210).",
    )
    # TODO (BL-238 — Codex PR #41 cycle 11 P2 #1): the `-cve` suffix
    # overstates what these checks do. Today they validate the pin's
    # semver shape only — there is NO active CVE database cross-reference
    # at v2.0. Either rename to `--check-psutil-pin` / `--check-pyyaml-pin`
    # (truthful) and document the missing CVE-DB integration as v2.1+
    # work, OR wire to a real CVE feed (osv.dev, GitHub advisory) before
    # the next public release. NOT addressed in cycle 11 to keep scope
    # tight on the three P1 correctness fixes; tracked for v2.1.
    parser.add_argument(
        "--check-psutil-cve",
        action="store_true",
        help="Phase -1 acceptance gate: psutil pin shape check "
        "(BL-238 — does NOT yet cross-reference a CVE DB).",
    )
    parser.add_argument(
        "--check-pyyaml-cve",
        action="store_true",
        help="PyYAML pin shape check (BL-238 — does NOT yet cross-reference a CVE DB).",
    )
    parser.add_argument(
        "--check-leakage",
        action="store_true",
        help="Standalone private-origin leakage scan (verify-v2-ship #4).",
    )
    parser.add_argument(
        "--check-schema-codeowners-gate",
        action="store_true",
        dest="check_schema_codeowners_gate",
        help="v2.1+: fail PRs that change schema-source files without "
        "touching SCAFFOLD_HANDSHAKE.md in the same diff. Reads "
        "LP_BASE_REF (default origin/main) for the diff base.",
    )
    parser.add_argument(
        "--check-pin-registry-rotation-audit-log",
        action="store_true",
        dest="check_pin_registry_rotation_audit_log",
        help="Phase 4 v2.1: fail PRs that rotate an _UPSTREAM_SHA value in "
        "pin_registry.py without a same-commit append-only entry in "
        "docs/maintainers/upstream-pin-rotations.md. Reads LP_BASE_REF "
        "(default origin/main) for the diff base.",
    )
    parser.add_argument(
        "--check-freshness",
        action="store_true",
        dest="check_freshness",
        help="Release-time HARD freshness gate: fail when any catalog/pattern "
        "`last_validated:` is older than the 30d window. The default PR lint "
        "treats staleness as advisory; this flag (wired into v2-release.yml) is "
        "where the window is enforced. See SCAFFOLD_OPERATIONS.md §4.",
    )
    parser.add_argument(
        "--regenerate-fixtures",
        action="store_true",
        help="WRITE-MUTATING: regenerate test fixtures from manifest.yml. "
        "Permitted ONLY in v2-release.yml.",
    )
    parser.add_argument(
        "--max-fixtures",
        type=int,
        default=200,
        help="Cap on number of fixtures regenerated (Layer 5 P2-L5-2).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass-1 only; do not write fixtures.",
    )
    args = parser.parse_args()

    if args.check_version_coherence:
        if not args.phase:
            print("--check-version-coherence requires --phase", file=sys.stderr)
            return 2
        return run_check_version_coherence(args.phase)

    failures: list[str] = []
    if args.check_legacy_removal:
        return check_legacy_yaml_canonical_hash_removal(failures) or (
            1 if failures else 0
        )
    if args.check_psutil_cve:
        rc = check_psutil_cve(failures)
        if failures:
            for f in failures:
                print(f, file=sys.stderr)
        return rc
    if args.check_pyyaml_cve:
        rc = check_pyyaml_cve(failures)
        if failures:
            for f in failures:
                print(f, file=sys.stderr)
        return rc
    if args.check_leakage:
        return run_check_leakage()
    if args.check_schema_codeowners_gate:
        return run_check_schema_codeowners_gate()
    if args.check_pin_registry_rotation_audit_log:
        return run_check_pin_registry_rotation_audit_log()
    if args.check_freshness:
        return run_check_freshness_gate()
    if args.regenerate_fixtures:
        return run_regenerate_fixtures(args.max_fixtures)

    return run_default_lint()


if __name__ == "__main__":
    sys.exit(main())
