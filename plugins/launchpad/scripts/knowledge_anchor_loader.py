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

    Symlink resolution happens BEFORE read; ancestor-symlink rejection mirrors
    the §6 path validator's TOCTOU defense.
    """
    resolved = path.resolve(strict=True)
    plugins_root_real = plugins_root.resolve(strict=True)
    if not resolved.is_relative_to(plugins_root_real):
        raise ValueError(f"knowledge anchor escapes plugins root: {resolved}")
    if resolved.is_symlink():
        raise ValueError(f"knowledge anchor is symlink: {resolved}")
    cur = resolved
    while cur != plugins_root_real:
        if cur.is_symlink():
            raise ValueError(f"ancestor of knowledge anchor is symlink: {cur}")
        if cur.parent == cur:
            break
        cur = cur.parent

    buf = resolved.read_bytes()
    actual = hashlib.sha256(buf).hexdigest()
    if actual != expected_sha256:
        raise ValueError(
            f"checksum mismatch on {resolved}: expected {expected_sha256}, got {actual}"
        )
    return buf


__all__ = ["read_and_verify"]
