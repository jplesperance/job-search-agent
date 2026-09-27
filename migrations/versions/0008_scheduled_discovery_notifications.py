"""add canonical source postings and notification state

Revision ID: 0008
Revises: 0007
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if "job_source_postings" not in _tables():
        op.create_table(
            "job_source_postings",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("discovery_source_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("source", sa.String(length=120), nullable=False),
            sa.Column("external_id", sa.String(length=300), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=True),
            sa.Column("normalized_source_url", sa.Text(), nullable=True),
            sa.Column("normalized_company", sa.String(length=200), nullable=False, server_default=""),
            sa.Column("normalized_title", sa.String(length=250), nullable=False, server_default=""),
            sa.Column("normalized_location", sa.String(length=250), nullable=False, server_default=""),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.Column("posting_status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["job_opportunities.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["discovery_source_id"], ["discovery_sources.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source", "external_id", name="uq_job_source_postings_source_external"),
        )
        op.create_index("ix_job_source_postings_job_id", "job_source_postings", ["job_id"], unique=False)
        op.create_index("ix_job_source_postings_discovery_source_id", "job_source_postings", ["discovery_source_id"], unique=False)
        op.create_index("ix_job_source_postings_normalized_source_url", "job_source_postings", ["normalized_source_url"], unique=False)
        op.create_index("ix_job_source_postings_identity", "job_source_postings", ["normalized_company", "normalized_title", "normalized_location"], unique=False)
        op.create_index("ix_job_source_postings_posting_status", "job_source_postings", ["posting_status"], unique=False)

        # Preserve existing discovered postings without requiring a UUID extension.
        op.execute(sa.text("""
            INSERT INTO job_source_postings (
                id, job_id, discovery_source_id, source, external_id, source_url,
                normalized_company, normalized_title, normalized_location,
                content_hash, posting_status, first_seen_at, last_seen_at
            )
            SELECT
                id, id, discovery_source_id, source, external_id, source_url,
                '', '', '', content_hash, posting_status, discovered_at,
                COALESCE(last_seen_at, discovered_at)
            FROM job_opportunities
            WHERE external_id IS NOT NULL
            ON CONFLICT (source, external_id) DO NOTHING
        """))

    if "notification_states" not in _tables():
        op.create_table(
            "notification_states",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("discovery_run_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("channel", sa.String(length=40), nullable=False),
            sa.Column("notification_type", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("provider_message_id", sa.String(length=250), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("payload_hash", sa.String(length=64), nullable=True),
            sa.ForeignKeyConstraint(["job_id"], ["job_opportunities.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["discovery_run_id"], ["discovery_runs.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("job_id", "channel", "notification_type", name="uq_notification_states_job_channel_type"),
        )
        op.create_index("ix_notification_states_job_id", "notification_states", ["job_id"], unique=False)
        op.create_index("ix_notification_states_status", "notification_states", ["status"], unique=False)


def downgrade() -> None:
    tables = _tables()
    if "notification_states" in tables:
        op.drop_index("ix_notification_states_status", table_name="notification_states")
        op.drop_index("ix_notification_states_job_id", table_name="notification_states")
        op.drop_table("notification_states")
    if "job_source_postings" in tables:
        op.drop_index("ix_job_source_postings_posting_status", table_name="job_source_postings")
        op.drop_index("ix_job_source_postings_identity", table_name="job_source_postings")
        op.drop_index("ix_job_source_postings_normalized_source_url", table_name="job_source_postings")
        op.drop_index("ix_job_source_postings_discovery_source_id", table_name="job_source_postings")
        op.drop_index("ix_job_source_postings_job_id", table_name="job_source_postings")
        op.drop_table("job_source_postings")
