"""add commute-zone compensation policy metadata

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    policy_cols = _columns("targeting_policies")
    if "remote_minimum_base_salary_usd" not in policy_cols:
        op.add_column(
            "targeting_policies",
            sa.Column("remote_minimum_base_salary_usd", sa.Numeric(12, 2), nullable=True),
        )
    if "location_compensation_rules" not in policy_cols:
        op.add_column(
            "targeting_policies",
            sa.Column(
                "location_compensation_rules",
                postgresql.JSONB(),
                nullable=False,
                server_default="[]",
            ),
        )

    analysis_cols = _columns("job_analyses")
    if "location_context" not in analysis_cols:
        op.add_column(
            "job_analyses",
            sa.Column("location_context", postgresql.JSONB(), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    analysis_cols = _columns("job_analyses")
    if "location_context" in analysis_cols:
        op.drop_column("job_analyses", "location_context")

    policy_cols = _columns("targeting_policies")
    if "location_compensation_rules" in policy_cols:
        op.drop_column("targeting_policies", "location_compensation_rules")
    if "remote_minimum_base_salary_usd" in policy_cols:
        op.drop_column("targeting_policies", "remote_minimum_base_salary_usd")
