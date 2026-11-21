"""Clinical observation table and idempotent backfill

Revision ID: 003
Revises: 002
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "clinical_observation" not in inspector.get_table_names():
        op.create_table(
            "clinical_observation",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("patient_id", sa.Integer(), nullable=False),
            sa.Column("visit_id", sa.Integer(), nullable=True),
            sa.Column("observation_code", sa.String(length=80), nullable=False),
            sa.Column("observation_name", sa.String(length=200), nullable=False),
            sa.Column("value_numeric", sa.Float(), nullable=True),
            sa.Column("value_text", sa.String(length=100), nullable=False),
            sa.Column("unit", sa.String(length=50), nullable=True),
            sa.Column("reference_range_low", sa.Float(), nullable=True),
            sa.Column("reference_range_high", sa.Float(), nullable=True),
            sa.Column("reference_range", sa.String(length=100), nullable=True),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.Column("source", sa.String(length=40), nullable=False),
            sa.Column("source_record_type", sa.String(length=40), nullable=True),
            sa.Column("source_record_id", sa.Integer(), nullable=True),
            sa.Column("verification_status", sa.String(length=20), nullable=False),
            sa.Column("verified_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["patient_id"], ["patient.id"]),
            sa.ForeignKeyConstraint(["visit_id"], ["visit.id"]),
            sa.ForeignKeyConstraint(["verified_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "source_record_type",
                "source_record_id",
                "observation_code",
                name="uq_clinical_observation_source",
            ),
        )
        op.create_index("ix_clinical_observation_patient_id", "clinical_observation", ["patient_id"])
        op.create_index("ix_clinical_observation_observation_code", "clinical_observation", ["observation_code"])
        op.create_index("ix_clinical_observation_observed_at", "clinical_observation", ["observed_at"])

    from app.services.observation_sync import backfill_connection

    backfill_connection(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "clinical_observation" in inspector.get_table_names():
        op.drop_index("ix_clinical_observation_observed_at", table_name="clinical_observation")
        op.drop_index("ix_clinical_observation_observation_code", table_name="clinical_observation")
        op.drop_index("ix_clinical_observation_patient_id", table_name="clinical_observation")
        op.drop_table("clinical_observation")
