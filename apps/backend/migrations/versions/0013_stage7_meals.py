"""Add Stage 7 meal membership and voting data / 新增 Stage 7 約飯與投票資料。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_stage7_meals"
down_revision: str | None = "0012_review_threads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meal_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("host_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("join_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("decided_restaurant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("visibility IN ('public', 'private')", name="ck_meal_events_visibility"),
        sa.CheckConstraint(
            "status IN ('open', 'voting', 'decided', 'cancelled', 'completed')",
            name="ck_meal_events_status",
        ),
        sa.CheckConstraint("capacity >= 2", name="ck_meal_events_capacity"),
        sa.ForeignKeyConstraint(["host_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_restaurant_id"], ["restaurants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meal_events_host_user_id", "meal_events", ["host_user_id"])
    op.create_index("ix_meal_events_scheduled_at", "meal_events", ["scheduled_at"])
    op.create_index(
        "ix_meal_events_visibility_status_time",
        "meal_events",
        ["visibility", "status", "scheduled_at"],
    )

    op.create_table(
        "meal_memberships",
        sa.Column("meal_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "membership_status IN ('host', 'member', 'pending', 'rejected', 'left', 'removed')",
            name="ck_meal_memberships_status",
        ),
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("meal_event_id", "user_id"),
    )
    op.create_index("ix_meal_memberships_user_id", "meal_memberships", ["user_id"])
    op.create_index(
        "ix_meal_memberships_meal_status",
        "meal_memberships",
        ["meal_event_id", "membership_status"],
    )

    op.create_table(
        "meal_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meal_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("position BETWEEN 1 AND 3", name="ck_meal_candidates_position"),
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meal_event_id", "restaurant_id", name="uq_meal_candidates_restaurant"),
        sa.UniqueConstraint("meal_event_id", "position", name="uq_meal_candidates_position"),
    )
    op.create_index("ix_meal_candidates_meal_event_id", "meal_candidates", ["meal_event_id"])

    op.create_table(
        "meal_votes",
        sa.Column("meal_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("voter_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["voter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["meal_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("meal_event_id", "voter_user_id"),
    )
    op.create_index("ix_meal_votes_candidate_id", "meal_votes", ["candidate_id"])


def downgrade() -> None:
    op.drop_index("ix_meal_votes_candidate_id", table_name="meal_votes")
    op.drop_table("meal_votes")
    op.drop_index("ix_meal_candidates_meal_event_id", table_name="meal_candidates")
    op.drop_table("meal_candidates")
    op.drop_index("ix_meal_memberships_meal_status", table_name="meal_memberships")
    op.drop_index("ix_meal_memberships_user_id", table_name="meal_memberships")
    op.drop_table("meal_memberships")
    op.drop_index("ix_meal_events_visibility_status_time", table_name="meal_events")
    op.drop_index("ix_meal_events_scheduled_at", table_name="meal_events")
    op.drop_index("ix_meal_events_host_user_id", table_name="meal_events")
    op.drop_table("meal_events")
