"""Store the Google Place ID mapping / 保存 Google Place ID 對應。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_google_place_mapping"
down_revision: str | None = "0021_private_meal_conditions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add an optional Google Place ID to each restaurant."""
    op.add_column(
        "restaurants",
        sa.Column("google_place_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_restaurants_google_place_id",
        "restaurants",
        ["google_place_id"],
    )


def downgrade() -> None:
    """Remove the Google Place ID mapping."""
    op.drop_index("ix_restaurants_google_place_id", table_name="restaurants")
    op.drop_column("restaurants", "google_place_id")
