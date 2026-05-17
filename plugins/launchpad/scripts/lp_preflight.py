"""External infrastructure preflight gate (BL-364, v2.1.7).

The v2.1.6 autonomous-ack gate (BL-356) forces user authorization before
`/lp-inf` enters the autonomous implementation loop. It does NOT check
whether the EXTERNAL infrastructure that the ship phase depends on is in
place (provider account, deploy project, GitHub Secrets, DNS, custom
domain, analytics tokens, etc.). Result: `/lp-build` spends 30+ minutes
of autonomous implementation, then `/lp-ship` writes deploy workflow
files referencing missing secrets, attempts to deploy, and fails at the
external-dependency wall.

This module supplies the preflight gate that closes that gap. It is the
front-of-the-funnel mirror of the autonomous-ack gate: surface the
prerequisites at the start of the autonomous flow, block until resolved,
then proceed.

**Architecture:**

  - Provider-profile templates ship under
    `plugins/launchpad/preflight-profiles/<name>.yaml`. Each profile
    declares a list of checks plus per-check default stale windows.
  - The consuming project's `.launchpad/preflight.config.yaml` lists
    which profiles to apply plus per-item overrides
    (`stale_window_days`, etc.).
  - Adding a new provider equals adding a profile YAML; the engine
    knows nothing provider-specific.

**Check categories:**

  A   auto-detect, silent
      Things LaunchPad can verify by reading project files. Pass
      silently; surface only on failure.

  B   auto-detect via API, requires user-provided credentials
      Provider API token works (test API call), deploy project exists,
      GitHub Secrets are populated (if GitHub API token is available).

  C1  user confirms, preflight probes to verify
      User must tick the confirmation box in the checklist; THEN the
      preflight runs the probe. Probe failure blocks (clearer feedback
      than "did you actually configure DNS?").

  C2  user confirms, no programmatic verification possible
      Preflight trusts the confirmation; failure surfaces at the actual
      deploy step with a "preflight C2 item X was confirmed but failed
      at deploy" message.

**Slash-command integration:**

  - `/lp-preflight`: standalone command, runs the engine + writes
    `.launchpad/preflight-checklist.md`, exits 0 on pass, nonzero on
    fail.
  - `/lp-ship` Step 0.6: calls `assert_preflight_ok(repo_root)` AFTER
    the BL-356 ack gate at Step 0.5; refuses to ship if preflight
    fails.
  - `/lp-build` Step 0.6: same call as `/lp-ship` Step 0.6, invoked
    BEFORE entering `/lp-inf`. Fail-fast on ship blockers before
    autonomous implementation work begins.

**Single-source-of-truth invariant:** preflight logic lives in this
module. Command markdown files MUST reference `assert_preflight_ok` by
name rather than re-implementing the dispatch inline. Mirrors the
BL-356 invariant on `autonomous_guard.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import quote, urlsplit

# Sibling-script imports (atomic-replace primitive for the receipt artifact;
# allowlisted in plugin-v2-handshake-lint.py per BL-371).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from atomic_io import atomic_write_replace  # noqa: E402

# Vendor bootstrap for PyYAML (mirrors plugin-config-loader.py).
_VENDOR = Path(__file__).resolve().parent / "plugin_stack_adapters" / "_vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

try:
    import yaml  # type: ignore

    _YAMLError: type[Exception] = yaml.YAMLError
except ImportError:  # pragma: no cover - vendor bootstrap covers this
    yaml = None  # type: ignore[assignment]
    _YAMLError = Exception  # fallback unreachable: _load_yaml raises first


def _load_yaml(text: str) -> Any:
    if yaml is None:  # pragma: no cover - vendor bootstrap covers this
        raise PreflightConfigError(
            "PyYAML not available; vendor it into "
            "plugins/launchpad/scripts/plugin_stack_adapters/_vendor/ "
            "or install system-wide."
        )
    return yaml.safe_load(text)


# ---------------------------------------------------------------------------
# Constants.
# ---------------------------------------------------------------------------

CONFIG_PATH = ".launchpad/preflight.config.yaml"
CHECKLIST_PATH = ".launchpad/preflight-checklist.md"
RECEIPT_PATH = ".launchpad/preflight-receipt.json"
AUDIT_LOG_PATH = ".launchpad/audit.log"
PROFILE_DIR_NAME = "preflight-profiles"

RECEIPT_VERSION = 1
"""Schema version for `.launchpad/preflight-receipt.json` (BL-371). v2 reserved."""

DEFAULT_FRESHNESS_WINDOW_SECONDS = 3600
"""Default receipt freshness window (1 hour) used when neither the CLI
flag nor the config's top-level `freshness_window_seconds` is set."""

DEFAULT_STALE_WINDOW_DAYS = 30
"""Default stale window if neither the profile nor the override sets one."""

VALID_CATEGORIES = ("A", "B", "C1", "C2")

_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
"""Strict charset for provider profile names in `.launchpad/preflight.config.yaml`.

Provider names are interpolated directly into the filesystem path
`<profile_dir>/<name>.yaml`. Without this guard a malicious or mistaken
value like `../../etc/passwd` would escape the profile directory.
Codex round-3 P2.
"""

CHECKLIST_HEADER = """\
# Preflight Checklist

Generated: {timestamp}
Providers: {providers}

This file is generated by `/lp-preflight` (and by `/lp-build` + `/lp-ship`
at Step 0.6). To pass the gate, work down the checklist items below: read
the setup hint, take the action, then either tick the confirmation box
(for C1 / C2 items) or wait for the next preflight run to auto-detect
the change (for A / B items). After ticking a box, re-run `/lp-preflight`
to verify.
"""


# ---------------------------------------------------------------------------
# Exception hierarchy.
# ---------------------------------------------------------------------------


class PreflightError(Exception):
    """Base class for preflight failures.

    Catching this lets `/lp-ship` and `/lp-build` surface ANY preflight
    failure with a generic wrapper while rendering the specific message
    via `str(exc)`.
    """


class PreflightConfigError(PreflightError):
    """Raised when `.launchpad/preflight.config.yaml` or a referenced
    profile cannot be loaded or fails schema validation."""


class PreflightFailedError(PreflightError):
    """Raised by `assert_preflight_ok` when one or more checks fail.

    `str(exc)` returns a multi-line summary naming the failed items plus
    the path to the generated checklist file for follow-up.
    """


# ---------------------------------------------------------------------------
# Schema types.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckDefinition:
    """One check loaded from a provider profile, post-override merge."""

    item_id: str
    category: str
    title: str
    setup_hint: str
    stale_window_days: int
    probe: str | None
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CheckResult:
    """Outcome of running one check."""

    item_id: str
    category: str
    status: str  # "pass" | "fail" | "needs-confirmation"
    message: str
    setup_hint: str


@dataclass
class CheckConfirmation:
    """Per-item state parsed from `.launchpad/preflight-checklist.md`.

    `confirmed` is True iff the user ticked the box. `last_confirmed` is
    an ISO-8601 UTC timestamp string (or None if never confirmed).
    """

    item_id: str
    confirmed: bool
    last_confirmed: str | None


@dataclass
class HttpResponse:
    status: int
    body: str


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class ProbeClients:
    """Injectable seam for testability.

    Production callers use `default_clients()`; tests supply mock
    callables so probes never touch the network or shell.
    """

    http_get: Callable[[str, dict[str, str]], HttpResponse]
    run_command: Callable[[list[str]], CommandResult]


def default_clients() -> ProbeClients:
    """Real-world clients backed by stdlib urllib + subprocess."""

    def _http_get(url: str, headers: dict[str, str]) -> HttpResponse:
        # Bandit B310: enforce https-only at the callsite. Provider
        # profiles construct fixed-shape API endpoints (api.cloudflare.com,
        # api.vercel.com, api.netlify.com), all HTTPS; rejecting non-https
        # closes the file:/ and custom-scheme attack surface even though
        # the URL never comes from end-user input. Two-layer check:
        # `urlsplit(url).scheme.lower() == "https"` is the primary gate
        # (robust against weird inputs, semantically correct per RFC 3986
        # where schemes are case-insensitive), while the case-sensitive
        # `url.startswith("https://")` guard refuses non-canonical case
        # variants like `HTTPS://` so a typo'd profile is caught at the
        # gate rather than silently issuing a request via urllib (which
        # normalizes case itself).
        if not url.startswith("https://") or urlsplit(url).scheme.lower() != "https":
            return HttpResponse(status=0, body=f"refused non-https URL: {url[:64]}")
        req = urllib_request.Request(url, headers=headers, method="GET")
        try:
            with urllib_request.urlopen(req, timeout=10) as resp:  # nosec B310 - canonical https:// prefix + urlsplit().scheme.lower() == "https" enforced above
                body_bytes = resp.read()
                return HttpResponse(
                    status=resp.status,
                    body=body_bytes.decode("utf-8", errors="replace"),
                )
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            return HttpResponse(status=exc.code, body=body)
        except (urllib_error.URLError, TimeoutError, OSError) as exc:
            return HttpResponse(status=0, body=f"network error: {exc}")

    def _run(args: list[str]) -> CommandResult:
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, check=False, timeout=15
            )
        except FileNotFoundError as exc:
            return CommandResult(returncode=127, stdout="", stderr=str(exc))
        except subprocess.TimeoutExpired as exc:
            return CommandResult(returncode=124, stdout="", stderr=str(exc))
        return CommandResult(
            returncode=result.returncode, stdout=result.stdout, stderr=result.stderr
        )

    return ProbeClients(http_get=_http_get, run_command=_run)


