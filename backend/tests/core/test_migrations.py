"""The database reaches the current schema, whether it is fresh or predates migrations."""

import sqlite3

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

import app.models  # noqa: F401  registers the tables used below
from app.core.db import init_db
from app.models import Job


def _tables(path) -> list[str]:
    return sorted(
        row[0]
        for row in sqlite3.connect(path).execute(
            "select name from sqlite_master where type='table' order by name"
        )
    )


def _revision(path) -> str | None:
    rows = list(sqlite3.connect(path).execute("select version_num from alembic_version"))
    return rows[0][0] if rows else None


def test_a_fresh_database_gets_every_revision(tmp_path):
    fresh = tmp_path / "fresh.db"
    init_db(f"sqlite:///{fresh}")
    assert _tables(fresh) == ["alembic_version", "job"]
    assert _revision(fresh)


def test_a_database_from_before_migrations_is_adopted_not_rebuilt(tmp_path):
    """The old create_all files exist in the wild, and their rows must survive the upgrade."""
    legacy = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{legacy}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Job(id="keepme", title="Keep me"))
        session.commit()
    engine.dispose()

    init_db(f"sqlite:///{legacy}")

    kept = list(sqlite3.connect(legacy).execute("select id, title from job"))
    assert kept == [("keepme", "Keep me")]
    assert _revision(legacy)


def test_running_the_migrations_twice_changes_nothing(tmp_path):
    fresh = tmp_path / "fresh.db"
    init_db(f"sqlite:///{fresh}")
    first = _revision(fresh)
    init_db(f"sqlite:///{fresh}")
    assert _revision(fresh) == first
    assert "job" in _tables(fresh)
