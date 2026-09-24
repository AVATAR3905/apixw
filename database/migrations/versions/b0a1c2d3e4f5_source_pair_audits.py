"""source-pair markup audit columns on discrepancy_audits (Phase 2)

Revision ID: b0a1c2d3e4f5
Revises: a1b2c3d4e5f6
Create Date: 2026-09-15 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0a1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add OTA source-pair markup audit columns to discrepancy_audits."""
    op.add_column(
        "discrepancy_audits",
        sa.Column("audit_type", sa.String(length=30), nullable=False, server_default="CROSS_FEED"),
    )
    op.add_column("discrepancy_audits", sa.Column("source_a_id", sa.Integer(), nullable=True))
    op.add_column("discrepancy_audits", sa.Column("source_b_id", sa.Integer(), nullable=True))
    op.add_column("discrepancy_audits", sa.Column("source_a_name", sa.String(length=100), nullable=True))
    op.add_column("discrepancy_audits", sa.Column("source_b_name", sa.String(length=100), nullable=True))
    op.add_column("discrepancy_audits", sa.Column("feed_type_a", sa.String(length=30), nullable=True))
    op.add_column("discrepancy_audits", sa.Column("feed_type_b", sa.String(length=30), nullable=True))
    op.add_column("discrepancy_audits", sa.Column("price_a", sa.Float(), nullable=True))
    op.add_column("discrepancy_audits", sa.Column("price_b", sa.Float(), nullable=True))
    op.add_column("discrepancy_audits", sa.Column("markup_amount", sa.Float(), nullable=True))
    op.add_column("discrepancy_audits", sa.Column("markup_pct", sa.Float(), nullable=True))
    op.create_index(
        "idx_audit_type_travel", "discrepancy_audits", ["audit_type", "travel_date"], unique=False
    )


def downgrade() -> None:
    """Drop OTA source-pair markup audit columns from discrepancy_audits."""
    op.drop_index("idx_audit_type_travel", table_name="discrepancy_audits")
    op.drop_column("discrepancy_audits", "markup_pct")
    op.drop_column("discrepancy_audits", "markup_amount")
    op.drop_column("discrepancy_audits", "price_b")
    op.drop_column("discrepancy_audits", "price_a")
    op.drop_column("discrepancy_audits", "feed_type_b")
    op.drop_column("discrepancy_audits", "feed_type_a")
    op.drop_column("discrepancy_audits", "source_b_name")
    op.drop_column("discrepancy_audits", "source_a_name")
    op.drop_column("discrepancy_audits", "source_b_id")
    op.drop_column("discrepancy_audits", "source_a_id")
    op.drop_column("discrepancy_audits", "audit_type")
