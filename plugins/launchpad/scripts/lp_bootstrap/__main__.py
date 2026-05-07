"""`python -m lp_bootstrap` argparse entry point.

v2.1 Codex PR #50 P1.D (D4): NEW. Provides a CLI wrapper around
`run_bootstrap()` so smoke-test harnesses can invoke the engine via the
package's __main__ module rather than poking the internal API. The
`--dry-run` flag short-circuits the render loop while still acquiring
and clearing the bootstrap sentinel — a useful sentinel-lifecycle
verification on a clean tmpdir.

Exit codes:
  0   success
  64  invalid argument (e.g., unknown mode)
  65  data error (e.g., engine returned a non-success outcome)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lp_bootstrap.engine import run_bootstrap


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lp_bootstrap",
        description=(
            "Materialize the v2.1 30-path infrastructure overlay. Used by "
            "/lp-bootstrap; this entrypoint is primarily for smoke tests."
        ),
    )
    p.add_argument(
        "--cwd", type=Path, default=Path.cwd(),
        help="Project root (default: current working directory).",
    )
    p.add_argument(
        "--mode",
        choices=("greenfield", "brownfield-auto", "refresh", "refresh-all", "recover"),
        default="greenfield",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Acquire+clear the bootstrap sentinel and exit without writing "
            "the manifest or rendering files. Sentinel-lifecycle smoke test."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_bootstrap(
            args.cwd,
            mode=args.mode,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001 — CLI surface absorbs all engine errors
        print(f"lp_bootstrap: error: {exc}", file=sys.stderr)
        return 65
    if result.outcome != "success":
        print(
            f"lp_bootstrap: outcome={result.outcome} "
            f"errors={result.errors!r}",
            file=sys.stderr,
        )
        return 65
    return 0


if __name__ == "__main__":
    sys.exit(main())
