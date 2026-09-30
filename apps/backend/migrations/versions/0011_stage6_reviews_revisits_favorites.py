"""Add Stage 6 review, revisit, like, and favorite data / 新增 Stage 6 留言資料。"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_stage6_reviews"
down_revision: str | None = "0010_stage5_common_profile_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REVIEW_REASONS = (
    ("10000000-0000-4000-8000-000000000001", "good-food", "好吃", "positive"),
    ("10000000-0000-4000-8000-000000000002", "good-value", "價格合理", "positive"),
    ("10000000-0000-4000-8000-000000000003", "good-portion", "份量足", "positive"),
    ("10000000-0000-4000-8000-000000000004", "good-service", "服務好", "positive"),
    ("10000000-0000-4000-8000-000000000005", "fast-service", "出餐快", "positive"),
    ("10000000-0000-4000-8000-000000000006", "too-expensive", "太貴", "negative"),
    ("10000000-0000-4000-8000-000000000007", "small-portion", "份量少", "negative"),
    ("10000000-0000-4000-8000-000000000008", "poor-food", "不好吃", "negative"),
    ("10000000-0000-4000-8000-000000000009", "hygiene-issue", "衛生問題", "negative"),
    ("10000000-0000-4000-8000-000000000010", "slow-service", "等太久", "negative"),
    ("10000000-0000-4000-8000-000000000011", "poor-service", "服務不好", "negative"),
    ("10000000-0000-4000-8000-000000000012", "misleading-photo", "照片不符", "negative"),
)


def upgrade() -> None:
    op.create_table(
        "restaurant_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("revisit_status", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "revisit_status IN ('will_return', 'neutral', 'will_not_return')",
            name="ck_restaurant_reviews_revisit_status",
        ),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_restaurant_reviews_restaurant_created",
        "restaurant_reviews",
        ["restaurant_id", "created_at"],
    )
    op.create_index(
        "ix_restaurant_reviews_restaurant_user_created",
        "restaurant_reviews",
        ["restaurant_id", "user_id", "created_at"],
    )

    op.create_table(
        "review_reasons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("polarity", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_review_reasons_slug", "review_reasons", ["slug"])

    op.create_table(
        "restaurant_review_reasons",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["reason_id"], ["review_reasons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["review_id"], ["restaurant_reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("review_id", "reason_id"),
    )

    op.create_table(
        "review_likes",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["review_id"], ["restaurant_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("review_id", "user_id"),
    )

    op.create_table(
        "restaurant_favorites",
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("restaurant_id", "user_id"),
    )

    reason_table = sa.table(
        "review_reasons",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("polarity", sa.String()),
    )
    op.bulk_insert(
        reason_table,
        [
            {
                "id": uuid.UUID(reason_id),
                "slug": slug,
                "display_name": display_name,
                "polarity": polarity,
            }
            for reason_id, slug, display_name, polarity in REVIEW_REASONS
        ],
    )


def downgrade() -> None:
    op.drop_table("restaurant_favorites")
    op.drop_table("review_likes")
    op.drop_table("restaurant_review_reasons")
    op.drop_index("ix_review_reasons_slug", table_name="review_reasons")
    op.drop_table("review_reasons")
    op.drop_index("ix_restaurant_reviews_restaurant_user_created", table_name="restaurant_reviews")
    op.drop_index("ix_restaurant_reviews_restaurant_created", table_name="restaurant_reviews")
    op.drop_table("restaurant_reviews")
