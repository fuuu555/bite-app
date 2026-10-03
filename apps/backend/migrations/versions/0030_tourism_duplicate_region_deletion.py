"""Add permanent tourism-source deletion markers and remove soft-ignore state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_tourism_source_deletions"
down_revision: str | None = "0029_tourism_duplicates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tourism_deleted_source_records",
        sa.Column("source_dataset", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=160), nullable=False),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_dataset IN ('food', 'attraction', 'hotel', 'service_site')",
            name="ck_tourism_deleted_source_records_dataset",
        ),
        sa.PrimaryKeyConstraint(
            "source_dataset",
            "source_record_id",
            name="pk_tourism_deleted_source_records",
        ),
    )
    op.drop_column("tourism_source_places", "is_ignored")


def downgrade() -> None:
    op.add_column(
        "tourism_source_places",
        sa.Column("is_ignored", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.drop_table("tourism_deleted_source_records")
