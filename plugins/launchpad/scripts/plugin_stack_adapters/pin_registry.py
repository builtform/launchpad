"""Pin registry: single source of truth for upstream template commit SHAs.

CODEOWNERS-protected. Every modification of a `sha` value in `_PINS` requires a
same-commit append-only entry in `docs/maintainers/upstream-pin-rotations.md`
(enforced by the rotation-detector lint rule in `plugin-v2-handshake-lint.py`).

Dual-resolved SHAs only: every pin must have been verified via BOTH
`git ls-remote` and the GitHub REST `/repos/{owner}/{repo}/git/refs/tags/{tag}`
endpoint, with both returning the same value, before being recorded here.
See Phase 4 plan section 3.2.
"""
from __future__ import annotations

import re
from typing import Literal, TypedDict

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

AttestationRef = Literal["unsigned", "verified"]


class Pin(TypedDict):
    sha: str
    repo_url: str
    license: str
    attestation_ref: AttestationRef


_PINS: dict[tuple[str, str | None], Pin] = {
    ("nextjs_standalone", None): {
        "sha": "9aad7123ef8accc79d6ece399f249c46bdb6b138",
        "repo_url": "https://github.com/vercel/next-forge",
        "license": "MIT",
        "attestation_ref": "unsigned",
    },
    ("nextjs_fastapi", None): {
        "sha": "62b67456e8f01760970455282282ecaa393fbd38",
        "repo_url": "https://github.com/vintasoftware/nextjs-fastapi-template",
        "license": "MIT",
        "attestation_ref": "unsigned",
    },
    ("astro", "docs"): {
        "sha": "2c530192705d569a7f6f29a33cd34b61932f786e",
        "repo_url": "https://github.com/withastro/starlight",
        "license": "MIT",
        "attestation_ref": "unsigned",
    },
    ("astro", "blog"): {
        "sha": "3f67b84bcfd232574a4832d4d32fcc724fdd3be5",
        "repo_url": "https://github.com/withastro/astro",
        "license": "MIT",
        "attestation_ref": "unsigned",
    },
    ("astro", "marketing"): {
        "sha": "3f67b84bcfd232574a4832d4d32fcc724fdd3be5",
        "repo_url": "https://github.com/withastro/astro",
        "license": "MIT",
        "attestation_ref": "unsigned",
    },
}


class PinNotFoundError(KeyError):
    pass


class InvalidPinShaError(ValueError):
    pass


def get_pin(adapter_id: str, sub_template_id: str | None = None) -> Pin:
    key = (adapter_id, sub_template_id)
    if key not in _PINS:
        raise PinNotFoundError(
            f"no pin registered for adapter={adapter_id!r} "
            f"sub_template={sub_template_id!r}"
        )
    pin = _PINS[key]
    if not _SHA_RE.match(pin["sha"]):
        raise InvalidPinShaError(
            f"pin sha for {key} is not a 40-char hex commit SHA: {pin['sha']!r}"
        )
    return pin


def all_pins() -> list[tuple[str, str | None, Pin]]:
    return [(adapter, sub, pin) for (adapter, sub), pin in _PINS.items()]


__all__ = [
    "Pin",
    "AttestationRef",
    "PinNotFoundError",
    "InvalidPinShaError",
    "get_pin",
    "all_pins",
]