# ---------------------------------------------------------------------------
# Profile + config loading.
# ---------------------------------------------------------------------------


def _profile_dir() -> Path:
    """Return the bundled profile directory.

    The directory is a sibling of `scripts/` under `plugins/launchpad/`.
    """
    return Path(__file__).resolve().parent.parent / PROFILE_DIR_NAME


def _validate_category(category: str, item_id: str, profile_name: str) -> None:
    if category not in VALID_CATEGORIES:
        raise PreflightConfigError(
            f"profile {profile_name!r} item {item_id!r}: category "
            f"{category!r} not in {VALID_CATEGORIES}"
        )


def _coerce_check(
    raw: dict[str, Any],
    profile_name: str,
    overrides: dict[str, dict[str, Any]],
) -> CheckDefinition:
    """Build a CheckDefinition from a raw YAML dict + caller overrides."""
    if not isinstance(raw, dict):
        # Catches malformed entries like `checks: [1]` or `checks: [foo]`
        # which would otherwise raise an unhandled TypeError inside the
        # `required not in raw` membership test. Codex round-2 P2.
        raise PreflightConfigError(
            f"profile {profile_name!r}: check entry must be a mapping; "
            f"got {type(raw).__name__} ({raw!r:.60})"
        )
    for required in ("id", "category", "title", "setup_hint"):
        if required not in raw:
            raise PreflightConfigError(
                f"profile {profile_name!r}: check is missing required "
                f"field {required!r}"
            )
    item_id = str(raw["id"])
    category = str(raw["category"])
    _validate_category(category, item_id, profile_name)
    override = overrides.get(item_id, {})
    raw_window = override.get(
        "stale_window_days",
        raw.get("stale_window_days", DEFAULT_STALE_WINDOW_DAYS),
    )
    # Validate stale_window_days as a positive int. A malformed value like
    # `stale_window_days: soon` would otherwise raise raw ValueError from
    # `int()` and bypass the CLI's PreflightConfigError -> exit-code-2 path
    # (Codex round-3 P1). Pre-CONFIG-ERROR check + range guard so users
    # see an actionable message naming the offending profile and check id.
    try:
        stale_window = int(raw_window)
    except (TypeError, ValueError) as exc:
        raise PreflightConfigError(
            f"profile {profile_name!r} item {item_id!r}: "
            f"`stale_window_days` must be a non-negative integer; "
            f"got {raw_window!r} ({type(raw_window).__name__})"
        ) from exc
    if stale_window < 0:
        raise PreflightConfigError(
            f"profile {profile_name!r} item {item_id!r}: "
            f"`stale_window_days` must be non-negative; got {stale_window}"
        )
    probe = raw.get("probe")
    if probe is not None:
        probe = str(probe)
    # Merge profile args with override args. Profile YAMLs document this
    # contract (e.g., namecheap-dns.apex-resolves-via-cname:
    # "Override args.domain in .launchpad/preflight.config.yaml"), but the
    # original implementation only merged stale_window_days. The merge is a
    # shallow dict.update so override values shadow profile defaults on a
    # per-key basis.
    profile_args = raw.get("args", {})
    if not isinstance(profile_args, dict):
        raise PreflightConfigError(
            f"profile {profile_name!r} item {item_id!r}: `args:` must be a "
            f"mapping; got {type(profile_args).__name__}"
        )
    override_args = override.get("args", {})
    if not isinstance(override_args, dict):
        raise PreflightConfigError(
            f"overrides for {item_id!r}: `args:` must be a mapping; "
            f"got {type(override_args).__name__}"
        )
    merged_args: dict[str, Any] = dict(profile_args)
    merged_args.update(override_args)
    return CheckDefinition(
        item_id=item_id,
        category=category,
        title=str(raw["title"]),
        setup_hint=str(raw["setup_hint"]).rstrip(),
        stale_window_days=stale_window,
        probe=probe,
        args=merged_args,
    )


def load_profile(
    profile_path: Path,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> list[CheckDefinition]:
    """Load and validate one provider profile YAML.

    Raises PreflightConfigError on parse or schema failure.
    """
    if not profile_path.is_file():
        raise PreflightConfigError(f"profile file not found: {profile_path}")
    try:
        raw = _load_yaml(profile_path.read_text(encoding="utf-8"))
    except _YAMLError as exc:
        raise PreflightConfigError(f"failed to parse {profile_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PreflightConfigError(
            f"profile {profile_path.name} root must be a mapping; got "
            f"{type(raw).__name__}"
        )
    if "checks" not in raw or not isinstance(raw["checks"], list):
        raise PreflightConfigError(
            f"profile {profile_path.name} must have a list `checks:` key"
        )
    overrides = overrides or {}
    profile_name = profile_path.stem
    return [_coerce_check(item, profile_name, overrides) for item in raw["checks"]]


def load_preflight_config(
    repo_root: Path,
    profile_dir: Path | None = None,
) -> tuple[list[CheckDefinition], list[str]]:
    """Load `.launchpad/preflight.config.yaml` + every referenced profile.

    Returns (checks, providers). `providers` is the user-declared list of
    profile names; used in the checklist header.

    Raises PreflightConfigError if the config or any profile fails to
    load.
    """
    cfg_path = repo_root / CONFIG_PATH
    if not cfg_path.is_file():
        raise PreflightConfigError(
            f"`{CONFIG_PATH}` not found. Create it with a `providers:` list "
            f"naming the preflight profiles to apply, then re-run "
            f"`/lp-preflight`. See `plugins/launchpad/preflight-profiles/` "
            f"for the bundled profile names."
        )
    try:
        raw = _load_yaml(cfg_path.read_text(encoding="utf-8"))
    except _YAMLError as exc:
        raise PreflightConfigError(f"failed to parse {CONFIG_PATH}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PreflightConfigError(
            f"{CONFIG_PATH} root must be a mapping; got {type(raw).__name__}"
        )
    # Refuse missing-or-empty providers: the existence of preflight.config.yaml
    # is what enables the gate at /lp-ship Step 0.6 + /lp-build Step 0.6, so an
    # empty `providers:` would silently bypass all external-infrastructure
    # verification with a vacuously-true "report.ok = True". Either the user
    # omits the file entirely (gate disabled) or declares one or more profiles.
    if "providers" not in raw:
        raise PreflightConfigError(
            f"{CONFIG_PATH}: `providers:` key is required. Declare one or more "
            f"profile names (e.g., `providers: [spec-completeness]`), or delete "
            f"{CONFIG_PATH} entirely to disable the preflight gate."
        )
    providers = raw["providers"]
    if not isinstance(providers, list) or not all(
        isinstance(p, str) for p in providers
    ):
        raise PreflightConfigError(
            f"{CONFIG_PATH}: `providers:` must be a list of profile-name strings"
        )
    if not providers:
        raise PreflightConfigError(
            f"{CONFIG_PATH}: `providers:` is empty. Declare at least one profile "
            f"or delete {CONFIG_PATH} entirely to disable the preflight gate."
        )
    overrides_raw = raw.get("overrides") or {}
    if not isinstance(overrides_raw, dict):
        raise PreflightConfigError(
            f"{CONFIG_PATH}: `overrides:` must be a mapping of item-id to override-dict"
        )
    overrides: dict[str, dict[str, Any]] = {}
    for k, v in overrides_raw.items():
        if not isinstance(v, dict):
            raise PreflightConfigError(
                f"{CONFIG_PATH}: overrides[{k!r}] must be a mapping; "
                f"got {type(v).__name__}. Silently dropping malformed override "
                f"values masks config typos; declare overrides as "
                f"`<item-id>: {{ stale_window_days: N, args: {{...}} }}`."
            )
        overrides[str(k)] = dict(v)
    pdir = profile_dir or _profile_dir()
    checks: list[CheckDefinition] = []
    seen_ids: set[str] = set()
    for provider in providers:
        # Validate provider names against a strict profile-id regex
        # before constructing the filesystem path. A malicious or
        # mistaken value like `../../etc/passwd` would otherwise
        # interpolate into pdir without confinement. Codex round-3 P2.
        if not _PROFILE_NAME_RE.fullmatch(provider):
            raise PreflightConfigError(
                f"{CONFIG_PATH}: provider name {provider!r} must match "
                f"`^[A-Za-z0-9_-]+$` (no path separators, no traversal "
                f"segments). Bundled profile names live at "
                f"`plugins/launchpad/preflight-profiles/<name>.yaml`."
            )
        path = pdir / f"{provider}.yaml"
        provider_checks = load_profile(path, overrides=overrides)
        for chk in provider_checks:
            if chk.item_id in seen_ids:
                raise PreflightConfigError(
                    f"duplicate check id {chk.item_id!r} across profiles; "
                    f"item ids must be unique"
                )
            seen_ids.add(chk.item_id)
            checks.append(chk)
    return checks, list(providers)


# ---------------------------------------------------------------------------
# Checklist file I/O.
# ---------------------------------------------------------------------------


_CHECKLIST_ITEM_RE = re.compile(
    r"^\s*-\s+\[(?P<box>[ xX])\]\s+(?P<title>.+?)"
    r"(?:\s+\(id:\s*(?P<id>[^)]+)\))?\s*$",
    re.MULTILINE,
)
_CHECKLIST_LAST_CONFIRMED_RE = re.compile(
    r"^\s+Last confirmed:\s+(?P<ts>\S+)", re.MULTILINE
)


def parse_checklist(path: Path) -> dict[str, CheckConfirmation]:
    """Parse a previously-generated checklist file.

    Returns {item_id: CheckConfirmation}. Items not found get a default
    CheckConfirmation(confirmed=False, last_confirmed=None) at lookup
    time by the engine; this parser only emits entries it actually
    found.

    Tolerant: missing file → {}, malformed lines → skipped silently
    (the engine treats missing entries as unconfirmed, which is
    safe-by-default).
    """
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, CheckConfirmation] = {}
    # Parse line-by-line so a "Last confirmed:" line is attributed to
    # the most recently seen item.
    current_id: str | None = None
    current_confirmed = False
    for line in text.splitlines():
        m = _CHECKLIST_ITEM_RE.match(line)
        if m:
            item_id = m.group("id")
            if item_id is None:
                current_id = None
                continue
            current_id = item_id
            box_group = m.group("box") or " "
            current_confirmed = box_group.lower() == "x"
            out[item_id] = CheckConfirmation(
                item_id=item_id,
                confirmed=current_confirmed,
                last_confirmed=None,
            )
            continue
        m2 = _CHECKLIST_LAST_CONFIRMED_RE.match(line)
        if m2 and current_id and current_id in out:
            ts = m2.group("ts")
            existing = out[current_id]
            out[current_id] = CheckConfirmation(
                item_id=current_id,
                confirmed=existing.confirmed,
                last_confirmed=ts if ts != "never" else None,
            )
    return out


