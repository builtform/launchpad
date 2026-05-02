"""Stable SHA-256 over dict-shaped payloads via JSON canonicalization.

Per SCAFFOLD_HANDSHAKE.md §3. Sole responsibility: integrity envelope. Plugin-
shipped-asset loading lives in `knowledge_anchor_loader.py`.
"""
from __future__ import annotations

import hashlib
import json


def canonical_hash(payload: dict) -> str:
    """Stable SHA-256 over a dict-shaped payload via JSON canonicalization.

    JSON canonicalization is byte-deterministic across implementations:
    sort_keys + tight separators + ASCII escape + reject NaN/Infinity.
    """
    if not isinstance(payload, dict):
        raise ValueError(
            f"canonical_hash requires a dict payload, got {type(payload).__name__}"
        )
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["canonical_hash"]
