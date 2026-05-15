"""lp_pick_stack package — owner of pick-stack-side primitives.

Inlines the manual-override `VALID_COMBINATIONS` frozenset of `(stack, role)`
tuples per HANDSHAKE §12 + pick-stack plan §3.4. NOT a separate YAML or .py
file: at 13 rules the file overhead doesn't earn its keep. Promote to a
separate module when the matrix exceeds ~30 rules; promote to YAML when the
rules need data-file editing without a Python diff.

The 13 tuples below cover all 10 stacks from the v2.0 catalog (HANDSHAKE §11)
at their canonical default role, plus dual-role variations for next/django/
rails (which ship both fullstack and backend-only personas). Multi-stack
combinations (frontend + backend polyglot, frontend-main + frontend-dashboard,
backend-managed + frontend) compose two valid singletons and are validated
by the pick-stack command's layer-set-validation logic, which lives later in
the pipeline and is gated by the matrix's cross-layer rules (single-role-
per-layer, fullstack-precludes-split, mobile-standalone, polyglot-allowed,
multi-frontend-allowed, backend-managed-pairing, path-uniqueness).

Constants exported:
  - WRITTEN_DECISION_VERSION (writer-side §10 single source — legacy `version` field)
  - SCHEMA_VERSION_V2_1 (v2.1 envelope indicator — `schema_version` field)
  - LICENSE_ENUM (locked starter set per V3 plan §10.v2.1)
  - identity allowlist regexes per V3 plan §10.v2.1 acceptance rules
"""

from __future__ import annotations

import re

# Decision-file version constant (§10 lifecycle bump list). Bumped from
# "0.x-test" to "1.0" in the coordinated v2.0.0 ship commit per HANDSHAKE
# §10. v2.1+ revisions follow the §10 forward-compat policy (BL-211).
#
# v2.1 keeps `version` at "1.0" as an additive-minor envelope: the new
# `schema_version: "1.1"` field is the v2.1 reader indicator per §10.v2.1.
# The legacy `version` field is preserved for v2.0 readers that key off it.
WRITTEN_DECISION_VERSION = "1.0"

# v2.1 envelope indicator (V3 plan §11.1, §10.v2.1 acceptance rules).
# A scaffold-decision.json with `schema_version: "1.1"` is read in full
# v2.1 mode (identity validated against allowlist regexes; stacks required
# as array). Absent or "1.0" reads as legacy 1.0 with UNSET identity
# sentinels and a WARN.
SCHEMA_VERSION_V2_1 = "1.1"

# License enum — locked starter set per V3 plan §10.v2.1 design-time
# decision (Phase 0.3). "Other" carries a free-form `license_other_body`
# field with sanitization rules: max 10KB, printable ASCII, no Jinja
# delimiters or HTML tags.
LICENSE_ENUM = frozenset(
    {
        "MIT",
        "Apache-2.0",
        "GPL-3.0",
        "BSD-3-Clause",
        "ISC",
        "MPL-2.0",
        "Other",
    }
)

# Identity input allowlist regexes (V3 plan §10.v2.1). Validated at
# /lp-pick-stack and /lp-update-identity prompt time, AND at canonical
# read time so a hand-edited scaffold-decision.json with hostile values
# fails closed before any kernel render uses them.
#
# Phase 1+2 retroactive amendment A2: must start with an ASCII letter.
# Closes path-traversal vector ('.', '..'), corrupt npm/pip names, and
# leading-dash inputs that inject as flags into shell-interpolated commands.
# The literal strings '.' and '..' are ALSO rejected at validate_identity
# even though the leading-letter rule already excludes them, as
# defense-in-depth against future regex relaxation.
IDENTITY_PROJECT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
IDENTITY_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
# Phase 1+2 retroactive amendment A4: bumped from {1,128} to {1,200} to
# match HANDSHAKE §10.v2.1 (200-char doc value); 128 was an arbitrary
# tightening that legitimately-long corporate copyright strings exceeded.
IDENTITY_COPYRIGHT_HOLDER_RE = re.compile(r"^[\x20-\x7E]{1,200}$")
IDENTITY_REPO_URL_RE = re.compile(r"^https?://[\w./%-]{1,512}$")

# Phase 1+2 retroactive amendment A2: literal-string reject set checked
# at validate_identity for project_name. The leading-letter rule above
# already excludes these, but an explicit reject keeps the intent visible
# at the callsite even if the regex is later relaxed.
IDENTITY_PROJECT_NAME_LITERAL_REJECTS = frozenset({".", ".."})

# Forbidden chars in copyright holder (defense-in-depth on top of the
# printable-ASCII allowlist; matches the V3 plan §10.v2.1 design lock).
IDENTITY_COPYRIGHT_FORBIDDEN_CHARS = frozenset(
    {
        "`",
        '"',
        "'",
        "$",
        ";",
        # Phase 10 v2.1 (security-auditor F3): prevent Jinja delimiter / HTML
        # tag / format-string injection through the copyright_holder field
        # which is the only identity value that may contain free-form text.
        "{",
        "}",
        "<",
        ">",
        "%",
    }
)

