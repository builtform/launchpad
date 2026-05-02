#!/usr/bin/env python3
"""Receipt loader/validator for `/lp-define` (HANDSHAKE §5 + §12).

Loads `.launchpad/scaffold-receipt.json`, validates its schema + integrity
envelope (SHA-256 self-hash), and returns the parsed dict for downstream
adapter dispatch. Carries the version-policy constants per HANDSHAKE §10:

  - ACCEPTED_RECEIPT_VERSIONS: frozenset of versions this consumer accepts
    (single-element at v2.0; expanded under BL-211 v2.2 forward-compat policy).
  - WRITTEN_RECEIPT_VERSION: version this writer stamps on new receipts.

Strict-equality enforcement at v2.0 — unknown version → hard reject with
`reason: "version_unsupported"`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from decision_integrity import canonical_hash

# v2.0 single-element frozensets per HANDSHAKE §10. Coordinated bump applied
# at v2.0.0 ship: "0.x-test" → "1.0".
ACCEPTED_RECEIPT_VERSIONS = frozenset({"1.0"})
WRITTEN_RECEIPT_VERSION = "1.0"


REQUIRED_FIELDS = (
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


class ReceiptValidationError(ValueError):
    """Receipt failed schema or integrity validation. Carries `reason` for
    the §4-style structured rejection log."""

    def __init__(self, message: str, reason: str):
        super().__init__(f"{reason}: {message}")
        self.reason = reason


def load_receipt(receipt_path: Path) -> dict:
    """Read + validate `scaffold-receipt.json`. Returns the parsed dict.

    Raises ReceiptValidationError with structured `.reason` on any failure:
    - file_not_found
    - parse_error
    - missing_field (with field name in message)
    - version_unsupported (with seen_version)
    - sha256_mismatch
    """
    if not receipt_path.is_file():
        raise ReceiptValidationError(
            f"receipt file does not exist: {receipt_path}",
            reason="file_not_found",
        )

    try:
        text = receipt_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceiptValidationError(str(exc), reason="parse_error") from exc

    if not isinstance(data, dict):
        raise ReceiptValidationError(
            f"receipt root must be an object, got {type(data).__name__}",
            reason="parse_error",
        )

    for field in REQUIRED_FIELDS:
        if field not in data:
            raise ReceiptValidationError(
                f"missing required field: {field}",
                reason="missing_field",
            )

    seen_version = data.get("version")
    if seen_version not in ACCEPTED_RECEIPT_VERSIONS:
        raise ReceiptValidationError(
            f"receipt version {seen_version!r} not in ACCEPTED_RECEIPT_VERSIONS "
            f"({sorted(ACCEPTED_RECEIPT_VERSIONS)})",
            reason="version_unsupported",
        )

    # SHA-256 self-hash: canonical_hash over payload with `sha256` removed.
    expected = data["sha256"]
    payload = {k: v for k, v in data.items() if k != "sha256"}
    actual = canonical_hash(payload)
    if actual != expected:
        raise ReceiptValidationError(
            f"receipt sha256 mismatch: expected {expected}, computed {actual}",
            reason="sha256_mismatch",
        )

    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "receipt",
        nargs="?",
        default=".launchpad/scaffold-receipt.json",
        help="Path to scaffold-receipt.json (default: .launchpad/scaffold-receipt.json)",
    )
    parser.add_argument(
        "--show-version-policy", action="store_true",
        help="Print ACCEPTED_RECEIPT_VERSIONS + WRITTEN_RECEIPT_VERSION and exit.",
    )
    args = parser.parse_args()

    if args.show_version_policy:
        print(json.dumps({
            "ACCEPTED_RECEIPT_VERSIONS": sorted(ACCEPTED_RECEIPT_VERSIONS),
            "WRITTEN_RECEIPT_VERSION": WRITTEN_RECEIPT_VERSION,
        }, indent=2))
        return 0

    try:
        data = load_receipt(Path(args.receipt))
    except ReceiptValidationError as exc:
        print(json.dumps({
            "outcome": "rejected",
            "reason": exc.reason,
            "message": str(exc),
        }), file=sys.stderr)
        return 1

    print(json.dumps({
        "outcome": "accepted",
        "version": data["version"],
        "decision_sha256": data["decision_sha256"],
        "layers_materialized_count": len(data["layers_materialized"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
