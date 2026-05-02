"""First-run marker consumption (HANDSHAKE §4 rule 10 strip-back substitute).

Per HANDSHAKE §1.5 + BL-235: the v2.0 marker is a simple positive-presence
empty file. Consumption is a single `os.rename(.first-run-marker,
.first-run-marker.consumed.<iso-sec-ts>)` under no lock (single-writer
assumption at single-maintainer scale).

The integrity-bound JSON envelope, dedicated lock, FD-based read, pre-rename
re-stat, and microsecond+pid timestamp suffix are ALL deferred to v2.2.

Marker semantic value at v2.0: presence signals `/lp-brainstorm` has run in
this cwd, authorizing the empty-nonce-ledger first-run fast path in
`/lp-scaffold-stack`. Standalone `/lp-pick-stack` invocations have no marker;
`/lp-scaffold-stack` then takes the slow path (full nonce-ledger check).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

MARKER_FILENAME = ".first-run-marker"
CONSUMED_PREFIX = ".first-run-marker.consumed."
CONSUMED_RETENTION = 5


def _launchpad_dir(repo_root: Path) -> Path:
    return repo_root / ".launchpad"


def marker_path(repo_root: Path) -> Path:
    return _launchpad_dir(repo_root) / MARKER_FILENAME


def consume_marker(repo_root: Path) -> Path | None:
    """Rename the marker to `.first-run-marker.consumed.<iso-sec-ts>` if present.

    Returns the consumed-marker Path on success, None if the marker was
    absent (standalone `/lp-pick-stack` invocation — slow-path scaffold-stack)
    or the rename failed (race / stale file; not a hard error at v2.0 strip-back).

    Per HANDSHAKE §4 rule 10 strip-back substitute: NO payload parse, NO
    integrity check, NO pre-rename re-stat (those defer to v2.2 BL-235).

    Retention: keeps at most 5 most-recent `.consumed.<ts>` files; older
    unlinked under no lock (single-process invocation model).
    """
    src = marker_path(repo_root)
    if not src.exists():
        return None
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    target = _launchpad_dir(repo_root) / f"{CONSUMED_PREFIX}{ts}"
    # Same-second collision protection (single-process model is rare; this is
    # belt+braces): suffix with .pid if target exists.
    if target.exists():
        target = _launchpad_dir(repo_root) / f"{CONSUMED_PREFIX}{ts}.{os.getpid()}"
    try:
        os.rename(str(src), str(target))
    except OSError:
        return None  # race or stale; proceed without consumption per spec

    _prune_consumed_markers(repo_root)
    return target


def _prune_consumed_markers(repo_root: Path) -> None:
    """Keep at most CONSUMED_RETENTION newest `.consumed.<ts>` files."""
    lp = _launchpad_dir(repo_root)
    if not lp.exists():
        return
    consumed = sorted(
        (p for p in lp.iterdir() if p.name.startswith(CONSUMED_PREFIX)),
        key=lambda p: p.name,
    )
    for old in consumed[:-CONSUMED_RETENTION]:
        try:
            old.unlink()
        except OSError:
            pass


def marker_present(repo_root: Path) -> bool:
    """True if an unconsumed `.first-run-marker` exists in `.launchpad/`."""
    return marker_path(repo_root).exists()


__all__ = [
    "CONSUMED_PREFIX",
    "CONSUMED_RETENTION",
    "MARKER_FILENAME",
    "consume_marker",
    "marker_path",
    "marker_present",
]
