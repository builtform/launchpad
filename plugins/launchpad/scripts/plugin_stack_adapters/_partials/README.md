# `_partials/` — shared Jinja2 template fragments

This directory holds shared template artifacts (partials + macros) that
multiple stack adapters can `{% include %}` or `{% from … import … %}`.

## Naming convention

- All filenames begin with an underscore (`_python_gates.j2.fragment`,
  `_require_tool_macro.j2.fragment`). The leading underscore signals
  "shared/private — not a stack adapter."
- Stack-id enumeration code MUST filter `_*` paths to avoid treating
  `_partials/` as a phantom stack. See
  `tests/test_lefthook_template_python_gates.py::test_partials_not_in_active_stack_enum`.

## Loader resolution

The `ChoiceLoader` in `_renderer_base.make_stack_aware_jinja_env()`
roots `plugin_stack_adapters/` as one of the search paths. Includers
reference partials via the absolute-from-loader-root form:

    {% include "_partials/_python_gates.j2.fragment" %}

NOT relative-to-includer:

    {% include "../_partials/_python_gates.j2.fragment" %}  # WRONG

Cross-partial macro imports use the same form:

    {% from "_partials/_require_tool_macro.j2.fragment" import require_tool %}

## Current contents

- `_python_gates.j2.fragment` — 5 Python lefthook gates (BL-316). Included by `nextjs_fastapi/templates/lefthook.j2.fragment` at v2.1.2.
- `_require_tool_macro.j2.fragment` — `require_tool(name, install_pin)` macro for fail-loud preambles. Cross-partial import: `{% from "_partials/_require_tool_macro.j2.fragment" import require_tool %}`.

## v2.2 caveats

- `_python_gates.j2.fragment` hardcodes `pyright apps/api` then `pyright api` probe order. v2.2 stack adapters whose Python workspace lives elsewhere (e.g., `python_django` defaults to repo root per `polyglot_path_rewriter.py`) MUST override the pyright probe block in their own fragment, NOT blanket-include this partial unmodified. v2.2 may extract the probe block into a parametrized macro to avoid the override pattern.
