"""The engine database: where it lives, and how it gets to the current schema.

The schema is owned by Alembic from now on. `init_db` runs the migrations on startup, and a database
that was created before migrations existed (the app used to call `create_all`) is stamped with the
current revision instead of being recreated, so an installation in the wild keeps its rows.
"""

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlmodel import create_engine as sqlmodel_create_engine

from alembic import command
from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def database_url() -> str:
    """The SQLite URL of the engine database inside the configured data directory."""
    return f"sqlite:///{get_settings().data_dir / 'engine.db'}"


engine = sqlmodel_create_engine(
    database_url(),
    connect_args={"check_same_thread": False},
)


def migration_config(url: str) -> Config:
    """Alembic config pointed at one database file, independent of the ini file's own URL."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["sqlalchemy_url"] = url
    return config


def init_db(url: str | None = None) -> None:
    """Bring a database file to the current schema.

    A fresh file gets every revision. A file that already has tables but no revision marker was made
    by the old `create_all` path, and its schema is the initial revision, so it is stamped as current
    instead of being recreated (which would throw the existing rows away). Models are imported first
    so the metadata sees every table.
    """
    import app.models  # noqa: F401

    target = url or database_url()
    config = migration_config(target)
    if _is_legacy_database(target):
        command.stamp(config, "head")
    else:
        command.upgrade(config, "head")


def _is_legacy_database(url: str) -> bool:
    """Whether this file predates migrations: tables exist, but no revision marker does."""
    inspector_engine = create_engine(url)
    try:
        inspector = inspect(inspector_engine)
        names = inspector.get_table_names()
        if not names:
            return False
        with inspector_engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        return current is None and "job" in names
    finally:
        inspector_engine.dispose()
