"""Seed the fixed tourism icon classifications / 建立固定觀光資料圖示分類。"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_seed_tourism_cuisines"
down_revision: str | None = "0027_tourism_manage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TOURISM_CLASSIFICATIONS = (
    ("tourism-food", "餐飲", "tools-kitchen-3", "#F26B4F"),
    ("tourism-attraction", "景點", "map-pin", "#657B8C"),
    ("tourism-lodging", "旅館民宿", "bed", "#8B6BB1"),
    ("tourism-service-site", "旅遊服務站", "info-circle", "#4E8F6B"),
)


def upgrade() -> None:
    """Create canonical icon classifications and clear old per-place overrides."""
    bind = op.get_bind()
    for slug, display_name, icon_key, color in TOURISM_CLASSIFICATIONS:
        found = bind.execute(
            sa.text("SELECT id FROM cuisines WHERE slug = :slug LIMIT 1"),
            {"slug": slug},
        ).first()
        if found is None:
            found = bind.execute(
                sa.text("SELECT id FROM cuisines WHERE display_name = :name LIMIT 1"),
                {"name": display_name},
            ).first()
        if found:
            bind.execute(
                sa.text(
                    """
                    UPDATE cuisines SET slug = :slug, display_name = :display_name,
                        icon_key = :icon_key, color = :color, is_active = TRUE
                    WHERE id = :id
                    """
                ),
                {
                    "id": found.id,
                    "slug": slug,
                    "display_name": display_name,
                    "icon_key": icon_key,
                    "color": color,
                },
            )
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO cuisines (id, slug, display_name, icon_key, color, is_active)
                VALUES (:id, :slug, :display_name, :icon_key, :color, TRUE)
                """
            ),
            {
                "id": uuid.uuid4(),
                "slug": slug,
                "display_name": display_name,
                "icon_key": icon_key,
                "color": color,
            },
        )
    bind.execute(sa.text("UPDATE tourism_source_places SET display_icon_key = NULL"))


def downgrade() -> None:
    """Keep seeded categories because administrators may have attached restaurants."""
    # These are system defaults and may have become referenced after migration.
    # Deliberately retain them on downgrade rather than risk deleting user-linked data.
