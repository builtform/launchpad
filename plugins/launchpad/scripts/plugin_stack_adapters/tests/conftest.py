"""Shared pytest configuration for the v2.0 adapter test suite.

Adds `plugins/launchpad/scripts/` to sys.path so the adapter tests can
`from plugin_stack_adapters.<stack>_adapter import run` without a separate
package install. Mirrors the convention used by the Phase -1 library tests
under `plugins/launchpad/scripts/tests/`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
