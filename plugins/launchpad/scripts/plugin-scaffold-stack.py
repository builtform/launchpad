#!/usr/bin/env python3
"""/lp-scaffold-stack CLI orchestrator (HANDSHAKE §4 + §5 consumer).

Top-level CLI for the v2.0 scaffold-stack pipeline. Imports the
`lp_scaffold_stack.engine.run_pipeline()` entrypoint and surfaces a POSIX
exit code per the §4 reason enum.

Exit codes:
  0 — success (outcome=completed)
  1 — validation rejection (outcome=aborted) OR partial-failure (outcome=failed)
  2 — argument-parsing error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make sibling-script imports work when invoked directly.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lp_scaffold_stack.engine import (  # noqa: E402
    DEFAULT_CATEGORY_PATTERNS_YML,
    DEFAULT_PLUGINS_ROOT,
    DEFAULT_SCAFFOLDERS_YML,
    Outcome,
    run_pipeline,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="/lp-scaffold-stack — consumes scaffold-decision.json, "
                    "materializes layers, writes scaffold-receipt.json.",
    )
    parser.add_argument(
        "--cwd", type=Path, default=Path.cwd(),
        help="Working directory (defaults to CWD).",
    )
    parser.add_argument(
        "--decision-file", type=Path, default=None,
        help="Override .launchpad/scaffold-decision.json path.",
    )
    parser.add_argument(
        "--scaffolders-yml", type=Path, default=DEFAULT_SCAFFOLDERS_YML,
        help="Override the scaffolders catalog path (test/CI hook).",
    )
    parser.add_argument(
        "--category-patterns-yml", type=Path, default=DEFAULT_CATEGORY_PATTERNS_YML,
        help="Override the category-patterns catalog path (test/CI hook).",
    )
    parser.add_argument(
        "--plugins-root", type=Path, default=DEFAULT_PLUGINS_ROOT,
        help="Override the LaunchPad repo root for knowledge-anchor reads.",
    )
    parser.add_argument(
        "--no-telemetry", action="store_true",
        help="Skip telemetry writes for this invocation.",
    )
    parser.add_argument(
        "--skip-greenfield-gate", action="store_true",
        help="Internal/test hook: bypass cwd_state greenfield check.",
    )
    args = parser.parse_args(argv)

    result = run_pipeline(
        args.cwd,
        decision_file_path=args.decision_file,
        scaffolders_yml=args.scaffolders_yml,
        category_patterns_yml=args.category_patterns_yml,
        plugins_root=args.plugins_root,
        skip_greenfield_gate=args.skip_greenfield_gate,
        write_telemetry_flag=not args.no_telemetry,
    )

    if result.success:
        print(
            f"/lp-scaffold-stack: {Outcome.COMPLETED} in {result.elapsed_seconds:.2f}s "
            f"(layers={len(result.layers_materialized)}, "
            f"secret_scan_passed={result.secret_scan_passed})"
        )
        if result.receipt_path is not None:
            print(f"receipt: {result.receipt_path}")
        return 0

    # Failure path — surface structured reason/message + log paths so the
    # user can diagnose without grepping the JSONL audit log themselves
    # (PR #41 cycle 3 #5 — closed silent-CLI-exit bug).
    print(
        f"/lp-scaffold-stack: {result.outcome}"
        f"{f' reason={result.reason!r}' if result.reason else ''}"
        f"{f' — {result.message}' if result.message else ''}",
        file=sys.stderr,
    )
    if result.failed_record_path is not None:
        print(f"partial-cleanup record: {result.failed_record_path}", file=sys.stderr)
    if result.rejection_log_path is not None:
        print(f"rejection log: {result.rejection_log_path}", file=sys.stderr)
    if result.outcome == Outcome.ABORTED:
        return 1
    # Outcome.FAILED — partial-cleanup recorded.
    return 1


if __name__ == "__main__":
    sys.exit(main())
