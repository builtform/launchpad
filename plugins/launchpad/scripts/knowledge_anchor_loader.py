"""Atomic read-and-verify for plugin-shipped knowledge-anchor pattern docs
(HANDSHAKE §9.2).

Splits from `decision_integrity.py` per SRP — integrity envelope vs.
plugin-shipped-asset loading are distinct concerns. Curate-mode scaffolders
pin pattern docs by `knowledge_anchor_sha256`; this helper closes the TOCTOU
window between read-time hash check and consumption.

Callers MUST pass the returned bytes (never the path) into Claude's context
constructor.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def read_and_verify(
    path: Path,
    expected_sha256: str,
    plugins_root: Path,
) -> bytes:
    """Read a plugin-shipped trusted file once, hash the buffer, return buffer.

    Symlink rejection runs on the ORIGINAL `path` and each of its ORIGINAL
    ancestors BEFORE any `resolve()` call — `resolve(strict=True)` would
    dereference symlinks transparently, which renders any post-resolve
    `is_symlink()` check dead code. The pre-resolve walk mirrors the §6 path
    validator's TOCTOU defense and refuses ANY symlink in the original path
    chain, even one that resolves to a target inside `plugins_root`.

    `lstat()` is used (not `stat()`) so a symlink reports `S_ISLNK` rather
    than its target's mode.
    """
    import os
    import stat as stat_module

    plugins_root_real = plugins_root.resolve(strict=True)

    # Pre-resolve walk: refuse the original path or any of its ancestors if
    # any component is a symlink. Walks UP from `path`'s absolute form to the
    # filesystem root; bounded by `plugins_root_real` only as a stopping
    # heuristic — if the original path is OUTSIDE plugins_root entirely, we
    # still walk to root (which is unreachable via symlinks anyway).
    original_abs = path if path.is_absolute() else (Path.cwd() / path)
    cur = original_abs
    while True:
        # lstat raises FileNotFoundError if `cur` doesn't exist; that's OK —
        # the subsequent resolve(strict=True) will raise the same way and
        # the caller treats both as a missing-anchor failure.
        try:
            cur_stat = os.lstat(cur)
        except FileNotFoundError:
            break
        if stat_module.S_ISLNK(cur_stat.st_mode):
            raise ValueError(
                f"knowledge anchor path or ancestor is a symlink: {cur}"
            )
        parent = cur.parent
        if parent == cur:  # reached filesystem root
            break
        cur = parent

    # Now safe to resolve and hash; resolve verifies existence too.
    resolved = original_abs.resolve(strict=True)
    if not resolved.is_relative_to(plugins_root_real):
        raise ValueError(f"knowledge anchor escapes plugins root: {resolved}")

    buf = resolved.read_bytes()
    actual = hashlib.sha256(buf).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            f"checksum mismatch on {resolved}: expected {expected_sha256}, got {actual}"
        )
    return buf


__all__ = ["read_and_verify"]
