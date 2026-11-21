"""Ensure a light OPD visit exists for desk billing and queue vitals."""

from datetime import date, datetime, time

from sqlalchemy.orm import Session

from app.models import Appointment, Visit


def ensure_opd_visit_for_day(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int,
    day: date | None = None,
    visit_type: str = "OPD",
    appt: Appointment | None = None,
) -> Visit:
    day = day or date.today()
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)
    existing = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id, Visit.visit_date >= start, Visit.visit_date <= end)
        .order_by(Visit.id.desc())
        .first()
    )
    if existing:
        if appt and _copy_vitals(existing, appt):
            db.flush()
        return existing
    visit = Visit(
        patient_id=patient_id,
        doctor_id=doctor_id,
        visit_date=datetime.combine(day, datetime.utcnow().time()),
        visit_type=visit_type,
        status="draft",
    )
    if appt:
        _copy_vitals(visit, appt)
    db.add(visit)
    db.flush()
    return visit


def _copy_vitals(visit: Visit, appt: Appointment) -> bool:
    changed = False
    mapping = (
        ("height", "height"),
        ("weight", "weight"),
        ("bp_systolic", "bp_systolic"),
        ("bp_diastolic", "bp_diastolic"),
        ("pulse", "pulse"),
        ("temperature", "temperature"),
        ("spo2", "spo2"),
    )
    for visit_attr, appt_attr in mapping:
        value = getattr(appt, appt_attr, None)
        if value is not None and getattr(visit, visit_attr, None) is None:
            setattr(visit, visit_attr, value)
            changed = True
    return changed


def appointment_vitals_for_patient_day(db: Session, patient_id: int, day: date | None = None) -> dict:
    day = day or date.today()
    start = datetime.combine(day, time.min)
    end = datetime.combine(day, time.max)
    appt = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at <= end,
        )
        .order_by(Appointment.id.desc())
        .first()
    )
    if not appt:
        return {}
    return {
        "height": appt.height,
        "weight": appt.weight,
        "bp_systolic": appt.bp_systolic,
        "bp_diastolic": appt.bp_diastolic,
        "pulse": appt.pulse,
        "temperature": appt.temperature,
        "spo2": appt.spo2,
    }
