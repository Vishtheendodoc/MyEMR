from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models import ClinicalObservation, User
from app.schemas.observation import ObservationCreate, ObservationResponse
from app.services.audit import write_audit
from app.services.clinic_scope import ensure_patient_access, ensure_visit_access
from app.services.observation_sync import sync_patient_observations
from app.services.patient_360 import parse_numeric

router = APIRouter(tags=["observations"])


def _list_rows(db: Session, patient_id: int) -> list[ClinicalObservation]:
    return (
        db.query(ClinicalObservation)
        .filter_by(patient_id=patient_id)
        .order_by(ClinicalObservation.observed_at.desc(), ClinicalObservation.id.desc())
        .all()
    )


@router.get("/patients/{patient_id}/observations", response_model=list[ObservationResponse])
def list_observations(
    patient_id: int,
    user: User = Depends(require_role()),
    db: Session = Depends(get_db),
):
    """Doctor-only. Reconciles labs, CGM, and visit vitals before listing."""
    ensure_patient_access(db, patient_id, user)
    sync_patient_observations(db, patient_id)
    db.commit()
    return _list_rows(db, patient_id)


@router.post("/patients/{patient_id}/observations", response_model=ObservationResponse, status_code=201)
def create_observation(
    patient_id: int,
    data: ObservationCreate,
    user: User = Depends(require_role()),
    db: Session = Depends(get_db),
):
    ensure_patient_access(db, patient_id, user)
    if data.visit_id is not None:
        visit = ensure_visit_access(db, data.visit_id, user)
        if visit.patient_id != patient_id:
            raise HTTPException(status_code=400, detail="Visit does not belong to this patient")
    pending = data.source in {"imported", "laboratory_report"}
    row = ClinicalObservation(
        patient_id=patient_id,
        visit_id=data.visit_id,
        observation_code=data.observation_code,
        observation_name=data.observation_name.strip(),
        value_text=data.value_text.strip(),
        value_numeric=data.value_numeric if data.value_numeric is not None else parse_numeric(data.value_text),
        unit=(data.unit or None),
        reference_range_low=data.reference_range_low,
        reference_range_high=data.reference_range_high,
        reference_range=(data.reference_range or None),
        observed_at=data.observed_at,
        source=data.source,
        source_record_type=None,
        source_record_id=None,
        verification_status="pending" if pending else "verified",
        verified_by=None if pending else user.id,
    )
    db.add(row)
    db.flush()
    vital_codes = {
        "height", "weight", "bmi", "bp_systolic", "bp_diastolic",
        "pulse", "temperature", "spo2", "cgm_glucose",
    }
    if row.observation_code not in vital_codes:
        from app.models import LabResult

        lab = LabResult(
            patient_id=patient_id,
            visit_id=row.visit_id,
            test_name=row.observation_name.strip(),
            value=row.value_text.strip(),
            unit=row.unit,
            reference_range=row.reference_range,
            result_date=row.observed_at.date(),
            notes="From observation",
        )
        db.add(lab)
        db.flush()
        row.source_record_type = "lab_result"
        row.source_record_id = lab.id
    write_audit(
        db,
        user_id=user.id,
        action="observation.create",
        entity_type="clinical_observation",
        entity_id=row.id,
        details=f"{row.source}:{row.observation_code}",
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/observations/{observation_id}/verify", response_model=ObservationResponse)
def verify_observation(
    observation_id: int,
    user: User = Depends(require_role()),
    db: Session = Depends(get_db),
):
    row = db.get(ClinicalObservation, observation_id)
    if not row:
        raise HTTPException(status_code=404, detail="Observation not found")
    ensure_patient_access(db, row.patient_id, user)
    if row.verification_status == "verified":
        return row
    row.verification_status = "verified"
    row.verified_by = user.id
    write_audit(
        db,
        user_id=user.id,
        action="observation.verify",
        entity_type="clinical_observation",
        entity_id=row.id,
        details=row.observation_code,
    )
    db.commit()
    db.refresh(row)
    return row
