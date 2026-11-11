import sqlite3

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import db_setup
import models

# a database exactly as the previous revision (0001) leaves it, with data, to be brought to the newest one
DATA_AT_0001 = """
insert into users (email, password_hash) values ('a@lab.br', 'hash-a'), ('b@lab.br', 'hash-b');
insert into projects (id, title, year, insect_group, finished) values
    (1, 'Finished', 2025, 'Coleoptera', 1), (2, 'In progress', 2026, 'Lepidoptera', 0), (3, 'No status', 2024, 'Hymenoptera', NULL);
insert into specimens (id, catalog_number, insect_order, species, project_id, collector) values
    (1, 'A-1', 'Coleoptera', 'Dynastes hercules', 1, 'Secret'), (2, 'A-2', 'Lepidoptera', 'Morpho helenor', 2, NULL),
    (3, 'LOOSE-1', 'Coleoptera', 'Canthon virens', NULL, NULL);
insert into measurements (specimen_id, trait, value, unit) values (1, 'Comprimento corporal', 60.5, 'mm');
"""


def config():
    return Config(db_setup.ALEMBIC_INI)


def upgrade_to(engine, revision):
    with engine.begin() as connection:
        cfg = config()
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, revision)


def downgrade_to(engine, revision):
    with engine.begin() as connection:
        cfg = config()
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, revision)


@pytest.fixture
def at_0001(tmp_path):
    path = str(tmp_path / "at0001.db")
    engine = create_engine("sqlite:///" + path.replace("\\", "/"))
    upgrade_to(engine, "0001")
    con = sqlite3.connect(path)
    con.executescript(DATA_AT_0001)
    con.commit()
    con.close()
    engine.dispose()
    return path


def fetch(engine, sql):
    with engine.connect() as connection:
        return connection.execute(text(sql)).fetchall()


# ---------- moving existing data into the first laboratory ----------
def test_existing_data_moves_into_the_first_laboratory(at_0001, initialize_at):
    engine = initialize_at(at_0001)
    assert fetch(engine, "select id, slug, name, institution, collection_code, listed from laboratories") == [
        (1, "ufmg", "EntomoBase UFMG", "UFMG", "EntomoBase", 1)]
    assert fetch(engine, "select distinct laboratory_id from projects") == [(1,)]
    assert fetch(engine, "select distinct laboratory_id from specimens") == [(1,)]


def test_nothing_is_lost(at_0001, initialize_at):
    engine = initialize_at(at_0001)
    assert fetch(engine, "select title, year, finished from projects order by id") == [
        ("Finished", 2025, 1), ("In progress", 2026, 0), ("No status", 2024, None)]
    assert fetch(engine, "select catalog_number, project_id, collector from specimens order by id") == [
        ("A-1", 1, "Secret"), ("A-2", 2, None), ("LOOSE-1", None, None)]
    assert fetch(engine, "select trait, value from measurements") == [("Comprimento corporal", 60.5)]
    assert fetch(engine, "select email from users order by id") == [("a@lab.br",), ("b@lab.br",)]


def test_a_finished_project_becomes_public_and_the_others_private(at_0001, initialize_at):
    engine = initialize_at(at_0001)
    assert fetch(engine, "select title, visibility from projects order by id") == [
        ("Finished", "public"), ("In progress", "private"), ("No status", "private")]


def test_existing_users_become_administrators_of_the_first_laboratory(at_0001, initialize_at):
    engine = initialize_at(at_0001)
    assert fetch(engine, "select user_id, laboratory_id, role from memberships order by user_id") == [(1, 1, "admin"), (2, 1, "admin")]
    assert fetch(engine, "select is_superadmin, name from users") == [(0, None), (0, None)]


def test_share_tokens_start_empty(at_0001, initialize_at):
    engine = initialize_at(at_0001)
    assert fetch(engine, "select count(*) from projects where share_token is not null") == [(0,)]


def test_the_migrated_database_matches_the_models(at_0001, initialize_at):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    engine = initialize_at(at_0001)
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), models.Base.metadata) == []