# Placeholder values written when PII opt-in is declined. /lp-update-identity
# (Phase 10) detects these by exact-match against this dict's values plus a
# leading-`<` shape check inside validate_identity (no separate compiled
# regex needed -- a single `startswith("<") and endswith(">")` covers it).
#
# Field set matches HANDSHAKE section 10.v2.1 (Phase 0.3 lock):
# project_name, email, copyright_holder, repo_url. License is the 5th
# identity question with its own enum + sanitization rules (see below).
IDENTITY_PLACEHOLDERS = {
    "project_name": "<project-name>",
    "email": "<email>",
    "copyright_holder": "<copyright-holder>",
    "repo_url": "<repo-url>",
}

# License `Other` body sanitization (V3 plan §10.v2.1 design lock).
LICENSE_OTHER_MAX_BYTES = 10 * 1024  # 10KB cap
LICENSE_OTHER_FORBIDDEN_SUBSTRINGS = ("{{", "{%", "{#", "<", ">")  # Jinja + HTML guard

# 26 (stack, role) tuples — manual-override catalog. Covers all 10 stacks
# from the v2.0 catalog (HANDSHAKE §11) at their canonical default role,
# plus dual-role variations for stacks that ship both fullstack and
# backend-only personas (next, django, rails). Single-purpose stacks
# (astro, eleventy, hugo, hono, fastapi, supabase, expo) are pinned to
# their one valid role; cross-role tuples remain default-deny.
#
# v2.1.4 BL-331: `generic` is selectable as a primary stack across all
# 5 framework-shape roles. The generic adapter is a no-op scaffolder
# (already wired into _ADAPTER_REGISTRY at v2.1) — choosing it produces
# a barebones LaunchPad workspace shell with the cross-cutting wiring
# (lefthook, agents.yml, config.yml, CI) but no upstream template
# fetch. Use case: third-party Astro themes / custom starters /
# frameworks not yet supported by a stack-aware adapter, where the user
# wants the LaunchPad pipeline benefits without LaunchPad fetching a
# template they will throw away. Prior to v2.1.4 the only path to
# `generic` was through the v2.2-candidate fallback (passing
# --accept-v22-fallback against a v2.2-candidate id like `python_generic`),
# which surfaced an unrelated WARN and obscured the actual intent.
VALID_COMBINATIONS = frozenset(
    {
        # Frontend (single-purpose) — base role
        ("astro", "frontend"),
        ("eleventy", "frontend"),
        ("hugo", "frontend"),
        # Multi-frontend variants — used by the multi-frontend category
        # (frontend-main + frontend-dashboard pairing). manual_override_resolver
        # already accepts these roles in ALLOWED_ROLES; tuples below close the
        # cross-check so users can manually re-create the multi-frontend shape
        # (PR #41 cycle 5 #4 + Greptile cycle-4 P1 closure).
        ("astro", "frontend-main"),
        ("astro", "frontend-dashboard"),
        ("eleventy", "frontend-main"),
        ("eleventy", "frontend-dashboard"),
        ("hugo", "frontend-main"),
        ("hugo", "frontend-dashboard"),
        ("next", "frontend-main"),
        ("next", "frontend-dashboard"),
        # Frontend or fullstack (next is the only TS framework with both modes)
        ("next", "frontend"),
        ("next", "fullstack"),
        # Backend (single-purpose)
        ("hono", "backend"),
        ("fastapi", "backend"),
        ("supabase", "backend-managed"),
        # Backend or fullstack (server-rendered frameworks with API-only mode)
        ("django", "backend"),
        ("django", "fullstack"),
        ("rails", "backend"),
        ("rails", "fullstack"),
        # Mobile (single-purpose)
        ("expo", "mobile"),
        # v2.1.4 BL-331: `generic` selectable as a primary stack — barebones
        # workspace shell, bring-your-own-framework. Five role-shape
        # variations because the user picks `generic` to indicate the
        # FRAMEWORK is unspecified, not the role; the role still drives
        # cross-layer pairing semantics (e.g., generic-as-backend can
        # pair with astro-as-frontend in a polyglot scaffold).
        ("generic", "frontend"),
        ("generic", "frontend-main"),
        ("generic", "frontend-dashboard"),
        ("generic", "backend"),
        ("generic", "fullstack"),
    }
)


def is_valid_combination(stack: str, role: str) -> bool:
    """Return True if (stack, role) is in the manual-override catalog.

    Pure-CPU; no I/O. Multi-layer combination validation (polyglot,
    multi-frontend, backend-managed pairing) is the pick-stack command's
    job — this helper is the per-tuple base check that those rules
    compose on top of.
    """
    return (stack, role) in VALID_COMBINATIONS


__all__ = [
    "IDENTITY_COPYRIGHT_FORBIDDEN_CHARS",
    "IDENTITY_COPYRIGHT_HOLDER_RE",
    "IDENTITY_EMAIL_RE",
    "IDENTITY_PLACEHOLDERS",
    "IDENTITY_PROJECT_NAME_LITERAL_REJECTS",
    "IDENTITY_PROJECT_NAME_RE",
    "IDENTITY_REPO_URL_RE",
    "LICENSE_ENUM",
    "LICENSE_OTHER_FORBIDDEN_SUBSTRINGS",
    "LICENSE_OTHER_MAX_BYTES",
    "SCHEMA_VERSION_V2_1",
    "VALID_COMBINATIONS",
    "WRITTEN_DECISION_VERSION",
    "is_valid_combination",
]
