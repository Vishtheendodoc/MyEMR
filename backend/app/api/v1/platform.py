"""Doctor-only clinical intelligence, safety, and interop routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models import (
    ClinicalAlert,
    Prescription,
    SubstitutionRequest,
    User,
    Visit,
)
from app.services.audit import write_audit
from app.services.clinic_scope import ensure_patient_access
from app.services.intelligence import refresh_alerts
from app.services.medication_safety import decide_substitution, medication_safety, request_substitution
from app.services.platform_seed import seed_platform

router = APIRouter(tags=["clinical-platform"])


class DismissRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SubstitutionCreate(BaseModel):
    prescription_id: int
    requested_brand: str = Field(min_length=2, max_length=300)
    reason: str | None = None


def _ensure_seed(db: Session) -> None:
    seed_platform(db)


def _alert_dict(row: ClinicalAlert) -> dict:
    return {
        "id": row.id,
        "patient_id": row.patient_id,
        "rule_code": row.rule_code,
        "rule_version": row.rule_version,
        "title": row.title,
        "explanation": row.explanation,
        "triggering_parameters": row.triggering_parameters,
        "previous_values": row.previous_values,
        "recommended_review": row.recommended_review,
        "guideline_reference": row.guideline_reference,
        "severity": row.severity,
        "status": row.status,
        "override_reason": row.override_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "acted_at": row.acted_at.isoformat() if row.acted_at else None,
    }


@router.get("/patients/{patient_id}/intelligence")
def patient_intelligence(patient_id: int, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    _ensure_seed(db)
    patient = ensure_patient_access(db, patient_id, user)
    rows = refresh_alerts(db, patient)
    db.commit()
    return {"patient_id": patient_id, "alerts": [_alert_dict(row) for row in rows]}


def _open_alert(db: Session, alert_id: int, user: User) -> ClinicalAlert:
    row = db.get(ClinicalAlert, alert_id)
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    ensure_patient_access(db, row.patient_id, user)
    if row.status != "open":
        raise HTTPException(status_code=400, detail="This alert is already closed")
    return row


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    row = _open_alert(db, alert_id, user)
    row.status = "acknowledged"
    row.acted_by = user.id
    row.acted_at = datetime.utcnow()
    row.updated_at = row.acted_at
    write_audit(db, user_id=user.id, action="alert.acknowledge", entity_type="clinical_alert", entity_id=row.id, details=row.rule_code)
    db.commit()
    return _alert_dict(row)


@router.post("/alerts/{alert_id}/dismiss")
def dismiss_alert(alert_id: int, payload: DismissRequest, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    row = _open_alert(db, alert_id, user)
    row.status = "dismissed"
    row.override_reason = payload.reason.strip()
    row.acted_by = user.id
    row.acted_at = datetime.utcnow()
    row.updated_at = row.acted_at
    write_audit(db, user_id=user.id, action="alert.dismiss", entity_type="clinical_alert", entity_id=row.id, details=row.override_reason)
    db.commit()
    return _alert_dict(row)


@router.get("/patients/{patient_id}/medication-safety")
def patient_medication_safety(patient_id: int, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    _ensure_seed(db)
    patient = ensure_patient_access(db, patient_id, user)
    return medication_safety(db, patient.id, patient.allergies)


@router.post("/patients/{patient_id}/substitutions", status_code=201)
def create_substitution(patient_id: int, payload: SubstitutionCreate, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    patient = ensure_patient_access(db, patient_id, user)
    prescription = db.get(Prescription, payload.prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    visit = db.get(Visit, prescription.visit_id)
    if not visit or visit.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Prescription not found")
    row = request_substitution(
        db,
        patient_id=patient.id,
        prescription=prescription,
        requested_brand=payload.requested_brand,
        reason=payload.reason,
        user_id=user.id,
    )
    write_audit(db, user_id=user.id, action="substitution.request", entity_type="substitution_request", entity_id=row.id)
    db.commit()
    return {"id": row.id, "status": row.status, "prescription_id": prescription.id, "brand_medication_id": prescription.brand_medication_id}


@router.post("/substitutions/{request_id}/approve")
def approve_substitution(request_id: int, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    row = db.get(SubstitutionRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Substitution request not found")
    ensure_patient_access(db, row.patient_id, user)
    prescription = db.get(Prescription, row.prescription_id)
    before = prescription.brand_medication_id if prescription else None
    decide_substitution(db, row, "approved", user.id)
    write_audit(
        db,
        user_id=user.id,
        action="substitution.approve",
        entity_type="substitution_request",
        entity_id=row.id,
        details="Prescription medicine was not changed",
    )
    db.commit()
    db.refresh(prescription)
    return {
        "id": row.id,
        "status": row.status,
        "brand_medication_id": prescription.brand_medication_id if prescription else None,
        "unchanged": prescription.brand_medication_id == before if prescription else True,
    }


@router.get("/interop/status")
def interop_status(user: User = Depends(require_role())):
    return {
        "abdm_abha": {"configured": False, "note": "No ABDM gateway is configured. This is not an ABHA integration."},
        "fhir_r4": {"partial_patient_read": True, "certified": False, "note": "One local Patient read exists for the signed-in doctor. It is not a certified FHIR server."},
        "snomed_ct": {"configured": False},
        "loinc": {"configured": False},
        "clinical_documents": {"configured": False},
    }


@router.get("/fhir/Patient/{patient_id}")
def fhir_patient(patient_id: int, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    patient = ensure_patient_access(db, patient_id, user)
    gender = {"male": "male", "female": "female"}.get((patient.sex or "").lower(), "unknown")
    return {
        "resourceType": "Patient",
        "id": str(patient.id),
        "meta": {"tag": [{"system": "urn:endo-emr:local", "code": "partial-export", "display": "Not a certified FHIR, ABDM, SNOMED, or LOINC interface"}]},
        "name": [{"text": patient.name}],
        "gender": gender,
        "text": {
            "status": "additional",
            "div": "Partial local export for the treating clinic. Not a certified interoperability endpoint.",
        },
    }


@router.get("/admin/reliability")
def reliability(user: User = Depends(require_role())):
    return {
        "refresh_tokens": "Rotated on refresh and revoked on logout.",
        "login_rate_limit": "30 attempts per email per minute in this API process.",
        "backup": "For SQLite, copy the database file with scripts/backup_sqlite.py while the API is stopped. PostgreSQL backups belong to the database host.",
        "restore_check": "A test copies a SQLite file away and back and reads a stored row.",
        "monitoring": "Failed requests are written to the API log. There is no external uptime monitor in this installation.",
    }
