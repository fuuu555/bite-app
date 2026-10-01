"""Add local avatar assets and profile selection / 新增本地頭貼資產與個人選擇。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_local_avatar_assets"
down_revision: str | None = "0013_stage7_meals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "avatar_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_avatar_assets_storage_key", "avatar_assets", ["storage_key"])

    op.add_column(
        "user_profiles",
        sa.Column("avatar_source", sa.String(length=16), server_default="url", nullable=False),
    )
    op.add_column(
        "user_profiles",
        sa.Column("avatar_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_user_profiles_avatar_source",
        "user_profiles",
        "avatar_source IN ('builtin', 'google', 'url')",
    )
    op.create_foreign_key(
        "fk_user_profiles_avatar_asset_id",
        "user_profiles",
        "avatar_assets",
        ["avatar_asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_user_profiles_avatar_asset_id", "user_profiles", ["avatar_asset_id"])


def downgrade() -> None:
    op.drop_index("ix_user_profiles_avatar_asset_id", table_name="user_profiles")
    op.drop_constraint("fk_user_profiles_avatar_asset_id", "user_profiles", type_="foreignkey")
    op.drop_constraint("ck_user_profiles_avatar_source", "user_profiles", type_="check")
    op.drop_column("user_profiles", "avatar_asset_id")
    op.drop_column("user_profiles", "avatar_source")
    op.drop_index("ix_avatar_assets_storage_key", table_name="avatar_assets")
    op.drop_table("avatar_assets")
