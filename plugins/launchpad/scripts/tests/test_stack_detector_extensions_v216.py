"""BL-345 v2.1.6 — extend plugin-stack-detector.py to recognise additional stacks.

Before v2.1.6 the detector recognised: next.js, hono, react, express,
prisma (TS); django, fastapi, flask (Python); go, rust, rails, php.
Stack-id mapping was coarse — single-app Next projects fell through to
`generic`; Astro projects were entirely unrecognised; non-Django Python
projects fell through to `generic` and got broken pnpm-based bootstrap
output.

v2.1.6 extends the detector to recognise:
  * `astro` (via `astro` npm dep) -> stack id `astro`
  * `next.js` single-app (no monorepo signal) -> stack id `nextjs_standalone`
  * Python project of any kind -> stack id `python_generic` (or
    `python_django` if Django specifically detected)
  * `@11ty/eleventy`, `expo`, `@supabase/*` frameworks surfaced via the
    `frameworks` list (v2.2 active enum candidates; v2.1 maps them to
    `generic` until adapters land)

Test coverage:
- (1) astro detection via npm dep -> stack=astro
- (2) Single-app Next.js (no workspaces, no turbo) -> stack=nextjs_standalone
- (3) Monorepo Next.js (turbo dep + tsconfig) -> stack=ts_monorepo
  (unchanged from v2.1.5 — this regression check confirms the
  monorepo path is preserved)
- (4) Plain Python project (pyproject.toml, no framework) -> stack=python_generic
- (5) FastAPI project (no Django) -> stack=python_generic + framework=fastapi
- (6) Django project -> stack=python_django (unchanged regression check)
- (7) Eleventy / Expo / Supabase frameworks surface in `frameworks`
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

_DETECTOR_PATH = _SCRIPT_DIR / "plugin-stack-detector.py"
_spec = importlib.util.spec_from_file_location("plugin_stack_detector_v216", _DETECTOR_PATH)
assert _spec is not None and _spec.loader is not None
_detector = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_detector)
detect_from_manifest = _detector.detect_from_manifest


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# (1) Astro detection.
# ---------------------------------------------------------------------------


def test_astro_dep_detected_as_astro_stack(tmp_path: Path) -> None:
    """package.json with `astro` in dependencies -> stack id `astro`."""
    pkg = tmp_path / "package.json"
    _write(
        pkg,
        '{"name": "site", "dependencies": {"astro": "^4.0.0"}}',
    )
    result = detect_from_manifest(pkg)
    assert result.get("stack") == "astro", (
        f"Astro project should detect as `astro`; got {result.get('stack')!r}"
    )
    assert "astro" in result.get("frameworks", []), (
        "Astro framework should appear in `frameworks` list"
    )


def test_astro_dep_in_devdependencies_also_detected(tmp_path: Path) -> None:
    """`astro` in devDependencies (uncommon but valid) still detected."""
    pkg = tmp_path / "package.json"
    _write(
        pkg,
        '{"name": "site", "devDependencies": {"astro": "^4.0.0"}}',
    )
    result = detect_from_manifest(pkg)
    assert result.get("stack") == "astro"


# ---------------------------------------------------------------------------
# (2) + (3) Next.js detection: single-app vs monorepo.
# ---------------------------------------------------------------------------


def test_single_app_nextjs_detected_as_nextjs_standalone(tmp_path: Path) -> None:
    """Single-app Next.js (no workspaces, no turbo) -> `nextjs_standalone`."""
    pkg = tmp_path / "package.json"
    _write(
        pkg,
        '{"name": "site", "dependencies": {"next": "^15.0.0", "react": "^18.0.0"}}',
    )
    # tsconfig.json present -> TypeScript signal
    _write(tmp_path / "tsconfig.json", "{}")
    result = detect_from_manifest(pkg)
    assert result.get("stack") == "nextjs_standalone", (
        f"Single-app Next.js should detect as `nextjs_standalone`; got "
        f"{result.get('stack')!r}"
    )


def test_monorepo_nextjs_still_detected_as_ts_monorepo(tmp_path: Path) -> None:
    """Monorepo Next.js (turbo + tsconfig + Next dep) -> `ts_monorepo`.

    Regression check: BL-345 must not break the existing v2.1.5
    monorepo detection path that LaunchPad itself uses.
    """
    pkg = tmp_path / "package.json"
    _write(
        pkg,
        '{"name": "monorepo", "workspaces": ["apps/*", "packages/*"], '
        '"dependencies": {"next": "^15.0.0", "turbo": "^2.0.0"}}',
    )
    _write(tmp_path / "tsconfig.json", "{}")
    result = detect_from_manifest(pkg)
    assert result.get("stack") == "ts_monorepo"


# ---------------------------------------------------------------------------
# (4) + (5) + (6) Python project detection.
# ---------------------------------------------------------------------------


def test_plain_python_project_detected_as_python_generic(tmp_path: Path) -> None:
    """pyproject.toml with no framework -> `python_generic`.

    Pre-v2.1.6 this fell through to `generic`, producing broken
    pnpm-based bootstrap. BL-345 maps all Python projects to
    `python_generic` so the Python stack family applies (pytest,
    ruff, pyright commands).
    """
    pyproject = tmp_path / "pyproject.toml"
    _write(
        pyproject,
        '[project]\nname = "myapp"\ndependencies = []\n',
    )
    result = detect_from_manifest(pyproject)
    assert result.get("stack") == "python_generic", (
        f"Plain Python project should detect as `python_generic`; got "
        f"{result.get('stack')!r}"
    )


def test_fastapi_project_detected_as_python_generic(tmp_path: Path) -> None:
    """FastAPI project -> `python_generic` + framework=fastapi."""
    pyproject = tmp_path / "pyproject.toml"
    _write(
        pyproject,
        '[project]\nname = "api"\ndependencies = ["fastapi", "uvicorn"]\n',
    )
    result = detect_from_manifest(pyproject)
    assert result.get("stack") == "python_generic"
    assert "fastapi" in result.get("frameworks", [])


def test_django_project_still_detected_as_python_django(tmp_path: Path) -> None:
    """Django project -> `python_django`. Regression check that BL-345
    didn't break Django detection."""
    pyproject = tmp_path / "pyproject.toml"
    _write(
        pyproject,
        '[project]\nname = "djapp"\ndependencies = ["django>=5.0"]\n',
    )
    result = detect_from_manifest(pyproject)
    assert result.get("stack") == "python_django"
    assert "django" in result.get("frameworks", [])


