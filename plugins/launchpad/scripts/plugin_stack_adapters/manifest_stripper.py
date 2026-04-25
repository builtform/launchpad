"""Strip secret-bearing fields from parsed manifests before the generator
embeds values into canonical docs.

Complements the post-scan (`secret-patterns.txt`) by removing the FIELDS
where secrets routinely hide — strip-at-source catches unknown token formats
that pattern matching would miss.

Fields stripped:
  package.json:
    - scripts.*            (often contain DATABASE_URL=... inline)
    - publishConfig
    - config.*
  pyproject.toml:
    - [tool.poetry.source].*       (private registry URLs with tokens)
    - any [tool.*] section URL values
    - keys named token / password / secret / apikey / api_key (case-insensitive)
  Cargo.toml:
    - [registries.*]               (registry tokens)
  go.mod:
    - replace directives pointing at private paths
  Gemfile:
    - source URLs with embedded credentials
  composer.json:
    - repositories[].url with embedded credentials

Stripped values appear as '<redacted>' in generated docs. Users can manually
restore if the fields aren't actually sensitive in their repo.
"""
from __future__ import annotations

import re
from typing import Any


REDACTED = "<redacted>"

# Matches URLs with embedded credentials (user:pass@)
_CREDS_URL = re.compile(r"[a-z]+://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)

# Keys (any level) whose values always get redacted.
_SECRET_KEY_NAMES = {"token", "password", "secret", "apikey", "api_key"}


def _redact_if_creds_url(val: Any) -> Any:
    """Redact strings that look like 'scheme://user:pass@host'."""
    if isinstance(val, str) and _CREDS_URL.search(val):
        return REDACTED
    return val


def _redact_secret_keys(obj: Any) -> Any:
    """Walk a dict/list recursively; redact values under secret-named keys."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _SECRET_KEY_NAMES:
                out[k] = REDACTED
            else:
                out[k] = _redact_secret_keys(v)
        return out
    if isinstance(obj, list):
        return [_redact_secret_keys(item) for item in obj]
    return _redact_if_creds_url(obj)


def strip_package_json(data: dict[str, Any]) -> dict[str, Any]:
    """Strip secret-bearing fields from package.json.

    Never mutates the input — returns a new dict.
    """
    out = dict(data)
    if "scripts" in out:
        # Scripts often contain inlined env vars with secrets. Keep the key
        # list but redact values — the generator still knows WHICH scripts
        # exist without leaking their contents.
        out["scripts"] = {name: REDACTED for name in out["scripts"]}
    if "publishConfig" in out:
        out["publishConfig"] = REDACTED
    if "config" in out and isinstance(out["config"], dict):
        out["config"] = {k: REDACTED for k in out["config"]}
    # Generic URL-with-creds sweep for any remaining string field
    return _redact_secret_keys(out)


def strip_pyproject_toml(data: dict[str, Any]) -> dict[str, Any]:
    """Strip secret-bearing fields from pyproject.toml."""
    out = {k: v for k, v in data.items()}
    tool = out.get("tool")
    if isinstance(tool, dict):
        new_tool = {}
        for name, section in tool.items():
            if not isinstance(section, dict):
                new_tool[name] = section
                continue
            # poetry.source — private registries with tokens
            if name == "poetry" and "source" in section:
                new_section = dict(section)
                new_section["source"] = REDACTED
                new_tool[name] = new_section
            else:
                # Strip URL values and secret-named keys throughout any tool section
                new_tool[name] = _redact_secret_keys(section)
        out["tool"] = new_tool
    return _redact_secret_keys(out)


def strip_cargo_toml(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    if "registries" in out:
        out["registries"] = REDACTED
    return _redact_secret_keys(out)


def strip_go_mod(data: dict[str, Any]) -> dict[str, Any]:
    """go.mod parses to {module, raw}. Strip 'replace' lines pointing at
    private paths from the raw text."""
    out = dict(data)
    raw = out.get("raw", "")
    if not raw:
        return out

    cleaned_lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        # Heuristic: 'replace' directives with URL-like targets
        if stripped.startswith("replace ") and ("://" in stripped or "@" in stripped):
            cleaned_lines.append(f"replace <redacted> => <redacted>")
        else:
            cleaned_lines.append(line)
    out["raw"] = "\n".join(cleaned_lines)
    return out


def strip_gemfile(data: dict[str, Any]) -> dict[str, Any]:
    """Gemfile is free-form Ruby DSL; only raw text available. Redact any
    source URL lines containing credentials."""
    out = dict(data)
    raw = out.get("raw", "")
    if not raw:
        return out

    cleaned_lines = []
    for line in raw.splitlines():
        if _CREDS_URL.search(line):
            cleaned_lines.append(f"# <redacted: line contained credentials>")
        else:
            cleaned_lines.append(line)
    out["raw"] = "\n".join(cleaned_lines)
    return out


def strip_composer_json(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    if "repositories" in out and isinstance(out["repositories"], list):
        new_repos = []
        for repo in out["repositories"]:
            if isinstance(repo, dict) and "url" in repo:
                if isinstance(repo["url"], str) and _CREDS_URL.search(repo["url"]):
                    new_repo = dict(repo)
                    new_repo["url"] = REDACTED
                    new_repos.append(new_repo)
                    continue
            new_repos.append(repo)
        out["repositories"] = new_repos
    return _redact_secret_keys(out)


STRIPPERS = {
    "package.json": strip_package_json,
    "pyproject.toml": strip_pyproject_toml,
    "Cargo.toml": strip_cargo_toml,
    "go.mod": strip_go_mod,
    "Gemfile": strip_gemfile,
    "composer.json": strip_composer_json,
}


def strip(manifest_name: str, data: dict[str, Any]) -> dict[str, Any]:
    """Dispatch to the appropriate stripper for a given manifest filename."""
    fn = STRIPPERS.get(manifest_name)
    if fn is None:
        # Unknown manifest — apply the generic sweep as a safety net
        return _redact_secret_keys(data)
    return fn(data)
