"""Visit draft / lock helpers."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Prescription, Visit
from app.services.specialty_templates import build_prescription_investigations


def ensure_visit_editable(visit: Visit):
    if visit.status == "locked":
        raise HTTPException(
            status_code=403,
            detail="This visit is finalized and locked. No further changes allowed.",
        )


def can_finalize_visit(db: Session, visit: Visit) -> bool:
    """Visits may be finalized with prescriptions and/or investigations (meds optional)."""
    if db.query(Prescription).filter_by(visit_id=visit.id).count() > 0:
        return True
    if build_prescription_investigations(visit):
        return True
    if visit.follow_up_date:
        return True
    if (visit.follow_up_notes or "").strip():
        return True
    return False


def finalize_visit_error() -> str:
    return (
        "Add prescriptions, current investigations, or follow-up details before finalizing"
    )


def apply_visit_fields(visit: Visit, data, *, autosave: bool = False):
    """Apply VisitCreate/VisitUpdate fields onto a Visit model."""
    import json

    visit.visit_type = data.visit_type
    visit.chief_complaints = data.chief_complaints
    visit.height = data.height
    visit.weight = data.weight
    visit.mid_parental_height = data.mid_parental_height
    if data.height and data.weight:
        height_m = data.height / 100
        visit.bmi = round(data.weight / (height_m ** 2), 2)
    else:
        visit.bmi = None
    visit.bp_systolic = data.bp_systolic
    visit.bp_diastolic = data.bp_diastolic
    visit.pulse = data.pulse
    visit.temperature = data.temperature
    visit.spo2 = data.spo2
    visit.history = data.history
    visit.examination = data.examination
    visit.diagnosis = data.diagnosis
    visit.investigation = data.investigation
    visit.comorbidities = data.comorbidities
    visit.follow_up_date = data.follow_up_date
    visit.follow_up_notes = data.follow_up_notes
    visit.specialty_template = data.specialty_template
    visit.specialty_data = json.dumps(data.specialty_data) if data.specialty_data else None
    visit.prevent_data = json.dumps(data.prevent_data) if data.prevent_data else None
    if autosave or visit.status == "draft":
        visit.draft_updated_at = datetime.utcnow()
