"""dgca_monthly_fares table (Phase 3: official DGCA benchmark)

Revision ID: a1b2c3d4e5f6
Revises: fdf05b42557c
Create Date: 2026-09-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "fdf05b42557c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add DGCA monthly sector average-fare table + index_values.series_type column."""
    op.add_column(
        "index_values",
        sa.Column("series_type", sa.String(length=20), nullable=True, server_default="HEADLINE"),
    )
    op.create_index(
        "ix_index_values_series_type", "index_values", ["series_type"], unique=False
    )

    op.create_table(
        "dgca_monthly_fares",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False),
        sa.Column("sector_type", sa.String(length=20), nullable=True),
        sa.Column("average_fare", sa.Float(), nullable=False),
        sa.Column("total_passengers", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("source_version", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dgca_monthly_fares_period"), "dgca_monthly_fares", ["period"], unique=False
    )
    op.create_index(
        "idx_dgca_fare_lookup", "dgca_monthly_fares", ["route_id", "period", "sector_type"]
    )


def downgrade() -> None:
    """Drop DGCA monthly sector average-fare table + index_values.series_type column."""
    op.drop_index("ix_index_values_series_type", table_name="index_values")
    op.drop_column("index_values", "series_type")

    op.drop_index("idx_dgca_fare_lookup", table_name="dgca_monthly_fares")
    op.drop_index(op.f("ix_dgca_monthly_fares_period"), table_name="dgca_monthly_fares")
    op.drop_table("dgca_monthly_fares")
