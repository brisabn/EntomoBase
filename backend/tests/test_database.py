import pytest

import database
from database import database_url, is_sqlite


def test_without_database_url_it_is_the_local_sqlite_file(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = database_url()
    assert url.drivername == "sqlite" and url.database == "./entomobase.db"


def test_an_empty_database_url_is_the_same_as_none(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    assert database_url().database == "./entomobase.db"


def test_database_url_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db.example:5433/lab")
    url = database_url()
    assert (url.host, url.port, url.database, url.username, url.password) == ("db.example", 5433, "lab", "u", "p")


@pytest.mark.parametrize("given", ["postgresql://u:p@h/db", "postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"])
def test_a_postgresql_address_goes_to_the_psycopg_driver(given):
    url = database_url(given)
    assert url.drivername == "postgresql+psycopg" and url.database == "db"
    assert not is_sqlite(url)


def test_a_driver_chosen_on_purpose_is_kept():
    assert database_url("postgresql+psycopg2://u:p@h/db").drivername == "postgresql+psycopg2"


def test_sqlite_addresses_are_recognized():
    assert is_sqlite(database_url("sqlite:///./x.db"))
    # a PostgreSQL database may have sqlite in its name without being one
    assert not is_sqlite(database_url("postgresql://u:p@h/sqlite_copy"))


def test_only_sqlite_gets_the_thread_option(monkeypatch):
    seen = {}
    monkeypatch.setattr(database, "create_engine", lambda url, connect_args: seen.setdefault(url.drivername, connect_args))
    database.new_engine(database_url("sqlite:///./x.db"))
    database.new_engine(database_url("postgresql://u:p@h/db"))
    assert seen == {"sqlite": {"check_same_thread": False}, "postgresql+psycopg": {}}
