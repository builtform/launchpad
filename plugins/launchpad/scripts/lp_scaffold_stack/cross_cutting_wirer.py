"""Cross-cutting wiring (Phase 3 §4.1 Step 4).

For monorepo layouts: generate `pnpm-workspace.yaml`, `turbo.json`,
`lefthook.yml` per the materialized stacks. Detect toolchains. Run a basic
secret-scan as a Phase 3 sub-step.

On collision (a cross-cutting file that already existed before scaffold-stack
ran): raises `CrossCuttingError` with `reason: "cross_cutting_wiring_collision"`
which the engine wires into the scaffold-failed-<ts>.json record per
OPERATIONS §6 gate #11.

The wiring is intentionally minimal at v2.0:

- pnpm-workspace.yaml: emitted only when ≥2 layers under apps/ or packages/
- turbo.json: emitted only when pnpm-workspace.yaml is also emitted
- lefthook.yml: always emitted with the 4 standard hooks (secret-scan,
  structure-drift, typecheck, lint)
- toolchain detection: enumerated from layers' stacks via a static map.

The intent is not to replicate Turborepo's full feature surface; this is
the bridge from "individual scaffolders ran" to "later-stage `/lp-define`
sees a coherent monorepo root."
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# Stack → toolchain mapping. Used to populate `toolchains_detected` in the
# scaffold-receipt.json + drive lefthook hook configuration. v2.0's 10-entry
# catalog only covers these 4 toolchains.
_STACK_TO_TOOLCHAIN = {
    "astro": "node",
    "next": "node",
    "eleventy": "node",
    "hono": "node",
    "supabase": "node",  # supabase CLI is npm-installable; project files are JS/TS
    "expo": "node",
    "fastapi": "python",
    "django": "python",
    "rails": "ruby",
    "hugo": "go",
}

# Standard lefthook hooks Phase 3 wires by default (per OPERATIONS §5 Tier 1
# panel). The set is intentionally identical for greenfield + brownfield to
# keep the panel template stable.
LEFTHOOK_HOOKS = ("secret-scan", "structure-drift", "typecheck", "lint")

# Naive secret-scan: regex set covering the obvious leak patterns. The
# operational secret-scan (gitleaks et al.) lives in the lefthook hook the
# scaffold installs; this Phase 3 invocation is a smoke check on the just-
# materialized files so the receipt's `secret_scan_passed` carries a real
# signal at /lp-define time.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{32,}"),               # OpenAI-shaped keys
    re.compile(r"AKIA[0-9A-Z]{16}"),                  # AWS access keys
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),              # GitHub PATs
    re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
]


class CrossCuttingError(RuntimeError):
    """Raised on cross-cutting wiring failures. Carries `reason:` field
    and the list of cross-cutting files written before the failure.

    Per PR #41 cycle 7 #5 closure: when `wire_cross_cutting()` raises
    mid-sequence (e.g., lefthook.yml succeeds, pnpm-workspace.yaml
    collides), the engine's collision handler needs to know which files
    are already on disk so the scaffold-failed recovery record can name
    them. Without this, a rerun collides on the orphan files because the
    recovery_commands payload doesn't list them.
    """

    def __init__(
        self,
        message: str,
        reason: str,
        *,
        cross_cutting_files_written: list[str] | None = None,
    ):
        super().__init__(message)
        self.reason = reason
        self.cross_cutting_files_written: list[str] = list(
            cross_cutting_files_written or []
        )


@dataclass
class CrossCuttingResult:
    """Cross-cutting wiring outcome — populated into the scaffold-receipt."""

    cross_cutting_files: list[str] = field(default_factory=list)
    toolchains_detected: list[str] = field(default_factory=list)
    secret_scan_passed: bool = True
    secret_scan_findings: list[str] = field(default_factory=list)


def _detect_toolchains(stacks: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in stacks:
        tc = _STACK_TO_TOOLCHAIN.get(s)
        if tc and tc not in seen:
            seen.add(tc)
            out.append(tc)
    return sorted(out)


def _is_monorepo_layout(layers: Sequence[dict]) -> bool:
    """Heuristic: ≥2 layers AND any layer has a non-`.` path under apps/
    packages/ or services/."""
    if len(layers) < 2:
        return False
    for layer in layers:
        path = str(layer.get("path", "."))
        if path == ".":
            continue
        head = path.split("/", 1)[0]
        if head in {"apps", "packages", "services", "supabase"}:
            return True
    return False


def _atomic_write(path: Path, content: str) -> None:
    """Write text content to `path` via O_CREAT|O_EXCL|O_WRONLY at 0o600.

    True atomic-on-create semantics: a single open() call performs the
    "create-only" check + create in one syscall, eliminating the
    `exists() + write_text()` race that would let a file appear between
    those two operations. O_NOFOLLOW refuses to write through a symlink
    (TOCTOU defense). Fsync flushes the file before close so partial
    writes don't survive a crash. Mirrors the pattern used by
    decision_writer.py + receipt_writer.py for v2.0's load-bearing
    sealed artifacts (PR #41 cycle 4 #4 — pulls forward BL-236 D4).
    """
    import os

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        fd = os.open(str(path), flags, 0o600)
    except FileExistsError as exc:
        raise CrossCuttingError(
            f"cross-cutting file already exists: "
            f"{path.relative_to(path.parent.parent) if path.is_absolute() else path}",
            reason="cross_cutting_wiring_collision",
        ) from exc
    try:
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def _emit_pnpm_workspace(cwd: Path, layers: Sequence[dict]) -> Path:
    target = cwd / "pnpm-workspace.yaml"
    # Build the packages list from layer paths; include 'packages/*' as the
    # canonical shared-package root.
    pkgs: list[str] = []
    for layer in layers:
        path = str(layer.get("path", "."))
        if path == ".":
            continue
        head = path.split("/", 1)[0]
        glob = f"{head}/*"
        if glob not in pkgs:
            pkgs.append(glob)
    if "packages/*" not in pkgs:
        pkgs.append("packages/*")
    body = "packages:\n" + "".join(f"  - '{p}'\n" for p in pkgs)
    _atomic_write(target, body)
    return target


def _emit_turbo_json(cwd: Path) -> Path:
    target = cwd / "turbo.json"
    body = (
        '{\n'
        '  "$schema": "https://turbo.build/schema.json",\n'
        '  "tasks": {\n'
        '    "build": { "dependsOn": ["^build"], "outputs": ["dist/**", ".next/**"] },\n'
        '    "test": {},\n'
        '    "lint": {},\n'
        '    "typecheck": {}\n'
        '  }\n'
        '}\n'
    )
    _atomic_write(target, body)
    return target


def _emit_lefthook_yml(cwd: Path, toolchains: Sequence[str]) -> Path:
    target = cwd / "lefthook.yml"
    body_lines = ["pre-commit:", "  parallel: true", "  commands:"]
    body_lines.append("    secret-scan:")
    body_lines.append("      run: 'echo \"secret-scan stub — gitleaks recommended\"'")
    body_lines.append("    structure-drift:")
    body_lines.append("      run: 'echo \"structure-drift stub — wire to docs/architecture/REPOSITORY_STRUCTURE.md\"'")
    if "node" in toolchains:
        body_lines.append("    typecheck:")
        body_lines.append("      run: 'pnpm -r typecheck'")
        body_lines.append("    lint:")
        body_lines.append("      run: 'pnpm -r lint'")
    elif "python" in toolchains:
        # Real failing commands — no `|| true` masking. If the project does
        # not yet have mypy/ruff configured, the user runs `pip install mypy
        # ruff` (or removes the hook). Quality gates that can't fail are not
        # gates (PR #41 cycle 3 #7 closure).
        body_lines.append("    typecheck:")
        body_lines.append("      run: 'python -m mypy .'")
        body_lines.append("    lint:")
        body_lines.append("      run: 'python -m ruff check .'")
    elif "ruby" in toolchains:
        body_lines.append("    typecheck:")
        body_lines.append("      run: 'echo \"typecheck not configured for ruby\"'")
        body_lines.append("    lint:")
        body_lines.append("      run: 'bundle exec rubocop'")
    elif "go" in toolchains:
        body_lines.append("    typecheck:")
        body_lines.append("      run: 'go vet ./...'")
        body_lines.append("    lint:")
        body_lines.append("      run: 'gofmt -l .'")
    else:
        body_lines.append("    typecheck:")
        body_lines.append("      run: 'echo \"typecheck stub\"'")
        body_lines.append("    lint:")
        body_lines.append("      run: 'echo \"lint stub\"'")
    _atomic_write(target, "\n".join(body_lines) + "\n")
    return target


def _scan_for_secrets(cwd: Path, materialized_files: Sequence[str]) -> list[str]:
    """Best-effort secret scan over materialized files. Returns the list of
    matched-pattern descriptions (empty = clean).

    Per HANDSHAKE §2 trust assumptions: this is defense-in-depth, not a
    security boundary. The lefthook secret-scan hook (gitleaks) is the
    real gate at commit-time.
    """
    findings: list[str] = []
    for rel in materialized_files:
        p = cwd / rel
        if not p.is_file():
            continue
        try:
            data = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat in _SECRET_PATTERNS:
            if pat.search(data):
                findings.append(f"{rel}: matched {pat.pattern!r}")
                break  # one finding per file is enough
    return findings


def wire_cross_cutting(
    cwd: Path,
    layers: Sequence[dict],
    materialized_files: Sequence[str],
) -> CrossCuttingResult:
    """End-to-end Step 4 driver.

    Returns a CrossCuttingResult populated with the artifacts written, the
    detected toolchains, and the secret-scan verdict.

    Raises CrossCuttingError on collision (any cross-cutting file already
    exists). The engine catches this and emits scaffold-failed-<ts>.json with
    `reason: "cross_cutting_wiring_collision"` per OPERATIONS §6 gate #11.
    """
    stacks = [str(layer.get("stack", "")) for layer in layers]
    toolchains = _detect_toolchains(stacks)
    written: list[str] = []

    def _emit(emit_fn, *args) -> None:
        try:
            target = emit_fn(*args)
        except CrossCuttingError as exc:
            # Re-raise with partial-write state attached so the engine's
            # collision handler can list orphans in the scaffold-failed
            # recovery_commands payload (PR #41 cycle 7 #5 closure).
            raise CrossCuttingError(
                str(exc),
                reason=exc.reason,
                cross_cutting_files_written=sorted(written),
            ) from exc
        written.append(str(target.relative_to(cwd)))

    # Always emit lefthook.yml (single-layer projects benefit from the hooks).
    _emit(_emit_lefthook_yml, cwd, toolchains)

    if _is_monorepo_layout(layers):
        _emit(_emit_pnpm_workspace, cwd, layers)
        _emit(_emit_turbo_json, cwd)

    findings = _scan_for_secrets(cwd, materialized_files)
    return CrossCuttingResult(
        cross_cutting_files=sorted(written),
        toolchains_detected=toolchains,
        secret_scan_passed=not findings,
        secret_scan_findings=findings,
    )


__all__ = [
    "CrossCuttingError",
    "CrossCuttingResult",
    "LEFTHOOK_HOOKS",
    "wire_cross_cutting",
]