def _stale_window_label(days: int) -> str:
    if days >= 365 and days % 365 == 0:
        n = days // 365
        return f"{n} year{'s' if n != 1 else ''}"
    return f"{days} day{'s' if days != 1 else ''}"


def _render_check_block(
    chk: CheckDefinition,
    confirmation: CheckConfirmation,
    result: CheckResult,
) -> str:
    """Render one check as a markdown block in the checklist file.

    Box state mirrors the gating decision rather than the user's raw
    tick: stale-expired confirmations render as unticked so the user
    knows they need to re-confirm. C1 confirmed-but-probe-failed items
    render as ticked + an explicit FAIL status, so the user's prior
    confirmation is preserved while the failure is surfaced (C2 never
    runs a probe, so this combination is C1-only).
    """
    if result.status == "pass":
        box = "x"
    elif result.status == "needs-confirmation":
        box = " "
    elif result.status == "fail":
        box = "x" if chk.category == "C1" and confirmation.confirmed else " "
    else:
        raise ValueError(f"unknown status {result.status!r} for {chk.item_id}")
    # When the box is unticked AND the underlying status is
    # needs-confirmation (true stale OR never-confirmed), drop the
    # `Last confirmed:` timestamp so a user-re-tick on the next round
    # is treated as a fresh confirmation event by the first-tick
    # stamping branch in `run_preflight`. Preserving the old timestamp
    # would make re-tick + re-run see `confirmed=True` with stale ts,
    # _is_stale returns True forever, infinite re-prompt loop.
    # Codex round-3 P1.
    if box == " " and result.status == "needs-confirmation":
        last = "never"
    else:
        last = confirmation.last_confirmed or "never"
    window = _stale_window_label(chk.stale_window_days)
    lines = [
        f"- [{box}] {chk.title} (id: {chk.item_id})",
    ]
    for hint_line in chk.setup_hint.splitlines():
        lines.append(f"  {hint_line}".rstrip())
    lines.append(f"  Last confirmed: {last} (stale window: {window})")
    if result.status == "fail":
        lines.append(f"  Status: FAIL: {result.message}")
    elif result.status == "needs-confirmation":
        lines.append(f"  Status: {result.message}")
    return "\n".join(lines)


def render_checklist(
    checks: list[CheckDefinition],
    confirmations: dict[str, CheckConfirmation],
    results: list[CheckResult],
    providers: list[str],
    *,
    now: datetime | None = None,
) -> str:
    """Render the full checklist file content.

    Groups items into the three sections from the BL-364 UX:
    auto-detected (A + B), user-confirmation-with-probe (C1), and
    user-confirmation-trust-only (C2).
    """
    timestamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = CHECKLIST_HEADER.format(
        timestamp=timestamp, providers=", ".join(providers) if providers else "(none)"
    )
    by_id_result = {r.item_id: r for r in results}

    def _block(chk: CheckDefinition) -> str:
        conf = confirmations.get(
            chk.item_id, CheckConfirmation(chk.item_id, False, None)
        )
        result = by_id_result.get(
            chk.item_id, CheckResult(chk.item_id, chk.category, "pass", "", "")
        )
        return _render_check_block(chk, conf, result)

    auto = [c for c in checks if c.category in ("A", "B")]
    c1 = [c for c in checks if c.category == "C1"]
    c2 = [c for c in checks if c.category == "C2"]

    sections: list[str] = [header.rstrip()]
    sections.append("\n## Auto-detected (no action needed unless failing)\n")
    sections.append(
        "\n\n".join(_block(c) for c in auto) if auto else "(no auto-detected checks)"
    )
    sections.append("\n\n## User confirmation (verifiable via probe)\n")
    sections.append(
        "\n\n".join(_block(c) for c in c1) if c1 else "(no probe-verifiable checks)"
    )
    sections.append("\n\n## User confirmation (cannot verify programmatically)\n")
    sections.append(
        "\n\n".join(_block(c) for c in c2) if c2 else "(no trust-only checks)"
    )
    return "\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Probe dispatch.
# ---------------------------------------------------------------------------


ProbeFn = Callable[[Path, "CheckDefinition", ProbeClients], CheckResult]
_PROBE_REGISTRY: dict[str, ProbeFn] = {}


def register_probe(name: str) -> Callable[[ProbeFn], ProbeFn]:
    """Decorator: register a probe by name."""

    def _decorate(fn: ProbeFn) -> ProbeFn:
        if name in _PROBE_REGISTRY:
            raise RuntimeError(f"probe {name!r} already registered")
        _PROBE_REGISTRY[name] = fn
        return fn

    return _decorate


def _pass(chk: CheckDefinition, message: str = "ok") -> CheckResult:
    return CheckResult(chk.item_id, chk.category, "pass", message, chk.setup_hint)


def _fail(chk: CheckDefinition, message: str) -> CheckResult:
    return CheckResult(chk.item_id, chk.category, "fail", message, chk.setup_hint)


def _needs_confirmation(chk: CheckDefinition) -> CheckResult:
    return CheckResult(
        chk.item_id,
        chk.category,
        "needs-confirmation",
        "user has not ticked the confirmation box",
        chk.setup_hint,
    )


# ----- A-category probes (file-system checks) -----


def _resolve_under_root(rel: str, repo_root: Path) -> Path | None:
    """Resolve `rel` under `repo_root` AND confirm the resolved path stays
    inside the root. Defense-in-depth against path-traversal via profile
    `args.path: ../../etc/passwd` and absolute-path interpolation.
    Returns None if `rel` escapes the root or fails to resolve.
    Codex round-3 P2.
    """
    try:
        candidate = (repo_root / rel).resolve()
    except (OSError, RuntimeError):
        return None
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return candidate


