"""Add tourism place management fields / 新增觀光資料管理欄位。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_tourism_manage"
down_revision: str | None = "0026_tourism_classify"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store display overrides and the optional BiteMap restaurant link."""
    op.add_column(
        "tourism_source_places", sa.Column("display_name", sa.String(240), nullable=True)
    )
    op.add_column(
        "tourism_source_places", sa.Column("display_address", sa.Text(), nullable=True)
    )
    op.add_column(
        "tourism_source_places", sa.Column("display_icon_key", sa.String(40), nullable=True)
    )
    op.add_column(
        "tourism_source_places",
        sa.Column("is_map_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "tourism_source_places",
        sa.Column(
            "linked_restaurant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("restaurants.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
    )
    op.alter_column("tourism_source_places", "is_map_enabled", server_default=None)


def downgrade() -> None:
    """Remove tourism place management fields."""
    op.drop_column("tourism_source_places", "linked_restaurant_id")
    op.drop_column("tourism_source_places", "is_map_enabled")
    op.drop_column("tourism_source_places", "display_icon_key")
    op.drop_column("tourism_source_places", "display_address")
    op.drop_column("tourism_source_places", "display_name")
