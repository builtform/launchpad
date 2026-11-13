#!/usr/bin/env python3
"""Exit when a role-written inbox file is new or changed."""

from __future__ import annotations

import argparse
import math
import os
import stat
import sys
import time
from pathlib import Path

Snapshot = dict[str, tuple[int, int]]


def snapshot(roots: list[Path]) -> Snapshot:
    files: Snapshot = {}
    for root in roots:
        for inbox in sorted(root.glob("inbox-*")):
            if not inbox.is_dir():
                continue
            for path in sorted(inbox.iterdir()):
                if path.name.startswith(("verdict-", "ruling-", ".")):
                    continue
                try:
                    info = path.stat()
                except FileNotFoundError:
                    continue
                if stat.S_ISREG(info.st_mode):
                    files[str(path)] = (info.st_mtime_ns, info.st_size)
    return files


def read_state(path: Path) -> Snapshot | None:
    try:
        files: Snapshot = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            mtime, size, name = line.split("\t", 2)
            files[name] = (int(mtime), int(size))
        return files
    except (OSError, ValueError, UnicodeError):
        return None


def write_state(path: Path, files: Snapshot) -> None:
    path.write_text(
        "".join(f"{mtime}\t{size}\t{name}\n" for name, (mtime, size) in files.items()),
        encoding="utf-8",
    )


def interval_seconds(value: str) -> float:
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("interval must be a finite positive number")
    return seconds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=interval_seconds, default=30.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("roots", metavar="ROOT", type=Path, nargs="+")
    args = parser.parse_args()
    roots = [root.resolve() for root in args.roots]
    for root in roots:
        if not root.is_dir():
            parser.error(f"ROOT is not a directory: {root}")
    state = roots[0] / ".watch-state"
    try:
        baseline = read_state(state)
        if baseline is None:
            baseline = snapshot(roots)
            write_state(state, baseline)
        print(f"watching pid={os.getpid()} state={state}", flush=True)
        while True:
            current = snapshot(roots)
            changed = [
                name for name, info in current.items() if baseline.get(name) != info
            ]
            if changed:
                for name in changed:
                    print(f"CHANGED {name}", flush=True)
                write_state(state, current)
                return 0
            if args.once:
                return 1
            time.sleep(args.interval)
    except OSError as error:
        print(f"watch error: {error}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
