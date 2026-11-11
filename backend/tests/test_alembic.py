import os
import subprocess
import sys

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import db_setup
import models
from legacy_db import old_database, pre_alembic_database, rows
from security import is_hash, verify_password

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


def index_names(engine, table):
    return {i["name"] for i in inspect(engine).get_indexes(table)}


# ---------- the revisions themselves ----------
def test_there_is_exactly_one_head():
    assert len(ScriptDirectory.from_config(config()).get_heads()) == 1


def test_the_first_revision_has_no_parent():
    script = ScriptDirectory.from_config(config())
    assert script.get_revision("0001").down_revision is None


def test_a_new_database_is_created_by_the_migrations(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"))
    assert {t.name for t in models.Base.metadata.sorted_tables} <= set(inspect(engine).get_table_names())
    assert version(engine) == [head()]


def test_models_and_migrations_are_in_sync(tmp_path, initialize_at):
    # fails when someone changes models.py without creating the migration (alembic revision --autogenerate)
    engine = initialize_at(str(tmp_path / "new.db"))
    assert schema_differences(engine) == []


def test_running_the_migrations_again_changes_nothing(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"), times=3)
    assert version(engine) == [head()]
    assert schema_differences(engine) == []


def test_going_back_to_the_start_removes_the_tables_and_forward_restores_them(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"))
    with engine.begin() as connection:
        cfg = config()
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    db_setup.initialize_database()
    assert schema_differences(engine) == [] and version(engine) == [head()]


# ---------- a database that existed before Alembic ----------
def test_a_database_from_before_alembic_is_adopted_with_its_data(tmp_path, initialize_at):
    path = pre_alembic_database(tmp_path)
    assert "alembic_version" not in {n for (n,) in rows(path, "select name from sqlite_master where type='table'")}
    engine = initialize_at(path)
    assert version(engine) == [head()]
    assert rows(path, "select title, year from projects") == [("Current project", 2025)]
    assert rows(path, "select catalog_number, species from specimens") == [("Y-1", "Morpho helenor")]
    assert rows(path, "select trait, value from measurements") == [("Envergadura alar", 120.5)]
    assert schema_differences(engine) == []


def test_a_database_from_before_alembic_gets_its_plain_text_passwords_hashed(tmp_path, initialize_at):
    path = pre_alembic_database(tmp_path)
    initialize_at(path)
    (stored,) = rows(path, "select password_hash from users")[0]
    assert is_hash(stored) and verify_password("plain-password", stored)


def test_a_partial_database_gets_only_the_missing_tables(tmp_path, initialize_at):
    path = pre_alembic_database(tmp_path)
    import sqlite3
    con = sqlite3.connect(path)
    con.executescript("drop table measurements; drop table legacy_measurements; drop table taxa;")
    con.commit()
    con.close()
    engine = initialize_at(path)
    assert {t.name for t in models.Base.metadata.sorted_tables} <= set(inspect(engine).get_table_names())
    assert rows(path, "select catalog_number from specimens") == [("Y-1",)]
    assert schema_differences(engine) == []


def test_a_missing_index_is_created_on_an_existing_table(tmp_path, initialize_at):
    path = pre_alembic_database(tmp_path)
    import sqlite3
    con = sqlite3.connect(path)
    con.executescript("drop index ix_specimens_species;")
    con.commit()
    con.close()
    engine = initialize_at(path)
    assert "ix_specimens_species" in index_names(engine, "specimens")


def test_the_conversion_runs_only_once(tmp_path, initialize_at):
    # after the first run the database has an alembic_version table, so a plain text password put there
    # later is not touched: the one-time conversion no longer applies
    path = pre_alembic_database(tmp_path)
    engine = initialize_at(path)
    with engine.begin() as connection:
        connection.execute(text("update users set password_hash = 'plain-again'"))
    db_setup.initialize_database()
    assert rows(path, "select password_hash from users") == [("plain-again",)]


# ---------- an old Portuguese database ends up in the same state as a new one ----------
def test_an_old_database_matches_the_models_after_the_migration(tmp_path, initialize_at):
    engine = initialize_at(old_database(tmp_path))
    assert schema_differences(engine) == []
    assert version(engine) == [head()]


def test_old_index_names_are_replaced(tmp_path, initialize_at):
    path = old_database(tmp_path)
    assert {"ix_especimes_id", "ix_projetos_titulo"} <= {n for (n,) in rows(path, "select name from sqlite_master where type='index'")}
    engine = initialize_at(path)
    names = {n for (n,) in rows(path, "select name from sqlite_master where type='index'")}
    assert not {n for n in names if n.startswith(("ix_especimes_", "ix_projetos_", "ix_usuarios_", "ix_medicoes_", "ix_taxons_"))}
    assert {"ix_specimens_id", "ix_projects_title", "ix_specimens_catalog_number", "ix_users_email"} <= names
    assert schema_differences(engine) == []


def test_catalog_numbers_stay_unique_after_the_old_index_is_dropped(tmp_path, initialize_at):
    path = old_database(tmp_path)
    engine = initialize_at(path)
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("insert into specimens (catalog_number, insect_order, species) values ('X-1', 'C', 'A b')"))


# ---------- the command line ----------
def run_alembic(db_path, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("ENTOMOBASE_ENV",)}
    env["DATABASE_URL"] = "sqlite:///" + db_path.replace("\\", "/")
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, capture_output=True, text=True)


def test_the_command_line_creates_the_database(tmp_path):
    path = str(tmp_path / "cli.db")
    result = run_alembic(path, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    assert {t.name for t in models.Base.metadata.sorted_tables} <= {n for (n,) in rows(path, "select name from sqlite_master where type='table'")}
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
    import sqlite3
    con = sqlite3.connect(path)
    con.execute("drop index ix_specimens_species")
    con.commit()
    con.close()
    assert run_alembic(path, "check").returncode != 0


def test_a_very_old_database_with_only_some_tables_is_completed(tmp_path, initialize_at):
    import sqlite3
    path = str(tmp_path / "very_old.db")
    con = sqlite3.connect(path)
    con.executescript("""
        create table usuarios (id integer not null, email varchar not null, senha varchar not null, primary key (id));
        insert into usuarios (email, senha) values ('c@lab.br', 'plain-password');
    """)
    con.commit()
    con.close()
    engine = initialize_at(path)
    assert {t.name for t in models.Base.metadata.sorted_tables} <= set(inspect(engine).get_table_names())
    (stored,) = rows(path, "select password_hash from users")[0]
    assert is_hash(stored) and schema_differences(engine) == []
