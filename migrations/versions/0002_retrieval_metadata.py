"""add deterministic career evidence retrieval metadata

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table)}


def _indexes(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table)}


def upgrade() -> None:
    exp_cols = _columns("experiences")
    if "canonical_key" not in exp_cols:
        op.add_column("experiences", sa.Column("canonical_key", sa.String(length=200), nullable=True))
    if "verification_status" not in exp_cols:
        op.add_column("experiences", sa.Column("verification_status", sa.String(length=30), nullable=True))

    ev_cols = _columns("evidence_items")
    if "evidence_key" not in ev_cols:
        op.add_column("evidence_items", sa.Column("evidence_key", sa.String(length=80), nullable=True))
    if "verification_status" not in ev_cols:
        op.add_column("evidence_items", sa.Column("verification_status", sa.String(length=30), nullable=True))
    if "resume_eligible" not in ev_cols:
        op.add_column(
            "evidence_items",
            sa.Column("resume_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "resume_visibility" not in ev_cols:
        op.add_column("evidence_items", sa.Column("resume_visibility", sa.String(length=30), nullable=True))

    exp_indexes = _indexes("experiences")
    if "ix_experiences_canonical_key" not in exp_indexes:
        op.create_index("ix_experiences_canonical_key", "experiences", ["canonical_key"], unique=True)
    if "ix_experiences_verification_status" not in exp_indexes:
        op.create_index(
            "ix_experiences_verification_status", "experiences", ["verification_status"], unique=False
        )

    ev_indexes = _indexes("evidence_items")
    if "ix_evidence_items_evidence_key" not in ev_indexes:
        op.create_index("ix_evidence_items_evidence_key", "evidence_items", ["evidence_key"], unique=True)
    if "ix_evidence_items_verification_status" not in ev_indexes:
        op.create_index(
            "ix_evidence_items_verification_status",
            "evidence_items",
            ["verification_status"],
            unique=False,
        )
    if "ix_evidence_items_approval_status" not in ev_indexes:
        op.create_index(
            "ix_evidence_items_approval_status", "evidence_items", ["approval_status"], unique=False
        )
    if "ix_evidence_items_resume_eligible" not in ev_indexes:
        op.create_index(
            "ix_evidence_items_resume_eligible", "evidence_items", ["resume_eligible"], unique=False
        )
    if "ix_evidence_items_resume_visibility" not in ev_indexes:
        op.create_index(
            "ix_evidence_items_resume_visibility", "evidence_items", ["resume_visibility"], unique=False
        )


def downgrade() -> None:
    for name in (
        "ix_evidence_items_resume_visibility",
        "ix_evidence_items_resume_eligible",
        "ix_evidence_items_approval_status",
        "ix_evidence_items_verification_status",
        "ix_evidence_items_evidence_key",
    ):
        if name in _indexes("evidence_items"):
            op.drop_index(name, table_name="evidence_items")

    for column in ("resume_visibility", "resume_eligible", "verification_status", "evidence_key"):
        if column in _columns("evidence_items"):
            op.drop_column("evidence_items", column)

    for name in ("ix_experiences_verification_status", "ix_experiences_canonical_key"):
        if name in _indexes("experiences"):
            op.drop_index(name, table_name="experiences")

    for column in ("verification_status", "canonical_key"):
        if column in _columns("experiences"):
            op.drop_column("experiences", column)
