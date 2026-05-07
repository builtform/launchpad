"""v2.1.0 completion plan §4.1 short-write regression.

POSIX `write(2)` is permitted to perform a short write — `os.write(fd,
data)` may return a count smaller than `len(data)`. The pre-v2.1.0
sites at `atomic_write_excl` / `atomic_write_replace` /
`atomic_write_replace_batch` called `os.write` once and silently
truncated; this test asserts the new `_write_all` loop drains the full
payload across multiple syscalls.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import atomic_io  # noqa: E402


def test_write_all_handles_short_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Monkeypatch `os.write` to return 1 byte at a time and assert the
    full payload lands on disk via `atomic_write_excl`."""
    target = tmp_path / "out.txt"
    payload = b"hello, world! " * 32  # ~440 bytes

    real_write = atomic_io.os.write
    call_count = [0]

    def short_write(fd: int, data) -> int:
        call_count[0] += 1
        if isinstance(data, memoryview):
            data = bytes(data)
        if not data:
            return 0
        return real_write(fd, data[:1])

    monkeypatch.setattr(atomic_io.os, "write", short_write)
    atomic_io.atomic_write_excl(target, payload)
    assert target.read_bytes() == payload
    assert call_count[0] >= len(payload), (
        f"expected ≥{len(payload)} short-write calls, got {call_count[0]}"
    )


def test_write_all_raises_on_zero_return() -> None:
    """`_write_all` raises `OSError` if `os.write` returns 0 — guards
    against a misbehaved kernel pretending the write succeeded while
    not advancing the cursor."""
    import os
    rd, wr = os.pipe()
    try:
        with pytest.raises(OSError):
            # Force the helper into a corner: monkeypatch os.write at the
            # module surface to always return 0 so the loop can't make
            # progress.
            saved = atomic_io.os.write
            atomic_io.os.write = lambda fd, buf: 0  # type: ignore[assignment]
            try:
                atomic_io._write_all(wr, b"x")
            finally:
                atomic_io.os.write = saved  # type: ignore[assignment]
    finally:
        os.close(rd)
        os.close(wr)


def test_write_all_full_write_path() -> None:
    """When `os.write` returns the full length, `_write_all` makes
    exactly one syscall."""
    import os
    rd, wr = os.pipe()
    try:
        atomic_io._write_all(wr, b"abc")
        os.close(wr)
        wr = -1
        chunk = os.read(rd, 16)
        assert chunk == b"abc"
    finally:
        os.close(rd)
        if wr != -1:
            os.close(wr)
