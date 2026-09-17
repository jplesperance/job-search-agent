"""improve JD interpretation metadata

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    req_cols = _columns("job_requirements")
    if "requirement_kind" not in req_cols:
        op.add_column(
            "job_requirements",
            sa.Column("requirement_kind", sa.String(40), nullable=False, server_default="skill"),
        )
    if "skill_match_mode" not in req_cols:
        op.add_column(
            "job_requirements",
            sa.Column("skill_match_mode", sa.String(10), nullable=False, server_default="all"),
        )

    analysis_cols = _columns("job_analyses")
    if "confidence_context" not in analysis_cols:
        op.add_column(
            "job_analyses",
            sa.Column("confidence_context", postgresql.JSONB(), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    analysis_cols = _columns("job_analyses")
    if "confidence_context" in analysis_cols:
        op.drop_column("job_analyses", "confidence_context")

    req_cols = _columns("job_requirements")
    if "skill_match_mode" in req_cols:
        op.drop_column("job_requirements", "skill_match_mode")
    if "requirement_kind" in req_cols:
        op.drop_column("job_requirements", "requirement_kind")
