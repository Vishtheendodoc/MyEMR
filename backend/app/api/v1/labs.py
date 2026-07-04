from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import ImagingResult, LabResult, Patient, User
from app.schemas.extended import ImagingResultCreate, ImagingResultResponse, LabResultCreate, LabResultResponse
from app.services.timeline import build_patient_timeline

router = APIRouter(tags=["labs"])


def _check_patient(db: Session, patient_id: int, user: User) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient or patient.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/patients/{patient_id}/labs", response_model=list[LabResultResponse])
def list_labs(patient_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    return db.query(LabResult).filter_by(patient_id=patient_id).order_by(LabResult.result_date.desc()).all()


@router.post("/patients/{patient_id}/labs", response_model=LabResultResponse, status_code=201)
def add_lab(patient_id: int, data: LabResultCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    lab = LabResult(patient_id=patient_id, **data.model_dump())
    if not lab.result_date:
        lab.result_date = date.today()
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return lab


@router.delete("/labs/{lab_id}", status_code=204)
def delete_lab(lab_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lab = db.get(LabResult, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab result not found")
    _check_patient(db, lab.patient_id, user)
    db.delete(lab)
    db.commit()


@router.get("/patients/{patient_id}/imaging", response_model=list[ImagingResultResponse])
def list_imaging(patient_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    return db.query(ImagingResult).filter_by(patient_id=patient_id).order_by(ImagingResult.report_date.desc()).all()


@router.post("/patients/{patient_id}/imaging", response_model=ImagingResultResponse, status_code=201)
def add_imaging(patient_id: int, data: ImagingResultCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    img = ImagingResult(patient_id=patient_id, **data.model_dump())
    if not img.report_date:
        img.report_date = date.today()
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


@router.get("/patients/{patient_id}/timeline")
def patient_timeline(patient_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _check_patient(db, patient_id, user)
    return build_patient_timeline(db, patient_id)


@router.get("/follow-ups")
def follow_up_queue(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import date as dt_date
    from app.models import Visit

    today = dt_date.today()
    visits = (
        db.query(Visit)
        .join(Patient)
        .filter(Visit.doctor_id == user.id, Visit.follow_up_date.isnot(None), Visit.follow_up_date <= today)
        .order_by(Visit.follow_up_date.asc())
        .all()
    )
    return [
        {
            "visit_id": v.id,
            "patient_id": v.patient_id,
            "patient_name": v.patient.name,
            "patient_mrd": v.patient.mrd_number,
            "follow_up_date": v.follow_up_date.isoformat(),
            "diagnosis": v.diagnosis,
            "days_overdue": (today - v.follow_up_date).days,
        }
        for v in visits
    ]
