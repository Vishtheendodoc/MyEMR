from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Appointment, Bill, Patient, Visit
from app.schemas.extended import AppointmentCreate, AppointmentResponse, BillCreate, BillResponse
from app.services.appointment_service import appointment_counts_by_month

router = APIRouter(tags=["operations"])


@router.get("/appointments/calendar")
def appointments_calendar(
    year: int,
    month: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1–12")
    return appointment_counts_by_month(db, user.id, year, month)


@router.get("/appointments", response_model=list[AppointmentResponse])
def list_appointments(user=Depends(get_current_user), db: Session = Depends(get_db)):
    appts = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient))
        .filter_by(doctor_id=user.id)
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )
    return [
        AppointmentResponse(
            **{c.name: getattr(a, c.name) for c in Appointment.__table__.columns},
            patient_name=a.patient.name,
        )
        for a in appts
    ]


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
def create_appointment(data: AppointmentCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    patient = db.get(Patient, data.patient_id)
    if not patient or patient.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Patient not found")
    appt = Appointment(doctor_id=user.id, **data.model_dump())
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return AppointmentResponse(**{c.name: getattr(appt, c.name) for c in Appointment.__table__.columns}, patient_name=patient.name)


@router.patch("/appointments/{appt_id}/status")
def update_appointment_status(appt_id: int, status: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    appt = db.get(Appointment, appt_id)
    if not appt or appt.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appt.status = status
    db.commit()
    return {"success": True}


@router.get("/bills", response_model=list[BillResponse])
def list_bills(user=Depends(get_current_user), db: Session = Depends(get_db)):
    bills = (
        db.query(Bill)
        .options(joinedload(Bill.visit))
        .filter_by(doctor_id=user.id)
        .order_by(Bill.created_at.desc())
        .all()
    )
    result = []
    for b in bills:
        patient = db.get(Patient, b.patient_id)
        result.append(BillResponse(
            **{c.name: getattr(b, c.name) for c in Bill.__table__.columns},
            patient_name=patient.name if patient else None,
        ))
    return result


@router.post("/bills", response_model=BillResponse, status_code=201)
def create_bill(data: BillCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    visit = db.get(Visit, data.visit_id)
    if not visit or visit.doctor_id != user.id:
        raise HTTPException(status_code=404, detail="Visit not found")
    bill = Bill(
        visit_id=data.visit_id,
        patient_id=visit.patient_id,
        doctor_id=user.id,
        description=data.description,
        amount=data.amount,
        procedure_code=data.procedure_code,
        payment_status=data.payment_status,
        payment_method=data.payment_method,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    patient = db.get(Patient, visit.patient_id)
    return BillResponse(**{c.name: getattr(bill, c.name) for c in Bill.__table__.columns}, patient_name=patient.name if patient else None)


@router.get("/analytics")
def analytics(user=Depends(get_current_user), db: Session = Depends(get_db)):
    from collections import Counter
    from sqlalchemy import func, extract
    from app.models import Prescription

    visits = db.query(Visit).filter_by(doctor_id=user.id).all()
    diag_counter = Counter()
    for v in visits:
        if v.diagnosis:
            diag_counter[v.diagnosis.split(",")[0].strip()] += 1

    monthly = (
        db.query(extract("month", Visit.visit_date).label("month"), func.count(Visit.id))
        .filter(Visit.doctor_id == user.id)
        .group_by("month")
        .all()
    )

    rx_counts = (
        db.query(Prescription.brand_medication_id, func.count(Prescription.id))
        .join(Visit)
        .filter(Visit.doctor_id == user.id)
        .group_by(Prescription.brand_medication_id)
        .order_by(func.count(Prescription.id).desc())
        .limit(10)
        .all()
    )
    from app.models import BrandMedication
    top_meds = []
    for brand_id, count in rx_counts:
        brand = db.get(BrandMedication, brand_id)
        top_meds.append({"drug": brand.brand_name if brand else str(brand_id), "count": count})

    bills = db.query(Bill).filter_by(doctor_id=user.id).all()
    total = sum(b.amount for b in bills)
    paid = sum(b.amount for b in bills if b.payment_status == "paid")

    return {
        "diagnosis_distribution": [{"diagnosis": k, "count": v} for k, v in diag_counter.most_common(10)],
        "visit_volume_by_month": [{"month": int(m), "count": c} for m, c in monthly],
        "top_medications": top_meds,
        "revenue_summary": {"total_billed": total, "total_paid": paid, "pending": total - paid},
    }
