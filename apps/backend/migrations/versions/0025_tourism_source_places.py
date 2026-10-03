"""Add the official tourism source data layer / 新增觀光署官方資料層。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0025_tourism_source_places"
down_revision: str | None = "0024_explore_search_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create isolated official tourism places and import reports."""
    op.create_table(
        "tourism_source_places",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_dataset", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            sa.Computed(
                "CASE WHEN latitude IS NULL THEN NULL ELSE "
                "ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography END",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("official_url", sa.String(length=1000), nullable=True),
        sa.Column("opening_hours", sa.Text(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="active", nullable=False),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_dataset IN ('food', 'attraction', 'hotel', 'service_site')",
            name="ck_tourism_source_places_dataset",
        ),
        sa.CheckConstraint(
            "category IN ('restaurant', 'attraction', 'hotel', 'service_site')",
            name="ck_tourism_source_places_category",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'invalid', 'pending_review', 'published')",
            name="ck_tourism_source_places_status",
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_tourism_source_places_latitude",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_tourism_source_places_longitude",
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_tourism_source_places_coordinate_pair",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_dataset",
            "source_record_id",
            name="uq_tourism_source_places_dataset_record",
        ),
    )
    op.create_index(
        "ix_tourism_source_places_location_gist",
        "tourism_source_places",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "ix_tourism_source_places_category_status",
        "tourism_source_places",
        ["category", "status"],
        unique=False,
    )

    op.create_table(
        "tourism_import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_dataset", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="running", nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inserted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unchanged_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("invalid_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deactivated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "source_dataset IN ('food', 'attraction', 'hotel', 'service_site')",
            name="ck_tourism_import_runs_dataset",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_tourism_import_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tourism_import_runs_dataset_started",
        "tourism_import_runs",
        ["source_dataset", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the official tourism source data layer."""
    op.drop_index("ix_tourism_import_runs_dataset_started", table_name="tourism_import_runs")
    op.drop_table("tourism_import_runs")
    op.drop_index("ix_tourism_source_places_category_status", table_name="tourism_source_places")
    op.drop_index("ix_tourism_source_places_location_gist", table_name="tourism_source_places")
    op.drop_table("tourism_source_places")
