import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Job(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    title: str
    status: str = Field(default="queued")  # queued | running | done | failed
    stage: str | None = None
    error: str | None = None
    aspect: str = "9:16"
    mode: str = "voiceless"
    project_dir: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
