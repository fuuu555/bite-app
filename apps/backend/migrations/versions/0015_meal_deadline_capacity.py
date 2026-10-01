"""Add public meal deadline capacity state / 新增公開約飯截止人數狀態。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_meal_deadline_capacity"
down_revision: str | None = "0014_local_avatar_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow the host-decision status / 允許等待發起人確認的狀態。"""
    op.drop_constraint("ck_meal_events_status", "meal_events", type_="check")
    op.alter_column(
        "meal_events", "status", existing_type=sa.String(length=16), type_=sa.String(length=24)
    )
    op.create_check_constraint(
        "ck_meal_events_status",
        "meal_events",
        "status IN ('open', 'awaiting_host_decision', 'voting', 'decided', 'cancelled', 'completed')",
    )


def downgrade() -> None:
    """Return to the original Stage 7 status set / 回復原有約飯狀態集合。"""
    op.execute(
        "UPDATE meal_events SET status = 'cancelled' WHERE status = 'awaiting_host_decision'"
    )
    op.drop_constraint("ck_meal_events_status", "meal_events", type_="check")
    op.alter_column(
        "meal_events", "status", existing_type=sa.String(length=24), type_=sa.String(length=16)
    )
    op.create_check_constraint(
        "ck_meal_events_status",
        "meal_events",
        "status IN ('open', 'voting', 'decided', 'cancelled', 'completed')",
    )
