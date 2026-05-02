"""Forensic identity helper — `pid` + `pid_start_time` (HANDSHAKE §1.4).

Cross-platform via vendored psutil. Linux reads /proc/self/stat; macOS reads
via Mach kernel API; Windows reads via QueryProcessTimes. All produce a Unix
epoch float; we render to ISO 8601 UTC sec-precision (matches `generated_at`
format used elsewhere in v2.0).

Layer 8 narrowing: signature accepts NO arbitrary pid argument at v2.0. Only
own-process forensic identity is sanctioned. Cross-process forensic identity
(with PID-reuse race handling) deferred to v2.2 alongside `forensic_writer.py`
per BL-223 — at which point the signature MAY widen to accept
(pid: int, expected_start_time: float) for verified lookup.

Used inline at v2.0 by:
- the lefthook `commit-msg` hook (writes `restamp-history.jsonl`)
- `/lp-scaffold-stack` (writes `scaffold-rejection-<ts>.jsonl`)

`forensic_writer.py` (BL-223) will route these writers through a single
SRP-split module at v2.2; at v2.0 each writer calls this helper directly.
"""
from __future__ import annotations

from datetime import datetime, timezone

try:
    import psutil  # type: ignore[import-not-found]
    _PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]
    _PSUTIL_AVAILABLE = False


def get_pid_start_time() -> str:
    """Return the start time of the CURRENT process as ISO 8601 UTC sec-precision.

    No arguments by v2.0 contract — the caller cannot ask about an arbitrary
    PID. This closes the PID-reuse race for arbitrary-pid callers; v2.2 may
    widen with verified-lookup semantics.

    Per PR #41 cycle 11 #2 closure (Codex P1): psutil is now an optional
    dependency. The previous shape hard-failed at IMPORT time, blocking
    `git commit` on any fresh checkout where the user followed the
    documented `pnpm install` setup but hadn't yet run `pip install -r
    plugins/launchpad/scripts/requirements.txt`. The lefthook commit-msg
    hook is the regression vector — it imports this module on every
    commit. When psutil is unavailable, we fall back to a "process-start"
    sentinel string. Callers that want strict semantics check
    `psutil_available()` first.
    """
    if not _PSUTIL_AVAILABLE:
        # Forensic identity unavailable — emit a stable placeholder so
        # downstream JSONL writes don't crash. Restamp-history entries
        # written under this fallback are still well-formed; only the
        # `pid_start_time` field carries the placeholder.
        return "psutil-unavailable"
    return datetime.fromtimestamp(
        psutil.Process().create_time(), tz=timezone.utc  # type: ignore[union-attr]
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def psutil_available() -> bool:
    """Return True iff psutil is importable.

    Strict-mode callers (e.g., scaffold-rejection forensic writers) can
    use this to decide whether to refuse the operation OR proceed with
    a placeholder pid_start_time.
    """
    return _PSUTIL_AVAILABLE


__all__ = ["get_pid_start_time", "psutil_available"]
