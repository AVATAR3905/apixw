"""source_correlations table (Phase 5: multi-OTA ensemble correlation tracking)

Revision ID: c1d2e3f4a5b6
Revises: b0a1c2d3e4f5
Create Date: 2026-09-15 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b0a1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create source_correlations table for rolling feed-cohort correlation tracking."""
    op.create_table(
        "source_correlations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=True),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("correlation_type", sa.String(length=40), nullable=False, server_default="OTA_VS_CARRIER_DIRECT"),
        sa.Column("source_a", sa.String(length=100), nullable=False),
        sa.Column("source_b", sa.String(length=100), nullable=False),
        sa.Column("pearson_r", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_corr_lookup", "source_correlations", ["correlation_type", "period_end", "route_id"]
    )


def downgrade() -> None:
    """Drop source_correlations table."""
    op.drop_index("idx_corr_lookup", table_name="source_correlations")
    op.drop_table("source_correlations")