# ---------------------------------------------------------------------------
# (7) Other framework surfacing (eleventy / expo / supabase).
# ---------------------------------------------------------------------------


def test_eleventy_framework_surfaced(tmp_path: Path) -> None:
    """`@11ty/eleventy` dep adds `eleventy` to frameworks list (stack
    still `generic` at v2.1 — Eleventy adapter is v2.2 candidate)."""
    pkg = tmp_path / "package.json"
    _write(
        pkg,
        '{"name": "site", "devDependencies": {"@11ty/eleventy": "^3.0.0"}}',
    )
    result = detect_from_manifest(pkg)
    assert "eleventy" in result.get("frameworks", [])


def test_expo_framework_surfaced(tmp_path: Path) -> None:
    pkg = tmp_path / "package.json"
    _write(
        pkg,
        '{"name": "app", "dependencies": {"expo": "^51.0.0"}}',
    )
    result = detect_from_manifest(pkg)
    assert "expo" in result.get("frameworks", [])


def test_supabase_framework_surfaced(tmp_path: Path) -> None:
    pkg = tmp_path / "package.json"
    _write(
        pkg,
        '{"name": "app", "dependencies": {"@supabase/supabase-js": "^2.0.0", "next": "^15.0.0"}}',
    )
    _write(tmp_path / "tsconfig.json", "{}")
    result = detect_from_manifest(pkg)
    assert "supabase" in result.get("frameworks", [])
    # Next.js single-app + supabase still maps to nextjs_standalone
    # (supabase is a service, not a stack-shape choice).
    assert result.get("stack") == "nextjs_standalone"


# ---------------------------------------------------------------------------
# Hono detection (preserved from v2.1.5).
# ---------------------------------------------------------------------------


def test_hono_single_app_still_maps_to_generic(tmp_path: Path) -> None:
    """Hono alone (no Next, no Prisma, no monorepo) -> generic.

    Regression check: hono-only projects still fall through to generic
    because the ts_monorepo gate requires monorepo signal.
    """
    pkg = tmp_path / "package.json"
    _write(
        pkg,
        '{"name": "api", "dependencies": {"hono": "^4.0.0"}}',
    )
    result = detect_from_manifest(pkg)
    # No monorepo signal, no Next/Hono/Prisma in monorepo => generic.
    # frameworks still surfaces hono for the doc generator.
    assert "hono" in result.get("frameworks", [])
    assert result.get("stack") == "generic"
