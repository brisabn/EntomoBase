import sqlite3

import models
from legacy_db import OLD_SCHEMA, old_database, rows
from security import is_hash, verify_password


def test_old_portuguese_schema_is_renamed_without_losing_data(tmp_path, initialize_at):
    path = old_database(tmp_path)
    initialize_at(path)
    tables = {name for (name,) in rows(path, "select name from sqlite_master where type='table'")}
    assert {"projects", "specimens", "measurements", "legacy_measurements", "users", "taxa"} <= tables
    assert not ({"projetos", "especimes", "medidas", "medicoes", "usuarios", "taxons"} & tables)
    assert rows(path, "select title, year, insect_group, finished from projects") == [("Old project", 2024, "Coleoptera", 1)]
    assert rows(path, "select catalog_number, insect_order, species, project_id from specimens") == [("X-1", "Coleoptera", "Dynastes hercules", 1)]


def test_every_column_of_the_models_exists_after_the_migration(tmp_path, initialize_at):
    path = old_database(tmp_path)
    initialize_at(path)
    for table in models.Base.metadata.sorted_tables:
        columns = {name for (_, name, *_) in rows(path, f"pragma table_info({table.name})")}
        assert {c.name for c in table.columns} <= columns, table.name


def test_old_fixed_measurements_become_measurements_per_trait(tmp_path, initialize_at):
    path = old_database(tmp_path)
    initialize_at(path)
    assert sorted(rows(path, "select trait, value, unit from measurements")) == [
        ("Largura do pronoto", 20.0, "mm"), ("Tamanho do chifre", 40.5, "mm")]


def test_plain_text_passwords_become_hashes(tmp_path, initialize_at):
    path = old_database(tmp_path)
    initialize_at(path)
    (stored,) = rows(path, "select password_hash from users")[0]
    assert is_hash(stored) and "plain-password" not in stored
    assert verify_password("plain-password", stored)


def test_the_gbif_cache_is_emptied_because_it_held_old_status_names(tmp_path, initialize_at):
    path = old_database(tmp_path)
    initialize_at(path)
    assert rows(path, "select count(*) from taxa") == [(0,)]


def test_initializing_twice_changes_nothing(tmp_path, initialize_at):
    once = old_database(tmp_path)
    initialize_at(once, times=1)
    twice = str(tmp_path / "twice.db")
    con = sqlite3.connect(twice)
    con.executescript(OLD_SCHEMA)
    con.commit()
    con.close()
    initialize_at(twice, times=2)
    for sql in ("select * from projects", "select * from specimens", "select trait, value, unit from measurements order by id",
                "select count(*) from legacy_measurements", "select count(*) from users"):
        assert rows(once, sql) == rows(twice, sql), sql


def test_a_new_database_gets_every_table(tmp_path, initialize_at):
    path = str(tmp_path / "new.db")
    initialize_at(path)
    tables = {name for (name,) in rows(path, "select name from sqlite_master where type='table'")}
    assert {t.name for t in models.Base.metadata.sorted_tables} <= tables


def test_the_tests_use_their_own_database():
    from database import engine
    assert "entomobase_tests_" in str(engine.url)
