"""index_values variance estimation columns (bootstrap SE + confidence interval)

Revision ID: e9f8a7b6c5d4
Revises: d3e4f5a6b7c8
Create Date: 2026-09-17 10:00:00.000000

Adds NSO-standard uncertainty quantification columns to the index_values table
so every published index point carries a standard error and a bootstrap
confidence interval estimated by resampling the elementary route-horizon cells.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9f8a7b6c5d4"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add variance-estimation columns to index_values."""
    op.add_column(
        "index_values",
        sa.Column("standard_error", sa.Float(), nullable=True),
    )
    op.add_column(
        "index_values",
        sa.Column("index_ci_lower", sa.Float(), nullable=True),
    )
    op.add_column(
        "index_values",
        sa.Column("index_ci_upper", sa.Float(), nullable=True),
    )
    op.add_column(
        "index_values",
        sa.Column("bootstrap_replications", sa.Integer(), nullable=True),
    )
    op.add_column(
        "index_values",
        sa.Column("variance_method", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    """Drop variance-estimation columns from index_values."""
    op.drop_column("index_values", "variance_method")
    op.drop_column("index_values", "bootstrap_replications")
    op.drop_column("index_values", "index_ci_upper")
    op.drop_column("index_values", "index_ci_lower")
    op.drop_column("index_values", "standard_error")
