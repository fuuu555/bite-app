"""Enable PostGIS for geospatial store discovery / 啟用地圖店家查詢所需的 PostGIS。"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_postgis"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable the extension / 啟用空間資料庫 extension。"""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    """Remove the extension / 回復時移除空間資料庫 extension。"""
    # The PostGIS image also provisions topology and tiger-geocoder extensions.
    # PostGIS image 也會建立 topology 與 tiger-geocoder，需先移除相依 extension。
    op.execute("DROP EXTENSION IF EXISTS postgis_tiger_geocoder")
    op.execute("DROP EXTENSION IF EXISTS postgis_topology")
    op.execute("DROP EXTENSION IF EXISTS postgis")