def test_going_back_to_the_previous_revision_keeps_the_data(at_0001, initialize_at):
    engine = initialize_at(at_0001)
    downgrade_to(engine, "0001")
    tables = set(inspect(engine).get_table_names())
    assert "laboratories" not in tables and "memberships" not in tables
    assert "laboratory_id" not in {c["name"] for c in inspect(engine).get_columns("projects")}
    assert fetch(engine, "select title from projects order by id") == [("Finished",), ("In progress",), ("No status",)]
    assert fetch(engine, "select catalog_number from specimens order by id") == [("A-1",), ("A-2",), ("LOOSE-1",)]
    upgrade_to(engine, "head")
    assert fetch(engine, "select visibility from projects order by id") == [("public",), ("private",), ("private",)]


# ---------- the rules the new schema enforces ----------
@pytest.fixture
def empty(tmp_path, initialize_at):
    return initialize_at(str(tmp_path / "new.db"))


def insert(engine, sql, **params):
    with engine.begin() as connection:
        connection.execute(text(sql), params)


def test_a_project_needs_a_laboratory(empty):
    with pytest.raises(IntegrityError):
        insert(empty, "insert into projects (title, year, insect_group) values ('x', 2025, 'C')")


def test_a_specimen_needs_a_laboratory(empty):
    with pytest.raises(IntegrityError):
        insert(empty, "insert into specimens (catalog_number, insect_order, species) values ('x', 'C', 'A b')")


def test_laboratory_slugs_are_unique(empty):
    sql = "insert into laboratories (slug, name, institution, collection_code, license) values ('same', 'n', 'i', 'c', 'l')"
    insert(empty, sql)
    with pytest.raises(IntegrityError):
        insert(empty, sql)


def test_a_user_belongs_to_a_laboratory_only_once(empty):
    insert(empty, "insert into users (email, password_hash) values ('a@lab.br', 'h')")
    sql = "insert into memberships (user_id, laboratory_id, role) values (1, 1, 'admin')"
    insert(empty, sql)
    with pytest.raises(IntegrityError):
        insert(empty, sql)


def test_a_user_can_belong_to_two_laboratories(empty):
    insert(empty, "insert into laboratories (slug, name, institution, collection_code, license) values ('b', 'B', 'B', 'B', 'x')")
    insert(empty, "insert into users (email, password_hash) values ('a@lab.br', 'h')")
    insert(empty, "insert into memberships (user_id, laboratory_id, role) values (1, 1, 'admin')")
    insert(empty, "insert into memberships (user_id, laboratory_id, role) values (1, 2, 'researcher')")
    assert fetch(empty, "select count(*) from memberships") == [(2,)]


def test_a_share_token_belongs_to_one_project_but_many_projects_can_have_none(empty):
    insert(empty, "insert into projects (laboratory_id, title, year, insect_group, share_token) values (1, 'a', 2025, 'C', 'tok')")
    insert(empty, "insert into projects (laboratory_id, title, year, insect_group) values (1, 'b', 2025, 'C')")
    insert(empty, "insert into projects (laboratory_id, title, year, insect_group) values (1, 'c', 2025, 'C')")
    with pytest.raises(IntegrityError):
        insert(empty, "insert into projects (laboratory_id, title, year, insect_group, share_token) values (1, 'd', 2025, 'C', 'tok')")


def test_new_projects_default_to_private_and_new_users_to_not_superadmin(empty):
    insert(empty, "insert into projects (laboratory_id, title, year, insect_group) values (1, 'a', 2025, 'C')")
    insert(empty, "insert into users (email, password_hash) values ('a@lab.br', 'h')")
    assert fetch(empty, "select visibility from projects") == [("private",)]
    assert fetch(empty, "select is_superadmin from users") == [(0,)]


def test_a_new_laboratory_is_not_listed_by_default(empty):
    insert(empty, "insert into laboratories (slug, name, institution, collection_code, license) values ('b', 'B', 'B', 'B', 'x')")
    assert fetch(empty, "select listed from laboratories where slug = 'b'") == [(0,)]


def test_the_allowed_values_are_declared():
    assert models.ROLES == ("admin", "researcher")
    assert models.VISIBILITIES == ("private", "unlisted", "public")
