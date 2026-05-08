"""Verify scaffold-stack sentinel is acquired BEFORE adapter dispatch.

Phase 1 (cycle 5 F1 P0): the sentinel must be written before any
filesystem materialization to prevent concurrent invocations from
racing through the greenfield gate.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


ENGINE_PATH = _SCRIPTS_DIR / "lp_scaffold_stack" / "engine.py"


def _find_call_lineno(tree: ast.Module, func_name: str, call_substr: str) -> int | None:
    """Find the first line number of a Call node matching `call_substr`
    inside the function `func_name`.
    """
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != func_name:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            call_source = ast.dump(child.func)
            if call_substr in call_source:
                return child.lineno
    return None


def _find_assignment_call_lineno(
    tree: ast.Module, func_name: str, call_substr: str,
) -> int | None:
    """Find the first line of an assignment whose value is a Call matching
    `call_substr` inside function `func_name`.
    """
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != func_name:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Assign) and isinstance(child.value, ast.Call):
                if call_substr in ast.dump(child.value.func):
                    return child.lineno
    return None


class TestSentinelAcquiredBeforeDispatch:
    """AST-based structural test: sentinel write precedes dispatch."""

    @pytest.fixture(autouse=True)
    def _parse_engine(self) -> None:
        source = ENGINE_PATH.read_text(encoding="utf-8")
        self.tree = ast.parse(source, filename=str(ENGINE_PATH))

    def test_sentinel_write_precedes_dispatch(self) -> None:
        sentinel_line = _find_call_lineno(
            self.tree, "run_pipeline", "_scaffold_stack_write_sentinel",
        )
        dispatch_line = _find_call_lineno(
            self.tree, "run_pipeline", "dispatch_by_stack_ids",
        )
        assert sentinel_line is not None, (
            "_scaffold_stack_write_sentinel call not found in run_pipeline"
        )
        assert dispatch_line is not None, (
            "dispatch_by_stack_ids call not found in run_pipeline"
        )
        assert sentinel_line < dispatch_line, (
            f"sentinel write (line {sentinel_line}) must precede "
            f"dispatch (line {dispatch_line})"
        )

    def test_sentinel_write_precedes_wire_cross_cutting(self) -> None:
        sentinel_line = _find_call_lineno(
            self.tree, "run_pipeline", "_scaffold_stack_write_sentinel",
        )
        wiring_line = _find_call_lineno(
            self.tree, "run_pipeline", "wire_cross_cutting",
        )
        assert sentinel_line is not None
        assert wiring_line is not None
        assert sentinel_line < wiring_line, (
            f"sentinel write (line {sentinel_line}) must precede "
            f"cross-cutting wiring (line {wiring_line})"
        )

    def test_sentinel_clear_in_finally(self) -> None:
        source = ENGINE_PATH.read_text(encoding="utf-8")
        assert "_scaffold_stack_clear_sentinel" in source, (
            "sentinel clear call must exist in engine.py"
        )
