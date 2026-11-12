import sqlite3
from datetime import datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import db_setup
import models


def migrate(engine, direction, revision):
    with engine.begin() as connection:
        cfg = Config(db_setup.ALEMBIC_INI)
        cfg.attributes["connection"] = connection
        (command.upgrade if direction == "up" else command.downgrade)(cfg, revision)


# a database as revision 0002 leaves it, with two accounts, to be brought to the newest revision
@pytest.fixture
def at_0002(tmp_path):
    path = str(tmp_path / "at0002.db")
    engine = create_engine("sqlite:///" + path.replace("\\", "/"))
    migrate(engine, "up", "0002")
    con = sqlite3.connect(path)
    con.executescript("insert into users (email, password_hash) values ('a@lab.br', 'hash-a'), ('b@lab.br', 'hash-b');"
                      "insert into memberships (user_id, laboratory_id, role) values (1, 1, 'admin'), (2, 1, 'admin');")
    con.commit()
    con.close()
    engine.dispose()
    return path


@pytest.fixture
def empty(tmp_path, initialize_at):
    return initialize_at(str(tmp_path / "new.db"))


def fetch(engine, sql):
    with engine.connect() as connection:
        return connection.execute(text(sql)).fetchall()


def insert(engine, sql, **params):
    with engine.begin() as connection:
        connection.execute(text(sql), params)


# ---------- bringing an existing database up ----------
def test_existing_accounts_count_as_confirmed_right_now(at_0002, initialize_at):
    before = datetime.utcnow()
    engine = initialize_at(at_0002)
    moments = [row[0] for row in engine.connect().execute(text("select email_verified_at from users order by id"))]
    assert len(moments) == 2 and all(moment is not None for moment in moments)
    for moment in moments:
        assert before - timedelta(seconds=5) <= datetime.fromisoformat(moment) <= datetime.utcnow() + timedelta(seconds=5)


def test_existing_accounts_keep_their_data(at_0002, initialize_at):
    engine = initialize_at(at_0002)
    assert fetch(engine, "select email, password_hash from users order by id") == [("a@lab.br", "hash-a"), ("b@lab.br", "hash-b")]
    assert fetch(engine, "select user_id, role from memberships order by user_id") == [(1, "admin"), (2, "admin")]


def test_the_migrated_database_matches_the_models(at_0002, initialize_at):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    engine = initialize_at(at_0002)
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), models.Base.metadata) == []


def test_going_back_forgets_the_confirmations_but_keeps_the_accounts(at_0002, initialize_at):
    engine = initialize_at(at_0002)
    insert(engine, "insert into email_confirmations (user_id, code_hash, created_at, expires_at) values (1, 'h', '2026-01-01 00:00:00', '2026-01-02 00:00:00')")
    migrate(engine, "down", "0002")
    assert "email_confirmations" not in inspect(engine).get_table_names()
    assert "email_verified_at" not in {c["name"] for c in inspect(engine).get_columns("users")}
    assert fetch(engine, "select email from users order by id") == [("a@lab.br",), ("b@lab.br",)]
    migrate(engine, "up", "head")
    assert fetch(engine, "select count(*) from users where email_verified_at is not null") == [(2,)]


# ---------- the rules the new schema enforces ----------
def test_a_new_account_starts_unconfirmed(empty):
    insert(empty, "insert into users (email, password_hash) values ('new@lab.br', 'h')")
    assert fetch(empty, "select email_verified_at from users") == [(None,)]


def test_a_confirmation_needs_all_its_fields(empty):
    insert(empty, "insert into users (email, password_hash) values ('new@lab.br', 'h')")
    for missing in ("user_id", "code_hash", "created_at", "expires_at"):
        values = {"user_id": 1, "code_hash": "h", "created_at": "2026-01-01 00:00:00", "expires_at": "2026-01-02 00:00:00"}
        del values[missing]
        columns = ", ".join(values)
        with pytest.raises(IntegrityError):
            insert(empty, f"insert into email_confirmations ({columns}) values ({', '.join(':' + k for k in values)})", **values)


def test_a_code_belongs_to_one_confirmation_but_a_user_can_have_several(empty):
    insert(empty, "insert into users (email, password_hash) values ('new@lab.br', 'h')")
    sql = "insert into email_confirmations (user_id, code_hash, created_at, expires_at) values (1, :code, '2026-01-01 00:00:00', '2026-01-02 00:00:00')"
    insert(empty, sql, code="one")
    insert(empty, sql, code="two")
    with pytest.raises(IntegrityError):
        insert(empty, sql, code="one")


def test_the_models_know_the_confirmations_of_a_user(empty):
    from sqlalchemy.orm import Session
    with Session(empty) as session:
        user = models.User(email="new@lab.br", password_hash="h")
        now = datetime.utcnow()
        user.email_confirmations.append(models.EmailConfirmation(code_hash="h", created_at=now, expires_at=now + timedelta(hours=1)))
        session.add(user)
        session.commit()
        assert session.query(models.EmailConfirmation).one().user.email == "new@lab.br"
        session.delete(user)
        session.commit()
        assert session.query(models.EmailConfirmation).count() == 0
