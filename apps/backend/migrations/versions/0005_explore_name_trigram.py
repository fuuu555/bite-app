"""Optimize case-insensitive restaurant name search / 最佳化店名搜尋。"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_explore_name_trigram"
down_revision: str | None = "0004_menu_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a trigram index for the existing lower-case name predicate."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX ix_restaurants_name_lower_trgm
        ON restaurants
        USING gin (lower(name) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    """Remove only the index owned by this migration."""
    op.execute("DROP INDEX IF EXISTS ix_restaurants_name_lower_trgm")
