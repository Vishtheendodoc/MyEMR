"""Remove the patient recall tables

Revision ID: 006
Revises: 005
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    names = set(sa.inspect(op.get_bind()).get_table_names())
    for name in ("patient_care_plan", "monitoring_schedule"):
        if name in names:
            op.drop_table(name)


def downgrade() -> None:
    op.create_table(
        "monitoring_schedule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("condition_code", sa.String(40), nullable=False),
        sa.Column("monitoring_type", sa.String(80), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("condition_code", "monitoring_type", name="uq_monitoring_schedule"),
    )
    op.create_table(
        "patient_care_plan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("diagnosis_id", sa.Integer(), sa.ForeignKey("diagnosis_master.id")),
        sa.Column("condition_code", sa.String(40)),
        sa.Column("monitoring_type", sa.String(80), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("assigned_doctor", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("completion_status", sa.String(20), nullable=False),
        sa.Column("reminder_status", sa.String(20), nullable=False),
        sa.Column("interval_days", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
