"""Phase 11 v3.1 -- E2E brownfield re-entry pipeline (DA1).

Drives `/lp-define` over an existing brownfield repo + asserts idempotent
re-entry. Scope per Phase 11 plan section 4 Slice B step 2:

  - First-run /lp-define populates the seven canonical doc artifacts.
  - Second-run with `force=True` writes byte-identical content (no
    clobber, no diff, no PII WARN false positives, no sentinel leakage).

Brownfield is simulated via a `package.json` + `pyproject.toml` shape so
the stack detector returns a non-empty stacks list. Identity preservation
is validated via `lp_update_identity.engine.PII_WARN_LINES` import (the
public Phase 10 amendment surface) -- the brownfield re-run does NOT call
update-identity, so the WARN should not appear in stderr.
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from lp_bootstrap import LAUNCHPAD_DIR_NAME  # noqa: E402
from lp_bootstrap import SENTINEL_NAME as _BOOTSTRAP_SENTINEL_NAME  # noqa: E402
from lp_define_runner import generate as define_generate  # noqa: E402
from lp_scaffold_stack.sentinel import (  # noqa: E402
    SCAFFOLD_STACK_SENTINEL_NAME as _SCAFFOLD_STACK_SENTINEL_NAME,
)
from lp_update_identity import (  # noqa: E402
    IDENTITY_UPDATE_SENTINEL_NAME as _IDENTITY_UPDATE_SENTINEL_NAME,
)
from lp_update_identity.engine import PII_WARN_LINES  # noqa: E402


def _build_brownfield_repo(repo_root: Path) -> None:
    """Lay down a minimal Next.js + Express brownfield shape so the
    stack detector returns ts_monorepo without spawning real tooling."""
    (repo_root / "package.json").write_text(
        json.dumps({
            "name": "v21-brownfield-fixture",
            "version": "1.0.0",
            "dependencies": {
                "next": "15.0.0",
                "express": "4.18.0",
                "react": "18.0.0",
            },
        }),
        encoding="utf-8",
    )
    (repo_root / "README.md").write_text(
        "# v21 brownfield fixture\n\nNext.js + Express monorepo.\n",
        encoding="utf-8",
    )


def _read_doc_snapshot(repo_root: Path) -> dict[str, str]:
    """Capture byte content of the doc artifacts /lp-define renders."""
    docs_dir = repo_root / "docs"
    out: dict[str, str] = {}
    if not docs_dir.exists():
        return out
    for p in sorted(docs_dir.rglob("*.md")):
        out[str(p.relative_to(repo_root))] = p.read_text(encoding="utf-8")
    return out


def test_brownfield_idempotent_define_re_entry(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """First /lp-define run populates docs; second run with force=True
    is a no-op write (byte-identical content)."""
    repo_root = tmp_path
    os.chmod(repo_root, 0o700)
    _build_brownfield_repo(repo_root)

    # First run: must create the doc artifacts.
    rc1 = define_generate(repo_root, force=True, emit_trust_banner=False)
    assert rc1 == 0, f"first /lp-define run returned non-zero: {rc1}"

    snapshot1 = _read_doc_snapshot(repo_root)
    assert snapshot1, "no docs/*.md emitted by first /lp-define run"
    assert any("docs/architecture/TECH_STACK.md" in k for k in snapshot1), (
        "TECH_STACK.md missing from first-run snapshot"
    )

    # Second run with force=True must be byte-identical.
    captured_first = capsys.readouterr()  # drain captured output

    rc2 = define_generate(repo_root, force=True, emit_trust_banner=False)
    assert rc2 == 0, f"second /lp-define run returned non-zero: {rc2}"
    snapshot2 = _read_doc_snapshot(repo_root)

    assert snapshot1 == snapshot2, (
        "second /lp-define run produced a content diff; not idempotent. "
        f"changed_files="
        f"{[k for k in snapshot1 if snapshot1[k] != snapshot2.get(k)]}"
    )

    # PII WARN must NOT appear in stderr -- /lp-define never mutates
    # identity, so the WARN print path (lp_update_identity) is unreached.
    captured = capsys.readouterr()
    pii_warn_first_line = PII_WARN_LINES[0]
    assert pii_warn_first_line not in captured.err, (
        f"PII WARN leaked into /lp-define stderr (false positive): "
        f"{pii_warn_first_line!r}"
    )

    # Sentinel files (lp-bootstrap + lp-update-identity + lp-scaffold-stack)
    # must not exist post-/lp-define -- the runner does not stage any of
    # these sentinels. Filenames sourced from each package's canonical
    # constants (Phase 11 hardening A3: prior literal strings used a
    # `lp-` prefix not present in the actual constants, so two of three
    # assertions were tautologically true and could not catch regressions).
    launchpad_dir = repo_root / LAUNCHPAD_DIR_NAME
    for sentinel_filename in (
        _BOOTSTRAP_SENTINEL_NAME,
        _IDENTITY_UPDATE_SENTINEL_NAME,
        _SCAFFOLD_STACK_SENTINEL_NAME,
    ):
        sentinel_path = launchpad_dir / sentinel_filename
        assert not sentinel_path.exists(), (
            f"unexpected sentinel after /lp-define re-entry: {sentinel_path}"
        )
