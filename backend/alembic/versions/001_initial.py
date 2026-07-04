"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=150), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("display_name", sa.String(length=150), nullable=True),
        sa.Column("password", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("qualifications", sa.String(length=200), nullable=True),
        sa.Column("kmc_number", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    op.create_table(
        "comorbidity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "diagnosis_master",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("diagnosis_name", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("icd_code", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("diagnosis_name"),
    )

    op.create_table(
        "generic_drug",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generic_name", sa.String(length=200), nullable=False),
        sa.Column("drug_class", sa.String(length=100), nullable=True),
        sa.Column("indication", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("generic_name"),
    )
    op.create_index(op.f("ix_generic_drug_generic_name"), "generic_drug", ["generic_name"], unique=True)

    op.create_table(
        "patient",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mrd_number", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("age", sa.String(length=10), nullable=False),
        sa.Column("sex", sa.String(length=10), nullable=False),
        sa.Column("contact", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("date_registered", sa.DateTime(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mrd_number"),
    )

    op.create_table(
        "brand_medication",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand_name", sa.String(length=200), nullable=False),
        sa.Column("generic_drug_id", sa.Integer(), nullable=False),
        sa.Column("manufacturer", sa.String(length=200), nullable=True),
        sa.Column("strength", sa.String(length=100), nullable=True),
        sa.Column("formulation", sa.String(length=100), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["generic_drug_id"], ["generic_drug.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "drug_comorbidity_interaction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generic_drug_id", sa.Integer(), nullable=False),
        sa.Column("comorbidity_id", sa.Integer(), nullable=False),
        sa.Column("interaction_type", sa.String(length=50), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["comorbidity_id"], ["comorbidity.id"]),
        sa.ForeignKeyConstraint(["generic_drug_id"], ["generic_drug.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "visit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("visit_date", sa.DateTime(), nullable=False),
        sa.Column("visit_type", sa.String(length=50), nullable=False),
        sa.Column("chief_complaints", sa.Text(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("bmi", sa.Float(), nullable=True),
        sa.Column("bp_systolic", sa.Integer(), nullable=True),
        sa.Column("bp_diastolic", sa.Integer(), nullable=True),
        sa.Column("pulse", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("spo2", sa.Integer(), nullable=True),
        sa.Column("history", sa.Text(), nullable=True),
        sa.Column("examination", sa.Text(), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("investigation", sa.Text(), nullable=True),
        sa.Column("comorbidities", sa.Text(), nullable=True),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("follow_up_notes", sa.Text(), nullable=True),
        sa.Column("pdf_page_count", sa.Integer(), nullable=True),
        sa.Column("pdf_generated_at", sa.DateTime(), nullable=True),
        sa.Column("pdf_font_size", sa.Integer(), nullable=True),
        sa.Column("pdf_header_space", sa.Integer(), nullable=True),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "prescription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=False),
        sa.Column("brand_medication_id", sa.Integer(), nullable=False),
        sa.Column("custom_drug_name", sa.String(length=300), nullable=True),
        sa.Column("custom_generic_name", sa.String(length=200), nullable=True),
        sa.Column("dosage", sa.String(length=100), nullable=True),
        sa.Column("dose_morning", sa.String(length=50), nullable=True),
        sa.Column("dose_afternoon", sa.String(length=50), nullable=True),
        sa.Column("dose_evening", sa.String(length=50), nullable=True),
        sa.Column("frequency", sa.String(length=100), nullable=True),
        sa.Column("timing", sa.String(length=100), nullable=True),
        sa.Column("duration", sa.String(length=100), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("warnings", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["brand_medication_id"], ["brand_medication.id"]),
        sa.ForeignKeyConstraint(["visit_id"], ["visit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("prescription")
    op.drop_table("visit")
    op.drop_table("drug_comorbidity_interaction")
    op.drop_table("brand_medication")
    op.drop_table("patient")
    op.drop_index(op.f("ix_generic_drug_generic_name"), table_name="generic_drug")
    op.drop_table("generic_drug")
    op.drop_table("diagnosis_master")
    op.drop_table("comorbidity")
    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")
