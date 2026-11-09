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
