"""track source health and delivery of failure/recovery alerts

Revision ID: 0009
Revises: 0008
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_source_health",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("incident_open", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("incident_started_at", sa.DateTime(timezone=True)),
        sa.Column("failure_alert_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recovery_alert_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_alert_at", sa.DateTime(timezone=True)),
        sa.Column("last_alert_error", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["discovery_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id"),
    )


def downgrade() -> None:
    op.drop_table("discovery_source_health")
