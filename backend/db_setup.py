import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from database import engine

ALEMBIC_INI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alembic.ini")


# brings the database to the newest Alembic revision, reusing this module's connection
def run_alembic_upgrade():
    config = Config(ALEMBIC_INI)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


# creates or updates the database; safe to run many times
# called when the API starts and by the scripts (seed.py, create_admin.py), never on import
#
# - a new database: Alembic creates everything
# - a database Alembic already manages: Alembic applies the revisions it is missing
# - a database with tables but no alembic_version table was not created by Alembic: it is refused, because
#   guessing its state could damage it
def initialize_database():
    tables = set(inspect(engine).get_table_names())
    if tables and "alembic_version" not in tables:
        raise RuntimeError(
            "The database has tables but no alembic_version table, so it was not created by the migrations. "
            "Delete the database file and start again (python seed.py creates the demo data)."
        )
    run_alembic_upgrade()
