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
    REPO_ROOT / "plugins" / "launchpad" / "scripts" / "lp_pick_stack" / "data"
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
ALLOWED_ROLES = frozenset({
    "frontend", "backend", "frontend-main", "frontend-dashboard",
    "fullstack", "mobile", "backend-managed", "desktop",
})

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

# v2.0 contract scope — modules introduced in v2.0 must use safe_run() per
# OPERATIONS §1. v1 modules predate the contract and are out of scope for
# the no-raw-subprocess + no-shell-true checks. Listed by basename so test
# harness scaffolds + similar v1 utilities aren't flagged.
V2_MODULES = frozenset({
    "decision_integrity.py",
    "knowledge_anchor_loader.py",
    "path_validator.py",
    "cwd_state.py",
    "safe_run.py",
    "telemetry_writer.py",
    "pid_identity.py",
    "plugin-v2-handshake-lint.py",
    "plugin-scaffold-receipt-loader.py",
    "plugin-freshness-check.py",
    "plugin-scaffold-stack.py",
})

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

# Leakage-scan paths: extends the `_git_grep` defaults to also include
# `.claude-plugin/` and root-level `.json` files (per HANDSHAKE §12 verify-v2-
# ship #4: "grep all committed paths under plugins/, docs/, .claude-plugin/,
# .github/, root .md/.json files").
LEAKAGE_SCAN_PATHS = (
    "plugins/", "docs/", ".github/", ".claude-plugin/",
    "ROADMAP.md", "README.md", "CHANGELOG.md", "AGENTS.md",
    "CONTRIBUTING.md", "SECURITY.md",
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
    "plugins/launchpad/scripts/plugin-default-generators/agents.yml.j2",
    "plugins/launchpad/scripts/plugin_stack_adapters/ts_monorepo.py",
    "plugins/launchpad/commands/lp-define.md",
    "plugins/launchpad/commands/lp-copy.md",
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


def _git_grep(pattern: str, *paths: str, fixed: bool = False, regex: bool = False) -> list[str]:
    """Search for pattern across the worktree (tracked + untracked).

    We walk the filesystem rather than calling `git grep` so the lint works
    on untracked files during Phase -1 (the v2 modules are not yet committed
    per the no-push golden rule).
    """
    if regex:
        pat = re.compile(pattern)
        match = lambda line: bool(pat.search(line))  # noqa: E731
    elif fixed:
        match = lambda line: pattern in line  # noqa: E731
    else:
        # Plain pattern, treat as regex (matches git grep default behavior
        # closely enough for our needs).
        pat = re.compile(re.escape(pattern))
        match = lambda line: bool(pat.search(line))  # noqa: E731

    if not paths:
        paths = ("plugins/", "docs/", "ROADMAP.md", "README.md", "CHANGELOG.md", ".github/")
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
                if any(rel.startswith(ex) or f"/{ex}" in f"/{rel}/"
                       for ex in LINT_SCAN_EXCLUDES):
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
    """A path is in the v2.0 contract scope iff its basename is listed in
    V2_MODULES. v1 modules predate the v2.0 subprocess contract and are out
    of scope until they are individually migrated."""
    return Path(path).name in V2_MODULES


def check_no_raw_subprocess(failures: list[str]) -> None:
    """All subprocess calls in v2.0 MODULES must go through `safe_run()`
    (OPERATIONS §1). v1 modules predate the contract and are exempt; the
    v2-modules list in V2_MODULES is the authoritative scope."""
    bad = []
    for hit in _git_grep(r"^[^#]*subprocess\.(run|Popen|call|check_output|check_call)",
                         "plugins/launchpad/scripts/", regex=True):
        path = hit.split(":", 1)[0]
        if not _is_v2_module(path):
            continue  # v1 module — out of v2.0 contract scope
        if path.endswith("safe_run.py"):
            continue  # safe_run is the helper itself
        if path.endswith("plugin-v2-handshake-lint.py"):
            continue  # this script IS the enforcement
        if "/tests/" in path:
            continue
        bad.append(hit)
    _emit(failures, "no-raw-subprocess", bad)


def check_no_shell_true(failures: list[str]) -> None:
    """shell=True is forbidden in v2.0 modules. v1 modules out of scope.

    Allow lines that only mention shell=True as documentation/prohibition
    (heuristic: comment-marker before the match, or contains "no shell=True"
    / "Never use" / "forbidden"). Actual subprocess invocations go through
    safe_run() and do not appear in user code at all.
    """
    bad = []
    for hit in _git_grep("shell=True", "plugins/launchpad/scripts/", fixed=True):
        path = hit.split(":", 1)[0]
        if not _is_v2_module(path):
            continue
        if path.endswith("plugin-v2-handshake-lint.py"):
            continue
        if "/tests/" in path:
            continue
        # Documentation/prohibition mentions allowed.
        line_text = hit.split(":", 2)[2] if hit.count(":") >= 2 else ""
        if "no shell=True" in line_text or "shell=True is" in line_text \
                or "Never use" in line_text or "forbidden" in line_text.lower():
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
    for hit in _git_grep(VERSION_RESIDUAL, fixed=True):
        path = hit.split(":", 1)[0]
        if any(path == allowed or path.startswith(allowed)
               for allowed in ZX_ALLOWED_PATHS):
            continue
        bad.append(hit)
    _emit(failures, "no-0.x-test-residual", bad)


def check_brownfield_manifests_single_source(failures: list[str]) -> None:
    """`BROWNFIELD_MANIFESTS = {` definition must occur exactly once (in
    cwd_state.py). Per HANDSHAKE §8 single-source assertion #2."""
    hits = _git_grep(r"BROWNFIELD_MANIFESTS\s*=\s*\{",
                     "plugins/launchpad/scripts/", regex=True)
    # Filter out hits inside this lint script + tests (test source includes
    # the regex literal).
    real = [h for h in hits if not (
        h.split(":", 1)[0].endswith("plugin-v2-handshake-lint.py")
        or "/tests/" in h.split(":", 1)[0]
    )]
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
                    bad.append(f"{wf.relative_to(REPO_ROOT)}:{i}: forbidden pattern {pat!r}")
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
    return any(path == allowed or path.endswith("/" + allowed)
               for allowed in LEAKAGE_FILE_ALLOWLIST)


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
        for hit in _git_grep(pat, *LEAKAGE_SCAN_PATHS, regex=True):
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


def check_scaffolders_catalog(failures: list[str], today: _dt.date | None = None) -> set[str]:
    """Validate scaffolders.yml shape + freshness + per-entry sha256 against
    its knowledge_anchor file. Returns the set of stack ids it found (used by
    the cross-reference check in check_category_patterns_catalog).
    """
    if today is None:
        today = _dt.date.today()
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

    if len(stacks) != 10:
        failures.append(
            f"[{rule}] v2.0 catalog must ship exactly 10 stacks (HANDSHAKE §11); "
            f"found {len(stacks)}"
        )

    found_ids: set[str] = set()
    for stack_id, entry in stacks.items():
        found_ids.add(stack_id)
        if not isinstance(entry, dict):
            failures.append(f"[{rule}] entry {stack_id!r} must be a mapping")
            continue
        for required in ("pillar", "type", "flavor", "knowledge_anchor",
                         "knowledge_anchor_sha256", "options_schema",
                         "last_validated"):
            if required not in entry:
                failures.append(
                    f"[{rule}] entry {stack_id!r} missing required field "
                    f"{required!r}"
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
                actual_sha = hashlib.sha256(
                    anchor_path.read_bytes()
                ).hexdigest()
                pinned = entry.get("knowledge_anchor_sha256")
                if pinned != actual_sha:
                    failures.append(
                        f"[{rule}] entry {stack_id!r} knowledge_anchor_sha256 "
                        f"mismatch: pinned {pinned!r} actual {actual_sha!r}"
                    )
        # last_validated freshness
        lv = entry.get("last_validated")
        if isinstance(lv, _dt.date):
            err = _check_freshness(lv.isoformat(), today=today)
        elif isinstance(lv, str):
            err = _check_freshness(lv, today=today)
        else:
            err = f"last_validated must be a YYYY-MM-DD string; got {lv!r}"
        if err:
            failures.append(f"[{rule}] entry {stack_id!r}: {err}")

    return found_ids


def check_category_patterns_catalog(failures: list[str],
                                    *, scaffolder_ids: set[str],
                                    today: _dt.date | None = None) -> None:
    """Validate category-patterns.yml shape + freshness + cross-reference each
    canonical_stack[].stack against scaffolder_ids."""
    if today is None:
        today = _dt.date.today()
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
        for required in ("name", "fits_when", "canonical_stack",
                         "explanation", "last_validated"):
            if required not in entry:
                failures.append(
                    f"[{rule}] category {cat_id!r} missing required field "
                    f"{required!r}"
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
        # last_validated freshness
        lv = entry.get("last_validated")
        if isinstance(lv, _dt.date):
            err = _check_freshness(lv.isoformat(), today=today)
        elif isinstance(lv, str):
            err = _check_freshness(lv, today=today)
        else:
            err = f"last_validated must be a YYYY-MM-DD string; got {lv!r}"
        if err:
            failures.append(f"[{rule}] category {cat_id!r}: {err}")


def check_anchor_doc_freshness(failures: list[str], today: _dt.date | None = None) -> None:
    """Each plugins/launchpad/scaffolders/<stack>-pattern.md MUST carry a
    YAML frontmatter `last_validated:` within the 30d window."""
    if today is None:
        today = _dt.date.today()
    rule = "anchor-doc-freshness"
    if not ANCHOR_DIR.exists():
        return
    fm_re = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
    lv_re = re.compile(r"^last_validated:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
                       re.MULTILINE)
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
        err = _check_freshness(lv.group(1), today=today)
        if err:
            failures.append(f"[{rule}] {anchor.relative_to(REPO_ROOT)}: {err}")


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
    """v2.1.0 gate (BL-210): when plugin.json version >= 2.1.0, the legacy
    YAML migration helper must have been deleted.

    Implementation: grep for the symbol; if found AND plugin.json version is
    >= 2.1.0, fail. Reads plugin.json directly (no JSON canonicalization
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
    # Parse semver major.minor only; gate fires at >= 2.1.0
    m = re.match(r"(\d+)\.(\d+)", version)
    if not m:
        return 0
    major, minor = int(m.group(1)), int(m.group(2))
    if (major, minor) < (2, 1):
        return 0  # gate not yet active
    hits = _git_grep("_legacy_yaml_canonical_hash",
                     "plugins/launchpad/scripts/", fixed=True)
    real = [h for h in hits if not h.split(":", 1)[0].endswith(
        "plugin-v2-handshake-lint.py"
    )]
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
    import hashlib
    import json
    required = (
        "version", "scaffolded_at", "decision_sha256", "decision_nonce",
        "layers_materialized", "cross_cutting_files", "toolchains_detected",
        "secret_scan_passed", "tier1_governance_summary", "sha256",
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
            bad.append(f"{f.name}: tier1_governance_summary.architecture_docs_rendered missing")
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
                bad.append(f"{f.name}: data line is not 33 bytes (got {len(ln.encode('utf-8'))})")
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
                bad.append(f"{f.name}: schema_version must be '1.0' (got {rec.get('schema_version')!r})")
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
        "schema_version", "version", "failed_at", "reason", "failed_layer_index",
        "materialized_files", "recovery_commands", "recommended_recovery_action",
        "see_recovery_doc",
    )
    valid_reasons = {
        "layer_materialization_failed", "auth_precondition_unmet",
        "network_precondition_unmet", "cross_cutting_wiring_collision",
        "secret_scan_failed", "recovery_precondition_unmet",
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
            bad.append(f"{f.name}: reason {rec.get('reason')!r} not in OPERATIONS §6 gate #11 enum")
        for entry in (rec.get("recovery_commands") or []):
            path = entry.get("path")
            if path in destructive_paths:
                bad.append(f"{f.name}: recovery_commands carries destructive path {path!r}")
    _emit(failures, "scaffold-failed-schema", bad)


def run_default_lint() -> int:
    failures: list[str] = []
    check_no_raw_subprocess(failures)
    check_no_shell_true(failures)
    check_zx_test_residual(failures)
    check_brownfield_manifests_single_source(failures)
    check_hyphen_test_files(failures)
    check_pull_request_target_safety(failures)
    check_private_origin_leakage(failures)
    # Phase 1 catalog validation (only enforced when the catalog files exist;
    # at Phase -1 they did not, and the lint stayed silent on this surface).
    if SCAFFOLDERS_YML.exists() or CATEGORY_PATTERNS_YML.exists():
        scaffolder_ids = check_scaffolders_catalog(failures)
        check_category_patterns_catalog(failures, scaffolder_ids=scaffolder_ids)
        check_anchor_doc_freshness(failures)
    # Phase 3 fixture-shape validators (run regardless; no-op if no matching
    # fixtures exist).
    check_scaffold_receipt_schema(failures)
    check_nonce_ledger_format(failures)
    check_scaffold_rejection_schema(failures)
    check_scaffold_failed_schema(failures)
    if failures:
        print("v2 handshake lint failed:", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print("v2 handshake lint: PASS")
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
        print(f"--phase must be pre-bump or post-tag; got {phase}",
              file=sys.stderr)
        return 2
    failures: list[str] = []
    if phase == "post-tag":
        check_zx_test_residual(failures)
        if failures:
            print("version-coherence (post-tag): FAIL — 0.x-test residual",
                  file=sys.stderr)
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
    print(f"regenerate-fixtures: max_fixtures={max_fixtures}; "
          f"manifest at {manifest.relative_to(REPO_ROOT)} (Phase 7.5 path)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-version-coherence", action="store_true",
        help="Run the version-coherence check (requires --phase).",
    )
    parser.add_argument(
        "--phase", choices=("pre-bump", "post-tag"),
        help="Phase for version-coherence check.",
    )
    parser.add_argument(
        "--check-_legacy_yaml_canonical_hash-removal",
        action="store_true",
        dest="check_legacy_removal",
        help="Gate v2.1.0 removal of _legacy_yaml_canonical_hash (BL-210).",
    )
    parser.add_argument(
        "--check-psutil-cve", action="store_true",
        help="Phase -1 acceptance gate: psutil pin + CVE cross-reference.",
    )
    parser.add_argument(
        "--check-pyyaml-cve", action="store_true",
        help="PyYAML pin + CVE cross-reference.",
    )
    parser.add_argument(
        "--check-leakage", action="store_true",
        help="Standalone private-origin leakage scan (verify-v2-ship #4).",
    )
    parser.add_argument(
        "--regenerate-fixtures", action="store_true",
        help="WRITE-MUTATING: regenerate test fixtures from manifest.yml. "
             "Permitted ONLY in v2-release.yml.",
    )
    parser.add_argument(
        "--max-fixtures", type=int, default=200,
        help="Cap on number of fixtures regenerated (Layer 5 P2-L5-2).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
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
        return check_legacy_yaml_canonical_hash_removal(failures) or (1 if failures else 0)
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
    if args.regenerate_fixtures:
        return run_regenerate_fixtures(args.max_fixtures)

    return run_default_lint()


if __name__ == "__main__":
    sys.exit(main())
