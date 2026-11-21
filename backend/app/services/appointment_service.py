"""Appointment helpers: follow-up sync and calendar aggregation."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Appointment, Patient, Visit


def normalize_channel(value: str | None) -> str:
    text = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text == "online":
        return "online"
    if text in {"walk_in", "walkin"}:
        return "walk_in"
    return "in_clinic"


def create_appointment_from_follow_up(
    db: Session,
    visit: Visit,
    doctor_id: int,
    at: time | None = None,
) -> Appointment | None:
    """Create or move the scheduled appointment for a follow-up date."""
    if not visit.follow_up_date:
        return None

    scheduled_at = datetime.combine(visit.follow_up_date, at or time(10, 0))

    note_parts = [f"Follow-up from visit #{visit.id}"]
    if visit.diagnosis:
        note_parts.append(visit.diagnosis)
    if visit.follow_up_notes:
        note_parts.append(visit.follow_up_notes)
    notes = " — ".join(note_parts)

    linked = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == visit.patient_id,
            Appointment.status == "scheduled",
            Appointment.notes.like(f"%Follow-up from visit #{visit.id}%"),
        )
        .order_by(Appointment.id.desc())
        .first()
    )
    if linked:
        linked.scheduled_at = scheduled_at
        linked.notes = notes
        linked.channel = linked.channel or "in_clinic"
        return linked

    day_start = datetime.combine(visit.follow_up_date, time.min)
    day_end = day_start + timedelta(days=1)
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
        if not existing.channel:
            existing.channel = "in_clinic"
        return existing

    appt = Appointment(
        patient_id=visit.patient_id,
        doctor_id=doctor_id,
        scheduled_at=scheduled_at,
        duration_minutes=15,
        status="scheduled",
        channel="in_clinic",
        notes=notes,
    )
    db.add(appt)
    return appt


def linked_follow_up_appointments(db: Session, visit: Visit) -> list[Appointment]:
    marker = f"Follow-up from visit #{visit.id}"
    return (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == visit.patient_id,
            Appointment.notes.isnot(None),
            Appointment.notes.like(f"%{marker}%"),
        )
        .all()
    )


def follow_up_calendar_outcome(db: Session, visit: Visit) -> str | None:
    """How the calendar left this follow-up: cancelled, done, or still open."""
    linked = linked_follow_up_appointments(db, visit)
    if not linked:
        return None
    active = {"scheduled", "arrived", "in_consult"}
    if any((row.status or "") in active for row in linked):
        return None
    if any((row.status or "") == "completed" for row in linked):
        return "done"
    if all((row.status or "") in {"cancelled", "no_show"} for row in linked):
        return "cancelled"
    return None


def follow_up_cancelled_on_calendar(db: Session, visit: Visit) -> bool:
    return follow_up_calendar_outcome(db, visit) == "cancelled"


def sync_follow_up_date_from_appointment(db: Session, appt: Appointment) -> None:
    """A moved follow-up slot keeps the same date on the follow-up list."""
    import re

    match = re.search(r"Follow-up from visit #(\d+)", appt.notes or "")
    if not match or not appt.scheduled_at or appt.patient_id is None:
        return
    visit = db.get(Visit, int(match.group(1)))
    if not visit or visit.patient_id != appt.patient_id:
        return
    when = appt.scheduled_at
    if when.tzinfo is not None:
        from zoneinfo import ZoneInfo

        when = when.astimezone(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    visit.follow_up_date = when.date()


def appointment_counts_by_month(db: Session, clinic_id: int, year: int, month: int) -> dict:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    rows = (
        db.query(func.date(Appointment.scheduled_at).label("day"), func.count(Appointment.id))
        .join(Patient, Appointment.patient_id == Patient.id)
        .filter(
            Patient.clinic_id == clinic_id,
            Appointment.status != "cancelled",
            or_(Patient.registration_status.is_(None), Patient.registration_status != "cancelled"),
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
