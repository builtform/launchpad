"""lp_bootstrap package (v2.1 Phase 3).

Owns the `/lp-bootstrap` slash command + bootstrap-manifest mechanism + the
30-path infrastructure overlay (V3 plan section 17.1 Phase 3, locked design
in `docs/plans/launchpad_plans/2026-05-05-v2.1-phase3-implementation-plan.md`
sections 1 to 8).

Surface boundary:

  * The bootstrap-manifest covers infrastructure ONLY. Kernel-file refresh
    (LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md, README.md, etc.) goes
    through `KernelRenderer.refresh()` directly per Day-1 decision D2 +
    section 6.8. `/lp-bootstrap --refresh <path>` rejects kernel paths with
    `UNKNOWN_REFRESH_PATH`.

  * v2.1 ships three active per-file conflict policies plus one
    `--refresh`-mode variant. The two unused-in-v2.1 policies
    (`skip-if-exists`, `overwrite-always`) are deferred to Phase 4 if an
    adapter overlay demands them, else to v2.2 (section 3.2).

This module exposes the constants + dataclasses + enums shared by every
sibling module in the package. Behavioural code lives in:

  * `manifest_writer.py` -- BootstrapManifest dataclass + write_manifest +
    `_normalize_path` + `verify_source_template_shas` + module-load-cached
    `_SOURCE_TEMPLATE_SHAS`.
  * `policy.py` -- 3 active policy applicators + `overwrite-with-backup` for
    `--refresh`; backup-dir helper; gitignore-append helper with
    fail-closed verification.
  * `sentinel.py` -- `.launchpad/.bootstrap-in-progress` lifecycle + PID
    liveness via `os.kill(pid, 0)`.
  * `engine.py` (Slice C) -- top-level `run_bootstrap()` orchestration.

Path inventory pinned in `INFRASTRUCTURE_FILES`. `.gitignore` renders FIRST
in the loop (per harden C2) so sentinel + backup paths are gitignored before
sentinel write fires.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal

# --- Filesystem name constants --------------------------------------------

# `.launchpad/` is the harness directory at the project root. Created by
# `/lp-pick-stack` (Phase 1) at scaffold time; `/lp-bootstrap` writes the
# sentinel + lock + manifest underneath it.
LAUNCHPAD_DIR_NAME: Final[str] = ".launchpad"

# Manifest envelope filename + schema version. Read via Phase 1's
# `plugin-config-loader.read_bootstrap_manifest()` 4-rule ladder. Schema 1.0
# reserves `security_fields: []` (always empty in v2.1 per harden B9 +
# section 6.2 v2.2-downgrade defense).
MANIFEST_FILENAME: Final[str] = "bootstrap-manifest.json"
MANIFEST_SCHEMA_VERSION: Final[str] = "1.0"

# Sentinel + flock target. Sentinel survives SIGKILL; flock auto-releases on
# process death. See section 3.5 state-transition matrix.
SENTINEL_NAME: Final[str] = ".bootstrap-in-progress"
LOCK_NAME: Final[str] = ".bootstrap.lock"

# `--refresh` / `--refresh-all` writes pre-edit content to
# `.launchpad/backups/<ts>-<PID>-<rand4>/<relpath>` before atomic-write of
# new content. Random 4-char suffix prevents same-second + same-PID
# collisions per harden C1.
BACKUP_DIR_NAME: Final[str] = "backups"

# One-line warnings ledger emitted by:
#   * gitignore allowlist scan (renderer) on unknown entries (do NOT block
#     write; closed-allowlist breaks legitimate brownfield additions).
#   * merge-keys policy on user-versus-plugin value-type conflicts.
WARNINGS_FILENAME: Final[str] = "bootstrap-warnings.json"


# --- Error code contract (section 3.7) ------------------------------------

class BootstrapErrorCode(StrEnum):
    """Structured error codes raised by `/lp-bootstrap`.

    Per harden A9 + B12. Per-module typed exceptions raised internally;
    `engine.run_bootstrap()` collects per-file failures into
    `BootstrapResult.errors` (the only place a list shape is justified
    since render-loop failures genuinely accumulate).

    The frozenset of codes is asserted in
    `tests/test_bootstrap_manifest.py::test_no_unknown_error_codes_emitted`
    matching the Phase 1 `IdentityValidationError` precedent.
    """
    # Manifest-class
    MANIFEST_TAMPERED = "manifest_tampered"
    MANIFEST_CORRUPT = "manifest_corrupt"
    NO_MANIFEST_TO_REFRESH = "no_manifest_to_refresh"

    # Plugin-version-class
    PLUGIN_VERSION_MISMATCH = "plugin_version_mismatch"
    # v2.1 Codex PR #50 cycle 6 F9: --accept-plugin-version-drift could not
    # reseal scaffold-decision.json (file missing, hand-edited, or corrupt).
    VERSION_DRIFT_RESEAL_FAILED = "version_drift_reseal_failed"

    # Concurrency-class
    SENTINEL_BLOCKING = "sentinel_blocking"
    STALE_SENTINEL_RECOVERED = "stale_sentinel_recovered"
    FLOCK_TIMEOUT = "flock_timeout"
    IDENTITY_UPDATE_IN_PROGRESS = "identity_update_in_progress"  # Phase 10 DA3 bidirectional sentinel parity (security F2)

    # Render-class
    TEMPLATE_RENDER_FAILED = "template_render_failed"
    TEMPLATE_NOT_FOUND = "template_not_found"
    POLICY_COLLISION = "policy_collision"
    SECRET_SCANNER_VIOLATION = "secret_scanner_violation"

    # Filesystem-class
    DISK_FULL = "disk_full"
    CROSS_DEVICE_REPLACE = "cross_device_replace"
    LAUNCHPAD_DIR_MISSING = "launchpad_dir_missing"
    PERMISSION_DENIED = "permission_denied"
    GITIGNORE_APPEND_FAILED = "gitignore_append_failed"

    # Argument-class
    UNKNOWN_REFRESH_PATH = "unknown_refresh_path"
    PATH_TRAVERSAL_REJECTED = "path_traversal_rejected"


class BootstrapStatus(StrEnum):
    """v2.1 Codex PR #50 P1.D (D4) status taxonomy for non-error outcomes.

    Distinct from `BootstrapErrorCode`: these are the success-class /
    informational outcomes the engine surfaces to callers (and to the
    `--recover` flow) to disambiguate "what state did we end up in".
    """
    # `--recover` cleared the sentinel; manifest unlinked because
    # manifest.created_at predated sentinel.acquired_at (provably stale).
    RECOVERED_SENTINEL_CLEAR_ONLY = "recovered_sentinel_clear_only"

    # Stale-sentinel detected by liveness predicates: pid_dead OR
    # hostname_mismatch OR mtime_age > STALE_SENTINEL_THRESHOLD_HOURS.
    STALE_SENTINEL_DETECTED = "stale_sentinel_detected"


@dataclass(frozen=True)
class BootstrapError:
    """Structured per-file or per-run failure surfaced through engine result."""
    code: BootstrapErrorCode
    path: Path | None
    remediation: str
    severity: Literal["error", "warn", "info"] = "error"


# --- 5-state cwd-state enum (section 3.9) ---------------------------------

class BootstrapState(StrEnum):
    """Result of `cwd_state.infrastructure_present(cwd)`.

    Phase 6 originally owned the helper; folded forward to Phase 3 since
    Phase 3 owns the `infrastructure/` directory contents. Per harden A6
    the boolean tuple shape is insufficient; brownfield `/lp-define`
    dispatches on richer state.
    """
    FULL = "full"
    PARTIAL_MISSING = "partial-missing"
    PARTIAL_STALE = "partial-stale"
    PRESENT_UNMANAGED = "present-unmanaged"
    ABSENT = "absent"


# --- Per-file conflict policies (section 3.2) -----------------------------

class BootstrapPolicy(StrEnum):
    """3 active policies (v2.1) plus 1 `--refresh`-mode variant.

    Two policies named in the original V3 contract (`skip-if-exists`,
    `overwrite-always`) are NOT shipped per harden B1; defer to Phase 4 if
    an adapter overlay demands them, else v2.2.
    """
    OVERWRITE_IF_UNCHANGED = "overwrite-if-unchanged"
    MERGE_KEYS = "merge-keys"
    APPEND_ONLY = "append-only"
    OVERWRITE_WITH_BACKUP = "overwrite-with-backup"  # --refresh / --refresh-all only


# --- 30-path infrastructure inventory (section 3.1) -----------------------

# Tuple shape: (template_relpath, target_relpath, policy, mode).
#   * template_relpath is relative to plugin_default_generators/infrastructure/.
#   * target_relpath is relative to the project root (cwd at bootstrap time);
#     POSIX-style, no leading `./`, no `..`, no absolute paths.
#   * policy is the conflict-resolution rule for normal `/lp-bootstrap`
#     runs (`overwrite-with-backup` is reserved for `--refresh` mode and
#     does NOT appear here).
#   * mode is the chmod target applied AFTER atomic os.replace per harden B8
#     (chmod-before-rename has a tempfile race).
#
# Order is load-bearing: `.gitignore` MUST render first per harden C2 so
# sentinel + backup paths are gitignored before sentinel write fires.
#
# Stack-aware vs stack-agnostic split (V3 section 9.3): rows for
# scripts/maintenance/check-repo-structure.sh,
# scripts/maintenance/detect-structure-drift.sh, and lefthook.yml are
# Phase 4 stack-aware files; Phase 3 ships the stack-agnostic baseline
# (Tier-1 typescript-monorepo defaults). Phase 4 adapter overlays
# specialize via wrap-and-overlay.
INFRASTRUCTURE_FILES: Final[tuple[
    tuple[str, str, BootstrapPolicy, int], ...
]] = (
    # 1. Gitignore renders FIRST (harden C2)
    ("gitignore.j2", ".gitignore", BootstrapPolicy.APPEND_ONLY, 0o644),

    # 2-12. scripts/compound/ (build pipeline + config)
    ("scripts/compound/build.sh.j2", "scripts/compound/build.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),
    ("scripts/compound/board.sh.j2", "scripts/compound/board.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),
    ("scripts/compound/analyze-report.sh.j2", "scripts/compound/analyze-report.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),
    ("scripts/compound/compound-learning.sh.j2", "scripts/compound/compound-learning.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),
    ("scripts/compound/evaluate.sh.j2", "scripts/compound/evaluate.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),
    ("scripts/compound/lib.sh.j2", "scripts/compound/lib.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("scripts/compound/loop.sh.j2", "scripts/compound/loop.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),
    ("scripts/compound/contract-prompt.md.j2", "scripts/compound/contract-prompt.md", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("scripts/compound/evaluate-prompt.md.j2", "scripts/compound/evaluate-prompt.md", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("scripts/compound/grading-criteria.md.j2", "scripts/compound/grading-criteria.md", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("scripts/compound/iteration-claude.md.j2", "scripts/compound/iteration-claude.md", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("scripts/compound/config.json.j2", "scripts/compound/config.json", BootstrapPolicy.MERGE_KEYS, 0o644),

    # 14-15. scripts/hooks/ (lefthook helpers)
    ("scripts/hooks/audit-skills.sh.j2", "scripts/hooks/audit-skills.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),
    ("scripts/hooks/track-skill-usage.sh.j2", "scripts/hooks/track-skill-usage.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),

    # 15a. v2.1 Codex PR #50 P1.A (D1): restamp-history commit-msg hook
    # (downstream-rendered template; introduces subject-line allowlist
    # accepting conventional-commit prefixes + `wip`).
    ("scripts/hooks/restamp-history-hook.py.j2", "scripts/hooks/restamp-history-hook.py", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),

    # 16-17. scripts/maintenance/ (structure drift detection; Phase 4 stack-aware)
    ("scripts/maintenance/check-repo-structure.sh.j2", "scripts/maintenance/check-repo-structure.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),
    ("scripts/maintenance/detect-structure-drift.sh.j2", "scripts/maintenance/detect-structure-drift.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),

    # 18. scripts/agent_hydration/ (CLAUDE.md sub-agent enumeration)
    ("scripts/agent_hydration/hydrate.sh.j2", "scripts/agent_hydration/hydrate.sh", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o755),

    # 19. lefthook.yml (Phase 4 stack-aware; v2.1 ships ts-monorepo baseline)
    ("lefthook.yml.j2", "lefthook.yml", BootstrapPolicy.MERGE_KEYS, 0o644),

    # 20. secret-patterns (sourced by lefthook secret-scan hook)
    ("secret-patterns.txt.j2", ".launchpad/secret-patterns.txt", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),

    # 21-26. .github/ (governance + CI)
    ("github/CODEOWNERS.j2", ".github/CODEOWNERS", BootstrapPolicy.MERGE_KEYS, 0o644),
    ("github/ISSUE_TEMPLATE/bug_report.yml.j2", ".github/ISSUE_TEMPLATE/bug_report.yml", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("github/ISSUE_TEMPLATE/plugin_install_issue.yml.j2", ".github/ISSUE_TEMPLATE/plugin_install_issue.yml", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("github/ISSUE_TEMPLATE/feature_request.yml.j2", ".github/ISSUE_TEMPLATE/feature_request.yml", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("github/workflows/ci.yml.j2", ".github/workflows/ci.yml", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("github/workflows/v2-handshake-lint.yml.j2", ".github/workflows/v2-handshake-lint.yml", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),

    # 27-28. .harness/ (review context + gitignore)
    ("harness/harness.local.md.j2", ".harness/harness.local.md", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("harness/gitignore.j2", ".harness/.gitignore", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),

    # 29-30. Review tooling configs
    ("greptile.json.j2", ".greptile.json", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
    ("gitleaks.toml.j2", ".gitleaks.toml", BootstrapPolicy.OVERWRITE_IF_UNCHANGED, 0o644),
)


# Derived constants -------------------------------------------------------

FILE_MODES: Final[Mapping[str, int]] = MappingProxyType({
    target: mode for _template, target, _policy, mode in INFRASTRUCTURE_FILES
})

INFRASTRUCTURE_TARGETS: Final[frozenset[str]] = frozenset(
    target for _template, target, _policy, _mode in INFRASTRUCTURE_FILES
)


# v2.1 Codex PR #50 P1.A (D1): hook-classification map keyed by
# target_relpath. Co-located with INFRASTRUCTURE_FILES so the drift gate
# (`set(HOOK_CLASSIFICATIONS) <= INFRASTRUCTURE_TARGETS`) catches any
# rename mismatch. v2.2 BL-265 refactors to a dataclass single-source.
HOOK_CLASSIFICATIONS: Final[Mapping[str, str]] = MappingProxyType({
    "scripts/hooks/restamp-history-hook.py": "commit-msg",
    "scripts/hooks/audit-skills.sh": "lefthook-helper",
    "scripts/hooks/track-skill-usage.sh": "lefthook-helper",
})


# v2.1 Codex PR #50 P1.D (D4): bootstrap sentinel staleness threshold (hours).
# Sentinel is treated stale if mtime_age exceeds this value AND no other
# liveness predicate fired (`pid_dead` and `hostname_mismatch` are
# instant-stale signals, while age is the soft fallback for pid/hostname
# matches that still look abandoned).
STALE_SENTINEL_THRESHOLD_HOURS: Final[int] = 2


__all__ = [
    "BACKUP_DIR_NAME",
    "BootstrapError",
    "BootstrapErrorCode",
    "BootstrapPolicy",
    "BootstrapState",
    "BootstrapStatus",
    "FILE_MODES",
    "HOOK_CLASSIFICATIONS",
    "INFRASTRUCTURE_FILES",
    "INFRASTRUCTURE_TARGETS",
    "LAUNCHPAD_DIR_NAME",
    "LOCK_NAME",
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA_VERSION",
    "SENTINEL_NAME",
    "STALE_SENTINEL_THRESHOLD_HOURS",
    "WARNINGS_FILENAME",
]
