"""add automated job discovery schema

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _indexes(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table)}


def upgrade() -> None:
    if "discovery_sources" not in _tables():
        op.create_table(
            "discovery_sources",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("company", sa.String(length=200), nullable=False),
            sa.Column("provider", sa.String(length=30), nullable=False),
            sa.Column("board_identifier", sa.String(length=250), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "board_identifier"),
        )
        op.create_index("ix_discovery_sources_provider", "discovery_sources", ["provider"], unique=False)
        op.create_index("ix_discovery_sources_enabled", "discovery_sources", ["enabled"], unique=False)

    if "discovery_runs" not in _tables():
        op.create_table(
            "discovery_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("postings_retrieved", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("title_candidates", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("jobs_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("jobs_updated", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("jobs_analyzed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("hard_filter_passed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("surfaced", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("postings_closed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["source_id"], ["discovery_sources.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_discovery_runs_source_id", "discovery_runs", ["source_id"], unique=False)
        op.create_index("ix_discovery_runs_status", "discovery_runs", ["status"], unique=False)

    job_cols = _columns("job_opportunities")
    if "work_arrangement" not in job_cols:
        op.add_column("job_opportunities", sa.Column("work_arrangement", sa.String(length=20), nullable=True))
    if "discovery_source_id" not in job_cols:
        op.add_column(
            "job_opportunities",
            sa.Column("discovery_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_job_opportunities_discovery_source",
            "job_opportunities",
            "discovery_sources",
            ["discovery_source_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "last_seen_at" not in job_cols:
        op.add_column(
            "job_opportunities",
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "posting_status" not in job_cols:
        op.add_column(
            "job_opportunities",
            sa.Column("posting_status", sa.String(length=20), nullable=False, server_default="open"),
        )

    indexes = _indexes("job_opportunities")
    if "ix_job_opportunities_work_arrangement" not in indexes:
        op.create_index("ix_job_opportunities_work_arrangement", "job_opportunities", ["work_arrangement"], unique=False)
    if "ix_job_opportunities_discovery_source_id" not in indexes:
        op.create_index(
            "ix_job_opportunities_discovery_source_id",
            "job_opportunities",
            ["discovery_source_id"],
            unique=False,
        )
    if "ix_job_opportunities_last_seen_at" not in indexes:
        op.create_index(
            "ix_job_opportunities_last_seen_at", "job_opportunities", ["last_seen_at"], unique=False
        )
    if "ix_job_opportunities_posting_status" not in indexes:
        op.create_index(
            "ix_job_opportunities_posting_status", "job_opportunities", ["posting_status"], unique=False
        )


def downgrade() -> None:
    indexes = _indexes("job_opportunities")
    for index in (
        "ix_job_opportunities_posting_status",
        "ix_job_opportunities_last_seen_at",
        "ix_job_opportunities_discovery_source_id",
        "ix_job_opportunities_work_arrangement",
    ):
        if index in indexes:
            op.drop_index(index, table_name="job_opportunities")

    job_cols = _columns("job_opportunities")
    if "posting_status" in job_cols:
        op.drop_column("job_opportunities", "posting_status")
    if "last_seen_at" in job_cols:
        op.drop_column("job_opportunities", "last_seen_at")
    if "work_arrangement" in job_cols:
        op.drop_column("job_opportunities", "work_arrangement")
    if "discovery_source_id" in job_cols:
        op.drop_constraint(
            "fk_job_opportunities_discovery_source", "job_opportunities", type_="foreignkey"
        )
        op.drop_column("job_opportunities", "discovery_source_id")

    if "discovery_runs" in _tables():
        op.drop_index("ix_discovery_runs_status", table_name="discovery_runs")
        op.drop_index("ix_discovery_runs_source_id", table_name="discovery_runs")
        op.drop_table("discovery_runs")
    if "discovery_sources" in _tables():
        op.drop_index("ix_discovery_sources_enabled", table_name="discovery_sources")
        op.drop_index("ix_discovery_sources_provider", table_name="discovery_sources")
        op.drop_table("discovery_sources")
