"""Add private meal condition labels / 新增私人約飯條件標示。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_private_meal_conditions"
down_revision: str | None = "0020_chat_message_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add an optional host-selected condition label for private meals."""
    op.add_column(
        "meal_events",
        sa.Column("private_condition", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        "ck_meal_events_private_condition",
        "meal_events",
        "private_condition IS NULL OR "
        "(visibility = 'private' AND private_condition IN ('male_only', 'female_only'))",
    )


def downgrade() -> None:
    """Remove private meal condition labels."""
    op.drop_constraint(
        "ck_meal_events_private_condition", "meal_events", type_="check"
    )
    op.drop_column("meal_events", "private_condition")
