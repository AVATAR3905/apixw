"""anomaly_events table (Phase 4: IQR/z-score anomaly detection & alerting)

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4a5b6
Create Date: 2026-09-15 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create anomaly_events table for persisted anomaly hits and alerts."""
    op.create_table(
        "anomaly_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("series", sa.String(length=20), nullable=False, server_default="BASE_FARE"),
        sa.Column("series_type", sa.String(length=20), nullable=False, server_default="HEADLINE"),
        sa.Column("route_id", sa.Integer(), nullable=True),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("anomaly_type", sa.String(length=40), nullable=False, server_default="PRICE_OUTLIER"),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="LOW"),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("reference_median", sa.Float(), nullable=True),
        sa.Column("detected_value", sa.Float(), nullable=True),
        sa.Column("reference_values_sample", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("detected_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_anomaly_lookup", "anomaly_events", ["observation_date", "series", "status"]
    )


def downgrade() -> None:
    """Drop anomaly_events table."""
    op.drop_index("idx_anomaly_lookup", table_name="anomaly_events")
    op.drop_table("anomaly_events")
