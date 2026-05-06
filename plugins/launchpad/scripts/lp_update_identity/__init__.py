"""lp_update_identity package (v2.1 Phase 10).

Owns the `/lp-update-identity` slash command which re-seals identity values
in `.launchpad/scaffold-decision.json` and re-renders the 7 kernel files via
`KernelRenderer.refresh()` per Phase 3 cement (`lp_bootstrap/__init__.py:10-14`
+ `lp-bootstrap.md:34-38`) -- NOT through `/lp-bootstrap --refresh`.

Surface boundary:

  * The `.launchpad/.identity-update-in-progress` sentinel structurally
    mirrors `lp_bootstrap/sentinel.py` per DA3 (with field renames called
    out below). Bidirectional cross-detection: `/lp-bootstrap` refuses on
    `.identity-update-in-progress` + live PID; `/lp-update-identity`
    refuses on `.bootstrap-in-progress` + live PID.
  * `_validate_preconditions()` lives inline in `engine.py` per DA4 module
    collapse (no separate `preconditions.py`).
  * `kernel_render_state` block lives inside `scaffold-decision.json` per
    DA7 flip (no sidecar artifact).

Behavioural code lives in:

  * `sentinel.py` -- `.launchpad/.identity-update-in-progress` lifecycle +
    PID liveness via `os.kill(pid, 0)`. O_CREAT|O_EXCL primitive at
    `os.open()` time so concurrent-create races refuse cleanly per F2.
  * `engine.py` (Slice C) -- `run_update_identity()` orchestration +
    inline `_validate_preconditions()`.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Final


# --- Filesystem name constants --------------------------------------------

# Sentinel filename for `/lp-update-identity` lifecycle. Lives at
# `<cwd>/.launchpad/.identity-update-in-progress`; written before any
# scaffold-decision mutation, removed on successful completion or
# auto-recovered on dead-PID re-entry.
IDENTITY_UPDATE_SENTINEL_NAME: Final[str] = ".identity-update-in-progress"

# Sentinel mode value. Free string per DA3 ("NOT typed Literal -- mirrors
# bootstrap's free-string with documented values"). v2.1 ships only this
# single mode.
IDENTITY_UPDATE_SENTINEL_MODE: Final[str] = "update-identity"


# --- Error code contract (DA4) --------------------------------------------

class IdentityUpdateErrorCode(StrEnum):
    """Structured error codes raised by `/lp-update-identity`.

    Per DA4 v3 (8 codes; collapsed from v1's 10 per code-simplicity P2;
    status enum split). User-visible category map lives in
    `commands/lp-update-identity.md` ## Error codes section.
    """
    SCAFFOLD_DECISION_MISSING = "scaffold_decision_missing"
    IDENTITY_UPDATE_IN_PROGRESS = "identity_update_in_progress"
    BOOTSTRAP_IN_PROGRESS = "bootstrap_in_progress"
    PERMISSION_DENIED = "permission_denied"
    USER_EDIT_BLOCKS_REFRESH = "user_edit_blocks_refresh"
    IDENTITY_VALIDATION_FAILED = "identity_validation_failed"
    GIT_CONFIG_EMAIL_MISMATCH = "git_config_email_mismatch"
    BROWNFIELD_SEED_REFUSED = "brownfield_seed_refused"


class IdentityUpdateStatus(StrEnum):
    """Info-class returns from `run_update_identity()`; not errors.

    Per DA4 status-vs-error split (code-simplicity P2). Carried by
    `UpdateIdentityResult.status`.
    """
    UPDATED = "updated"
    NO_OP = "no_op"
    SEEDED_FIRST_TIME = "seeded_first_time"


class IdentityUpdateSentinelError(RuntimeError):
    """Sentinel read/write/inspect failure raised by `sentinel.py`.

    Symmetric to `lp_bootstrap.sentinel.BootstrapSentinelError` per DA3.
    Carries an `IdentityUpdateErrorCode` reason so the engine can wire it
    into the user-facing structured error.
    """

    def __init__(
        self,
        message: str,
        *,
        reason: IdentityUpdateErrorCode,
        path: "object | None" = None,
        remediation: str = "",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.path = path
        self.remediation = remediation


__all__ = [
    "IDENTITY_UPDATE_SENTINEL_MODE",
    "IDENTITY_UPDATE_SENTINEL_NAME",
    "IdentityUpdateErrorCode",
    "IdentityUpdateSentinelError",
    "IdentityUpdateStatus",
]
