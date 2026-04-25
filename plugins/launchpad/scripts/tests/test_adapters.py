#!/usr/bin/env python3
"""Validate every concrete adapter's output against contracts.py.

Prevents per-stack Jinja2 template breakage caused by adapter drift. Every
adapter must return the full AdapterOutput shape with all required fields.

Run:
  python3 plugins/launchpad/scripts/tests/test_adapters.py

Exit 0 on pass, 1 on failure.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import get_args, get_type_hints

# Make plugin_stack_adapters importable as a module
PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_SCRIPTS))

from plugin_stack_adapters import generic, go_cli, polyglot, python_django, ts_monorepo  # noqa: E402
from plugin_stack_adapters.contracts import (  # noqa: E402
    AdapterOutput,
    AppFlowInfo,
    BackendInfo,
    CommandsConfig,
    FrontendInfo,
    PipelineOverrides,
    ProductContextInfo,
    TechStackInfo,
)

ADAPTERS = [
    ("ts_monorepo", ts_monorepo),
    ("python_django", python_django),
    ("go_cli", go_cli),
    ("generic", generic),
]


def _check_typed_dict(obj: dict, expected_type: type, context: str, errors: list[str]) -> None:
    """Shallow TypedDict validation — every required key present, no extras."""
    if not isinstance(obj, dict):
        errors.append(f"{context}: expected dict, got {type(obj).__name__}")
        return
    hints = get_type_hints(expected_type)
    # TypedDict doesn't expose required vs NotRequired at runtime reliably in
    # all Python versions; use __required_keys__ when available.
    required = getattr(expected_type, "__required_keys__", set(hints.keys()))
    for key in required:
        if key not in obj:
            errors.append(f"{context}: missing required key {key!r}")


def test_adapter(name: str, module) -> list[str]:
    errors: list[str] = []
    ctx = f"adapter={name}"

    # Run aggregated output
    output = module.run()
    _check_typed_dict(output, AdapterOutput, ctx, errors)

    # Validate nested sections
    _check_typed_dict(output["tech_stack"], TechStackInfo, f"{ctx}.tech_stack", errors)
    _check_typed_dict(output["backend"], BackendInfo, f"{ctx}.backend", errors)
    if output["frontend"] is not None:
        _check_typed_dict(output["frontend"], FrontendInfo, f"{ctx}.frontend", errors)
    if output["app_flow"] is not None:
        _check_typed_dict(output["app_flow"], AppFlowInfo, f"{ctx}.app_flow", errors)
    _check_typed_dict(output["product_context"], ProductContextInfo, f"{ctx}.product_context", errors)
    _check_typed_dict(output["commands"], CommandsConfig, f"{ctx}.commands", errors)
    # PipelineOverrides is total=False; no required keys to check.

    # Commands must be lists (always-array schema)
    for key in ("test", "typecheck", "lint", "format", "build"):
        val = output["commands"][key]
        if not isinstance(val, list):
            errors.append(f"{ctx}.commands.{key}: expected list, got {type(val).__name__}")
        elif not all(isinstance(v, str) for v in val):
            errors.append(f"{ctx}.commands.{key}: all entries must be strings")

    # stack_id must match the adapter's module
    if output["stack_id"] != name:
        errors.append(f"{ctx}.stack_id={output['stack_id']!r} != adapter name {name!r}")

    return errors


def test_polyglot_composer() -> list[str]:
    errors: list[str] = []

    # Single-stack input → fast path (no merging)
    single = polyglot.compose(["ts_monorepo"])
    if single["stack_id"] != "ts_monorepo":
        errors.append(f"polyglot single-stack: expected stack_id=ts_monorepo, got {single['stack_id']!r}")

    # Polyglot shape: TS + Python
    merged = polyglot.compose(["python_django", "ts_monorepo"])  # precedence should reorder
    if merged["stack_id"] != "ts_monorepo":
        errors.append(f"polyglot: expected ts_monorepo to win precedence, got {merged['stack_id']!r}")

    # commands.test must contain BOTH suites (polyglot composition)
    test_cmds = merged["commands"]["test"]
    if "pnpm test" not in test_cmds:
        errors.append(f"polyglot.commands.test missing 'pnpm test': {test_cmds}")
    if "pytest" not in test_cmds:
        errors.append(f"polyglot.commands.test missing 'pytest': {test_cmds}")

    # Pipeline overrides: if Python says frontend_docs_enabled=False, merged should respect
    if merged["pipeline_overrides"].get("frontend_docs_enabled") is not False:
        errors.append(
            f"polyglot.pipeline_overrides: restrictive merge should set frontend_docs_enabled=False "
            f"when any adapter requests it (got {merged['pipeline_overrides']})"
        )

    # Frontend should come from ts_monorepo (precedence winner, non-None)
    if merged["frontend"] is None:
        errors.append("polyglot.frontend: expected TS frontend info, got None")

    # stack_summary should concatenate
    if "+" not in merged["product_context"]["stack_summary"]:
        errors.append(
            f"polyglot.product_context.stack_summary: expected concatenated summary, got "
            f"{merged['product_context']['stack_summary']!r}"
        )

    # Empty input should error
    try:
        polyglot.compose([])
        errors.append("polyglot.compose([]): expected ValueError, got success")
    except ValueError:
        pass

    return errors


def main() -> int:
    all_errors: list[str] = []

    for name, mod in ADAPTERS:
        errs = test_adapter(name, mod)
        all_errors.extend(errs)

    all_errors.extend(test_polyglot_composer())

    if all_errors:
        print("FAIL: adapter contract validation")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print(f"PASS: adapter contracts ({len(ADAPTERS)} concrete + polyglot composer)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
