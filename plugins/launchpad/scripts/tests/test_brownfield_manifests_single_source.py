"""HANDSHAKE §8 single-source enforcement for BROWNFIELD_MANIFESTS.

Three layers protect against drift between v1 (plugin-stack-detector.py)
and v2 (cwd_state.py):

1. Unit test (this file): identity check + grep against the v1 module source
   to ensure it does not redefine the constant.
2. CI lint grep (`plugin-v2-handshake-lint.py`): asserts only one definition
   site exists across `plugins/launchpad/scripts/`.
3. Import grep: asserts every reference outside `cwd_state.py` is via
   `from cwd_state import` (or the relative-import equivalent).
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load_stack_detector():
    """Load plugin-stack-detector.py via importlib.

    The hyphenated filename is not a valid Python module identifier, so we
    use the spec-from-file-location idiom.
    """
    src = _SCRIPTS / "plugin-stack-detector.py"
    spec = importlib.util.spec_from_file_location("plugin_stack_detector", src)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_v1_does_not_redefine_constant():
    """plugin-stack-detector.py must IMPORT BROWNFIELD_MANIFESTS, not redefine.

    See HANDSHAKE §8 single-source assertion #1.
    """
    mod = _load_stack_detector()
    src = inspect.getsource(mod)
    assert "BROWNFIELD_MANIFESTS = {" not in src, (
        "v1 must IMPORT BROWNFIELD_MANIFESTS, not redefine. See HANDSHAKE §8."
    )


def test_v1_identity_with_v2_constant():
    """The constant referenced from plugin-stack-detector is the same object
    as the one defined in cwd_state."""
    from cwd_state import BROWNFIELD_MANIFESTS as cwd_set

    mod = _load_stack_detector()
    assert getattr(mod, "BROWNFIELD_MANIFESTS", None) is cwd_set, (
        "plugin-stack-detector.BROWNFIELD_MANIFESTS must be the SAME object "
        "as cwd_state.BROWNFIELD_MANIFESTS (identity check)."
    )