@register_probe("file-exists")
def _probe_file_exists(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    rel = str(chk.args.get("path", ""))
    if not rel:
        return _fail(chk, "probe `file-exists` requires `args.path`")
    target = _resolve_under_root(rel, repo_root)
    if target is None:
        return _fail(chk, f"args.path {rel!r} escapes repo root; refusing to inspect")
    if target.is_file():
        return _pass(chk, f"{rel} exists")
    return _fail(chk, f"file {rel!r} not found under repo root")


@register_probe("file-contains")
def _probe_file_contains(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    rel = str(chk.args.get("path", ""))
    pattern = str(chk.args.get("pattern", ""))
    if not rel or not pattern:
        return _fail(
            chk, "probe `file-contains` requires `args.path` and `args.pattern`"
        )
    target = _resolve_under_root(rel, repo_root)
    if target is None:
        return _fail(chk, f"args.path {rel!r} escapes repo root; refusing to inspect")
    if not target.is_file():
        return _fail(chk, f"file {rel!r} not found")
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        return _fail(chk, f"cannot read {rel}: {exc}")
    try:
        matched = re.search(pattern, text, re.MULTILINE)
    except re.error as exc:
        # Greptile round-2 P2: a user-authored or future-bundled profile
        # may supply an invalid regex (e.g., unbalanced parens). Catch
        # at the probe boundary so the CLI exits with the structured
        # CONFIG-ERROR refuse-message rather than an unhandled traceback.
        return _fail(chk, f"invalid regex pattern {pattern!r}: {exc}")
    if matched:
        return _pass(chk, f"{rel} matches /{pattern}/")
    return _fail(chk, f"{rel} does not contain pattern /{pattern}/")


@register_probe("prd-tbd-markers-absent")
def _probe_prd_tbd(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    rel = str(chk.args.get("path", "docs/architecture/PRD.md"))
    prd = _resolve_under_root(rel, repo_root)
    if prd is None:
        return _fail(chk, f"args.path {rel!r} escapes repo root; refusing to inspect")
    if not prd.is_file():
        return _fail(chk, f"PRD file not found: {rel}")
    try:
        text = prd.read_text(encoding="utf-8")
    except OSError as exc:
        return _fail(chk, f"cannot read PRD: {exc}")
    matches = [
        (i + 1, line) for i, line in enumerate(text.splitlines()) if "[TBD]" in line
    ]
    if not matches:
        return _pass(chk, "no [TBD] markers in PRD")
    sample = ", ".join(f"line {ln}" for ln, _ in matches[:3])
    suffix = f" (+{len(matches) - 3} more)" if len(matches) > 3 else ""
    return _fail(
        chk, f"PRD contains {len(matches)} [TBD] marker(s) at {sample}{suffix}"
    )


@register_probe("changelog-has-version-entry")
def _probe_changelog(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    rel = str(chk.args.get("path", "CHANGELOG.md"))
    version = chk.args.get("version")
    changelog = _resolve_under_root(rel, repo_root)
    if changelog is None:
        return _fail(chk, f"args.path {rel!r} escapes repo root; refusing to inspect")
    if not changelog.is_file():
        return _fail(chk, f"{rel} not found")
    try:
        text = changelog.read_text(encoding="utf-8")
    except OSError as exc:
        return _fail(chk, f"cannot read {rel}: {exc}")
    if version:
        needle = f"## [{version}]"
        if needle in text:
            return _pass(chk, f"{rel} contains {needle}")
        return _fail(chk, f"{rel} missing entry {needle}")
    if re.search(r"^##\s*\[?(?:v?\d+\.\d+\.\d+|Unreleased)\]?", text, re.MULTILINE):
        return _pass(chk, f"{rel} has at least one version entry")
    return _fail(chk, f"{rel} has no version entries")


_SHIP_READY_STATUSES = frozenset({"approved", "reviewed", "built"})
"""Section-spec statuses that count as ship-ready for the preflight gate.

The documented lifecycle (see `/lp-build` Step 0.3 + the section-registry
status contract) advances each section through:

    defined -> shaped -> designed -> planned -> hardened -> approved
    -> reviewed -> built

`approved` is the minimum ship-ready state; `reviewed` (post-code-review)
and `built` (post-ship) are stages further along in the same lifecycle.
The preflight gate fires at both `/lp-build` Step 0.6 (before the run)
AND `/lp-ship` Step 0.6 (which is reachable after `/lp-build` advances
the section to `reviewed` / `built`). Requiring exactly `approved` would
block `/lp-ship` recovery-path invocations after a successful build.
"""


@register_probe("section-specs-approved")
def _probe_section_specs_approved(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    """Verify every in-scope section spec is at a ship-ready status.

    Ship-ready statuses: `approved`, `reviewed`, `built` (see
    `_SHIP_READY_STATUSES`). `args.section_glob` (default
    `docs/tasks/sections/*.md`) controls which files are inspected.
    Missing directory means no sections to check (pass with a note).

    Target-scoped mode (Codex round-5 P1-A): when `args.section_path`
    is set (engine plumbs this from `--section` CLI flag), the probe
    inspects ONLY that single file. This prevents `/lp-build <approved>`
    from being false-blocked by unrelated `shaped`/`planned` work on
    other sections.
    """
    plan_suffix = "-plan.md"
    root_resolved = repo_root.resolve()
    # Codex round-5 P1-A: target-scoped path overrides the glob entirely.
    # `/lp-build` resolves the section name first and passes `--section
    # docs/tasks/sections/<name>.md` so this check applies only to the
    # section being built. `/lp-ship` + standalone `/lp-preflight` do
    # not pass `--section` and retain the all-sections semantic.
    section_path_arg = chk.args.get("section_path")
    if section_path_arg:
        rel = str(section_path_arg)
        target = _resolve_under_root(rel, repo_root)
        if target is None:
            return _fail(
                chk,
                f"`args.section_path` {rel!r} does not resolve under the repo root",
            )
        if not target.is_file():
            return _fail(chk, f"`args.section_path` {rel!r} is not a file")
        matches = [target]
    else:
        glob = str(chk.args.get("section_glob", "docs/tasks/sections/*.md"))
        # Validate the glob is a repo-root-relative pattern. Absolute patterns
        # raise NotImplementedError from Path.glob; `..` segments would scan
        # outside the repo. Codex round-4 P1.
        if glob.startswith("/") or ".." in Path(glob).parts:
            return _fail(
                chk,
                f"`args.section_glob` {glob!r} must be a repo-root-relative pattern "
                f"(no absolute paths, no `..` segments). Default is "
                f"`docs/tasks/sections/*.md`.",
            )
        # Exclude implementation plan files which live alongside section specs
        # at `docs/tasks/sections/<name>-plan.md` per /lp-plan + /lp-pnf
        # conventions. Plan files have NO `status:` frontmatter, so including
        # them would false-fail the probe with "no status field" on a fully
        # approved section. Codex round-3 P1.
        try:
            matched_paths = list(repo_root.glob(glob))
        except (NotImplementedError, OSError) as exc:
            return _fail(chk, f"`args.section_glob` {glob!r} failed to glob: {exc}")
        # Confine each match under repo_root (defense-in-depth even though
        # the pattern is pre-validated above; symlink under repo could still
        # point outside).
        confined: list[Path] = []
        for p in matched_paths:
            if p.name.endswith(plan_suffix):
                continue
            try:
                p.resolve().relative_to(root_resolved)
            except (OSError, ValueError):
                continue
            confined.append(p)
        matches = sorted(confined)
        if not matches:
            return _pass(chk, f"no section specs found at {glob}")
    bad: list[str] = []
    for path in matches:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            bad.append(f"{path.name} (unreadable)")
            continue
        # Look for `status: <value>` in YAML frontmatter or anywhere
        # in the first ~60 lines. The "ship-ready" set covers approved
        # (pre-build) + reviewed (post-review, pre-ship) + built
        # (post-ship recovery-path) so the gate doesn't block /lp-ship
        # invocations after /lp-build has advanced the section.
        head = "\n".join(text.splitlines()[:60])
        m = re.search(r"^status:\s*([A-Za-z_]+)\s*$", head, re.MULTILINE)
        if not m:
            bad.append(f"{path.name} (no status field)")
        elif m.group(1).lower() not in _SHIP_READY_STATUSES:
            bad.append(f"{path.name} (status={m.group(1)})")
    if not bad:
        return _pass(chk, f"all {len(matches)} section spec(s) ship-ready")
    return _fail(chk, f"{len(bad)} section(s) not ship-ready: {', '.join(bad[:5])}")


# ----- B-category probes (network/API) -----


def _resolve_env(key: str) -> str | None:
    val = os.environ.get(key, "").strip()
    return val or None


_URL_SEGMENT_RE = re.compile(r"[A-Za-z0-9_-]+")


def _validated_segment(name: str, value: str) -> str | None:
    """Return a URL-quoted path segment iff `value` is a safe identifier.

    Defense-in-depth around B-probe URL construction: env-supplied
    identifiers (`account`, `slug`, `project`, `site`) are interpolated
    into provider API URLs via f-strings, so a stray `/`, `?`, `#`, `..`,
    newline, or whitespace would silently rewrite the URL path or query.
    A strict `[A-Za-z0-9_-]+` charset matches the documented shapes for
    Cloudflare account IDs + Pages project slugs, Vercel project IDs /
    names, and Netlify site IDs; anything else is rejected at the gate
    rather than producing a 404 from the provider with no warning.

    Returns the percent-encoded segment on success, or None when `value`
    contains characters outside the allowed charset (callers surface
    that as a `_fail(...)` with a precise message).
    """
    if not _URL_SEGMENT_RE.fullmatch(value):
        return None
    return quote(value, safe="")


@register_probe("cloudflare-api-token-valid")
def _probe_cf_token(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    token_env = chk.args.get("token_env", "CLOUDFLARE_API_TOKEN")
    token = _resolve_env(token_env)
    if not token:
        return _fail(
            chk,
            f"env var {token_env} is not set; export it or add it to .env "
            f"and re-source",
        )
    resp = clients.http_get(
        "https://api.cloudflare.com/client/v4/user/tokens/verify",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if resp.status == 0:
        return _fail(
            chk,
            f"network error talking to Cloudflare: {resp.body.removeprefix('network error: ')}",
        )
    if resp.status != 200:
        return _fail(chk, f"Cloudflare token verify failed: HTTP {resp.status}")
    try:
        data = json.loads(resp.body)
    except json.JSONDecodeError:
        return _fail(chk, "Cloudflare token verify returned non-JSON body")
    if data.get("success") and (data.get("result") or {}).get("status") == "active":
        return _pass(chk, "Cloudflare API token verified active")
    return _fail(chk, "Cloudflare token verify returned status != active")


@register_probe("cloudflare-pages-project-exists")
def _probe_cf_pages(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    token = _resolve_env(chk.args.get("token_env", "CLOUDFLARE_API_TOKEN"))
    account = _resolve_env(chk.args.get("account_id_env", "CLOUDFLARE_ACCOUNT_ID"))
    slug = _resolve_env(chk.args.get("slug_env", "CLOUDFLARE_PAGES_PROJECT_SLUG"))
    if not token or not account or not slug:
        return _fail(
            chk,
            "missing one of CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID / "
            "CLOUDFLARE_PAGES_PROJECT_SLUG env vars",
        )
    account_seg = _validated_segment("CLOUDFLARE_ACCOUNT_ID", account)
    slug_seg = _validated_segment("CLOUDFLARE_PAGES_PROJECT_SLUG", slug)
    if account_seg is None:
        return _fail(
            chk,
            f"CLOUDFLARE_ACCOUNT_ID {account!r} must match [A-Za-z0-9_-]+; "
            "refusing to construct request URL",
        )
    if slug_seg is None:
        return _fail(
            chk,
            f"CLOUDFLARE_PAGES_PROJECT_SLUG {slug!r} must match [A-Za-z0-9_-]+; "
            "refusing to construct request URL",
        )
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_seg}"
        f"/pages/projects/{slug_seg}"
    )
    resp = clients.http_get(
        url, {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    )
    if resp.status == 0:
        return _fail(
            chk,
            f"network error talking to Cloudflare: {resp.body.removeprefix('network error: ')}",
        )
    if resp.status == 200:
        return _pass(chk, f"Cloudflare Pages project {slug!r} exists")
    if resp.status == 404:
        return _fail(
            chk,
            f"Cloudflare Pages project {slug!r} not found in account "
            f"{account!r} (HTTP 404)",
        )
    return _fail(chk, f"Cloudflare Pages probe failed: HTTP {resp.status}")


@register_probe("vercel-api-token-valid")
def _probe_vercel_token(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    token = _resolve_env(chk.args.get("token_env", "VERCEL_TOKEN"))
    if not token:
        return _fail(chk, "env var VERCEL_TOKEN is not set")
    resp = clients.http_get(
        "https://api.vercel.com/v2/user",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if resp.status == 0:
        return _fail(
            chk,
            f"network error talking to Vercel: {resp.body.removeprefix('network error: ')}",
        )
    if resp.status == 200:
        return _pass(chk, "Vercel API token verified")
    return _fail(chk, f"Vercel token verify failed: HTTP {resp.status}")


@register_probe("vercel-project-exists")
def _probe_vercel_project(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    token = _resolve_env(chk.args.get("token_env", "VERCEL_TOKEN"))
    project = _resolve_env(chk.args.get("project_env", "VERCEL_PROJECT_ID"))
    if not token or not project:
        return _fail(chk, "missing VERCEL_TOKEN or VERCEL_PROJECT_ID env var")
    project_seg = _validated_segment("VERCEL_PROJECT_ID", project)
    if project_seg is None:
        return _fail(
            chk,
            f"VERCEL_PROJECT_ID {project!r} must match [A-Za-z0-9_-]+; "
            "refusing to construct request URL",
        )
    # Optional team-scoping via VERCEL_ORG_ID (Codex round-2 P2). When the
    # token has team scope, the API will reject team-owned projects unless
    # the teamId query param is passed; conversely, personal-scope tokens
    # work without teamId. We pass teamId when the env var is present so
    # team-owned projects verify correctly without breaking personal use.
    org = _resolve_env(chk.args.get("org_env", "VERCEL_ORG_ID"))
    url = f"https://api.vercel.com/v9/projects/{project_seg}"
    if org:
        org_seg = _validated_segment("VERCEL_ORG_ID", org)
        if org_seg is None:
            return _fail(
                chk,
                f"VERCEL_ORG_ID {org!r} must match [A-Za-z0-9_-]+; "
                "refusing to construct request URL",
            )
        url = f"{url}?teamId={org_seg}"
    resp = clients.http_get(
        url,
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if resp.status == 0:
        return _fail(
            chk,
            f"network error talking to Vercel: {resp.body.removeprefix('network error: ')}",
        )
    if resp.status == 200:
        scope = f" (teamId={org!r})" if org else ""
        return _pass(chk, f"Vercel project {project!r} exists{scope}")
    if resp.status == 404:
        return _fail(chk, f"Vercel project {project!r} not found (HTTP 404)")
    return _fail(chk, f"Vercel project probe failed: HTTP {resp.status}")


@register_probe("netlify-api-token-valid")
def _probe_netlify_token(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    token = _resolve_env(chk.args.get("token_env", "NETLIFY_AUTH_TOKEN"))
    if not token:
        return _fail(chk, "env var NETLIFY_AUTH_TOKEN is not set")
    resp = clients.http_get(
        "https://api.netlify.com/api/v1/user",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if resp.status == 0:
        return _fail(
            chk,
            f"network error talking to Netlify: {resp.body.removeprefix('network error: ')}",
        )
    if resp.status == 200:
        return _pass(chk, "Netlify API token verified")
    return _fail(chk, f"Netlify token verify failed: HTTP {resp.status}")


@register_probe("netlify-site-exists")
def _probe_netlify_site(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    token = _resolve_env(chk.args.get("token_env", "NETLIFY_AUTH_TOKEN"))
    site = _resolve_env(chk.args.get("site_env", "NETLIFY_SITE_ID"))
    if not token or not site:
        return _fail(chk, "missing NETLIFY_AUTH_TOKEN or NETLIFY_SITE_ID env var")
    site_seg = _validated_segment("NETLIFY_SITE_ID", site)
    if site_seg is None:
        return _fail(
            chk,
            f"NETLIFY_SITE_ID {site!r} must match [A-Za-z0-9_-]+; "
            "refusing to construct request URL",
        )
    resp = clients.http_get(
        f"https://api.netlify.com/api/v1/sites/{site_seg}",
        {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    if resp.status == 0:
        return _fail(
            chk,
            f"network error talking to Netlify: {resp.body.removeprefix('network error: ')}",
        )
    if resp.status == 200:
        return _pass(chk, f"Netlify site {site!r} exists")
    if resp.status == 404:
        return _fail(chk, f"Netlify site {site!r} not found (HTTP 404)")
    return _fail(chk, f"Netlify site probe failed: HTTP {resp.status}")


_GH_REPO_SLUG_RE = re.compile(
    r"github\.com[:/](?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)

_GH_OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
"""Strict charset for `args.repo` overrides on github-secrets probes.

Validates `<owner>/<repo>` shape: alphanumerics, `.`, `_`, `-`, with a
single `/` separator. Codex round-4 P2: a typo or path-style value
would silently let gh fall back to cwd-ambient resolution, defeating
the fail-closed origin-derived slug.
"""


def _derive_gh_repo_slug(repo_root: Path, clients: ProbeClients) -> str | None:
    """Derive an `owner/repo` slug from the repo's origin remote URL.

    Returns None if `git -C <repo_root> remote get-url origin` fails or the
    URL is not a github.com URL. Callers should fall back to gh's
    ambient-cwd inference with an explicit warning in the failure message.
    """
    result = clients.run_command(
        ["git", "-C", str(repo_root), "remote", "get-url", "origin"]
    )
    if result.returncode != 0:
        return None
    m = _GH_REPO_SLUG_RE.search(result.stdout.strip())
    if not m:
        return None
    return f"{m.group('owner')}/{m.group('repo')}"


@register_probe("github-secrets-populated")
def _probe_github_secrets(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    raw_required = chk.args.get("required_secrets", [])
    # Validate required_secrets is a list of strings. A scalar value like
    # `required_secrets: VERCEL_TOKEN` (missing the YAML list brackets)
    # would otherwise iterate character-by-character and report missing
    # secrets named "V", "E", "R", etc. Codex round-4 P2.
    if not isinstance(raw_required, list):
        return _fail(
            chk,
            f"`args.required_secrets` must be a list of secret-name strings; "
            f"got {type(raw_required).__name__} ({raw_required!r:.60}). Use "
            f"YAML list syntax: `required_secrets: [SECRET_A, SECRET_B]`.",
        )
    if not all(isinstance(s, str) for s in raw_required):
        return _fail(
            chk,
            "`args.required_secrets` must be a list of STRINGS; "
            "non-string entries detected",
        )
    required = list(raw_required)
    if not required:
        return _fail(chk, "`required_secrets` arg list is empty")
    # Use the gh CLI rather than the raw GitHub API: gh auth handles token
    # resolution from gh config OR GH_TOKEN/GITHUB_TOKEN env vars, which
    # matches how most users already authenticate locally. Pin --repo to
    # the slug derived from repo_root's git remote so an invocation like
    # `/lp-preflight --repo-root /elsewhere` from a different cwd validates
    # the right repository (closes Codex P1: cwd-ambient gh inference can
    # false-pass when --repo-root and cwd disagree).
    # Fail-closed when the slug cannot be derived from repo_root's git
    # remote. Falling back to gh's ambient cwd inference can validate the
    # WRONG repository when /lp-preflight is invoked with --repo-root
    # pointing somewhere other than $PWD (Codex round-2 P1). Users with a
    # non-github origin or no origin at all can either set args.repo as
    # an override in .launchpad/preflight.config.yaml OR remove the
    # github-secrets-populated check from their profile config.
    explicit_repo = chk.args.get("repo")
    if explicit_repo is not None:
        # Validate owner/repo shape before passing to gh. A typo like
        # `repo: just-the-name` would let gh fall back to its own
        # resolution (cwd-ambient), defeating the fail-closed origin
        # derivation. Codex round-4 P2.
        if not isinstance(explicit_repo, str) or not _GH_OWNER_REPO_RE.fullmatch(
            explicit_repo
        ):
            return _fail(
                chk,
                f"`args.repo` override {explicit_repo!r} must match "
                f"`<owner>/<repo>` (alphanumerics, `.`, `_`, `-`; single `/`). "
                f"Refusing to pass to `gh --repo`.",
            )
    slug = explicit_repo if explicit_repo else _derive_gh_repo_slug(repo_root, clients)
    if slug is None:
        return _fail(
            chk,
            "cannot derive GitHub repo slug from `git -C <repo_root> remote "
            "get-url origin` (no origin remote, or remote is not a github.com "
            "URL). Fail-closed to avoid validating secrets in the wrong "
            "repository. Either set the `origin` remote to a github.com URL, "
            "OR add `args.repo: <owner>/<repo>` to this check's override in "
            "`.launchpad/preflight.config.yaml`, OR remove the "
            "`github-secrets-populated` check from your provider profile.",
        )
    cmd = ["gh", "secret", "list", "--json", "name", "--repo", slug]
    result = clients.run_command(cmd)
    if result.returncode == 127:
        return _fail(
            chk,
            "the `gh` CLI is not installed; install GitHub CLI (https://cli.github.com/) "
            "or skip this probe by removing the github-secrets profile reference",
        )
    if result.returncode != 0:
        return _fail(
            chk,
            f"`gh secret list` failed (exit {result.returncode}): "
            f"{result.stderr.strip() or 'no output'}",
        )
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return _fail(chk, "`gh secret list` returned non-JSON output")
    present = {item.get("name") for item in data if isinstance(item, dict)}
    missing = [s for s in required if s not in present]
    if not missing:
        return _pass(chk, f"all required secrets present: {', '.join(required)}")
    return _fail(chk, f"missing GitHub Secrets: {', '.join(missing)}")


@register_probe("git-uncommitted-changes-warn")
def _probe_uncommitted(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    """Warn-only check for uncommitted git changes.

    Per BL-364 locked design decision 1: uncommitted changes warn, do NOT
    block. The probe returns `pass` regardless of the working-tree state,
    but the success message names how many files are modified so the
    checklist surface still informs the user. Tests assert the message
    shape distinguishes clean from dirty.
    """
    result = clients.run_command(["git", "-C", str(repo_root), "status", "--porcelain"])
    if result.returncode == 127:
        return _pass(chk, "git not installed; skipping uncommitted-changes warning")
    if result.returncode != 0:
        return _pass(
            chk, f"git status failed (rc={result.returncode}); skipping warning"
        )
    dirty = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if not dirty:
        return _pass(chk, "working tree clean")
    return _pass(
        chk,
        f"WARNING: {len(dirty)} uncommitted change(s) in working tree "
        f"(warn-only; not blocking)",
    )


# Cloudflare's published edge ranges, parsed as IPv4 networks. The /12
# covers 104.16.0.0 through 104.31.255.255; the /13 covers 172.64.0.0
# through 172.71.255.255. Codex round-5 P2: replace raw-string
# `startswith()` matching with `ipaddress.ip_address()` parsing so a
# CNAME hostname like `104.16.example.com.` cannot false-positive the
# IP-range check.
_CLOUDFLARE_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.IPv4Network("104.16.0.0/12"),
    ipaddress.IPv4Network("172.64.0.0/13"),
)


def _parse_dig_answer(raw: str) -> tuple[ipaddress.IPv4Address | None, str]:
    """Classify one `dig +short` answer line as either an IPv4 address
    or a hostname.

    Returns `(ip_address, hostname)`: at most one is non-None/non-empty.
    The hostname has the trailing dot stripped to match `.suffix` checks
    cleanly. A non-parseable answer returns `(None, "")` so callers can
    skip it. Codex round-5 P2.
    """
    candidate = raw.strip().rstrip(".")
    if not candidate:
        return (None, "")
    try:
        return (ipaddress.IPv4Address(candidate), "")
    except (ipaddress.AddressValueError, ValueError):
        return (None, candidate)


@register_probe("dns-resolves-via-cname")
def _probe_dns_cname(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    """Resolve `args.domain` and assert the answer chain contains a
    CNAME or A record matching `args.expected_suffix` (a domain suffix
    string like `.pages.dev` or `.netlify.app`) OR matches any prefix in
    `args.expected_prefixes` (list of IP prefix strings).

    Provider-agnostic complement to `dns-resolves-to-cloudflare`. Used
    by the namecheap-dns / vercel / netlify profiles.

    Codex round-5 P2: IP-prefix matching applies ONLY to answers that
    parse as IPv4 addresses; CNAME hostnames are matched against the
    suffix only. Prevents a CNAME like `104.16.cdn.example.com.` from
    false-matching the `104.16.` prefix.
    """
    domain = chk.args.get("domain") or _resolve_env(
        chk.args.get("domain_env", "PREFLIGHT_DOMAIN")
    )
    expected_suffix = chk.args.get("expected_suffix")
    raw_prefixes = chk.args.get("expected_prefixes", [])
    # Validate expected_prefixes shape: must be a list of strings.
    # A scalar string like `expected_prefixes: "104.16."` would silently
    # iterate character-by-character, checking prefixes "1", "0", "4",
    # ".", "1", "6", "." and false-passing arbitrary 1.x.x.x answers.
    # Codex round-3 P2.
    if not isinstance(raw_prefixes, list):
        return _fail(
            chk,
            f"`args.expected_prefixes` must be a list of strings; got "
            f"{type(raw_prefixes).__name__} ({raw_prefixes!r:.60}). Use YAML "
            f"list syntax: `expected_prefixes: [104.16., 172.64.]`.",
        )
    if not all(isinstance(p, str) for p in raw_prefixes):
        return _fail(
            chk,
            "`args.expected_prefixes` must be a list of STRINGS; "
            "non-string entries detected",
        )
    expected_prefixes = list(raw_prefixes)
    if not domain:
        return _fail(
            chk,
            "no domain configured; set `args.domain` or export PREFLIGHT_DOMAIN",
        )
    if not expected_suffix and not expected_prefixes:
        return _fail(
            chk,
            "probe requires either `args.expected_suffix` or `args.expected_prefixes`",
        )
    result = clients.run_command(["dig", "+short", "--", str(domain)])
    if result.returncode == 127:
        return _fail(chk, "the `dig` CLI is not installed; install BIND tools")
    if result.returncode != 0:
        return _fail(
            chk, f"`dig` failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    raw_answers = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if not raw_answers:
        return _fail(chk, f"no DNS records for {domain}")
    parsed = [_parse_dig_answer(a) for a in raw_answers]
    # Display set: keep the original textual form (trailing dot stripped)
    # for error messaging.
    display = [ip.exploded if ip is not None else host for ip, host in parsed]
    suffix = str(expected_suffix).rstrip(".") if expected_suffix else None
    for ip, host in parsed:
        if suffix and host and host.endswith(suffix):
            return _pass(chk, f"{domain} resolves via {host}")
        if ip is not None:
            ip_text = ip.exploded
            for prefix in expected_prefixes:
                if ip_text.startswith(prefix):
                    return _pass(chk, f"{domain} resolves to {ip_text}")
    return _fail(
        chk,
        f"{domain} resolves to {', '.join(display[:3])} which does not match "
        f"expected suffix/prefix",
    )


@register_probe("dns-resolves-to-cloudflare")
def _probe_dns_cloudflare(
    repo_root: Path, chk: CheckDefinition, clients: ProbeClients
) -> CheckResult:
    """Resolve `args.domain` and assert the answer chain lands on a
    Cloudflare edge IP (in 104.16.0.0/12 or 172.64.0.0/13) or a known
    Cloudflare CNAME suffix (`.cloudflare.com` or `.pages.dev`).

    Codex round-5 P2: answers are parsed via `ipaddress.IPv4Address`
    before being checked against the network ranges; hostnames are
    matched only against the suffix list. Prevents a CNAME hostname
    like `104.16.cdn.example.com.` from false-matching the IP range.
    """
    domain = chk.args.get("domain") or _resolve_env(
        chk.args.get("domain_env", "PREFLIGHT_DOMAIN")
    )
    if not domain:
        return _fail(
            chk,
            "no domain configured; set `args.domain` in your preflight "
            "config override or export PREFLIGHT_DOMAIN",
        )
    result = clients.run_command(["dig", "+short", "--", str(domain)])
    if result.returncode == 127:
        return _fail(
            chk,
            "the `dig` CLI is not installed; install BIND tools or skip this probe",
        )
    if result.returncode != 0:
        return _fail(
            chk, f"`dig` failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    raw_answers = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if not raw_answers:
        return _fail(chk, f"no DNS A records for {domain}")
    parsed = [_parse_dig_answer(a) for a in raw_answers]
    display = [ip.exploded if ip is not None else host for ip, host in parsed]
    for ip, host in parsed:
        if ip is not None and any(ip in net for net in _CLOUDFLARE_NETWORKS):
            return _pass(chk, f"{domain} resolves to Cloudflare ({ip.exploded})")
        if host and (host.endswith(".cloudflare.com") or host.endswith(".pages.dev")):
            return _pass(chk, f"{domain} CNAME points to Cloudflare ({host})")
    return _fail(
        chk,
        f"{domain} resolves to {', '.join(display[:3])} which does not match "
        f"Cloudflare edge ranges or known CNAME suffixes",
    )


# ---------------------------------------------------------------------------
# Engine.
# ---------------------------------------------------------------------------


def _is_stale(confirmation: CheckConfirmation, stale_window_days: int) -> bool:
    if confirmation.last_confirmed is None:
        return True
    try:
        # py311+ `fromisoformat` parses `Z` natively; no `.replace()` needed.
        ts = datetime.fromisoformat(confirmation.last_confirmed)
    except ValueError:
        # Distinguish a corrupt timestamp from a genuinely stale one: log to
        # stderr so a user who hand-edited the checklist into an unparseable
        # state sees feedback, then return True (safe-by-default) so the gate
        # still re-prompts for confirmation rather than masking the corruption.
        print(
            f"[preflight] WARNING: corrupt last_confirmed timestamp "
            f"{confirmation.last_confirmed!r} for item {confirmation.item_id!r}; "
            f"treating as stale and prompting re-confirmation.",
            file=sys.stderr,
        )
        return True
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    age_days = (datetime.now(UTC) - ts).days
    return age_days >= stale_window_days


def _run_one_check(
    chk: CheckDefinition,
    confirmation: CheckConfirmation,
    repo_root: Path,
    clients: ProbeClients,
) -> CheckResult:
    """Dispatch one check based on its category.

    Returns a CheckResult. Does NOT raise on probe failure; that's
    surfaced via `status="fail"` so the engine can aggregate across all
    checks.
    """
    if chk.category == "A":
        # Auto-detect; run probe directly, surface only on failure.
        if not chk.probe:
            return _fail(chk, "category A check missing `probe:`")
        probe = _PROBE_REGISTRY.get(chk.probe)
        if probe is None:
            return _fail(chk, f"unknown probe {chk.probe!r}")
        return probe(repo_root, chk, clients)

    if chk.category == "B":
        # Auto-detect via API. Requires user-provided credentials.
        if not chk.probe:
            return _fail(chk, "category B check missing `probe:`")
        probe = _PROBE_REGISTRY.get(chk.probe)
        if probe is None:
            return _fail(chk, f"unknown probe {chk.probe!r}")
        return probe(repo_root, chk, clients)

    if chk.category == "C1":
        # User must tick the confirmation box first, THEN we run the probe.
        if not confirmation.confirmed:
            return _needs_confirmation(chk)
        if _is_stale(confirmation, chk.stale_window_days):
            return CheckResult(
                chk.item_id,
                chk.category,
                "needs-confirmation",
                f"confirmation is stale (window: {chk.stale_window_days} days); "
                f"untick the box, address the item, and re-confirm",
                chk.setup_hint,
            )
        if not chk.probe:
            return _fail(chk, "category C1 check missing `probe:`")
        probe = _PROBE_REGISTRY.get(chk.probe)
        if probe is None:
            return _fail(chk, f"unknown probe {chk.probe!r}")
        return probe(repo_root, chk, clients)

    if chk.category == "C2":
        # Trust-only. If confirmed and not stale, pass; else needs confirmation.
        if not confirmation.confirmed:
            return _needs_confirmation(chk)
        if _is_stale(confirmation, chk.stale_window_days):
            return CheckResult(
                chk.item_id,
                chk.category,
                "needs-confirmation",
                f"confirmation is stale (window: {chk.stale_window_days} days)",
                chk.setup_hint,
            )
        return CheckResult(
            chk.item_id,
            chk.category,
            "pass",
            "trusted; not verified programmatically",
            chk.setup_hint,
        )

    return _fail(chk, f"unhandled category {chk.category!r}")


@dataclass
class PreflightReport:
    """Aggregate result of running preflight."""

    results: list[CheckResult]
    providers: list[str]
    checklist_path: Path
    failures: list[CheckResult] = field(default_factory=list)
    needs_confirmation: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures and not self.needs_confirmation


def run_preflight(
    repo_root: Path,
    *,
    clients: ProbeClients | None = None,
    profile_dir: Path | None = None,
    write_checklist: bool = True,
    now: datetime | None = None,
    target_section: str | None = None,
) -> PreflightReport:
    """Load config, run all checks, optionally write the checklist file.

    Returns a PreflightReport. Caller decides what to do with the
    report; the slash-command Step 0.6 wrappers turn `report.ok = False`
    into a refuse-message + exit, the standalone `/lp-preflight` prints
    a summary to the terminal.

    Raises PreflightConfigError on config/profile load failure.

    `target_section` (Codex round-5 P1-A) is a repo-root-relative path
    to a single section spec (e.g., `docs/tasks/sections/foo.md`).
    When set, the `section-specs-approved` probe is scoped to that
    file only. `/lp-build` resolves the target before Step 0.6 and
    passes it via `--section`; `/lp-ship` and standalone runs leave
    it unset (all-sections semantic).
    """
    clients = clients or default_clients()
    checks, providers = load_preflight_config(repo_root, profile_dir=profile_dir)
    if target_section is not None:
        # CheckDefinition is frozen; rebuild the list with a new args
        # dict on the section-specs-approved entry. Done here (not in
        # the probe itself) so the probe sees `section_path` via the
        # normal `chk.args` channel and stays ignorant of CLI flags.
        checks = [
            (
                replace(chk, args={**chk.args, "section_path": target_section})
                if chk.probe == "section-specs-approved"
                else chk
            )
            for chk in checks
        ]
    checklist_path = repo_root / CHECKLIST_PATH
    confirmations = parse_checklist(checklist_path)
    now_dt = now or datetime.now(UTC)
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Stamp newly-confirmed items (user ticked the box but the prior
    # checklist had no timestamp): treat the current run as the
    # confirmation event. Without this, first-time tick + re-run would
    # be flagged stale by `_is_stale` because last_confirmed is None.
    for chk in checks:
        conf = confirmations.get(chk.item_id)
        if conf is not None and conf.confirmed and conf.last_confirmed is None:
            confirmations[chk.item_id] = CheckConfirmation(
                item_id=chk.item_id,
                confirmed=True,
                last_confirmed=now_iso,
            )
    results: list[CheckResult] = []
    for chk in checks:
        conf = confirmations.get(
            chk.item_id, CheckConfirmation(chk.item_id, False, None)
        )
        results.append(_run_one_check(chk, conf, repo_root, clients))

    if write_checklist:
        content = render_checklist(
            checks, confirmations, results, providers, now=now_dt
        )
        checklist_path.parent.mkdir(parents=True, exist_ok=True)
        checklist_path.write_text(content, encoding="utf-8")

    failures = [r for r in results if r.status == "fail"]
    needs = [r for r in results if r.status == "needs-confirmation"]
    return PreflightReport(
        results=results,
        providers=providers,
        checklist_path=checklist_path,
        failures=failures,
        needs_confirmation=needs,
    )


def assert_preflight_ok(
    repo_root: Path,
    *,
    clients: ProbeClients | None = None,
    profile_dir: Path | None = None,
    target_section: str | None = None,
) -> PreflightReport:
    """Raise PreflightFailedError if any check fails or needs confirmation.

    Used by `/lp-ship` Step 0.6 + `/lp-build` Step 0.6 as the single
    callsite. Returns the report on success so callers can log
    pass-counts without re-running.

    Exception `str(exc)` is the canonical refuse-message: a multi-line
    summary naming the failed/pending items plus the path to the
    generated checklist.
    """
    report = run_preflight(
        repo_root,
        clients=clients,
        profile_dir=profile_dir,
        target_section=target_section,
    )
    if report.ok:
        return report
    raise PreflightFailedError(_format_refuse(report))


def _format_refuse(report: PreflightReport) -> str:
    lines = ["External-infrastructure preflight failed.", ""]
    if report.failures:
        lines.append(f"Failed checks ({len(report.failures)}):")
        for r in report.failures:
            lines.append(f"  - {r.item_id}: {r.message}")
        lines.append("")
    if report.needs_confirmation:
        lines.append(f"Awaiting your confirmation ({len(report.needs_confirmation)}):")
        for r in report.needs_confirmation:
            lines.append(f"  - {r.item_id}: {r.message}")
        lines.append("")
    lines.append(
        f"Edit `{CHECKLIST_PATH}` to tick confirmation boxes (setup hints "
        f"are inline per item), then re-run `/lp-preflight` to verify. "
        f"When all checks pass, re-run the original command."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Receipt artifact (BL-371: memoization between /lp-build and /lp-ship).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReceiptCheckResult:
    """Verdict on whether an on-disk receipt licenses skipping probes.

    `reason` is one of: ``valid``, ``missing``, ``corrupt``, ``stale``,
    ``config_changed``, ``checklist_changed``, ``prior_failed``. Audit-log
    lines on stale-receipt invalidation include this reason verbatim.
    """

    valid: bool
    reason: str
    receipt_age_seconds: int | None
    writer_command: str | None


def _sha256_of_file(path: Path) -> str | None:
    """Return hex SHA-256 of ``path``, or ``None`` if the file is missing."""
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audit_log_event(repo_root: Path, line: str) -> None:
    """Append a single event line to ``.launchpad/audit.log``.

    Best-effort: write failures are swallowed so a log outage cannot block
    the preflight gate. Format mirrors ``plugin-audit-log.py`` only in the
    ISO-8601-UTC timestamp prefix; receipt events use the BL-371 token
    shape ``<command> preflight-<action> <key>=<value> ...``.
    """
    log_dir = repo_root / ".launchpad"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "audit.log"
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp} {line}\n")
    except OSError:
        pass


def _read_receipt(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / RECEIPT_PATH
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _freshness_window_from_config(repo_root: Path) -> int | None:
    """Read top-level ``freshness_window_seconds`` from preflight.config.yaml.

    Returns ``None`` if the key is unset, malformed, or the config is
    absent / unparseable. Errors do NOT raise: the receipt path must be
    resilient to config-load failures, and ``load_preflight_config`` will
    re-surface real errors on the probe path.
    """
    cfg = repo_root / CONFIG_PATH
    if not cfg.is_file():
        return None
    try:
        raw = _load_yaml(cfg.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, dict):
        return None
    val = raw.get("freshness_window_seconds")
    # ``bool`` is a subclass of ``int``; reject explicitly so ``True`` is
    # not silently treated as ``1``.
    if isinstance(val, bool):
        return None
    if not isinstance(val, int) or val <= 0:
        return None
    return val


def check_receipt_validity(
    repo_root: Path,
    *,
    freshness_window_seconds: int,
    now: datetime | None = None,
) -> ReceiptCheckResult:
    """Decide whether the on-disk receipt licenses skipping probes.

    Validity requires ALL of:

    * receipt file present, parses as JSON, and is a v1 dict
    * ``exit_code == 0``
    * ``timestamp_utc`` parses; ``(now - timestamp) < freshness_window_seconds``
    * ``config_sha256`` matches the current preflight config (or both null)
    * ``checklist_sha256`` matches the current checklist (or both null)
    """
    now = now or datetime.now(UTC)
    receipt = _read_receipt(repo_root)
    if receipt is None:
        return ReceiptCheckResult(False, "missing", None, None)
    if receipt.get("version") != RECEIPT_VERSION:
        return ReceiptCheckResult(False, "corrupt", None, None)
    writer = receipt.get("writer_command")
    writer_str = writer if isinstance(writer, str) else None
    if receipt.get("exit_code") != 0:
        return ReceiptCheckResult(False, "prior_failed", None, writer_str)
    ts_raw = receipt.get("timestamp_utc")
    if not isinstance(ts_raw, str):
        return ReceiptCheckResult(False, "corrupt", None, writer_str)
    try:
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
    except ValueError:
        return ReceiptCheckResult(False, "corrupt", None, writer_str)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    age = int((now - ts).total_seconds())
    if age < 0:
        return ReceiptCheckResult(False, "corrupt", age, writer_str)
    if age >= freshness_window_seconds:
        return ReceiptCheckResult(False, "stale", age, writer_str)
    if _sha256_of_file(repo_root / CONFIG_PATH) != receipt.get("config_sha256"):
        return ReceiptCheckResult(False, "config_changed", age, writer_str)
    if _sha256_of_file(repo_root / CHECKLIST_PATH) != receipt.get("checklist_sha256"):
        return ReceiptCheckResult(False, "checklist_changed", age, writer_str)
    return ReceiptCheckResult(True, "valid", age, writer_str)


def write_receipt(
    repo_root: Path,
    *,
    exit_code: int,
    section_path: str | None,
    writer_command: str,
    freshness_window_seconds: int,
) -> Path | None:
    """Write a fresh receipt on success; remove any stale receipt on failure.

    Returns the receipt path when written, ``None`` when the file was
    removed or no action was needed. Atomic-replace prevents partial-write
    races with a concurrent ``--read-receipt`` reader.
    """
    path = repo_root / RECEIPT_PATH
    if exit_code != 0:
        try:
            path.unlink()
        except (FileNotFoundError, OSError):
            return None
        return None
    payload = {
        "version": RECEIPT_VERSION,
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exit_code": exit_code,
        "config_sha256": _sha256_of_file(repo_root / CONFIG_PATH),
        "checklist_sha256": _sha256_of_file(repo_root / CHECKLIST_PATH),
        "section_path": section_path,
        "writer_command": writer_command,
        "freshness_window_seconds": freshness_window_seconds,
    }
    body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_replace(path, body, trusted_root=repo_root)
    return path


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _format_summary(report: PreflightReport) -> str:
    """One-screen status block for terminal output."""
    pass_count = sum(1 for r in report.results if r.status == "pass")
    fail_count = len(report.failures)
    need_count = len(report.needs_confirmation)
    total = len(report.results)
    lines = [
        f"[preflight] Ran {total} check(s) "
        f"(providers: {', '.join(report.providers) or '(none)'})",
        f"[preflight] OK: {pass_count}",
    ]
    if need_count:
        lines.append(f"[preflight] AWAITING CONFIRMATION: {need_count}")
        for r in report.needs_confirmation:
            lines.append(f"[preflight]   - {r.item_id}")
    if fail_count:
        lines.append(f"[preflight] FAIL: {fail_count}")
        for r in report.failures:
            lines.append(f"[preflight]   - {r.item_id}: {r.message}")
    lines.append(f"[preflight] Checklist: {report.checklist_path}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lp_preflight",
        description=(
            "Run the external-infrastructure preflight gate (BL-364). "
            "Reads .launchpad/preflight.config.yaml, loads referenced profiles, "
            "runs all checks, writes .launchpad/preflight-checklist.md, and "
            "exits 0 on success or nonzero on failure."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=os.environ.get("LP_REPO_ROOT", "."),
        help="path to repo root (default: cwd or $LP_REPO_ROOT)",
    )
    parser.add_argument(
        "--no-write-checklist",
        action="store_true",
        help="do not generate/update the checklist file (read-only mode)",
    )
    parser.add_argument(
        "--section",
        default=None,
        help=(
            "Repo-root-relative path to a single section spec (e.g., "
            "docs/tasks/sections/foo.md). When provided, scopes the "
            "section-specs-approved check to that file only. `/lp-build` "
            "passes this after target resolution; `/lp-ship` and "
            "standalone runs leave it unset (all-sections semantic)."
        ),
    )
    parser.add_argument(
        "--write-receipt",
        action="store_true",
        help=(
            "On exit 0, write `.launchpad/preflight-receipt.json` with the "
            "config + checklist SHA-256 plus the freshness window so a "
            "subsequent /lp-ship or /lp-build invocation can skip probes "
            "when the receipt is still valid. On nonzero exit, any "
            "existing receipt is removed. BL-371."
        ),
    )
    parser.add_argument(
        "--read-receipt",
        action="store_true",
        help=(
            "Before running probes, check `.launchpad/preflight-receipt.json` "
            "and skip probes when `exit_code == 0`, the timestamp is within "
            "the freshness window, and the recorded config + checklist "
            "SHA-256 still match the on-disk files. BL-371."
        ),
    )
    parser.add_argument(
        "--writer-command",
        default=None,
        help=(
            "Identifier of the command writing the receipt "
            "(e.g., /lp-build, /lp-ship). Default: /lp-preflight. BL-371."
        ),
    )
    parser.add_argument(
        "--freshness-window-seconds",
        type=int,
        default=None,
        help=(
            "Override the receipt freshness window. Default: top-level "
            f"`freshness_window_seconds` in {CONFIG_PATH}, else "
            f"{DEFAULT_FRESHNESS_WINDOW_SECONDS}. Must be positive. BL-371."
        ),
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    writer_command = args.writer_command or "/lp-preflight"
    freshness = args.freshness_window_seconds
    if freshness is None:
        freshness = (
            _freshness_window_from_config(repo_root) or DEFAULT_FRESHNESS_WINDOW_SECONDS
        )
    elif freshness <= 0:
        print(
            "[preflight] CONFIG ERROR: --freshness-window-seconds must be "
            f"a positive integer; got {args.freshness_window_seconds}",
            file=sys.stderr,
        )
        return 2

    if args.read_receipt:
        verdict = check_receipt_validity(repo_root, freshness_window_seconds=freshness)
        if verdict.valid:
            issued_by = verdict.writer_command or "/lp-preflight"
            print(
                f"[preflight] receipt valid; skipping probes "
                f"(issued {verdict.receipt_age_seconds}s ago by {issued_by})"
            )
            _audit_log_event(
                repo_root,
                f"{writer_command} preflight-skipped-via-receipt "
                f"receipt_age_seconds={verdict.receipt_age_seconds} "
                f"writer={issued_by}",
            )
            return 0
        if verdict.reason != "missing":
            _audit_log_event(
                repo_root,
                f"{writer_command} preflight-receipt-{verdict.reason}",
            )

    try:
        report = run_preflight(
            repo_root,
            write_checklist=not args.no_write_checklist,
            target_section=args.section,
        )
    except PreflightConfigError as exc:
        print(f"[preflight] CONFIG ERROR: {exc}", file=sys.stderr)
        if args.write_receipt:
            write_receipt(
                repo_root,
                exit_code=2,
                section_path=args.section,
                writer_command=writer_command,
                freshness_window_seconds=freshness,
            )
        return 2
    print(_format_summary(report))
    exit_code = 0 if report.ok else 1
    if not report.ok:
        print("")
        print(_format_refuse(report))
    if args.write_receipt:
        write_receipt(
            repo_root,
            exit_code=exit_code,
            section_path=args.section,
            writer_command=writer_command,
            freshness_window_seconds=freshness,
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
