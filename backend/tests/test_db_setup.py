import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db_setup
import models
from conftest import EMAIL, PASSWORD
from helpers import create_specimen
from security import is_hash, verify_password

# the database as the first versions created it: Portuguese names, plain text passwords, fixed measurements
OLD_SCHEMA = """
create table usuarios (id integer primary key, email varchar not null, senha varchar not null);
create table projetos (id integer primary key, titulo varchar not null, ano integer not null, grupo_insetos varchar not null,
    tracos_medidos varchar, local_coleta varchar, capa_url varchar, dataset_externo_url varchar, finalizado boolean,
    publicacao_vinculada varchar);
create table especimes (id integer primary key, codigo_etiqueta varchar not null unique, grupo_insetos varchar not null,
    especie varchar not null, data_coleta date, local_coleta varchar, latitude float, longitude float, notas varchar,
    fotografia_url varchar, projeto_id integer);
create table medicoes (id integer primary key, especime_id integer not null, tamanho_chifre_mm float, largura_pronoto_mm float not null);
create table taxons (id integer primary key, nome_informado varchar not null, situacao varchar not null, sugestao varchar,
    chave_gbif integer, familia varchar, ordem varchar, consultado_em datetime not null);
insert into usuarios (email, senha) values ('a@lab.br', 'plain-password');
insert into projetos (id, titulo, ano, grupo_insetos, finalizado) values (1, 'Old project', 2024, 'Coleoptera', 1);
insert into especimes (id, codigo_etiqueta, grupo_insetos, especie, projeto_id) values (1, 'X-1', 'Coleoptera', 'Dynastes hercules', 1);
insert into medicoes (especime_id, tamanho_chifre_mm, largura_pronoto_mm) values (1, 40.5, 20.0);
insert into taxons (nome_informado, situacao, consultado_em) values ('A b', 'sinonimo', '2025-01-01 00:00:00');
"""


# runs initialize_database() against a separate temporary database, in this process so coverage sees it
@pytest.fixture
def initialize_at(monkeypatch):
    engines = []

    def run(db_path, times=1):
        engine = create_engine("sqlite:///" + db_path.replace("\\", "/"))
        engines.append(engine)
        monkeypatch.setattr(db_setup, "engine", engine)
        monkeypatch.setattr(db_setup, "SessionLocal", sessionmaker(bind=engine))
        for _ in range(times):
            db_setup.initialize_database()

    yield run
    for engine in engines:
        engine.dispose()


def rows(db_path, sql):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def old_database(tmp_path):
    path = str(tmp_path / "old.db")
    con = sqlite3.connect(path)
    con.executescript(OLD_SCHEMA)
    con.commit()
    con.close()
    return path


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


def test_plain_text_passwords_are_also_fixed_in_the_running_database(client, db):
    from db_setup import initialize_database
    db.add(models.User(email=EMAIL, password_hash=PASSWORD))
    db.commit()
    initialize_database()
    db.expire_all()
    assert is_hash(db.query(models.User).one().password_hash)
    assert client.post("/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200


def test_the_tests_use_their_own_database():
    from database import engine
    assert "entomobase_tests_" in str(engine.url)
