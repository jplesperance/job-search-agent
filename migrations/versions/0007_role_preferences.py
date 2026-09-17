"""add discovery role-preference policy fields

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    cols = _columns("targeting_policies")
    if "excluded_title_terms" not in cols:
        op.add_column(
            "targeting_policies",
            sa.Column(
                "excluded_title_terms",
                sa.ARRAY(sa.String(length=150)),
                nullable=False,
                server_default="{}",
            ),
        )
    if "exclude_software_engineering_roles" not in cols:
        op.add_column(
            "targeting_policies",
            sa.Column(
                "exclude_software_engineering_roles",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "exclude_heavy_coding_roles" not in cols:
        op.add_column(
            "targeting_policies",
            sa.Column(
                "exclude_heavy_coding_roles",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    cols = _columns("targeting_policies")
    if "exclude_heavy_coding_roles" in cols:
        op.drop_column("targeting_policies", "exclude_heavy_coding_roles")
    if "exclude_software_engineering_roles" in cols:
        op.drop_column("targeting_policies", "exclude_software_engineering_roles")
    if "excluded_title_terms" in cols:
        op.drop_column("targeting_policies", "excluded_title_terms")
