"""Add tourism duplicate management and seed the Zhongyuan test restaurant."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029_tourism_duplicates"
down_revision: str | None = "0028_seed_tourism_cuisines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEST_CUISINE_ID = "b31a1111-bf7a-45ef-9d5d-9b49b4390421"
TEST_RESTAURANT_ID = "b31a2222-bf7a-45ef-9d5d-9b49b4390421"
TEST_RESTAURANT_NAME = "中原大學測試店"
TEST_RESTAURANT_ADDRESS = "桃園市中壢區普忠里中北路200號"


def upgrade() -> None:
    """Persist ignored tourism places and seed a clone-safe test restaurant."""
    op.add_column(
        "tourism_source_places",
        sa.Column("is_ignored", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.alter_column("tourism_source_places", "is_ignored", server_default=None)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX ix_tourism_source_places_display_name_trgm
        ON tourism_source_places
        USING gin (
            lower(regexp_replace(coalesce(display_name, name), '[[:space:][:punct:]]+', '', 'g'))
            gin_trgm_ops
        )
        """
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO cuisines (id, slug, display_name, color, icon_key, is_active)
            VALUES (:id, 'taiwanese', '台灣料理', '#4E8F6B', 'rice-bowl', TRUE)
            ON CONFLICT (slug) DO NOTHING
            """
        ),
        {"id": TEST_CUISINE_ID},
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO restaurants (
                id, name, address, primary_cuisine_id, price_range, status, source_type,
                latitude, longitude, google_lookup_enabled
            )
            SELECT
                :id, CAST(:name AS varchar(160)), :address, c.id,
                'under_200', 'published', 'manual',
                24.9571129, 121.2425529, FALSE
            FROM cuisines AS c
            WHERE c.slug = 'taiwanese'
              AND NOT EXISTS (
                  SELECT 1 FROM restaurants AS r
                  WHERE lower(trim(r.name)) = lower(CAST(:name AS varchar(160)))
                    AND lower(trim(r.address)) = lower(:address)
              )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": TEST_RESTAURANT_ID,
            "name": TEST_RESTAURANT_NAME,
            "address": TEST_RESTAURANT_ADDRESS,
        },
    )


def downgrade() -> None:
    """Keep seeded user data; remove only schema introduced by this revision."""
    op.drop_index(
        "ix_tourism_source_places_display_name_trgm",
        table_name="tourism_source_places",
    )
    op.drop_column("tourism_source_places", "is_ignored")
