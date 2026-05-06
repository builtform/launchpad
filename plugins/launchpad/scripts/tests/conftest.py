"""Phase 8.5 Slice D: shared pytest fixtures for the v2.1 /lp-define
orchestrator (lp_define_runner.py).

`lp_define_invoke` -- session-scoped fixture wrapping the new orchestration
entrypoint. Tests that previously called the legacy plugin-doc-generator
via subprocess can use this fixture to invoke `lp_define_runner.generate`
in-process, amortizing renderer instantiation across the test session.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
_VENDOR = _SCRIPTS / "plugin_stack_adapters" / "_vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


@pytest.fixture(scope="session")
def lp_define_invoke():
    """Return a callable `(repo_root, **kwargs) -> int` that invokes the
    v2.1 /lp-define orchestrator in-process. Emits banner suppressed by
    default; callers can override by passing `emit_trust_banner=True`.

    Phase 8.5 plan section 2.1 surface for test_define + test_pipeline_matrix
    migrations. Renderer environment instantiation amortizes across the
    test session via the LpDefineRenderer's loader cache.
    """
    import lp_define_runner

    def _invoke(repo_root: Path, **kwargs) -> int:
        kwargs.setdefault("emit_trust_banner", False)
        return lp_define_runner.generate(repo_root, **kwargs)

    return _invoke
