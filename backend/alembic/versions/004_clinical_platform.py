"""Clinical intelligence, follow-up, safety, assistant, research, and sessions

Revision ID: 004
Revises: 003
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _missing(name: str) -> bool:
    return name not in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _missing("clinical_rule"):
        op.create_table(
            "clinical_rule",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("version", sa.String(20), nullable=False),
            sa.Column("domain", sa.String(40), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("guideline_reference", sa.String(200), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("recommended_review", sa.Text(), nullable=False),
            sa.Column("observation_code", sa.String(80)),
            sa.Column("direction", sa.String(20), nullable=False),
            sa.Column("threshold_low", sa.Float()),
            sa.Column("threshold_high", sa.Float()),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("code"),
        )
    if _missing("clinical_alert"):
        op.create_table(
            "clinical_alert",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False),
            sa.Column("clinic_id", sa.Integer(), nullable=False),
            sa.Column("rule_code", sa.String(80), nullable=False),
            sa.Column("rule_version", sa.String(20), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("triggering_parameters", sa.Text()),
            sa.Column("previous_values", sa.Text()),
            sa.Column("recommended_review", sa.Text(), nullable=False),
            sa.Column("guideline_reference", sa.String(200), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("override_reason", sa.Text()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("acted_at", sa.DateTime()),
            sa.Column("acted_by", sa.Integer(), sa.ForeignKey("user.id")),
        )
        op.create_index("ix_clinical_alert_patient_id", "clinical_alert", ["patient_id"])
        op.create_index("ix_clinical_alert_rule_code", "clinical_alert", ["rule_code"])
        op.create_index("ix_clinical_alert_status", "clinical_alert", ["status"])
    if _missing("monitoring_schedule"):
        op.create_table(
            "monitoring_schedule",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("condition_code", sa.String(40), nullable=False),
            sa.Column("monitoring_type", sa.String(80), nullable=False),
            sa.Column("interval_days", sa.Integer(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("notes", sa.Text()),
            sa.UniqueConstraint("condition_code", "monitoring_type", name="uq_monitoring_schedule"),
        )
    if _missing("patient_care_plan"):
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
        op.create_index("ix_patient_care_plan_patient_id", "patient_care_plan", ["patient_id"])
        op.create_index("ix_patient_care_plan_target_date", "patient_care_plan", ["target_date"])
    if _missing("drug_pair_interaction"):
        op.create_table(
            "drug_pair_interaction",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("generic_a", sa.String(200), nullable=False),
            sa.Column("generic_b", sa.String(200), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("recommendation", sa.Text(), nullable=False),
            sa.UniqueConstraint("generic_a", "generic_b", name="uq_drug_pair"),
        )
    if _missing("substitution_request"):
        op.create_table(
            "substitution_request",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False),
            sa.Column("prescription_id", sa.Integer(), sa.ForeignKey("prescription.id"), nullable=False),
            sa.Column("current_label", sa.String(300), nullable=False),
            sa.Column("requested_brand", sa.String(300), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("reason", sa.Text()),
            sa.Column("requested_by", sa.Integer(), sa.ForeignKey("user.id")),
            sa.Column("decided_by", sa.Integer(), sa.ForeignKey("user.id")),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("decided_at", sa.DateTime()),
        )
        op.create_index("ix_substitution_request_patient_id", "substitution_request", ["patient_id"])
    if _missing("ai_consent"):
        op.create_table(
            "ai_consent",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False),
            sa.Column("purpose", sa.String(40), nullable=False),
            sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("user.id")),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_ai_consent_patient_id", "ai_consent", ["patient_id"])
    if _missing("ai_request_log"):
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
    if _missing("ai_draft"):
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
        op.create_index("ix_ai_draft_patient_id", "ai_draft", ["patient_id"])
    if _missing("research_ethics"):
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
    if _missing("research_consent"):
        op.create_table(
            "research_consent",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False),
            sa.Column("ethics_id", sa.Integer(), sa.ForeignKey("research_ethics.id")),
            sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("user.id")),
            sa.Column("created_at", sa.DateTime()),
        )
    if _missing("research_subject"):
        op.create_table(
            "research_subject",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patient.id"), nullable=False),
            sa.Column("subject_code", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("patient_id"),
            sa.UniqueConstraint("subject_code"),
        )
    if _missing("refresh_session"):
        op.create_table(
            "refresh_session",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("jti", sa.String(64), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("replaced_by", sa.String(64)),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("jti"),
        )
        op.create_index("ix_refresh_session_user_id", "refresh_session", ["user_id"])
    from app.services.platform_seed import seed_connection

    seed_connection(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    names = set(sa.inspect(bind).get_table_names())
    for name in (
        "refresh_session",
        "research_subject",
        "research_consent",
        "research_ethics",
        "ai_draft",
        "ai_request_log",
        "ai_consent",
        "substitution_request",
        "drug_pair_interaction",
        "patient_care_plan",
        "monitoring_schedule",
        "clinical_alert",
        "clinical_rule",
    ):
        if name in names:
            op.drop_table(name)
