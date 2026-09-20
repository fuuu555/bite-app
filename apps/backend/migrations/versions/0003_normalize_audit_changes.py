"""Normalize audit field changes / 將稽核欄位變更正規化。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_audit_3nf"
down_revision: str | None = "0002_stage1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Move repeated field facts out of JSON snapshots / 將重複欄位事實移出 JSON 快照。"""
    op.create_table(
        "audit_log_changes",
        sa.Column("audit_log_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["audit_log_id"], ["audit_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("audit_log_id", "field_name"),
    )

    # Preserve existing audit history while converting each changed field into one row.
    # 保留既有稽核歷史，並將每個異動欄位轉成一筆明細。
    op.execute(
        sa.text(
            """
            INSERT INTO audit_log_changes (
                audit_log_id,
                field_name,
                before_value,
                after_value
            )
            SELECT
                audit_logs.id,
                field_names.field_name,
                audit_logs.before_data ->> field_names.field_name,
                audit_logs.after_data ->> field_names.field_name
            FROM audit_logs
            CROSS JOIN LATERAL jsonb_object_keys(
                COALESCE(audit_logs.before_data, '{}'::jsonb)
                || COALESCE(audit_logs.after_data, '{}'::jsonb)
            ) AS field_names(field_name)
            WHERE audit_logs.before_data -> field_names.field_name
                IS DISTINCT FROM audit_logs.after_data -> field_names.field_name
            """
        )
    )

    op.drop_constraint("audit_logs_id_created_at_key", "audit_logs", type_="unique")
    op.drop_column("audit_logs", "after_data")
    op.drop_column("audit_logs", "before_data")


def downgrade() -> None:
    """Restore snapshot columns for rollback / 回復快照欄位以支援降版。"""
    op.add_column(
        "audit_logs",
        sa.Column("before_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("after_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE audit_logs
            SET
                before_data = snapshots.before_data,
                after_data = snapshots.after_data
            FROM (
                SELECT
                    audit_log_id,
                    jsonb_object_agg(field_name, before_value)
                        FILTER (WHERE before_value IS NOT NULL) AS before_data,
                    jsonb_object_agg(field_name, after_value)
                        FILTER (WHERE after_value IS NOT NULL) AS after_data
                FROM audit_log_changes
                GROUP BY audit_log_id
            ) AS snapshots
            WHERE audit_logs.id = snapshots.audit_log_id
            """
        )
    )

    op.create_unique_constraint(
        "audit_logs_id_created_at_key",
        "audit_logs",
        ["id", "created_at"],
    )
    op.drop_table("audit_log_changes")
