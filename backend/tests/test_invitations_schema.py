import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import db_setup

COLUMNS = "laboratory_id, email, role, invited_by_id, code_hash, created_at, expires_at"
VALUES = "1, 'x@ufmg.br', 'researcher', 1, 'hash-1', '2026-11-13 10:00:00', '2026-11-20 10:00:00'"


@pytest.fixture
def empty(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"))
    insert(engine, "insert into users (email, password_hash) values ('a@ufmg.br', 'h')")
    insert(engine, "insert into laboratories (slug, name, institution, collection_code, license, listed) values ('lab-b', 'B', 'B', 'B', 'l', 0)")
    return engine


def insert(engine, sql):
    with engine.begin() as connection:
        connection.execute(text(sql))


def fetch(engine, sql):
    with engine.connect() as connection:
        return connection.execute(text(sql)).fetchall()


@pytest.mark.parametrize("missing", [c.strip() for c in COLUMNS.split(",")])
def test_an_invitation_needs_every_field(empty, missing):
    columns = [c.strip() for c in COLUMNS.split(",")]
    values = [v.strip() for v in VALUES.split(",")]
    position = columns.index(missing)
    del columns[position], values[position]
    with pytest.raises(IntegrityError):
        insert(empty, f"insert into invitations ({', '.join(columns)}) values ({', '.join(values)})")


def test_one_invitation_per_address_in_each_laboratory(empty):
    insert(empty, f"insert into invitations ({COLUMNS}) values ({VALUES})")
    with pytest.raises(IntegrityError):
        insert(empty, f"insert into invitations ({COLUMNS}) values ({VALUES.replace('hash-1', 'hash-2')})")
    # the same address in another laboratory is fine
    other = fetch(empty, "select id from laboratories where slug = 'lab-b'")[0][0]
    insert(empty, f"insert into invitations ({COLUMNS}) values ({VALUES.replace('hash-1', 'hash-2').replace('1,', f'{other},', 1)})")
    assert fetch(empty, "select count(*) from invitations") == [(2,)]


def test_two_invitations_never_share_a_code(empty):
    insert(empty, f"insert into invitations ({COLUMNS}) values ({VALUES})")
    with pytest.raises(IntegrityError):
        insert(empty, f"insert into invitations ({COLUMNS}) values ({VALUES.replace('x@ufmg.br', 'y@ufmg.br')})")


def test_going_back_removes_only_the_invitations(empty):
    insert(empty, f"insert into invitations ({COLUMNS}) values ({VALUES})")
    with empty.begin() as connection:
        cfg = Config(db_setup.ALEMBIC_INI)
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "0004")
    assert "invitations" not in inspect(empty).get_table_names()
    assert "laboratory_requests" in inspect(empty).get_table_names()
    assert fetch(empty, "select email from users") == [("a@ufmg.br",)]
    db_setup.initialize_database()
    assert fetch(empty, "select count(*) from invitations") == [(0,)]
