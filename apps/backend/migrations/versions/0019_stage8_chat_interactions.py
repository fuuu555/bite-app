"""Add chat read cursors, message recall and follows / 新增聊天互動與追蹤。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_stage8_chat_interactions"
down_revision: str | None = "0018_friend_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add normalized follow data and durable chat interaction state."""
    op.add_column(
        "conversation_members",
        sa.Column(
            "last_read_message_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "conversation_members",
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversation_members_last_read_message",
        "conversation_members",
        "messages",
        ["last_read_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("messages", sa.Column("recalled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "user_follows",
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("followed_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "follower_id <> followed_id", name="ck_user_follows_distinct_users"
        ),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["followed_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("follower_id", "followed_id"),
    )
    op.create_index(
        "ix_user_follows_followed_id",
        "user_follows",
        ["followed_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove chat interaction state and follow relations."""
    op.drop_index("ix_user_follows_followed_id", table_name="user_follows")
    op.drop_table("user_follows")
    op.drop_column("messages", "recalled_at")
    op.drop_constraint(
        "fk_conversation_members_last_read_message",
        "conversation_members",
        type_="foreignkey",
    )
    op.drop_column("conversation_members", "last_read_at")
    op.drop_column("conversation_members", "last_read_message_id")
