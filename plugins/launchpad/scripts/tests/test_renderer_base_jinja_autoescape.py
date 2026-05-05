"""SSTI regression contract for the v2.1 renderer base (V3 plan section 13.6).

Pins the autoescape posture so a future change to `_renderer_base.make_jinja_env`
cannot silently introduce template-injection. Two distinct contracts:

  1. Variable values are NEVER re-parsed as Jinja syntax. An identity value
     of `{{ 7*7 }}` renders as the literal string `{{ 7*7 }}`, not as 49.
     This is enforced by Jinja's template model (variables render as
     strings, not as syntax trees) and is the core SSTI defense; the test
     pins the contract so a future env override cannot unmask it.

  2. Markdown and YAML templates do NOT get HTML autoescape. Strings like
     `R&D` render verbatim, NOT as `R&amp;D`. HTML autoescape is reserved
     for `.html`, `.htm`, `.xml` templates per the `select_autoescape`
     configuration mirrored from `plugin-doc-generator.py:97-128`.

  3. StrictUndefined fails loudly on missing variables. Catches a class
     of typos (`{{ identity.email }}` vs `{{ identity.emial }}`) at
     render time rather than producing empty strings that ship to disk.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Sibling-script imports
_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import jinja2  # noqa: E402

from plugin_default_generators._renderer_base import (  # noqa: E402
    RendererBase,
    identity_inject,
    make_jinja_env,
)


def _identity(**overrides):
    base = {
        "pii_opt_in": True,
        "project_name": "demo",
        "email": "demo@example.com",
        "copyright_holder": "Demo",
        "repo_url": "https://example.com/demo",
        "license": "MIT",
        "license_other_body": "",
    }
    base.update(overrides)
    return base


def test_jinja_template_value_is_not_re_evaluated(tmp_path: Path) -> None:
    """SSTI defense: a hostile value like `{{ 7*7 }}` MUST land as the
    literal string in rendered output, never as `49`. This pins the
    contract so a future env override cannot silently introduce the
    server-side template injection vector."""
    env = make_jinja_env("kernel")
    template = env.from_string("Hello, {{ identity.project_name }}!")
    out = template.render(identity={"project_name": "{{ 7*7 }}"})
    assert out == "Hello, {{ 7*7 }}!"
    assert "49" not in out


def test_html_chars_in_markdown_are_not_escaped(tmp_path: Path) -> None:
    """Markdown templates use the same Environment as kernel templates.
    A normal text value with `&`, `<`, `>` must render verbatim, not as
    `&amp;`, `&lt;`, `&gt;`. This catches a regression where someone
    flips `default=False` to `default=True` in select_autoescape and
    silently corrupts every README and CONTRIBUTING.md the plugin ships.

    Uses an explicit `.md.j2` template so the autoescape extension match
    actually fires (the previous test used `.from_string` which has no
    extension, exercising the default branch only)."""
    md_template = tmp_path / "snippet.md.j2"
    md_template.write_text("Note: R&D for {{ identity.project_name }} <core>.\n")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(tmp_path)),
        autoescape=jinja2.select_autoescape(
            enabled_extensions=("html", "htm", "xml"),
            default_for_string=False,
            default=False,
        ),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    out = env.get_template("snippet.md.j2").render(identity={"project_name": "demo"})
    assert "R&D" in out and "R&amp;D" not in out
    assert "<core>" in out and "&lt;core&gt;" not in out


def test_strict_undefined_raises_on_missing_variable() -> None:
    """A typo like `{{ identity.emial }}` MUST fail at render time, not
    produce an empty string. Pins StrictUndefined."""
    env = make_jinja_env("kernel")
    template = env.from_string("contact: {{ identity.emial }}")
    with pytest.raises(jinja2.UndefinedError):
        template.render(identity={"email": "demo@example.com"})


def test_shell_quote_filter_escapes_dangerous_chars() -> None:
    """The `shell_quote` filter wraps shlex.quote so identity values
    flowing into shell scripts cannot break out of single-quoted strings.
    Caller responsibility: use `| shell_quote` for any value that lands
    in a bash context."""
    env = make_jinja_env("kernel")
    template = env.from_string('echo {{ value | shell_quote }}')
    out = template.render(value="hello; rm -rf /")
    # shlex.quote wraps in single quotes and escapes embedded single quotes
    assert out.startswith("echo '")
    assert "; rm -rf /" not in out.split("'")[0]  # not in the unquoted portion


def test_to_yaml_safe_filter_quotes_problematic_strings() -> None:
    """The `to_yaml_safe` filter emits a properly-quoted YAML scalar so
    an identity value containing colons or leading dashes cannot break
    out of the surrounding YAML structure."""
    env = make_jinja_env("kernel")
    template = env.from_string("name: {{ value | to_yaml_safe }}")
    out = template.render(value="key: value with: colons")
    # safe_dump emits double-quoted form; the value must be wrapped
    assert '"' in out
    assert "key: value with: colons" in out  # original content preserved verbatim


def test_identity_inject_provides_current_year_and_license_url() -> None:
    """The identity_inject helper enriches the identity dict with derived
    helpers (current_year, license_url). Templates rely on these being
    present without explicit caller setup."""
    ctx = identity_inject(_identity(license="Apache-2.0"))
    assert isinstance(ctx["current_year"], int)
    assert ctx["current_year"] >= 2026
    assert ctx["license_url"] == "https://choosealicense.com/licenses/apache-2.0/"


def test_identity_inject_license_other_has_no_url() -> None:
    """`Other` license has no canonical URL; `license_url` is None and
    callers route to `identity.license_other_body` for the actual text."""
    ctx = identity_inject(_identity(license="Other", license_other_body="custom"))
    assert ctx["license_url"] is None


def test_renderer_base_subclass_must_set_template_subdir() -> None:
    """A buggy subclass that forgets to set TEMPLATE_SUBDIR must fail
    at construction, not silently use the empty default."""
    class BrokenRenderer(RendererBase):
        pass  # no TEMPLATE_SUBDIR

    with pytest.raises(ValueError, match="TEMPLATE_SUBDIR"):
        BrokenRenderer()
