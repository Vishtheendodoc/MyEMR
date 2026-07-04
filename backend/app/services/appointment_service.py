"""Appointment helpers: follow-up sync and calendar aggregation."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Appointment, Visit


def create_appointment_from_follow_up(
    db: Session,
    visit: Visit,
    doctor_id: int,
) -> Appointment | None:
    """Create or update a scheduled appointment when a visit has a follow-up date."""
    if not visit.follow_up_date:
        return None

    day_start = datetime.combine(visit.follow_up_date, time.min)
    day_end = day_start + timedelta(days=1)
    scheduled_at = datetime.combine(visit.follow_up_date, time(10, 0))

    note_parts = [f"Follow-up from visit #{visit.id}"]
    if visit.diagnosis:
        note_parts.append(visit.diagnosis)
    if visit.follow_up_notes:
        note_parts.append(visit.follow_up_notes)
    notes = " — ".join(note_parts)

    existing = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == visit.patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_at >= day_start,
            Appointment.scheduled_at < day_end,
            Appointment.status == "scheduled",
        )
        .first()
    )
    if existing:
        existing.notes = notes
        existing.scheduled_at = scheduled_at
        return existing

    appt = Appointment(
        patient_id=visit.patient_id,
        doctor_id=doctor_id,
        scheduled_at=scheduled_at,
        duration_minutes=15,
        status="scheduled",
        notes=notes,
    )
    db.add(appt)
    return appt


def appointment_counts_by_month(db: Session, doctor_id: int, year: int, month: int) -> dict:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    rows = (
        db.query(func.date(Appointment.scheduled_at).label("day"), func.count(Appointment.id))
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_at >= datetime.combine(start, time.min),
            Appointment.scheduled_at < datetime.combine(end, time.min),
        )
        .group_by("day")
        .all()
    )

    return {
        "year": year,
        "month": month,
        "days": [{"date": str(day), "count": count} for day, count in rows],
    }
