import os

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

import legacy_upgrade
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
# - a database from before Alembic (tables, but no alembic_version): converted once by legacy_upgrade,
#   then adopted by Alembic's first revision, which only creates what is missing
def initialize_database():
    tables = set(inspect(engine).get_table_names())
    predates_alembic = bool(tables) and "alembic_version" not in tables
    if predates_alembic:
        legacy_upgrade.prepare(engine)
        tables = set(inspect(engine).get_table_names())
    run_alembic_upgrade()
    if predates_alembic:
        legacy_upgrade.finish(engine, tables)
