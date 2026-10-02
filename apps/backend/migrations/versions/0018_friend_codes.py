"""Add unique six-digit friend lookup codes / 新增唯一六位數好友查找碼。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_friend_codes"
down_revision: str | None = "0017_social_direct_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill stable codes before enforcing the profile contract / 先回填再鎖定欄位契約。"""
    op.add_column("user_profiles", sa.Column("friend_code", sa.String(length=6), nullable=True))
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                profile_row RECORD;
                candidate TEXT;
            BEGIN
                FOR profile_row IN
                    SELECT user_id FROM user_profiles WHERE friend_code IS NULL
                LOOP
                    LOOP
                        candidate := lpad(floor(random() * 1000000)::bigint::text, 6, '0');
                        EXIT WHEN NOT EXISTS (
                            SELECT 1 FROM user_profiles WHERE friend_code = candidate
                        );
                    END LOOP;
                    UPDATE user_profiles
                    SET friend_code = candidate
                    WHERE user_id = profile_row.user_id;
                END LOOP;
            END $$;
            """
        )
    )
    op.create_check_constraint(
        "ck_user_profiles_friend_code_digits",
        "user_profiles",
        "friend_code ~ '^[0-9]{6}$'",
    )
    op.create_unique_constraint("uq_user_profiles_friend_code", "user_profiles", ["friend_code"])
    op.alter_column("user_profiles", "friend_code", nullable=False)


def downgrade() -> None:
    """Remove friend lookup codes / 移除好友查找碼。"""
    op.drop_constraint("uq_user_profiles_friend_code", "user_profiles", type_="unique")
    op.drop_constraint("ck_user_profiles_friend_code_digits", "user_profiles", type_="check")
    op.drop_column("user_profiles", "friend_code")
