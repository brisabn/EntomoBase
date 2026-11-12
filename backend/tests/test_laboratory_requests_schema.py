import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

import db_setup
import models

COLUMNS = "requester_id, slug, name, institution, collection_code, created_at"
VALUES = "1, 'lab-x', 'Lab X', 'UFMG', 'LX', '2026-11-12 10:00:00'"


@pytest.fixture
def empty(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"))
    insert(engine, "insert into users (email, password_hash) values ('a@ufmg.br', 'h')")
    return engine


def insert(engine, sql, **params):
    with engine.begin() as connection:
        connection.execute(text(sql), params)


def fetch(engine, sql):
    with engine.connect() as connection:
        return connection.execute(text(sql)).fetchall()


def test_a_new_request_is_pending_with_nothing_decided(empty):
    insert(empty, f"insert into laboratory_requests ({COLUMNS}) values ({VALUES})")
    assert fetch(empty, "select status, decided_at, decided_by_id, laboratory_id, license, message from laboratory_requests") == [
        ("pending", None, None, None, None, None)]


@pytest.mark.parametrize("missing", ["requester_id", "slug", "name", "institution", "collection_code", "created_at"])
def test_a_request_needs_its_required_fields(empty, missing):
    columns = [c.strip() for c in COLUMNS.split(",")]
    values = [v.strip() for v in VALUES.split(",")]
    position = columns.index(missing)
    del columns[position], values[position]
    with pytest.raises(IntegrityError):
        insert(empty, f"insert into laboratory_requests ({', '.join(columns)}) values ({', '.join(values)})")


def test_the_same_slug_may_be_asked_for_again(empty):
    insert(empty, f"insert into laboratory_requests ({COLUMNS}, status) values ({VALUES}, 'rejected')")
    insert(empty, f"insert into laboratory_requests ({COLUMNS}) values ({VALUES})")
    assert fetch(empty, "select count(*) from laboratory_requests where slug = 'lab-x'") == [(2,)]


def test_the_models_link_the_people_and_the_laboratory(empty):
    from datetime import datetime
    from sqlalchemy.orm import Session
    with Session(empty) as session:
        requester = session.query(models.User).one()
        admin = models.User(email="super@ufmg.br", password_hash="h", is_superadmin=True)
        laboratory = models.Laboratory(slug="lab-x", name="Lab X", institution="UFMG", collection_code="LX", license="l")
        request = models.LaboratoryRequest(requester=requester, slug="lab-x", name="Lab X", institution="UFMG", collection_code="LX",
                                           created_at=datetime(2026, 11, 12), status="approved", decided_by=admin, laboratory=laboratory,
                                           decided_at=datetime(2026, 11, 12, 1))
        session.add(request)
        session.commit()
        stored = session.query(models.LaboratoryRequest).one()
        assert (stored.requester.email, stored.decided_by.email, stored.laboratory.slug) == ("a@ufmg.br", "super@ufmg.br", "lab-x")


def test_the_statuses_are_declared():
    assert models.LAB_REQUEST_STATUSES == ("pending", "approved", "rejected")


def test_the_database_matches_the_models(empty):
    with empty.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), models.Base.metadata) == []


def test_going_back_removes_only_the_requests(empty):
    insert(empty, f"insert into laboratory_requests ({COLUMNS}) values ({VALUES})")
    with empty.begin() as connection:
        cfg = Config(db_setup.ALEMBIC_INI)
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "0003")
    assert "laboratory_requests" not in inspect(empty).get_table_names()
    assert fetch(empty, "select email from users") == [("a@ufmg.br",)]
    db_setup.initialize_database()
    assert fetch(empty, "select count(*) from laboratory_requests") == [(0,)]
