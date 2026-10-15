"""Alembic environment: the engine's own database, with the SQLModel metadata as the target.

The URL comes from the engine settings instead of the ini file, so migrations always run against the
data directory the app actually uses. A caller (or a test) can override it through
`config.attributes["sqlalchemy_url"]` or the `ULASAPP_DATABASE_URL` environment variable, which is how
the initial revision was generated against an empty file.

Batch mode is on because SQLite cannot alter a column in place: batch mode recreates the table, which
is what makes adding or changing a column possible for an existing installation.
"""

import os
from logging.config import fileConfig

import app.models  # noqa: F401  registers every table on the metadata before it is inspected
from alembic import context
from app.core.config import get_settings
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def database_url() -> str:
    """Where to migrate: an explicit override first, then the engine's own data directory."""
    override = config.attributes.get("sqlalchemy_url") or os.environ.get("ULASAPP_DATABASE_URL")
    if override:
        return str(override)
    return f"sqlite:///{get_settings().data_dir / 'engine.db'}"


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
