"""add deterministic job ingestion and matching schema

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if "content_hash" not in _columns("job_opportunities"):
        op.add_column("job_opportunities", sa.Column("content_hash", sa.String(length=64), nullable=True))
    if "ix_job_opportunities_content_hash" not in _indexes("job_opportunities"):
        op.create_index(
            "ix_job_opportunities_content_hash", "job_opportunities", ["content_hash"], unique=False
        )

    if "job_requirements" not in _tables():
        op.create_table(
            "job_requirements",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("requirement_type", sa.String(length=40), nullable=False),
            sa.Column("importance", sa.String(length=30), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column(
                "canonical_skills",
                postgresql.ARRAY(sa.String(length=150)),
                nullable=False,
                server_default="{}",
            ),
            sa.Column("minimum_years", sa.Integer(), nullable=True),
            sa.Column("source_section", sa.String(length=120), nullable=True),
            sa.Column("matched", sa.Boolean(), nullable=True),
            sa.ForeignKeyConstraint(["job_id"], ["job_opportunities.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("job_id", "ordinal"),
        )
        op.create_index("ix_job_requirements_job_id", "job_requirements", ["job_id"], unique=False)
        op.create_index(
            "ix_job_requirements_requirement_type",
            "job_requirements",
            ["requirement_type"],
            unique=False,
        )
        op.create_index(
            "ix_job_requirements_importance", "job_requirements", ["importance"], unique=False
        )

    analysis_cols = _columns("job_analyses")
    if "requirement_coverage" not in analysis_cols:
        op.add_column(
            "job_analyses",
            sa.Column("requirement_coverage", postgresql.JSONB(), nullable=False, server_default="[]"),
        )
    if "role_family" not in analysis_cols:
        op.add_column("job_analyses", sa.Column("role_family", sa.String(length=80), nullable=True))
    if "detected_seniority" not in analysis_cols:
        op.add_column(
            "job_analyses", sa.Column("detected_seniority", sa.String(length=40), nullable=True)
        )

    # v0.2 provisioned this array as varchar(36) because it originally held UUID strings.
    # v0.3 persists stable semantic evidence keys (e.g. TT-AISEC-001), so widen it.
    op.alter_column(
        "job_analyses",
        "matched_evidence_ids",
        existing_type=postgresql.ARRAY(sa.String(length=36)),
        type_=postgresql.ARRAY(sa.String(length=80)),
        existing_nullable=False,
    )


def downgrade() -> None:
    analysis_cols = _columns("job_analyses")
    for column in ("detected_seniority", "role_family", "requirement_coverage"):
        if column in analysis_cols:
            op.drop_column("job_analyses", column)
    op.alter_column(
        "job_analyses",
        "matched_evidence_ids",
        existing_type=postgresql.ARRAY(sa.String(length=80)),
        type_=postgresql.ARRAY(sa.String(length=36)),
        existing_nullable=False,
    )
    if "job_requirements" in _tables():
        op.drop_index("ix_job_requirements_importance", table_name="job_requirements")
        op.drop_index("ix_job_requirements_requirement_type", table_name="job_requirements")
        op.drop_index("ix_job_requirements_job_id", table_name="job_requirements")
        op.drop_table("job_requirements")
    if "ix_job_opportunities_content_hash" in _indexes("job_opportunities"):
        op.drop_index("ix_job_opportunities_content_hash", table_name="job_opportunities")
    if "content_hash" in _columns("job_opportunities"):
        op.drop_column("job_opportunities", "content_hash")
