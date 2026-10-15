"""job table

Revision ID: 55144fcf3f0c
Revises:
Create Date: 2026-10-12 14:34:00.494438

The schema as it stood when migrations were introduced. Databases created before this revision exist
in the wild (the app used to call create_all), so `app.core.db` stamps those instead of running this.
"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision = "55144fcf3f0c"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("stage", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("error", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("aspect", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("mode", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_dir", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column("updated_at", sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("job")
