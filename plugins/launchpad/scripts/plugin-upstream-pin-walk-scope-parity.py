#!/usr/bin/env python3
"""v2.1.4 BL-328: pin-rotation-time symlink-parity check for sub-template pins.

For every adapter that copies a sub-template subtree from a pinned upstream
(e.g. AstroAdapter copying `examples/portfolio` out of withastro/astro),
this script clones the pinned SHA and walks the SUBTREE that the adapter
will copy, asserting it is free of the disallowed filesystem-entry kinds
the runtime cache rejects (symlink / block_device / char_device / fifo /
socket).

The runtime check happens on the user's machine inside
`template_cache.fetch()`. Catching the same condition at PR time prevents a
pin rotation from shipping a broken `/lp-scaffold-stack` to users.

Why scope to the SUBTREE, not the whole tree? The runtime cache itself
scopes its D9.1 walk to the sub-template subtree (BL-328 fix). Walking
the whole tree at CI time would over-fail on test-fixture symlinks
elsewhere in the repo (e.g. withastro/astro keeps symlinked test
collections under `packages/`) and force pin owners to chase symlinks
they have no control over and the user never sees.

Subtree map (kept in this script — single-source-of-truth lives in the
adapter's `_SUB_PATHS`; this script imports it where possible).

Usage::

    plugin-upstream-pin-walk-scope-parity.py
    plugin-upstream-pin-walk-scope-parity.py --verbose
    plugin-upstream-pin-walk-scope-parity.py --offline-skip   # used in CI

Exit codes:

  0  — PASS. All pinned subtrees clean (or only `KNOWN_BAD_PINS`-waived
       findings, optionally with infra failures suppressed under
       `--offline-skip`).
  1  — FAIL: real parity finding (disallowed entry or missing
       sub-template subpath). NOT suppressed by `--offline-skip` —
       these are pin-shape problems, not network problems.
  2  — INFRA FAIL: git missing OR git fetch CalledProcessError /
       TimeoutExpired without `--offline-skip`. Pass `--offline-skip`
       to downgrade these to exit 0 (used in CI per the workflow
       contract that GitHub-unreachable runners must not fail the
       build).

Distinguishing infra from findings matters because `KNOWN_BAD_PINS`
should only waive REAL findings — a transient `git fetch` flake on an
allowlisted pin is still infra, not a waiver. See `PinCheckResult`.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from plugin_stack_adapters import astro as astro_module  # noqa: E402
from plugin_stack_adapters.pin_registry import all_pins  # noqa: E402

DISALLOWED_KINDS = ("symlink", "block_device", "char_device", "fifo", "socket")

# v2.1.4 known-bad allowlist. The CI parity check exposed two pins that
# would also fail at user runtime under the D9.1 hardening, but rotating
# them is out-of-scope for v2.1.4 (each rotation needs a clean upstream
# SHA + audit-log entry; deferred to v2.1.5 / v2.2 as separate BLs).
# Keeping these entries in the allowlist lets the parity script ship
# strict for FUTURE rotations while accepting the pre-existing failures
# as known-bad. Each entry is a `(adapter_id, sub_template_id, BL)`
# tuple — drop the entry when the matching BL ships its pin rotation.
KNOWN_BAD_PINS: tuple[tuple[str, str | None, str], ...] = (
    (
        "nextjs_fastapi",
        None,
        "BL-329 — vintasoftware/nextjs-fastapi-template@62b67456 has "
        "docs/CHANGELOG.md + docs/README.md as symlinks; rotate to a "
        "clean SHA in v2.1.5 / v2.2",
    ),
    (
        "astro",
        "docs",
        "BL-330 — withastro/starlight@2c530192 has README.md as a "
        "root-level symlink; rotate to a clean SHA in v2.1.5 / v2.2",
    ),
)


def _sub_path_for(adapter_id: str, sub_template_id: str | None) -> str | None:
    """Return the sub-template subtree path to walk, or None for whole-tree.

    Currently only AstroAdapter has sub-template subtrees; other pinned
    adapters consume the whole upstream tree, so we walk the whole
    fetched tree for them (which is what the production runtime does).
    """
    if adapter_id == "astro":
        sub = astro_module._SUB_PATHS.get(sub_template_id or "")  # type: ignore[arg-type]
        if sub == "":
            return None  # Starlight: whole-tree
        return sub
    return None


def _walk_for_disallowed(root: Path) -> tuple[Path, str] | None:
    """Mirror of `template_cache._store._walk_for_disallowed_entries` minus the
    audit-log target sanitization (this is a CI script, not the runtime)."""
    if root.is_symlink():
        return root, "symlink"
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        for name in (*dirnames, *filenames):
            entry = Path(dirpath) / name
            try:
                lst = os.lstat(str(entry))
            except OSError:
                continue
            mode = lst.st_mode
            if stat.S_ISLNK(mode):
                return entry, "symlink"
            if stat.S_ISBLK(mode):
                return entry, "block_device"
            if stat.S_ISCHR(mode):
                return entry, "char_device"
            if stat.S_ISFIFO(mode):
                return entry, "fifo"
            if stat.S_ISSOCK(mode):
                return entry, "socket"
    return None


def _shallow_fetch(repo_url: str, sha: str, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=str(target),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "fetch", "--quiet", "--depth", "1", repo_url, sha],
        cwd=str(target),
        check=True,
        capture_output=True,
        timeout=600,
    )
    subprocess.run(
        ["git", "checkout", "--quiet", sha],
        cwd=str(target),
        check=True,
        capture_output=True,
    )
    with contextlib.suppress(OSError):
        shutil.rmtree(target / ".git")


@dataclass(frozen=True)
class PinCheckResult:
    """Outcome of `_check_pin`. Distinguishes the two failure categories so
    `--offline-skip` can ignore network/timeout flakes without ignoring
    real disallowed-entry findings or stale-pin missing-subpath findings.

    - `findings`: real parity violations (disallowed entry or
      missing-subpath); always fails CI absent a `KNOWN_BAD_PINS` waiver.
    - `infra_errors`: transient infrastructure failures (git fetch
      CalledProcessError or TimeoutExpired) that say nothing about pin
      shape; suppressed under `--offline-skip` to honor the workflow
      contract that GitHub-unreachable runners do not fail the build.
    """

    findings: tuple[str, ...] = ()
    infra_errors: tuple[str, ...] = ()


def _check_pin(
    adapter_id: str,
    sub_template_id: str | None,
    repo_url: str,
    sha: str,
    *,
    verbose: bool,
) -> PinCheckResult:
    sub_path = _sub_path_for(adapter_id, sub_template_id)
    label = (
        f"{adapter_id}/{sub_template_id}" if sub_template_id is not None else adapter_id
    )
    if verbose:
        scope = sub_path if sub_path else "<whole-tree>"
        print(f"[{label}] checking {repo_url}@{sha[:8]} subtree={scope}")
    with tempfile.TemporaryDirectory(prefix="lp-pin-parity-") as tmp:
        target = Path(tmp) / "tree"
        try:
            _shallow_fetch(repo_url, sha, target)
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")[:512]
            return PinCheckResult(
                infra_errors=(
                    f"[{label}] fetch failed for {repo_url}@{sha[:8]}: {stderr}",
                )
            )
        except subprocess.TimeoutExpired:
            return PinCheckResult(
                infra_errors=(f"[{label}] fetch timed out for {repo_url}@{sha[:8]}",)
            )

        walk_root = target if not sub_path else target / sub_path
        if sub_path and not walk_root.is_dir():
            return PinCheckResult(
                findings=(
                    f"[{label}] sub-template subpath {sub_path!r} does not "
                    f"exist in {repo_url}@{sha[:8]} — pin may be stale",
                )
            )
        finding = _walk_for_disallowed(walk_root)
        if finding is not None:
            entry, kind = finding
            try:
                rel = entry.relative_to(walk_root).as_posix()
            except ValueError:
                rel = "<root>"
            scope_label = sub_path if sub_path else "<whole-tree>"
            return PinCheckResult(
                findings=(
                    f"[{label}] DISALLOWED ENTRY ({kind}) in {repo_url}@{sha[:8]} "
                    f"at walk_scope={scope_label} :: {rel} — runtime "
                    f"`template_cache.fetch()` will reject this pin for users",
                )
            )
    return PinCheckResult()


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True, timeout=5)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--offline-skip",
        action="store_true",
        help=(
            "Suppress infrastructure failures (git missing OR git fetch "
            "CalledProcessError / TimeoutExpired) and exit 0 instead of "
            "failing the build. Used by CI to keep the gate non-blocking "
            "when ephemeral runners can't reach github.com. REAL parity "
            "findings (disallowed-entry, missing sub-template subpath) "
            "still fail the build under --offline-skip; only the network "
            "/ tooling layer is suppressed."
        ),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if not _git_available():
        msg = "git not available; cannot perform pin-rotation parity check"
        if args.offline_skip:
            print(f"SKIP: {msg}")
            return 0
        print(f"ERROR: {msg}", file=sys.stderr)
        return 2

    known_bad = {(a, s): bl for (a, s, bl) in KNOWN_BAD_PINS}
    all_errors: list[str] = []
    waived: list[str] = []
    infra_errors: list[str] = []
    for adapter_id, sub_template_id, pin in all_pins():
        result = _check_pin(
            adapter_id,
            sub_template_id,
            pin["repo_url"],
            pin["sha"],
            verbose=args.verbose,
        )
        # Infrastructure failures (network / timeout) are tracked
        # separately from real parity findings. KNOWN_BAD_PINS only
        # waives REAL findings — a fetch failure on an allowlisted pin
        # is still an infra error, not a waiver.
        infra_errors.extend(result.infra_errors)
        if not result.findings:
            continue
        bl_ref = known_bad.get((adapter_id, sub_template_id))
        if bl_ref is not None:
            waived.extend(f"{f}  [WAIVED: {bl_ref}]" for f in result.findings)
        else:
            all_errors.extend(result.findings)

    if waived:
        print(
            f"upstream-pin-walk-scope-parity: {len(waived)} known-bad "
            f"finding(s) WAIVED via KNOWN_BAD_PINS allowlist:",
            file=sys.stderr,
        )
        for w in waived:
            print(f"  - {w}", file=sys.stderr)

    if infra_errors:
        # Always SURFACE infra errors so the operator sees them, but
        # under --offline-skip do not let them fail the build (the
        # workflow contract at v2-handshake-lint.yml says
        # GitHub-unreachable runners must not fail CI).
        label = "SKIP (--offline-skip)" if args.offline_skip else "INFRA"
        print(
            f"upstream-pin-walk-scope-parity: {len(infra_errors)} "
            f"infrastructure error(s) [{label}]:",
            file=sys.stderr,
        )
        for err in infra_errors:
            print(f"  - {err}", file=sys.stderr)

    if all_errors:
        print(
            "upstream-pin-walk-scope-parity: FAILED — "
            f"{len(all_errors)} new finding(s):",
            file=sys.stderr,
        )
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nFix options:\n"
            "  1. Rotate the pin to a SHA whose sub-template subtree is "
            "free of disallowed entries (record in "
            "docs/maintainers/upstream-pin-rotations.md per convention).\n"
            "  2. Update the adapter's `_SUB_PATHS` to point at a "
            "different subtree that is clean.\n"
            "  3. If the upstream changed shape AND rotation is out of "
            "scope for the current PR, add the (adapter_id, "
            "sub_template_id, BL-N) tuple to `KNOWN_BAD_PINS` with a BL "
            "tracking the rotation. This gate exists because BL-328 "
            "(Astro/marketing pin shipped with test-fixture symlinks "
            "under packages/) was discovered at user-runtime instead "
            "of at PR time.",
            file=sys.stderr,
        )
        return 1

    if infra_errors and not args.offline_skip:
        # Without --offline-skip, infrastructure failures still fail
        # the build (operators running locally want to see them).
        print(
            "upstream-pin-walk-scope-parity: INFRA FAIL — pass "
            "--offline-skip to ignore network/timeout flakes",
            file=sys.stderr,
        )
        return 2

    pin_count = sum(1 for _ in all_pins())
    skipped_label = (
        f", {len(infra_errors)} skipped (--offline-skip)"
        if infra_errors and args.offline_skip
        else ""
    )
    print(
        f"upstream-pin-walk-scope-parity: PASS "
        f"({pin_count} pin(s) checked, {len(waived)} waived{skipped_label})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
