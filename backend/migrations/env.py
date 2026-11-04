"""
Alembic environment.

The database URL and the model metadata both come from the application, so migrations can
never drift from what the app actually runs against. Nothing here hardcodes a connection.
"""

from logging.config import fileConfig
from pathlib import Path
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db import Base

# Importing the models registers every table on Base.metadata; autogenerate sees nothing
# without this.
from app import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# app/config.py is the default source of truth for the URL unless explicitly configured.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting — useful for reviewing a production change."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Without these, a changed column type or default is silently missed.
            compare_type=True,
            compare_server_default=True,
            # SQLite cannot ALTER most columns; batch mode rewrites the table instead.
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
