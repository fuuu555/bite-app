"""Add Explore full-text and address trigram indexes / 新增探索搜尋索引。"""

from collections.abc import Sequence

from alembic import op

revision: str = "0024_explore_search_indexes"
down_revision: str | None = "0023_google_lookup_toggle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Index restaurant names and addresses for Explore search."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX ix_restaurants_search_tsvector
        ON restaurants
        USING gin (
            to_tsvector(
                'simple',
                coalesce(name, '') || ' ' || coalesce(address, '')
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_restaurants_address_lower_trgm
        ON restaurants
        USING gin (lower(address) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    """Remove Explore search indexes."""
    op.execute("DROP INDEX IF EXISTS ix_restaurants_address_lower_trgm")
    op.execute("DROP INDEX IF EXISTS ix_restaurants_search_tsvector")
