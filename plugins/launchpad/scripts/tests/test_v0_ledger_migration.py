"""C1 (Layer 5 P1-DM5-1 + Layer 7 closure): v0 ledger migration with orphan
.scaffold-nonces.log.migration-tmp.<old-pid> cleanup.

Pre-write a header-less ledger with 3 valid UUID lines + a stray orphan tmp
file; on first scaffold-stack invocation, ledger gains the v1 header AND
all 3 prior nonces preserved AND orphan tmp is unlinked.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_scaffold_stack.nonce_ledger import (
    _FORMAT_HEADER,
    is_nonce_seen,
    ledger_path,
)


def test_v0_migration_with_orphan_cleanup(tmp_path: Path):
    lp = tmp_path / ".launchpad"
    lp.mkdir(parents=True, exist_ok=True)
    ledger = lp / ".scaffold-nonces.log"
    nonces = ["1" * 32, "2" * 32, "3" * 32]
    ledger.write_text("\n".join(nonces) + "\n", encoding="utf-8")

    # Stray orphan from a prior crashed acquisition.
    orphan = lp / ".scaffold-nonces.log.migration-tmp.99999"
    orphan.write_text("orphan-debris\n", encoding="utf-8")
    assert orphan.exists()

    # Triggering ANY ledger op migrates the v0 ledger + cleans orphan tmps.
    is_nonce_seen("0" * 32, tmp_path)

    # Ledger now has format header AND all 3 prior nonces.
    text = ledger.read_text(encoding="utf-8")
    assert text.startswith(_FORMAT_HEADER)
    for n in nonces:
        assert n in text

    # Orphan migration-tmp gone.
    assert not orphan.exists()

    # Rollover-tmp pattern would be UNTOUCHED (disjoint glob scope per
    # Layer 8 pin) — verify by pre-writing one and re-running.
    rollover_orphan = lp / ".scaffold-nonces.log.rollover-tmp.99998"
    rollover_orphan.write_text("rollover-orphan\n", encoding="utf-8")
    is_nonce_seen("4" * 32, tmp_path)
    assert rollover_orphan.exists(), "migration cleanup must NOT touch rollover-tmp pattern"
