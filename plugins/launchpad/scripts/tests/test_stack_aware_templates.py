"""Phase 4 v2.1 (Slice F) stack-aware template tests.

Per-adapter fragment include verification across 5 stacks * 7 templates,
SandboxedEnvironment for `.sh.j2`, singleton Jinja env across renders,
filter parity (shell_quote / to_yaml_safe).
"""
from __future__ import annotations

from pathlib import Path

import pytest

import jinja2
from jinja2.sandbox import SandboxedEnvironment

from plugin_default_generators._renderer_base import (
    GENERATORS_ROOT,
    STACK_FRAGMENTS_ROOT,
    make_jinja_env,
    make_sandboxed_jinja_env,
    make_stack_aware_jinja_env,
    validate_stack_id,
)

ADAPTERS = ("ts_monorepo", "nextjs_standalone", "nextjs_fastapi", "astro", "generic")
FRAGMENTS = (
    "tech_stack.j2.fragment",
    "backend_structure.j2.fragment",
    "repository_structure.j2.fragment",
    "config.j2.fragment",
    "lefthook.j2.fragment",
    "check_repo_structure.j2.fragment",
    "detect_drift.j2.fragment",
)


def test_all_thirty_five_per_adapter_fragments_exist_on_disk():
    for adapter in ADAPTERS:
        for fragment in FRAGMENTS:
            fpath = (
                STACK_FRAGMENTS_ROOT / adapter / "templates" / fragment
            )
            assert fpath.is_file(), f"missing fragment: {fpath}"


def test_seven_outer_templates_exist_under_stack_aware():
    outer_root = GENERATORS_ROOT / "stack_aware"
    expected = (
        "TECH_STACK.md.j2.outer",
        "BACKEND_STRUCTURE.md.j2.outer",
        "REPOSITORY_STRUCTURE.md.j2.outer",
        "config.yml.j2.outer",
        "lefthook.yml.j2.outer",
        "check-repo-structure.sh.j2.outer",
        "detect-structure-drift.sh.j2.outer",
    )
    for name in expected:
        assert (outer_root / name).is_file(), name


def test_stack_aware_env_renders_tech_stack_for_each_active_adapter():
    env = make_stack_aware_jinja_env()
    template = env.get_template("TECH_STACK.md.j2.outer")
    for adapter in ADAPTERS:
        rendered = template.render(selected_stack_ids=[validate_stack_id(adapter)])
        assert adapter in rendered, (adapter, rendered[:200])


def test_stack_aware_env_composition_mode_iterates_two_adapters():
    env = make_stack_aware_jinja_env()
    template = env.get_template("TECH_STACK.md.j2.outer")
    rendered = template.render(
        selected_stack_ids=["nextjs_standalone", "astro"]
    )
    assert "nextjs_standalone" in rendered
    assert "astro" in rendered


def test_stack_aware_env_singleton_id_stable_across_calls():
    env1 = make_stack_aware_jinja_env()
    env2 = make_stack_aware_jinja_env()
    assert id(env1) == id(env2)


def test_sandboxed_env_is_jinja_sandboxed_environment_instance():
    env = make_sandboxed_jinja_env()
    assert isinstance(env, SandboxedEnvironment)


def test_sandboxed_env_filter_parity_with_make_jinja_env():
    sandbox = make_sandboxed_jinja_env()
    canonical = make_jinja_env("kernel")
    for filter_name in ("shell_quote", "to_yaml_safe", "tojson"):
        assert filter_name in sandbox.filters, filter_name
        assert filter_name in canonical.filters, filter_name


def test_sandboxed_env_blocks_attribute_access_to_underscore_attributes():
    sandbox = make_sandboxed_jinja_env()
    template = sandbox.from_string("{{ obj._private }}")
    with pytest.raises(jinja2.exceptions.SecurityError):
        template.render(obj=type("O", (), {"_private": "secret"})())


def test_check_repo_structure_outer_uses_raw_block_for_shell_safety():
    template_path = (
        GENERATORS_ROOT / "stack_aware" / "check-repo-structure.sh.j2.outer"
    )
    text = template_path.read_text(encoding="utf-8")
    assert "{% raw %}" in text or "{%- raw %}" in text


def test_detect_drift_outer_uses_raw_block_for_shell_safety():
    template_path = (
        GENERATORS_ROOT / "stack_aware" / "detect-structure-drift.sh.j2.outer"
    )
    text = template_path.read_text(encoding="utf-8")
    assert "{% raw %}" in text or "{%- raw %}" in text


def test_each_adapter_fragment_for_check_repo_structure_uses_raw_block():
    for adapter in ADAPTERS:
        text = (
            STACK_FRAGMENTS_ROOT
            / adapter
            / "templates"
            / "check_repo_structure.j2.fragment"
        ).read_text(encoding="utf-8")
        assert "{% raw %}" in text, adapter


def test_lefthook_fragment_emits_per_adapter_command_node():
    env = make_stack_aware_jinja_env()
    template = env.get_template("lefthook.yml.j2.outer")
    rendered = template.render(selected_stack_ids=["nextjs_standalone"])
    assert "nextjs_standalone-noop" in rendered


def test_stack_aware_env_carries_shell_quote_filter():
    env = make_stack_aware_jinja_env()
    assert "shell_quote" in env.filters
    template = env.from_string("{{ value | shell_quote }}")
    assert template.render(value="hello world") == "'hello world'"


def test_repository_structure_outer_lists_each_selected_workspace():
    env = make_stack_aware_jinja_env()
    template = env.get_template("REPOSITORY_STRUCTURE.md.j2.outer")
    rendered = template.render(
        selected_stack_ids=["nextjs_standalone", "nextjs_fastapi"]
    )
    assert "nextjs_standalone" in rendered
    assert "nextjs_fastapi" in rendered


def test_config_fragment_uses_jinja_comment_block():
    template_path = (
        STACK_FRAGMENTS_ROOT / "ts_monorepo" / "templates" / "config.j2.fragment"
    )
    text = template_path.read_text(encoding="utf-8")
    assert "{# v2.1 stack-aware config fragment" in text
