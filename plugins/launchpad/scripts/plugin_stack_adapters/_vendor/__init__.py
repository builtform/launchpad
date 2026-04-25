"""Vendored dependencies for the LaunchPad plugin's canonical-doc generators.

Currently bundles: jinja2 3.1.6 + markupsafe 3.0.3 (pure-Python only — the
compiled _speedups.so is intentionally removed so the vendor bundle is
cross-platform and deterministic).

Total size ~600KB. No network at plugin-install time, no user pip install,
no C extensions.

Usage:
    from plugin_stack_adapters._vendor import enable
    enable()
    import jinja2
"""
from __future__ import annotations

import sys
from pathlib import Path

_VENDOR_DIR = Path(__file__).resolve().parent
_ENABLED = False


def enable() -> None:
    """Prepend the vendor dir to sys.path so `import jinja2` finds the vendored copy.

    Idempotent. Safe to call multiple times.
    """
    global _ENABLED
    if _ENABLED:
        return
    vendor_str = str(_VENDOR_DIR)
    if vendor_str not in sys.path:
        sys.path.insert(0, vendor_str)
    _ENABLED = True
