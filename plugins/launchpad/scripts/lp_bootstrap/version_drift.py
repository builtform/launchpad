"""Shared version_drift_log schema (v2.1 Codex PR #50 D7).

Owns the single canonical 5-key shape that BOTH `/lp-bootstrap` and
`/lp-update-identity` emit when appending a `version_drift_log` entry to
`scaffold-decision.json`. Cross-writer consistency removes the prior
two-writer drift risk where bootstrap and identity-update could land
divergent shapes.

Tagged-union return type:

    Names      — list of changed-field names (PII opt-in: true)
    Fingerprint — sha256 prefix of canonicalized name list
                 (PII opt-in: false)

Writer-side serialization rule:

    Names       -> entry["fields_changed"]: list[str]
    Fingerprint -> entry["fields_changed_fingerprint"]: str

v2.2 BL: this module relocates to `lp_shared/audit_log.py`. Importers
should expect a one-line import-path change with stable signature.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Union


@dataclass(frozen=True)
class Names:
    """Tagged variant: changed-field names sealed verbatim."""
    names: tuple[str, ...]


@dataclass(frozen=True)
class Fingerprint:
    """Tagged variant: 16-char sha256 prefix over canonicalized names.

    Layout: literal `"sha256:"` prefix + 16 lowercase hex chars (so the
    field is parseable as a tagged digest by future readers).
    """
    digest: str


ChangedFields = Union[Names, Fingerprint]


def _canonical_names(names: tuple[str, ...]) -> str:
    return ",".join(sorted(set(names)))


def _fingerprint(names: tuple[str, ...]) -> str:
    canonical = _canonical_names(names).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()[:16]


def compute_identity_fields_changed(
    prior: Mapping[str, str],
    current: Mapping[str, str],
    *,
    pii_opt_in: bool,
) -> ChangedFields:
    """Domain-agnostic key-diff with PII redaction.

    Works on any `Mapping[str, str]` (identity field maps OR version
    metadata maps). Helper owns redaction internally — callers never
    choose which key (`fields_changed` vs `fields_changed_fingerprint`)
    appears in the serialized entry; that follows mechanically from the
    returned variant tag.

    The diff treats two values as different when their string equality
    differs OR when one side is missing the key entirely.

    v2.2 BL: this function relocates to `lp_shared/audit_log.py`;
    importers should expect a one-line import-path change with stable
    signature.
    """
    keys = set(prior.keys()) | set(current.keys())
    changed: list[str] = []
    for key in sorted(keys):
        if prior.get(key) != current.get(key):
            changed.append(key)
    names_tuple = tuple(changed)
    if pii_opt_in:
        return Names(names=names_tuple)
    return Fingerprint(digest=_fingerprint(names_tuple))


__all__ = [
    "ChangedFields",
    "Fingerprint",
    "Names",
    "compute_identity_fields_changed",
]
