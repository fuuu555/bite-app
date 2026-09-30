"""Normalize review threads and revisit entries / 正規化留言串與再訪紀錄。"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_review_threads"
down_revision: str | None = "0011_stage6_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "restaurant_review_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "restaurant_id",
            "user_id",
            name="uq_restaurant_review_threads_restaurant_user",
        ),
    )
    op.create_index(
        "ix_restaurant_review_threads_restaurant_user",
        "restaurant_review_threads",
        ["restaurant_id", "user_id"],
    )

    op.add_column(
        "restaurant_reviews",
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("restaurant_reviews", sa.Column("entry_number", sa.Integer(), nullable=True))
    op.create_index("ix_restaurant_reviews_thread_id", "restaurant_reviews", ["thread_id"])

    connection = op.get_bind()
    review_groups = connection.execute(
        sa.text(
            "SELECT restaurant_id, user_id "
            "FROM restaurant_reviews "
            "GROUP BY restaurant_id, user_id"
        )
    ).mappings()
    for group in review_groups:
        thread_id = uuid.uuid4()
        connection.execute(
            sa.text(
                "INSERT INTO restaurant_review_threads "
                "(id, restaurant_id, user_id) VALUES (:id, :restaurant_id, :user_id)"
            ),
            {
                "id": thread_id,
                "restaurant_id": group["restaurant_id"],
                "user_id": group["user_id"],
            },
        )
        review_ids = connection.execute(
            sa.text(
                "SELECT id FROM restaurant_reviews "
                "WHERE restaurant_id = :restaurant_id AND user_id = :user_id "
                "ORDER BY created_at ASC, id ASC"
            ),
            {
                "restaurant_id": group["restaurant_id"],
                "user_id": group["user_id"],
            },
        ).scalars()
        for entry_number, review_id in enumerate(review_ids, start=1):
            connection.execute(
                sa.text(
                    "UPDATE restaurant_reviews "
                    "SET thread_id = :thread_id, entry_number = :entry_number "
                    "WHERE id = :review_id"
                ),
                {
                    "thread_id": thread_id,
                    "entry_number": entry_number,
                    "review_id": review_id,
                },
            )

    op.alter_column("restaurant_reviews", "thread_id", nullable=False)
    op.alter_column("restaurant_reviews", "entry_number", nullable=False)
    op.create_foreign_key(
        "fk_restaurant_reviews_thread_id",
        "restaurant_reviews",
        "restaurant_review_threads",
        ["thread_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_restaurant_reviews_thread_entry_number",
        "restaurant_reviews",
        ["thread_id", "entry_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_restaurant_reviews_thread_entry_number",
        "restaurant_reviews",
        type_="unique",
    )
    op.drop_constraint("fk_restaurant_reviews_thread_id", "restaurant_reviews", type_="foreignkey")
    op.drop_index("ix_restaurant_reviews_thread_id", table_name="restaurant_reviews")
    op.drop_column("restaurant_reviews", "entry_number")
    op.drop_column("restaurant_reviews", "thread_id")
    op.drop_index(
        "ix_restaurant_review_threads_restaurant_user",
        table_name="restaurant_review_threads",
    )
    op.drop_table("restaurant_review_threads")
