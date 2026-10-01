"""Allow Google users to share an email with admin accounts.

允許 Google 使用者與管理員共用 email。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_user_admin_email_overlap"
down_revision: str | None = "0008_google_oauth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.create_index(
        "uq_users_admin_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("role = 'admin'"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_admin_email", table_name="users")
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text(
            "SELECT email FROM users WHERE email IS NOT NULL "
            "GROUP BY email HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError("cannot restore unique users.email while duplicate user emails exist")
    op.create_unique_constraint("users_email_key", "users", ["email"])
