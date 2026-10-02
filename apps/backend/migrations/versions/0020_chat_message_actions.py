"""Add chat replies and pins / 新增聊天室回覆與釘選。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_chat_message_actions"
down_revision: str | None = "0019_stage8_chat_interactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add durable reply and pin relations."""
    op.add_column(
        "messages",
        sa.Column("reply_to_message_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_messages_reply_to_message",
        "messages",
        "messages",
        ["reply_to_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "message_pins",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pinned_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pinned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pinned_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index(
        "ix_message_pins_pinned_at",
        "message_pins",
        ["pinned_at", "message_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove durable reply and pin relations."""
    op.drop_index("ix_message_pins_pinned_at", table_name="message_pins")
    op.drop_table("message_pins")
    op.drop_constraint("fk_messages_reply_to_message", "messages", type_="foreignkey")
    op.drop_column("messages", "reply_to_message_id")
