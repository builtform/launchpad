"""LaunchPad plugin default generators package.

Houses the v2.1 renderer split (V3 plan section 13.6):
  * `_renderer_base.RendererBase` — shared Jinja env + atomic-write primitives.
  * `kernel_renderer.KernelRenderer` — 7 stack-agnostic identity-bearing files.
  * `infrastructure_renderer.InfrastructureRenderer` — Phase 3 30-path overlay.

Importing this package as `plugin_default_generators` lets sibling scripts use
plain `from plugin_default_generators.<module> import ...` instead of the
`importlib.util.spec_from_file_location` shim that the legacy hyphenated
directory name (`plugin-default-generators`) forced.
"""
