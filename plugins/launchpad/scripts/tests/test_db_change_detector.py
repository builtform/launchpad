"""Database detection across the supported schema and migration layouts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest

from db_change_detector import detect

_SCRIPT = Path(__file__).resolve().parents[1] / "db_change_detector.py"
_DRIZZLE = 'export default defineConfig({schema: "./src/schema.ts", out: "./drizzle"});'
_ALEMBIC = {"alembic/env.py": "", "alembic/script.py.mako": ""}


def _seed(root: Path, files: dict[str, str | bytes]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))


_CASES = [
    pytest.param(
        {"packages/db/prisma/schema.prisma": "model User {}", "packages/db/prisma/migrations/migration_lock.toml": "", "packages/db/prisma/migrations/20261107000000_init/migration.sql": ""},
        ["packages/db/prisma/schema.prisma"],
        {"tool": "prisma", "root": "packages/db", "changed_schema": ["packages/db/prisma/schema.prisma"], "changed_migrations": [], "migrations_dir": "packages/db/prisma/migrations"},
        id="prisma-template",
    ),
    pytest.param(
        {"prisma/schema/user.prisma": "", "prisma/schema/post.prisma": ""},
        ["prisma/schema/user.prisma"],
        {"tool": "prisma", "root": ".", "schema_paths": ["prisma/schema/post.prisma", "prisma/schema/user.prisma"]},
        id="prisma-multiple-schema-files",
    ),
    pytest.param(
        {"packages/db/drizzle.config.ts": _DRIZZLE, "packages/db/src/schema.ts": "", "packages/db/drizzle/0000_init.sql": "", "packages/db/drizzle/meta/_journal.json": "{}"},
        ["packages/db/src/schema.ts"],
        {"tool": "drizzle", "root": "packages/db", "schema_paths": ["packages/db/src/schema.ts"], "migrations_dir": "packages/db/drizzle"},
        id="drizzle-config",
    ),
    pytest.param(
        {"drizzle.config.ts": 'export default {schema: ["./src/a.ts", "./src/schema/*"], out: "./migrations-sql"};', "src/a.ts": "", "src/schema/users.ts": "", "migrations-sql/0001_x.sql": ""},
        ["src/schema/users.ts", "migrations-sql/0001_x.sql"],
        {"tool": "drizzle", "root": ".", "schema_paths": ["src/a.ts", "src/schema/users.ts"], "changed_schema": ["src/schema/users.ts"], "changed_migrations": ["migrations-sql/0001_x.sql"], "migrations_dir": "migrations-sql"},
        id="drizzle-array-and-glob",
    ),
    pytest.param(
        {"drizzle.config.ts": 'export default {schema: "./src/schema"};', "src/schema/users.ts": "", "src/schema/nested/posts.mts": ""},
        ["src/schema/users.ts"],
        {"tool": "drizzle", "schema_paths": ["src/schema/nested/posts.mts", "src/schema/users.ts"]},
        id="drizzle-folder",
    ),
    pytest.param(
        {"drizzle.config.ts": "export default {schema: schemaPath};", "src/schema.ts": ""},
        ["src/schema.ts"],
        {"tool": "drizzle", "note_contains": ["unresolved schema"]},
        id="drizzle-unresolved",
    ),
    pytest.param(
        {"drizzle.config.ts": 'export default {schema: "../../x.ts", out: "/tmp"};', "src/schema.ts": ""},
        ["src/schema.ts"],
        {"tool": "drizzle", "schema_paths": ["src/schema.ts"], "migrations_dir": "drizzle", "note_contains": ["unresolved schema", "unresolved out"], "note_count": 2},
        id="drizzle-escaping-values",
    ),
    pytest.param(
        {"drizzle/meta/_journal.json": "{}"}, ["drizzle/0001_b.sql"],
        {"tool": "drizzle", "migrations_dir": "drizzle"},
        id="drizzle-journal-only",
    ),
    pytest.param(
        {"drizzle.config.ts": 'export default {schema: "./packages/db/src/schema.ts"};', "packages/db/drizzle.config.ts": _DRIZZLE, "packages/db/src/schema.ts": ""},
        ["packages/db/src/schema.ts"],
        {"tool": "drizzle", "root": "packages/db", "changed_schema": ["packages/db/src/schema.ts"]},
        id="drizzle-nested-instances",
    ),
    pytest.param(
        {"drizzle.config.ts": _DRIZZLE, "drizzle/meta/_journal.json": "{}"},
        ["drizzle/0001_x.sql"], {"tool": "drizzle", "root": "."},
        id="drizzle-covered-journal",
    ),
    pytest.param(
        {"supabase/migrations/20261107000000_x.sql": ""},
        ["supabase/migrations/20261107000000_x.sql"],
        {"tool": "supabase", "root": ".", "changed_migrations": ["supabase/migrations/20261107000000_x.sql"]},
        id="supabase",
    ),
    pytest.param(
        {"packages/db/supabase/migrations/20261107000000_x.sql": ""},
        ["packages/db/supabase/migrations/20261107000000_x.sql"],
        {"tool": "supabase", "root": "packages/db"},
        id="supabase-nested",
    ),
    pytest.param(
        {"packages/db/db/migrate/20261107000000_x.rb": ""},
        ["packages/db/db/migrate/20261107000000_x.rb"],
        {"tool": "rails", "root": "packages/db"},
        id="rails-nested",
    ),
    pytest.param(
        {"services/api/db/migrations/001_init.sql": ""},
        ["services/api/db/migrations/001_init.sql"],
        {"tool": "sql", "note_contains": ["no schema side"]},
        id="sql-nested",
    ),
    pytest.param(
        {"app/models.py": "", "app/migrations/__init__.py": ""},
        ["app/models.py"], {"tool": "django", "root": ".", "changed_schema": ["app/models.py"]},
        id="django-model",
    ),
    pytest.param(
        {"app/migrations/__init__.py": "", "app/migrations/0002_add.py": ""},
        ["app/migrations/0002_add.py"],
        {"tool": "django", "changed_migrations": ["app/migrations/0002_add.py"]},
        id="django-migration",
    ),
    pytest.param({"app/models.py": ""}, ["app/models.py"], None, id="django-decoy"),
    pytest.param(
        {**_ALEMBIC, "alembic/versions/ab12_x.py": ""},
        ["alembic/versions/ab12_x.py"], {"tool": "alembic", "root": "."},
        id="alembic-migration",
    ),
    pytest.param(
        {**_ALEMBIC, "app/models.py": "from sqlalchemy.orm import DeclarativeBase\n"},
        ["app/models.py"], {"tool": "alembic", "changed_schema": ["app/models.py"], "schema_paths": ["app/models.py"], "note_contains": ["only changed"]},
        id="alembic-model",
    ),
    pytest.param(
        {".venv/lib/site-packages/alembic/templates/generic/env.py": "", ".venv/lib/site-packages/alembic/templates/generic/script.py.mako": "", "app/models.py": "from sqlalchemy.orm import DeclarativeBase\n"},
        ["app/models.py"], None, id="alembic-decoy",
    ),
    pytest.param(
        {"db/migrate/20261107000000_x.rb": "", "db/schema.rb": ""},
        ["db/migrate/20261107000000_x.rb", "db/schema.rb"],
        {"tool": "rails", "changed_schema": ["db/schema.rb"], "changed_migrations": ["db/migrate/20261107000000_x.rb"]},
        id="rails-both-sides",
    ),
    pytest.param({"db/migrations/001_init.sql": ""}, ["db/migrations/001_init.sql"], {"tool": "sql"}, id="plain-sql"),
    pytest.param({"src/app.ts": ""}, ["src/app.ts"], None, id="no-database-change"),
    pytest.param(
        {"drizzle.config.ts": b"\xff", "src/schema.ts": ""},
        ["src/schema.ts"], {"tool": "drizzle", "note_contains": ["unresolved"]},
        id="binary-config",
    ),
]


@pytest.mark.parametrize(("files", "changed", "expected"), _CASES)
def test_detection_layouts(tmp_path: Path, files, changed, expected):
    _seed(tmp_path, files)
    result = detect(changed, tmp_path)
    assert result["detector_version"] == 1
    assert result["ignored_paths"] == 0
    assert result["db_changes"] == (expected is not None)
    if expected is None:
        assert result["projects"] == []
        return
    assert len(result["projects"]) == 1
    project = result["projects"][0]
    for key, value in expected.items():
        if key == "note_contains":
            assert all(any(part in note for note in project["notes"]) for part in value)
        elif key == "note_count":
            assert len(project["notes"]) == value
        else:
            assert project[key] == value
    for key in ("schema_paths", "changed_schema", "changed_migrations", "changed_other", "notes"):
        assert project[key] == sorted(set(project[key]))
    for name in [project["root"], project["migrations_dir"], *project["schema_paths"], *project["changed_schema"], *project["changed_migrations"], *project["changed_other"]]:
        assert not PurePosixPath(name).is_absolute()
        assert ".." not in PurePosixPath(name).parts
        assert (tmp_path / name).resolve().is_relative_to(tmp_path.resolve())


def test_unsafe_input_is_counted(tmp_path: Path):
    result = detect(["/etc/passwd", "../x.sql", "x\0.sql", "", " \n"], tmp_path)
    assert result == {"detector_version": 1, "db_changes": False, "ignored_paths": 3, "projects": []}


def test_symlinked_schema_is_claimed_but_not_emitted(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.ts"
    outside.write_text("external", encoding="utf-8")
    _seed(tmp_path, {"drizzle.config.ts": _DRIZZLE})
    schema = tmp_path / "src/schema.ts"
    schema.parent.mkdir()
    try:
        schema.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable")
    result = detect(["src/schema.ts"], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["tool"] == "drizzle"
    assert "src/schema.ts" not in project["schema_paths"]
    assert project["changed_schema"] == []
    assert len(project["notes"]) == 1
    assert "src/schema.ts" in project["notes"][0]


def _cli(root: Path, paths: str, *args: str):
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--repo-root", str(root), *args],
        input=paths, text=True, capture_output=True, check=False, timeout=10,
    )


@pytest.mark.parametrize("args", [("--unknown",), ("--repo-root", "/nonexistent"), ("--repo-root",)])
def test_usage_errors(tmp_path: Path, args):
    result = _cli(tmp_path, "", *args)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("db_change_detector:")


def test_null_input_matches_imported_helper(tmp_path: Path):
    name = "supabase/migrations/20261107000000_x.sql"
    _seed(tmp_path, {name: ""})
    result = _cli(tmp_path, name + "\0", "--null")
    assert result.returncode == 0
    assert json.loads(result.stdout) == detect([name], tmp_path)


def test_cli_output_is_deterministic(tmp_path: Path):
    _seed(tmp_path, {"drizzle.config.ts": _DRIZZLE, "src/schema.ts": "", "drizzle/0001_x.sql": ""})
    paths = ["src/schema.ts", "drizzle/0001_x.sql", "src/schema.ts"]
    first = _cli(tmp_path, "\n".join(paths))
    second = _cli(tmp_path, "\n".join(reversed(paths)))
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout


def test_project_files_are_never_executed(tmp_path: Path):
    _seed(tmp_path, {"drizzle.config.ts": _DRIZZLE + '\nthrow new Error("must not execute");', "src/schema.ts": ""})
    assert detect(["src/schema.ts"], tmp_path)["db_changes"]
    source = _SCRIPT.read_text(encoding="utf-8")
    for token in ("import subprocess", "os.system", "exec(", "eval(", "importlib", "__import__", "runpy", "compile(", "pickle", "marshal"):
        assert token not in source


def test_large_config_is_unresolved(tmp_path: Path):
    _seed(tmp_path, {"drizzle.config.ts": "x" * (1024 * 1024 + 1), "src/schema.ts": ""})
    project = detect(["src/schema.ts"], tmp_path)["projects"][0]
    assert any("over 1 MiB" in note for note in project["notes"])


def test_globs_skip_excluded_directories_and_symlinks(tmp_path: Path):
    _seed(tmp_path, {"drizzle.config.ts": 'export default {schema: "./src/**/*.ts"};', "src/a.ts": "", "src/node_modules/skip.ts": "", "src/.venv/skip.ts": "", "src/dist/skip.ts": ""})
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "external.ts").write_text("external", encoding="utf-8")
    try:
        (tmp_path / "src/link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are unavailable")
    project = detect(["src/a.ts"], tmp_path)["projects"][0]
    assert project["schema_paths"] == ["src/a.ts"]


@pytest.mark.parametrize("quote", ["'", '"', chr(96)])
def test_config_literal_quote_forms(tmp_path: Path, quote: str):
    _seed(tmp_path, {"drizzle.config.ts": f"export default {{schema: {quote}./src/schema.ts{quote}, out: {quote}./sql-output{quote}}};", "src/schema.ts": ""})
    project = detect(["src/schema.ts"], tmp_path)["projects"][0]
    assert project["schema_paths"] == ["src/schema.ts"]
    assert project["migrations_dir"] == "sql-output"


@pytest.mark.parametrize("value", ["schemaPath", "resolvePath()", '["./src/schema.ts", ...others]', chr(96) + "./" + "$" + "{schemaPath}" + chr(96)])
def test_dynamic_config_values_are_unresolved(tmp_path: Path, value: str):
    _seed(tmp_path, {"drizzle.config.ts": f"export default {{schema: {value}, out: outputPath}};", "src/schema.ts": ""})
    project = detect(["src/schema.ts"], tmp_path)["projects"][0]
    assert any("unresolved schema" in note for note in project["notes"])
    assert any("unresolved out" in note for note in project["notes"])
    assert project["migrations_dir"] == "drizzle"


def test_binary_config_cli_succeeds(tmp_path: Path):
    _seed(tmp_path, {"drizzle.config.ts": b"\xff", "src/schema.ts": ""})
    result = _cli(tmp_path, "src/schema.ts\n")
    assert result.returncode == 0
    assert json.loads(result.stdout)["db_changes"]


def test_control_character_path_is_ignored(tmp_path: Path):
    result = detect(["sql/unsafe\x01.sql"], tmp_path)
    assert result["ignored_paths"] == 1
    assert result["db_changes"] is False


def test_prisma_sql_requires_migration_lock(tmp_path: Path):
    _seed(tmp_path, {"prisma/schema.prisma": "", "prisma/migrations/001/migration.sql": ""})
    project = detect(["prisma/migrations/001/migration.sql"], tmp_path)["projects"][0]
    assert project["tool"] == "sql"


def test_quoted_config_property_names(tmp_path: Path):
    _seed(tmp_path, {"drizzle.config.js": 'export default {"schema": "./custom/users.ts", "out": "./custom-migrations"};', "custom/users.ts": ""})
    project = detect(["custom/users.ts"], tmp_path)["projects"][0]
    assert project["schema_paths"] == ["custom/users.ts"]
    assert project["migrations_dir"] == "custom-migrations"


def test_prisma_schema_uses_migration_lock_anchor(tmp_path: Path):
    _seed(tmp_path, {"packages/db/a-schema/user.prisma": "", "packages/db/migrations/migration_lock.toml": ""})
    project = detect(["packages/db/a-schema/user.prisma"], tmp_path)["projects"][0]
    assert project["root"] == "packages/db"
    assert project["migrations_dir"] == "packages/db/migrations"


@pytest.mark.parametrize("error", [PermissionError("denied"), ValueError("unreadable"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")])
def test_project_read_errors_are_notes(tmp_path: Path, monkeypatch, error):
    _seed(tmp_path, {"drizzle.config.ts": _DRIZZLE, "src/schema.ts": ""})
    original = Path.open

    def guarded(path, *args, **kwargs):
        if path.name == "drizzle.config.ts":
            raise error
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    result = detect(["src/schema.ts"], tmp_path)
    assert result["db_changes"]
    assert any(type(error).__name__ in note for note in result["projects"][0]["notes"])


def test_drizzle_comments_and_strings_do_not_shadow_schema(tmp_path: Path):
    _seed(tmp_path, {
        "drizzle.config.ts": '// Previous setup: {schema: "./old-schema.ts"}\n'
        'const note = "{schema: \'./also-old.ts\'}";\n'
        '/* {schema: "./retired.ts"} */\n'
        'export default {schema: "./src/schema.ts"};',
        "src/schema.ts": "",
    })
    result = detect(["src/schema.ts"], tmp_path)
    assert result["db_changes"] is True
    assert result["projects"][0]["changed_schema"] == ["src/schema.ts"]
    assert result["projects"][0]["schema_paths"] == ["src/schema.ts"]


def test_drizzle_bracket_schema_glob(tmp_path: Path):
    _seed(tmp_path, {"drizzle.config.ts": 'export default {schema: "./src/[a-z]*.ts"};', "src/schema.ts": "", "src/1-decoy.ts": ""})
    result = detect(["src/schema.ts"], tmp_path)
    assert result["db_changes"] is True
    assert result["projects"][0]["schema_paths"] == ["src/schema.ts"]


def test_nested_alembic_configuration_change(tmp_path: Path):
    _seed(tmp_path, {"alembic.ini": "[alembic]\nscript_location = src/migrations\n", "src/migrations/env.py": "", "src/migrations/script.py.mako": ""})
    result = detect(["alembic.ini"], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["tool"] == "alembic"
    # The config owns the project's models; the script folder only holds revisions.
    assert project["root"] == "."
    assert project["changed_other"] == ["alembic.ini"]
    assert project["migrations_dir"] == "src/migrations/versions"


def test_adversarial_schema_glob_has_bounded_cli_runtime(tmp_path: Path):
    name = "src/" + "a" * 60 + ".ts"
    pattern = "src/" + "*a" * 10 + "b.ts"
    _seed(tmp_path, {"drizzle.config.ts": f'export default {{schema: "{pattern}"}};', name: ""})
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input=name + "\n", text=True, capture_output=True, check=False, timeout=2)
    assert result.returncode == 0
    assert json.loads(result.stdout)["db_changes"] is False


def test_fifo_config_does_not_block_cli(tmp_path: Path):
    import os
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO files unavailable")
    _seed(tmp_path, {"src/schema.ts": ""})
    os.mkfifo(tmp_path / "drizzle.config.ts")
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input="drizzle.config.ts\n", text=True, capture_output=True, check=False, timeout=2)
    assert result.returncode == 0
    assert any("non-regular" in note for project in json.loads(result.stdout)["projects"] for note in project["notes"])


def test_custom_alembic_location_from_here(tmp_path: Path):
    _seed(tmp_path, {"alembic.ini": "[alembic]\nscript_location = %(here)s/revisions\n", "revisions/env.py": "", "revisions/script.py.mako": "", "models.py": "from sqlalchemy.orm import DeclarativeBase\n"})
    result = detect(["models.py"], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["tool"] == "alembic"
    assert project["schema_paths"] == ["models.py"]
    assert project["changed_schema"] == ["models.py"]
    assert project["migrations_dir"] == "revisions/versions"


@pytest.mark.parametrize("config", ["not a config section", "[alembic]\nscript_location = ../outside\n", "[alembic]\nscript_location = /outside\n"])
def test_invalid_alembic_config_keeps_conventional_discovery(tmp_path: Path, config: str):
    _seed(tmp_path, {**_ALEMBIC, "alembic.ini": config, "models.py": "from sqlalchemy.orm import DeclarativeBase\n"})
    project = detect(["models.py"], tmp_path)["projects"][0]
    assert project["tool"] == "alembic"
    assert project["changed_schema"] == ["models.py"]
    assert any("unresolved script_location" in note for note in project["notes"])


@pytest.mark.parametrize("changed", ["drizzle.config.ts", "drizzle/meta/_journal.json", "drizzle/meta/0001_snapshot.json"])
def test_drizzle_metadata_only_change(tmp_path: Path, changed: str):
    _seed(tmp_path, {"drizzle.config.ts": _DRIZZLE, "src/schema.ts": "", "drizzle/meta/_journal.json": "{}", "drizzle/meta/0001_snapshot.json": "{}"})
    result = detect([changed], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["tool"] == "drizzle"
    assert project["changed_other"] == [changed]
    assert project["changed_schema"] == project["changed_migrations"] == []
    assert project["schema_paths"] == ["src/schema.ts"]
    assert project["migrations_dir"] == "drizzle"


@pytest.mark.parametrize("changed", ["prisma.config.ts", "prisma/migrations/migration_lock.toml"])
def test_prisma_metadata_only_change(tmp_path: Path, changed: str):
    _seed(tmp_path, {"prisma.config.ts": "export default {};", "prisma/schema.prisma": "", "prisma/migrations/migration_lock.toml": ""})
    result = detect([changed], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["tool"] == "prisma"
    assert project["changed_other"] == [changed]
    assert project["changed_schema"] == project["changed_migrations"] == []
    assert project["schema_paths"] == ["prisma/schema.prisma"]
    assert project["migrations_dir"] == "prisma/migrations"


def test_supabase_declarative_schema_only_change(tmp_path: Path):
    name = "supabase/schemas/public/users.sql"
    _seed(tmp_path, {name: "create table users (id integer);"})
    result = detect([name], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["tool"] == "supabase"
    assert project["schema_paths"] == project["changed_schema"] == [name]
    assert project["migrations_dir"] == "supabase/migrations"
    assert project["changed_migrations"] == project["changed_other"] == []


@pytest.mark.parametrize(("path", "pattern", "expected"), [
    ("src/schema.ts", "src/**/*.ts", True),
    ("src/nested/schema.ts", "src/**/*.ts", True),
    ("src/nested/schema.ts", "src/*.ts", False),
    ("src/a.ts", "src/?.ts", True),
    ("src/ab.ts", "src/?.ts", False),
    ("src/a.ts", "src/[!0-9]*.ts", True),
    ("src/5.ts", "src/[!0-9]*.ts", False),
    ("src/].ts", "src/[]].ts", True),
    ("src/foo/bar.ts", "src/foo**/bar.ts", False),
    ("src/foo-x/bar.ts", "src/foo**/bar.ts", True),
])
def test_posix_glob_boundaries(path: str, pattern: str, expected: bool):
    from db_change_detector import _matches
    assert _matches(path, pattern) is expected


@pytest.mark.parametrize("prefix", [
    'const quote = /"/;',
    "const quote = /'/;",
    'const quote = /`/;',
    'const quote = /["/]/;',
    r'const quote = /\{schema:"old"\}/;',
    'function quote() { return /"/; }',
    'const ratio = a / b / c;',
    'const quote = matches(/"/);',
    'const quote = /* quote matcher */ /"/;',
    'const quote = // quote matcher\n /"/;',
    'const quote = /* "/ */ /* next */ /"/;',
])
def test_regex_literals_do_not_hide_live_drizzle_schema(tmp_path: Path, prefix: str):
    name = "custom/schema.ts"
    _seed(tmp_path, {"drizzle.config.ts": prefix + '\nexport default {schema: "./custom/schema.ts"};', name: ""})
    result = detect([name], tmp_path)
    assert result["db_changes"] is True
    assert result["projects"][0]["schema_paths"] == [name]
    assert result["projects"][0]["changed_schema"] == [name]


def test_comment_prefix_scanning_has_bounded_cli_runtime(tmp_path: Path):
    name = "custom/schema.ts"
    text = "const value = " + "/* comment */ " * 30 + '0;\nexport default {schema: "./custom/schema.ts"};'
    _seed(tmp_path, {"drizzle.config.ts": text, name: ""})
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input=name + "\n", text=True, capture_output=True, check=False, timeout=2)
    assert result.returncode == 0
    assert json.loads(result.stdout)["projects"][0]["changed_schema"] == [name]


@pytest.mark.parametrize("unit", [
    pytest.param("[/", id="class-slash"),
    pytest.param("=/[", id="eq-slash-bracket"),
    pytest.param("=/*", id="unclosed-comment"),
    pytest.param("= /* */ ", id="closed-comments"),
    pytest.param("=//x\n", id="line-comments"),
    pytest.param("\"'", id="quote-runs"),
    pytest.param("=" + " " * 50 + "x", id="whitespace-runs"),
    pytest.param("=/**/", id="comment-runs"),
    pytest.param("[/" * 200 + "\n", id="multiline-class-slash"),
])
def test_linear_config_scan_at_read_cap(tmp_path: Path, unit: str):
    header = 'export default {schema: "./src/schema.ts", out: "./drizzle"}\n'
    remaining = 1024 * 1024 - len(header)
    text = header + (unit * (remaining // len(unit) + 1))[:remaining]
    assert len(text.encode()) == 1024 * 1024
    _seed(tmp_path, {"drizzle.config.ts": text, "src/schema.ts": ""})
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input="src/schema.ts\n", text=True, capture_output=True, check=False, timeout=5)
    assert result.returncode == 0
    project = json.loads(result.stdout)["projects"][0]
    assert project["schema_paths"] == ["src/schema.ts"]
    assert project["migrations_dir"] == "drizzle"
    assert any("schema location read" in note for note in project["notes"])
    assert not any("over 1 MiB" in note for note in project["notes"])


def test_missing_config_field_has_bounded_scan_at_read_cap(tmp_path: Path):
    header = 'export default {schema: "./src/schema.ts"}\n'
    remaining = 1024 * 1024 - len(header)
    text = header + ("=/[" * (remaining // 3 + 1))[:remaining]
    _seed(tmp_path, {"drizzle.config.ts": text, "src/schema.ts": ""})
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input="src/schema.ts\n", text=True, capture_output=True, check=False, timeout=5)
    assert result.returncode == 0
    project = json.loads(result.stdout)["projects"][0]
    assert project["schema_paths"] == ["src/schema.ts"]
    assert project["migrations_dir"] == "drizzle"
    assert any("schema location read" in note for note in project["notes"])


@pytest.mark.parametrize(("unit", "prefix", "expected"), [
    pytest.param("\n", "", False, id="newlines"),
    pytest.param("   \n", "", False, id="spaces-newlines"),
    pytest.param("\t", "", False, id="tabs"),
    pytest.param("from x\n", "", False, id="from-without-import"),
    pytest.param("\n", "from sqlalchemy.orm import DeclarativeBase\n", True, id="real-import"),
])
def test_sqlalchemy_classification_at_read_cap(tmp_path: Path, unit: str, prefix: str, expected: bool):
    remaining = 1024 * 1024 - len(prefix)
    text = prefix + (unit * (remaining // len(unit) + 1))[:remaining]
    assert len(text.encode()) == 1024 * 1024
    _seed(tmp_path, {**_ALEMBIC, "app/models.py": text})
    (tmp_path / "alembic/versions").mkdir()
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input="app/models.py\n", text=True, capture_output=True, check=False, timeout=5)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["db_changes"] is expected
    if expected:
        project = payload["projects"][0]
        assert project["tool"] == "alembic"
        assert project["schema_paths"] == project["changed_schema"] == ["app/models.py"]
        assert not any("over 1 MiB" in note for note in project["notes"])
    else:
        assert payload["projects"] == []


@pytest.mark.parametrize(("array", "expected"), [
    pytest.param('[/* tables */ "./custom/users.ts"]', ["custom/users.ts"], id="leading-block"),
    pytest.param('[// tables\n "./custom/users.ts"]', ["custom/users.ts"], id="leading-line"),
    pytest.param('[// tables\r "./custom/users.ts"]', ["custom/users.ts"], id="leading-line-cr"),
    pytest.param('["./custom/users.ts" /* end */]', ["custom/users.ts"], id="after-item"),
    pytest.param('["./custom/users.ts" /* comma */, "./custom/posts.ts"]', ["custom/posts.ts", "custom/users.ts"], id="before-comma"),
    pytest.param('["./custom/users.ts", /* posts */ "./custom/posts.ts"]', ["custom/posts.ts", "custom/users.ts"], id="after-comma-block"),
    pytest.param('["./custom/users.ts", // posts\n "./custom/posts.ts"]', ["custom/posts.ts", "custom/users.ts"], id="after-comma-line"),
    pytest.param('["./custom/users.ts" // end\n]', ["custom/users.ts"], id="before-end-line"),
    pytest.param('["./custom/users.ts", /* trailing */]', ["custom/users.ts"], id="trailing-comma"),
])
def test_commented_drizzle_arrays(tmp_path: Path, array: str, expected: list[str]) -> None:
    _seed(tmp_path, {"drizzle.config.ts": f"export default {{schema: {array}}};", "custom/users.ts": "", "custom/posts.ts": ""})
    result = detect(["custom/users.ts"], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["schema_paths"] == expected
    assert project["changed_schema"] == ["custom/users.ts"]


def test_configured_alembic_model_scope(tmp_path: Path) -> None:
    _seed(tmp_path, {"alembic.ini": "[alembic]\nscript_location = src/migrations\n", "src/migrations/env.py": "", "src/migrations/script.py.mako": "", "app/models.py": "from sqlalchemy.orm import DeclarativeBase\n"})
    result = detect(["app/models.py"], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["root"] == "."
    assert project["changed_schema"] == project["schema_paths"] == ["app/models.py"]
    assert project["migrations_dir"] == "src/migrations/versions"


@pytest.mark.parametrize(("unit", "unresolved"), [
    pytest.param("/*", True, id="unclosed-comment"),
    pytest.param("/**/", False, id="closed-comment"),
    pytest.param("// \n", False, id="line-comment"),
    pytest.param('"a", /* */', False, id="repeated-item-comment"),
    pytest.param("/*,", True, id="unclosed-comment-comma"),
])
def test_array_comment_scan_at_read_cap(tmp_path: Path, unit: str, unresolved: bool) -> None:
    header = 'export default {out: "./drizzle", schema: ["./src/schema.ts", '
    footer = ']};\n'
    remaining = 1024 * 1024 - len(header) - len(footer)
    copies, padding = divmod(remaining, len(unit))
    text = header + unit * copies + " " * padding + footer
    assert len(text.encode()) == 1024 * 1024
    _seed(tmp_path, {"drizzle.config.ts": text, "src/schema.ts": ""})
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input="src/schema.ts\n", text=True, capture_output=True, check=False, timeout=5)
    assert result.returncode == 0
    project = json.loads(result.stdout)["projects"][0]
    assert project["schema_paths"] == ["src/schema.ts"]
    assert any("unresolved schema" in note for note in project["notes"]) is unresolved
    assert not any("over 1 MiB" in note for note in project["notes"])
    if not unresolved:
        assert any("schema location read" in note for note in project["notes"])


def test_configured_alembic_folder_is_one_instance(tmp_path: Path) -> None:
    migration = "src/migrations/versions/x.py"
    _seed(tmp_path, {"alembic.ini": "[alembic]\nscript_location = src/migrations\n", "src/migrations/env.py": "", "src/migrations/script.py.mako": "", migration: ""})
    result = detect([migration], tmp_path)
    assert len(result["projects"]) == 1
    project = result["projects"][0]
    assert project["root"] == "."
    assert project["changed_migrations"] == [migration]
    assert project["migrations_dir"] == "src/migrations/versions"


@pytest.mark.parametrize(("folder", "root"), [("src/migrations", "src"), ("services/api/alembic", "services/api")])
def test_automatic_alembic_roots_are_unchanged(tmp_path: Path, folder: str, root: str) -> None:
    model = root + "/models.py"
    _seed(tmp_path, {folder + "/env.py": "", folder + "/script.py.mako": "", model: "from sqlalchemy.orm import DeclarativeBase\n"})
    result = detect([model], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["root"] == root
    assert project["schema_paths"] == [model]
    assert project["migrations_dir"] == folder + "/versions"


def _scaling_case(root: Path, case: str) -> tuple[list[str], dict]:
    files: dict[str, str] = {}
    changed: list[str] = []
    projects = []
    target = 3000
    if case == "django":
        target = 4000
        models = []
        directories = []
        for app in range(20):
            prefix = f"app_{app:02d}"
            model = prefix + "/models.py"
            files[model] = ""
            models.append(model)
            directories.append(prefix + "/migrations")
            files[prefix + "/migrations/__init__.py"] = ""
            for revision in range(10):
                name = prefix + f"/migrations/{revision:04d}_step.py"
                files[name] = ""
                changed.append(name)
        projects = [dict(tool="django", root=".", schema_paths=sorted(models), migrations_dir=".", changed_schema=[], changed_migrations=sorted(changed), changed_other=[], notes=["multiple migration directories: " + ", ".join(sorted(directories))])]
    elif case in {"rails", "supabase"}:
        schema = "db/schema.rb" if case == "rails" else "supabase/schemas/public/users.sql"
        directory = "db/migrate" if case == "rails" else "supabase/migrations"
        extension = "rb" if case == "rails" else "sql"
        files[schema] = ""
        for revision in range(1000):
            name = f"{directory}/{revision:014d}_step.{extension}"
            files[name] = ""
            changed.append(name)
        notes = [] if case == "rails" else ["Supabase migrations may be authoritative without declarative schemas"]
        projects = [dict(tool=case, root=".", schema_paths=[schema], migrations_dir=directory, changed_schema=[], changed_migrations=sorted(changed), changed_other=[], notes=notes)]
    elif case == "prisma":
        for number in range(1000):
            prefix = f"packages/db_{number:04d}"
            schema = prefix + "/prisma/schema.prisma"
            files[schema] = ""
            files[prefix + "/prisma.config.ts"] = ""
            files[prefix + "/prisma/migrations/migration_lock.toml"] = ""
            changed.append(schema)
            projects.append(dict(tool="prisma", root=prefix, schema_paths=[schema], migrations_dir=prefix + "/prisma/migrations", changed_schema=[schema], changed_migrations=[], changed_other=[], notes=[]))
    else:
        globs = case == "drizzle-globs"
        target = 300 if globs else 3000
        header = 'export default {schema: ["./custom/users.ts",'
        footer = '], out: "./drizzle"};\n'
        values = []
        used = len(header) + len(footer)
        number = 0
        while True:
            value = f'"./custom/missing_{number:06d}' + ('*.ts",' if globs else '.ts",')
            if used + len(value) > 1024 * 1024:
                break
            values.append(value)
            used += len(value)
            number += 1
        files["drizzle.config.ts"] = header + "".join(values) + " " * (1024 * 1024 - used) + footer
        assert len(files["drizzle.config.ts"].encode()) == 1024 * 1024
        files["custom/users.ts"] = ""
        if globs:
            files["src/schema.ts"] = ""
            changed = ["drizzle.config.ts"]
            schemas = ["custom/users.ts", "src/schema.ts"]
            notes = ["unresolved schema in drizzle.config.ts: more than 64 glob entries"]
        else:
            changed = ["custom/users.ts"]
            schemas = ["custom/users.ts"]
            notes = ["schema location read from drizzle.config.ts"]
        projects = [dict(tool="drizzle", root=".", schema_paths=schemas, migrations_dir="drizzle", changed_schema=[] if globs else changed, changed_migrations=[], changed_other=changed if globs else [], notes=notes)]
    number = 0
    while len(files) < target:
        files[f"misc/file_{number:05d}.txt"] = ""
        number += 1
    assert len(files) == target
    _seed(root, files)
    return changed, dict(detector_version=1, db_changes=True, ignored_paths=0, projects=projects)


@pytest.mark.parametrize("case", ["django", "rails", "supabase", "prisma", "drizzle-literals", "drizzle-globs"])
def test_repository_scaling_cli(tmp_path: Path, case: str) -> None:
    changed, expected = _scaling_case(tmp_path, case)
    # The quadratic baseline exceeded 30 seconds with only 300 repository files.
    timeout = 15 if case == "drizzle-literals" else 5
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input="\n".join(changed), text=True, capture_output=True, check=False, timeout=timeout)
    assert result.returncode == 0
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize("count", [64, 65])
def test_distinct_drizzle_glob_limit(tmp_path: Path, count: int) -> None:
    values = ["./custom/users.ts", *[f"./custom/missing_{number}*.ts" for number in range(count)]]
    _seed(tmp_path, {"drizzle.config.ts": 'export default {schema: ' + json.dumps(values) + '};', "custom/users.ts": "", "src/schema.ts": ""})
    project = detect(["drizzle.config.ts"], tmp_path)["projects"][0]
    if count == 64:
        assert project["schema_paths"] == ["custom/users.ts"]
        assert project["notes"] == ["schema location read from drizzle.config.ts"]
    else:
        assert project["schema_paths"] == ["custom/users.ts", "src/schema.ts"]
        assert project["notes"] == ["unresolved schema in drizzle.config.ts: more than 64 glob entries"]


def test_normalized_duplicate_globs_do_not_use_the_limit(tmp_path: Path) -> None:
    values = ["./" * number + "custom/*.ts" for number in range(66)]
    _seed(tmp_path, {"drizzle.config.ts": 'export default {schema: ' + json.dumps(values) + '};', "custom/users.ts": ""})
    project = detect(["drizzle.config.ts"], tmp_path)["projects"][0]
    assert project["schema_paths"] == ["custom/users.ts"]
    assert project["notes"] == ["schema location read from drizzle.config.ts"]


@pytest.mark.parametrize("literal", ["./custom/users.ts", "./custom"])
def test_capped_globs_preserve_changed_literal_schema(tmp_path: Path, literal: str) -> None:
    values = [literal, *[f"./custom/group_{n}/*.ts" for n in range(65)]]
    _seed(tmp_path, {"drizzle.config.ts": 'export default {schema:' + json.dumps(values) + '};', "custom/users.ts": ""})
    result = detect(["custom/users.ts"], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["changed_schema"] == project["schema_paths"] == ["custom/users.ts"]
    assert project["notes"] == ["unresolved schema in drizzle.config.ts: more than 64 glob entries"]


@pytest.mark.parametrize("config", [
    pytest.param('export default defineConfig({migrations:{table:"journal",schema:"drizzle"},schema:"./custom/users.ts",out:"./generated"});', id="migrations-before"),
    pytest.param('export default defineConfig({schema:"./custom/users.ts",migrations:{table:"journal",schema:"drizzle"},out:"./generated"});', id="migrations-after"),
    pytest.param('module.exports = {migrations:{out:"./nested"},schema:"./custom/users.ts",out:"./generated"};', id="nested-out-before"),
    pytest.param('const config = {schema:"./custom/users.ts",migrations:{out:"./nested"},out:"./generated"} satisfies Config;', id="const-satisfies"),
])
def test_drizzle_top_level_properties(tmp_path: Path, config: str) -> None:
    _seed(tmp_path, {"drizzle.config.ts": config, "custom/users.ts": ""})
    result = detect(["custom/users.ts"], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["schema_paths"] == ["custom/users.ts"]
    assert project["migrations_dir"] == "generated"


def test_drizzle_ambiguous_top_level_schema_is_unresolved(tmp_path: Path) -> None:
    _seed(tmp_path, {"drizzle.config.ts": 'const helper={schema:"public"}; export default defineConfig({schema:"./custom/users.ts"});', "custom/users.ts": "", "public/helper.ts": "", "src/schema.ts": ""})
    project = detect(["drizzle.config.ts"], tmp_path)["projects"][0]
    assert project["schema_paths"] == ["src/schema.ts"]
    assert any("unresolved schema" in note for note in project["notes"])
    assert "public" not in json.dumps(project)


@pytest.mark.parametrize("unit", ["{", "}"])
def test_deep_config_braces_at_read_cap(tmp_path: Path, unit: str) -> None:
    header = 'export default {schema:"./src/schema.ts",out:"./generated"};\n'
    text = header + unit * (1024 * 1024 - len(header))
    _seed(tmp_path, {"drizzle.config.ts": text, "src/schema.ts": ""})
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input="src/schema.ts\n", text=True, capture_output=True, check=False, timeout=5)
    assert result.returncode == 0
    project = json.loads(result.stdout)["projects"][0]
    assert project["schema_paths"] == ["src/schema.ts"]
    assert project["migrations_dir"] == "generated"


def test_drizzle_ambiguous_top_level_out_is_unresolved(tmp_path: Path) -> None:
    _seed(tmp_path, {"drizzle.config.ts": 'const helper={out:"./helper"}; export default {schema:"./custom/users.ts",out:"./generated"};', "custom/users.ts": ""})
    project = detect(["custom/users.ts"], tmp_path)["projects"][0]
    assert project["schema_paths"] == ["custom/users.ts"]
    assert project["migrations_dir"] == "drizzle"
    assert any("unresolved out" in note for note in project["notes"])
    assert "helper" not in json.dumps(project)


@pytest.mark.parametrize("config", [
    pytest.param('export default (() => { return defineConfig({schema:"./custom/users.ts",out:"./generated"}); })();', id="iife"),
    pytest.param('export default (() => { return defineConfig({migrations:{table:"journal",schema:"drizzle"},schema:"./custom/users.ts",out:"./generated"}); })();', id="iife-migrations-before"),
    pytest.param('function helper(){return [{schema:"nested"},{schema:"other"}];} export default {schema:"./custom/users.ts",out:"./generated"};', id="shallower-after-deeper-ambiguity"),
])
def test_drizzle_unique_shallowest_config_property(tmp_path: Path, config: str) -> None:
    _seed(tmp_path, {"drizzle.config.ts": config, "custom/users.ts": ""})
    result = detect(["custom/users.ts"], tmp_path)
    assert result["db_changes"] is True
    project = result["projects"][0]
    assert project["schema_paths"] == project["changed_schema"] == ["custom/users.ts"]
    assert project["migrations_dir"] == "generated"


def test_drizzle_wrapped_same_depth_properties_are_unresolved(tmp_path: Path) -> None:
    config = 'export default (() => { const helper={schema:"public"}; return defineConfig({schema:"./custom/users.ts",out:"./generated"}); })();'
    _seed(tmp_path, {"drizzle.config.ts": config, "custom/users.ts": "", "public/helper.ts": "", "src/schema.ts": ""})
    project = detect(["drizzle.config.ts"], tmp_path)["projects"][0]
    assert project["schema_paths"] == ["src/schema.ts"]
    assert project["migrations_dir"] == "generated"
    assert any("unresolved schema" in note for note in project["notes"])
    assert "public" not in json.dumps(project)


def test_repeated_config_properties_at_read_cap(tmp_path: Path) -> None:
    header = 'export default {schema:"./src/schema.ts",out:"./generated"};\n'
    unit = "{schema:1},"
    remaining = 1024 * 1024 - len(header)
    text = header + (unit * (remaining // len(unit))) + " " * (remaining % len(unit))
    _seed(tmp_path, {"drizzle.config.ts": text, "src/schema.ts": ""})
    result = subprocess.run([sys.executable, str(_SCRIPT), "--repo-root", str(tmp_path)], input="src/schema.ts\n", text=True, capture_output=True, check=False, timeout=5)
    assert result.returncode == 0
    project = json.loads(result.stdout)["projects"][0]
    assert project["schema_paths"] == ["src/schema.ts"]
    assert project["migrations_dir"] == "generated"
    assert any("unresolved schema" in note for note in project["notes"])
