"""Remove the research export tables

Revision ID: 007
Revises: 006
Create Date: 2026-11-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    names = set(sa.inspect(op.get_bind()).get_table_names())
    for name in ("research_consent", "research_subject", "research_ethics"):
        if name in names:
            op.drop_table(name)


def downgrade() -> None:
    op.create_table(
        "research_ethics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("protocol_title", sa.String(300), nullable=False),
        sa.Column("approval_reference", sa.String(100)),
        sa.Column("approved_on", sa.Date()),
        sa.Column("expires_on", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "research_consent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False),
        sa.Column("ethics_id", sa.Integer(), sa.ForeignKey("research_ethics.id")),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "research_subject",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False, unique=True),
        sa.Column("subject_code", sa.String(32), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime()),
    )
