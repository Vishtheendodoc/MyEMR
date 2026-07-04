"""Phase 2-5 tables and columns

Revision ID: 002
Revises: 001
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patient", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("visit", sa.Column("specialty_template", sa.String(length=50), nullable=True))
    op.add_column("visit", sa.Column("specialty_data", sa.Text(), nullable=True))

    op.create_table(
        "lab_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("test_name", sa.String(length=200), nullable=False),
        sa.Column("value", sa.String(length=100), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("reference_range", sa.String(length=100), nullable=True),
        sa.Column("result_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["visit_id"], ["visit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "imaging_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=True),
        sa.Column("study_type", sa.String(length=200), nullable=False),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("attachment_path", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["visit_id"], ["visit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cgm_reading",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("reading_time", sa.DateTime(), nullable=False),
        sa.Column("glucose_mg_dl", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "appointment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "bill",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("procedure_code", sa.String(length=50), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("payment_status", sa.String(length=50), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.ForeignKeyConstraint(["visit_id"], ["visit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("bill")
    op.drop_table("appointment")
    op.drop_table("cgm_reading")
    op.drop_table("imaging_result")
    op.drop_table("lab_result")
    op.drop_column("visit", "specialty_data")
    op.drop_column("visit", "specialty_template")
    op.drop_column("patient", "date_of_birth")
