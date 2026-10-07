from sqlmodel import SQLModel, create_engine

from app.core.config import get_settings

engine = create_engine(
    f"sqlite:///{get_settings().data_dir / 'engine.db'}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    # Models must be imported before create_all so SQLModel sees every table.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
