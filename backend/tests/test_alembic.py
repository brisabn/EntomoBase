import os
import sqlite3
import subprocess
import sys

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import db_setup
import models

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config():
    return Config(db_setup.ALEMBIC_INI)


def head():
    return ScriptDirectory.from_config(config()).get_current_head()


def version(engine):
    with engine.connect() as connection:
        return connection.execute(text("select version_num from alembic_version")).scalars().all()


# what Alembic would still have to change for the database to match models.py
def schema_differences(engine):
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return compare_metadata(context, models.Base.metadata)


def table_names(db_path):
    con = sqlite3.connect(db_path)
    try:
        return {name for (name,) in con.execute("select name from sqlite_master where type='table'")}
    finally:
        con.close()


# ---------- the revisions themselves ----------
def test_there_is_exactly_one_head():
    assert len(ScriptDirectory.from_config(config()).get_heads()) == 1


def test_the_first_revision_has_no_parent():
    assert ScriptDirectory.from_config(config()).get_revision("0001").down_revision is None


def test_a_new_database_is_created_by_the_migrations(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"))
    assert {t.name for t in models.Base.metadata.sorted_tables} <= set(inspect(engine).get_table_names())
    assert version(engine) == [head()]


def test_models_and_migrations_are_in_sync(tmp_path, initialize_at):
    # fails when someone changes models.py without creating the migration (alembic revision --autogenerate)
    engine = initialize_at(str(tmp_path / "new.db"))
    assert schema_differences(engine) == []


def test_running_the_migrations_again_keeps_the_data(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"))
    with engine.begin() as connection:
        connection.execute(text("insert into projects (title, year, insect_group) values ('Kept', 2025, 'Coleoptera')"))
    db_setup.initialize_database()
    db_setup.initialize_database()
    with engine.connect() as connection:
        assert connection.execute(text("select title from projects")).scalars().all() == ["Kept"]
    assert version(engine) == [head()] and schema_differences(engine) == []


def test_going_back_to_the_start_removes_the_tables_and_forward_restores_them(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"))
    with engine.begin() as connection:
        cfg = config()
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    db_setup.initialize_database()
    assert schema_differences(engine) == [] and version(engine) == [head()]


def test_catalog_numbers_are_unique_in_a_migrated_database(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"))
    insert = text("insert into specimens (catalog_number, insect_order, species) values ('X-1', 'C', 'A b')")
    with engine.begin() as connection:
        connection.execute(insert)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert)


# ---------- a database that was not created by the migrations ----------
def test_a_database_with_tables_but_no_history_is_refused_and_left_alone(tmp_path, initialize_at):
    path = str(tmp_path / "foreign.db")
    con = sqlite3.connect(path)
    con.executescript("create table projects (id integer primary key, title varchar); insert into projects values (1, 'Mine');")
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="no alembic_version"):
        initialize_at(path)
    assert table_names(path) == {"projects"}
    con = sqlite3.connect(path)
    assert con.execute("select title from projects").fetchall() == [("Mine",)]
    con.close()


def test_an_empty_existing_file_is_accepted(tmp_path, initialize_at):
    path = str(tmp_path / "empty.db")
    sqlite3.connect(path).close()
    engine = initialize_at(path)
    assert version(engine) == [head()]


# ---------- the command line ----------
def run_alembic(db_path, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("ENTOMOBASE_ENV",)}
    env["DATABASE_URL"] = "sqlite:///" + db_path.replace("\\", "/")
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, capture_output=True, text=True)


def test_the_command_line_creates_the_database(tmp_path):
    path = str(tmp_path / "cli.db")
    result = run_alembic(path, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    assert {t.name for t in models.Base.metadata.sorted_tables} <= table_names(path)
    current = run_alembic(path, "current")
    assert current.returncode == 0 and "0001 (head)" in current.stderr + current.stdout


def test_the_command_line_check_passes_when_models_and_migrations_agree(tmp_path):
    path = str(tmp_path / "cli.db")
    run_alembic(path, "upgrade", "head")
    result = run_alembic(path, "check")
    assert result.returncode == 0, result.stderr + result.stdout


def test_the_command_line_check_fails_when_the_database_is_behind(tmp_path):
    path = str(tmp_path / "cli.db")
    run_alembic(path, "upgrade", "head")
    con = sqlite3.connect(path)
    con.execute("drop index ix_specimens_species")
    con.commit()
    con.close()
    assert run_alembic(path, "check").returncode != 0
