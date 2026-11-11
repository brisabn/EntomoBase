from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

import models  # noqa: F401  (importing it registers the tables on Base.metadata)
from database import SQLALCHEMY_DATABASE_URL, Base

config = context.config
target_metadata = Base.metadata

# from the command line the logging comes from alembic.ini; when the API runs the migrations it
# passes its own connection and logging is left alone
if config.config_file_name is not None and "connection" not in config.attributes:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def configure(**kwargs):
    # batch mode lets SQLite apply changes it cannot do with ALTER TABLE, by rebuilding the table
    context.configure(target_metadata=target_metadata, render_as_batch=True, compare_type=True, **kwargs)


# prints the SQL instead of running it (alembic upgrade head --sql)
def run_migrations_offline() -> None:  # pragma: no cover
    configure(url=SQLALCHEMY_DATABASE_URL, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # the API (db_setup.py) hands over the connection it already has; the command line makes its own
    connection = config.attributes.get("connection")
    if connection is not None:
        configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(SQLALCHEMY_DATABASE_URL)  # pragma: no cover
    with engine.connect() as connection:  # pragma: no cover
        configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()  # pragma: no cover


if context.is_offline_mode():  # pragma: no cover
    run_migrations_offline()
else:
    run_migrations_online()
