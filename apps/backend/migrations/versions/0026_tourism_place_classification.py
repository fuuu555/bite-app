"""Add tourism tags and icon metadata / 新增觀光資料分類與圖示欄位。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_tourism_classify"
down_revision: str | None = "0025_tourism_source_places"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store deterministic subcategory and visual metadata."""
    op.add_column(
        "tourism_source_places",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "tourism_source_places",
        sa.Column("icon_key", sa.String(length=40), server_default="map-pin", nullable=False),
    )
    op.add_column(
        "tourism_source_places",
        sa.Column("icon_color", sa.String(length=7), server_default="#657b8c", nullable=False),
    )
    op.alter_column("tourism_source_places", "tags", server_default=None)
    op.alter_column("tourism_source_places", "icon_key", server_default=None)
    op.alter_column("tourism_source_places", "icon_color", server_default=None)


def downgrade() -> None:
    """Remove tourism visual metadata."""
    op.drop_column("tourism_source_places", "icon_color")
    op.drop_column("tourism_source_places", "icon_key")
    op.drop_column("tourism_source_places", "tags")
