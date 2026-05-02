"""C5: pid_identity.get_pid_start_time() returns ISO 8601 UTC sec-precision;
no platform-specific shell-out.

The CI lint asserts no /proc/<pid>/stat parsing or `ps -o lstart` shell-out
appears in the v2.0 codebase — we re-assert here as a sub-test that future
amendments don't reintroduce platform-specific shell-out.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pid_identity import get_pid_start_time

ISO_Z_SEC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_format_iso_utc_sec_precision():
    out = get_pid_start_time()
    assert ISO_Z_SEC.fullmatch(out), f"bad format: {out!r}"


def test_signature_no_args():
    """Layer 8 narrowing: get_pid_start_time accepts NO arbitrary pid argument."""
    import inspect
    sig = inspect.signature(get_pid_start_time)
    assert len(sig.parameters) == 0, (
        "get_pid_start_time must accept zero arguments at v2.0; widening "
        "to (pid: int, ...) is a v2.2 BL-223 change"
    )


def test_no_platform_specific_shellout_in_module():
    """CI lint asserts these patterns don't appear in CODE; re-assert as a
    unit test to catch reintroduction during amendment.

    Docstrings legitimately mention `/proc/` etc. as documentation of what
    psutil does cross-platform; we strip docstrings + comments before the
    grep so the test doesn't fight the doc.
    """
    import ast
    src = Path(__file__).resolve().parent.parent / "pid_identity.py"
    text = src.read_text(encoding="utf-8")

    # Strip line comments.
    code_lines = [ln.split("#", 1)[0] for ln in text.splitlines()]
    code_only = "\n".join(code_lines)

    # Strip docstrings via AST.
    tree = ast.parse(text)
    docstrings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            ds = ast.get_docstring(node, clean=False)
            if ds:
                docstrings.append(ds)
    for ds in docstrings:
        code_only = code_only.replace(ds, "")

    forbidden = (
        "/proc/", "ps -o lstart", "ps -p",
    )
    for pat in forbidden:
        assert pat not in code_only, (
            f"forbidden platform-specific pattern {pat!r} appeared in "
            f"pid_identity.py code (not just docstrings); "
            "psutil.Process().create_time() is the only sanctioned producer "
            "(HANDSHAKE §1.4)"
        )
