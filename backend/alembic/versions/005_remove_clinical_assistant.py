"""Remove the clinical assistant tables

Revision ID: 005
Revises: 004
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    names = set(sa.inspect(op.get_bind()).get_table_names())
    for name in ("ai_draft", "ai_request_log", "ai_consent"):
        if name in names:
            op.drop_table(name)


def downgrade() -> None:
    op.create_table(
        "ai_consent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "ai_request_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id")),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "ai_draft",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False),
        sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visit.id")),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("approved_at", sa.DateTime()),
    )
