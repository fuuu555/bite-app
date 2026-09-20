"""Add an optional menu link / 新增可選的菜單網址。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_menu_url"
down_revision: str | None = "0003_audit_3nf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store one canonical menu URL per restaurant / 每間店先保存一個菜單網址。"""
    op.add_column("restaurants", sa.Column("menu_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    """Remove the first-version menu URL / 移除初版菜單網址欄位。"""
    op.drop_column("restaurants", "menu_url")
