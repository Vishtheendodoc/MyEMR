from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models import ImagingResult, LabResult, Patient, User
from app.schemas.extended import ImagingResultCreate, ImagingResultResponse, LabResultCreate, LabResultResponse
from app.services.clinic_scope import clinic_id_of, ensure_patient_access
from app.services.observation_sync import remove_sourced_observations, sync_lab_observation
from app.services.timeline import build_patient_timeline

router = APIRouter(tags=["labs"])


def _check_patient(db: Session, patient_id: int, user: User) -> Patient:
    return ensure_patient_access(db, patient_id, user)


@router.get("/patients/{patient_id}/labs", response_model=list[LabResultResponse])
def list_labs(patient_id: int, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    return db.query(LabResult).filter_by(patient_id=patient_id).order_by(LabResult.result_date.desc()).all()


@router.post("/patients/{patient_id}/labs", response_model=LabResultResponse, status_code=201)
def add_lab(patient_id: int, data: LabResultCreate, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    lab = LabResult(patient_id=patient_id, **data.model_dump())
    if not lab.result_date:
        lab.result_date = date.today()
    db.add(lab)
    db.flush()
    sync_lab_observation(db, lab)
    db.commit()
    db.refresh(lab)
    return lab


@router.delete("/labs/{lab_id}", status_code=204)
def delete_lab(lab_id: int, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    lab = db.get(LabResult, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab result not found")
    _check_patient(db, lab.patient_id, user)
    remove_sourced_observations(db, "lab_result", lab.id)
    db.delete(lab)
    db.commit()


@router.get("/patients/{patient_id}/imaging", response_model=list[ImagingResultResponse])
def list_imaging(patient_id: int, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    return db.query(ImagingResult).filter_by(patient_id=patient_id).order_by(ImagingResult.report_date.desc()).all()


@router.post("/patients/{patient_id}/imaging", response_model=ImagingResultResponse, status_code=201)
def add_imaging(patient_id: int, data: ImagingResultCreate, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    img = ImagingResult(patient_id=patient_id, **data.model_dump())
    if not img.report_date:
        img.report_date = date.today()
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


@router.get("/patients/{patient_id}/timeline")
def patient_timeline(patient_id: int, user: User = Depends(require_role()), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    return build_patient_timeline(db, patient_id)


@router.get("/follow-ups")
def follow_up_queue(
    scope: str = "all",
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Organized follow-up queue. scope: overdue | today | upcoming | all"""
    from datetime import date as dt_date, timedelta
    from app.models import Visit

    from sqlalchemy.orm import joinedload

    today = dt_date.today()
    upcoming_end = today + timedelta(days=max(1, min(days, 180)))
    q = (
        db.query(Visit)
        .options(joinedload(Visit.patient))
        .join(Patient, Visit.patient_id == Patient.id)
        .filter(Patient.clinic_id == clinic_id_of(user), Visit.follow_up_date.isnot(None))
    )
    from app.services.clinic_scope import desk_doctor_id
    chosen = desk_doctor_id(user)
    if chosen:
        q = q.filter(or_(Patient.doctor_id == chosen, Patient.doctor_id.is_(None)))
    if scope == "overdue":
        q = q.filter(Visit.follow_up_date < today)
    elif scope == "today":
        q = q.filter(Visit.follow_up_date == today)
    elif scope == "upcoming":
        q = q.filter(Visit.follow_up_date > today, Visit.follow_up_date <= upcoming_end)
    else:
        q = q.filter(Visit.follow_up_date <= upcoming_end)

    from app.services.appointment_service import follow_up_calendar_outcome

    visits = q.order_by(Visit.follow_up_date.asc()).all()
    result = []
    for v in visits:
        if v.patient and (v.patient.registration_status or "") == "cancelled":
            continue
        delta = (v.follow_up_date - today).days
        outcome = follow_up_calendar_outcome(db, v)
        if outcome in {"cancelled", "done"} and scope in {"overdue", "today", "upcoming"}:
            continue
        if outcome:
            bucket = outcome
        elif delta < 0:
            bucket = "overdue"
        elif delta == 0:
            bucket = "today"
        else:
            bucket = "upcoming"
        result.append({
            "visit_id": v.id,
            "patient_id": v.patient_id,
            "patient_name": v.patient.name,
            "patient_mrd": v.patient.mrd_number,
            "patient_contact": v.patient.contact,
            "follow_up_date": v.follow_up_date.isoformat(),
            "follow_up_notes": v.follow_up_notes,
            "diagnosis": v.diagnosis if user.role in {"doctor", "nurse", "admin"} else None,
            "days_overdue": max(0, -delta),
            "days_until": max(0, delta),
            "bucket": bucket,
        })
    return result
