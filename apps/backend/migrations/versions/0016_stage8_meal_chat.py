"""Add persistent meal conversations and messages / 新增永久飯局聊天室與訊息。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_stage8_meal_chat"
down_revision: str | None = "0015_meal_deadline_capacity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create normalized chat tables and backfill meal rooms / 建立正規化聊天表並回填飯局。"""
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("meal_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("kind IN ('meal', 'direct')", name="ck_conversations_kind"),
        sa.CheckConstraint(
            "(kind = 'meal' AND meal_event_id IS NOT NULL) OR "
            "(kind = 'direct' AND meal_event_id IS NULL)",
            name="ck_conversations_kind_target",
        ),
        sa.ForeignKeyConstraint(["meal_event_id"], ["meal_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meal_event_id"),
    )
    op.create_table(
        "conversation_members",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("conversation_id", "user_id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "char_length(content) BETWEEN 1 AND 2000", name="ck_messages_content_length"
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at", "id"],
        unique=False,
    )
    op.create_index("ix_messages_sender_user_id", "messages", ["sender_user_id"], unique=False)

    op.execute(
        """
        INSERT INTO conversations (id, kind, meal_event_id, created_at, updated_at)
        SELECT gen_random_uuid(), 'meal', id, created_at, updated_at
        FROM meal_events
        """
    )
    op.execute(
        """
        INSERT INTO conversation_members (conversation_id, user_id, joined_at, left_at)
        SELECT c.id, mm.user_id, mm.created_at, NULL
        FROM meal_memberships AS mm
        JOIN conversations AS c ON c.meal_event_id = mm.meal_event_id
        WHERE mm.membership_status IN ('host', 'member')
        """
    )


def downgrade() -> None:
    """Remove Stage 8 chat storage / 移除 Stage 8 聊天儲存。"""
    op.drop_index("ix_messages_sender_user_id", table_name="messages")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversation_members")
    op.drop_table("conversations")
