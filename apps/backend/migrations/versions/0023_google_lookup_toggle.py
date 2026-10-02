"""Add the restaurant Google lookup toggle / 新增餐廳 Google 查詢開關。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_google_lookup_toggle"
down_revision: str | None = "0022_google_place_mapping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep existing restaurants enabled while allowing test data to opt out."""
    op.add_column(
        "restaurants",
        sa.Column(
            "google_lookup_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.alter_column("restaurants", "google_lookup_enabled", server_default=None)


def downgrade() -> None:
    """Remove the restaurant Google lookup toggle."""
    op.drop_column("restaurants", "google_lookup_enabled")
