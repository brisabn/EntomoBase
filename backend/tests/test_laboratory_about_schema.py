import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

import db_setup
import models


@pytest.fixture
def empty(tmp_path, initialize_at):
    engine = initialize_at(str(tmp_path / "new.db"))
    with engine.begin() as connection:
        connection.execute(text("insert into laboratories (slug, name, institution, collection_code, license, listed) "
                                "values ('lab-b', 'B', 'B', 'B', 'l', 1)"))
    return engine


def fetch(engine, sql):
    with engine.connect() as connection:
        return connection.execute(text(sql)).fetchall()


def test_a_laboratory_starts_without_a_presentation_contact_or_team(empty):
    assert fetch(empty, "select about, contact_email, team from laboratories where slug = 'lab-b'") == [(None, None, None)]


def test_the_team_comes_back_as_a_list_in_its_order(empty):
    team = [{"name": "Zé", "role": "Estudante"}, {"name": "Ana", "role": None}]
    with Session(empty) as session:
        session.query(models.Laboratory).filter_by(slug="lab-b").one().team = team
        session.commit()
    with Session(empty) as session:
        assert session.query(models.Laboratory).filter_by(slug="lab-b").one().team == team


def test_going_back_removes_only_the_new_columns(empty):
    with empty.begin() as connection:
        connection.execute(text("update laboratories set about = 'x', contact_email = 'a@b.br'"))
        cfg = Config(db_setup.ALEMBIC_INI)
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "0005")
    columns = {c["name"] for c in inspect(empty).get_columns("laboratories")}
    assert not {"about", "contact_email", "team"} & columns
    assert fetch(empty, "select slug, name from laboratories where slug = 'lab-b'") == [("lab-b", "B")]
    db_setup.initialize_database()
    assert fetch(empty, "select about from laboratories where slug = 'lab-b'") == [(None,)]
