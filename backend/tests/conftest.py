import os
import tempfile

# the tests always use their own database and settings, whatever the shell has set;
# this runs before any test file imports the application
_TEMP_DIR = tempfile.mkdtemp(prefix="entomobase_tests_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TEMP_DIR, "test.db").replace("\\", "/")
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-32-bytes-ok"
os.environ["CORS_ORIGINS"] = "http://allowed.test"
os.environ.pop("ENTOMOBASE_ENV", None)

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

import gbif
import models
from database import SessionLocal, engine

PASSWORD = "senhaforte1"
EMAIL = "admin@lab.br"


@pytest.fixture(scope="session")
def app():
    import main
    assert "test.db" in str(engine.url), "tests must never run against a real database"
    return main.app


# starts the application once, so the lifespan creates the tables in the test database
@pytest.fixture(scope="session", autouse=True)
def started_app(app):
    with TestClient(app):
        yield


# every test starts with empty tables and fresh login counters
@pytest.fixture(autouse=True)
def clean_state():
    import main
    with engine.begin() as conn:
        for table in reversed(models.Base.metadata.sorted_tables):
            conn.execute(table.delete())
    main.account_limiter._failures.clear()
    main.ip_limiter._failures.clear()
    yield


# GBIF is never reached in tests; individual tests replace these when they need an answer
@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the tests must not call the network")
    monkeypatch.setattr(gbif, "_get", refuse)
    monkeypatch.setattr(gbif, "lookup", lambda name: {
        "status": "ok", "suggestion": None, "gbif_key": 1, "family": None, "order_name": None,
    })


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(scope="session")
def password_hash():
    from security import hash_password
    return hash_password(PASSWORD)


@pytest.fixture
def user(password_hash):
    db = SessionLocal()
    try:
        db.add(models.User(email=EMAIL, password_hash=password_hash))
        db.commit()
    finally:
        db.close()
    return {"email": EMAIL, "password": PASSWORD}


def make_token(key=None, expires_in=timedelta(hours=1), email=EMAIL):
    import main
    exp = datetime.now(timezone.utc) + expires_in
    return jwt.encode({"sub": email, "exp": exp}, key or main.SECRET_KEY, algorithm="HS256")


@pytest.fixture
def admin(user):
    return {"Authorization": f"Bearer {make_token()}"}


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# runs initialize_database() against a separate temporary database, in this process so coverage sees it;
# returns an engine for that database, which stays open until the end of the test
@pytest.fixture
def initialize_at(monkeypatch):
    import db_setup
    from sqlalchemy import create_engine
    engines = []

    def run(db_path, times=1):
        engine = create_engine("sqlite:///" + db_path.replace("\\", "/"))
        engines.append(engine)
        monkeypatch.setattr(db_setup, "engine", engine)
        for _ in range(times):
            db_setup.initialize_database()
        return engine

    yield run
    for engine in engines:
        engine.dispose()
