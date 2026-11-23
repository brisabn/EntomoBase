import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

SQLITE_FILE_URL = "sqlite:///./entomobase.db"


# the address of the database, from DATABASE_URL; without it, a local SQLite file for quick development
# a plain postgresql:// or postgres:// address (the form most hosts give) is sent to the psycopg driver,
# the one in requirements.txt; SQLAlchemy alone would look for the older psycopg2
def database_url(raw=None):
    url = make_url(raw or os.getenv("DATABASE_URL") or SQLITE_FILE_URL)
    if url.drivername in ("postgresql", "postgres"):
        url = url.set(drivername="postgresql+psycopg")
    return url


def is_sqlite(url):
    return url.get_backend_name() == "sqlite"


def new_engine(url):
    # SQLite refuses by default a connection used by a thread other than the one that opened it, and the
    # API answers each request in a thread of its own
    connect_args = {"check_same_thread": False} if is_sqlite(url) else {}
    return create_engine(url, connect_args=connect_args)


SQLALCHEMY_DATABASE_URL = database_url()
engine = new_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
