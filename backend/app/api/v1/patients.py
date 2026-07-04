from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Patient, User, Visit
from app.schemas.patient import PatientCreate, PatientDetailResponse, PatientResponse, PatientUpdate, VisitSummary
from app.services.patient_service import ensure_mrd_available

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientResponse])
def list_patients(
    q: str | None = None,
    search_type: str = Query("name", pattern="^(name|mrd|diagnosis)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Patient).filter(Patient.doctor_id == user.id)
    if q:
        if search_type == "name":
            query = query.filter(Patient.name.ilike(f"%{q}%"))
        elif search_type == "mrd":
            query = query.filter(Patient.mrd_number.ilike(f"%{q}%"))
        elif search_type == "diagnosis":
            patient_ids = (
                db.query(Visit.patient_id)
                .filter(Visit.diagnosis.ilike(f"%{q}%"))
                .distinct()
                .all()
            )
            ids = [pid[0] for pid in patient_ids]
            query = query.filter(Patient.id.in_(ids))
    return query.order_by(Patient.date_registered.desc()).all()


@router.post("", response_model=PatientResponse, status_code=201)
def create_patient(
    data: PatientCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = data.model_dump()
    payload["mrd_number"] = ensure_mrd_available(db, payload.get("mrd_number"))
    patient = Patient(**payload, doctor_id=user.id)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientDetailResponse)
def get_patient(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Patient not found")
    visits = (
        db.query(Visit)
        .filter_by(patient_id=patient_id)
        .order_by(Visit.visit_date.desc())
        .all()
    )
    return PatientDetailResponse(
        **{c.name: getattr(patient, c.name) for c in Patient.__table__.columns},
        visits=[VisitSummary.model_validate(v) for v in visits],
    )


@router.patch("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    data: PatientUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = db.get(Patient, patient_id)
    if not patient or patient.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Patient not found")
    updates = data.model_dump()
    if "mrd_number" in updates:
        updates["mrd_number"] = ensure_mrd_available(
            db, updates["mrd_number"], exclude_patient_id=patient_id,
        )
    for key, value in updates.items():
        setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
    return patient
