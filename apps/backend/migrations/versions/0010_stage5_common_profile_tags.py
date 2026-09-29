"""Add common profile tags / 新增常用個人 Tag。"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010_stage5_common_profile_tags"
down_revision: str | None = "0009_user_admin_email_overlap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


COMMON_TAGS = (
    ("55555555-5555-4555-8555-555555555555", "甜食控"),
    ("66666666-6666-4666-8666-666666666666", "肉食派"),
    ("77777777-7777-4777-8777-777777777777", "台式小吃"),
    ("88888888-8888-4888-8888-888888888888", "日式料理"),
    ("99999999-9999-4999-8999-999999999999", "韓式料理"),
    ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "素食友善"),
)


def upgrade() -> None:
    profile_tags = sa.table(
        "profile_tags",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("is_system", sa.Boolean()),
    )
    op.bulk_insert(
        profile_tags,
        [
            {
                "id": tag_id,
                "slug": display_name,
                "display_name": display_name,
                "is_system": True,
            }
            for tag_id, display_name in COMMON_TAGS
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    tag_names = ", ".join(f"'{display_name}'" for _, display_name in COMMON_TAGS)
    referenced = connection.execute(
        sa.text(
            "SELECT 1 FROM user_profile_tags upt "
            "JOIN profile_tags pt ON pt.id = upt.tag_id "
            f"WHERE pt.slug IN ({tag_names}) LIMIT 1"
        )
    ).first()
    if referenced is not None:
        raise RuntimeError("cannot remove common profile tags while profiles use them")

    profile_tags = sa.table("profile_tags", sa.column("slug", sa.String()))
    op.execute(
        profile_tags.delete().where(
            profile_tags.c.slug.in_([display_name for _, display_name in COMMON_TAGS])
        )
    )
