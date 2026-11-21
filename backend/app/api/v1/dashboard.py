from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Appointment, BrandMedication, GenericDrug, Patient, User, Visit
from app.schemas.dashboard import DashboardResponse, DashboardStats, RecentVisitItem, TodayBoard, TodayConsult
from app.services.appointment_service import normalize_channel
from app.services.clinic_scope import clinic_id_of, desk_doctor_id, patients_query, visits_for_clinic
from app.services.clinic_time import as_kolkata, clinic_day, clinic_period_utc

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_REVISIT_TYPES = {"follow-up", "follow up", "revisit"}


def _kind(patient_id: int, prior: set[int], visit_type: str | None, notes: str | None) -> str:
    if patient_id in prior:
        return "revisit"
    if (visit_type or "").strip().lower() in _REVISIT_TYPES:
        return "revisit"
    if (notes or "").lower().startswith("follow-up"):
        return "revisit"
    return "new"


def _visit_status(visit: Visit) -> str:
    patient = visit.patient
    if patient and (patient.registration_status or "") == "cancelled":
        return "registration_cancelled"
    if (visit.status or "") == "cancelled":
        return "appointment_cancelled"
    if (visit.status or "") == "finalized" or visit.finalized_at:
        return "completed"
    if (visit.status or "") == "in_consult":
        return "in_consult"
    return "arrived"


def today_consultations(db: Session, user) -> TodayBoard:
    today = clinic_day(datetime.utcnow())
    start = datetime.combine(today, time.min)
    end = start + timedelta(days=1)
    visit_start, visit_end = clinic_period_utc(today, today)
    clinic_id = clinic_id_of(user)

    appointments = (
        db.query(Appointment)
        .join(Patient, Appointment.patient_id == Patient.id)
        .options(joinedload(Appointment.patient))
        .filter(
            Patient.clinic_id == clinic_id,
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at < end,
            *([or_(Patient.doctor_id == desk_doctor_id(user), Patient.doctor_id.is_(None))] if desk_doctor_id(user) else []),
        )
        .order_by(Appointment.scheduled_at.asc(), Appointment.token_number.asc())
        .all()
    )
    visits = (
        visits_for_clinic(db, user)
        .options(joinedload(Visit.patient))
        .filter(Visit.visit_date >= visit_start, Visit.visit_date < visit_end)
        .all()
    )
    prior = {
        row[0]
        for row in (
            db.query(Visit.patient_id)
            .join(Patient, Visit.patient_id == Patient.id)
            .filter(Patient.clinic_id == clinic_id, Visit.visit_date < visit_start)
            .distinct()
            .all()
        )
    }
    visits_by_patient: dict[int, Visit] = {}
    for visit in visits:
        if (visit.visit_type or "").lower() == "pharmacy":
            continue
        current = visits_by_patient.get(visit.patient_id)
        if current is None or (visit.visit_date or datetime.min) >= (current.visit_date or datetime.min):
            visits_by_patient[visit.patient_id] = visit

    rows: list[TodayConsult] = []
    seen: set[int] = set()
    for appt in appointments:
        patient = appt.patient
        visit = visits_by_patient.get(appt.patient_id)
        seen.add(appt.patient_id)
        if patient and (patient.registration_status or "") == "cancelled":
            board_status = "registration_cancelled"
        elif (appt.status or "") == "cancelled":
            board_status = "appointment_cancelled"
        else:
            board_status = appt.status or "scheduled"
        rows.append(TodayConsult(
            appointment_id=appt.id,
            visit_id=visit.id if visit else None,
            patient_id=appt.patient_id,
            patient_name=patient.name if patient else "",
            patient_mrd=patient.mrd_number if patient else None,
            patient_age=patient.age if patient else None,
            patient_sex=patient.sex if patient else None,
            scheduled_at=appt.scheduled_at,
            token_number=appt.token_number,
            status=board_status,
            channel=normalize_channel(appt.channel),
            kind=_kind(appt.patient_id, prior, visit.visit_type if visit else None, appt.notes),
            complaint=(visit.chief_complaints if visit and visit.chief_complaints else appt.notes),
        ))

    for patient_id, visit in visits_by_patient.items():
        if patient_id in seen:
            continue
        patient = visit.patient
        seen.add(patient_id)
        rows.append(TodayConsult(
            visit_id=visit.id,
            patient_id=patient_id,
            patient_name=patient.name if patient else "",
            patient_mrd=patient.mrd_number if patient else None,
            patient_age=patient.age if patient else None,
            patient_sex=patient.sex if patient else None,
            scheduled_at=visit.visit_date,
            status=_visit_status(visit),
            channel="walk_in",
            kind=_kind(patient_id, prior, visit.visit_type, None),
            complaint=visit.chief_complaints,
        ))

    registered = (
        patients_query(db, user)
        .filter(
            Patient.date_registered >= visit_start,
            Patient.date_registered < visit_end,
            or_(Patient.mrd_number.is_(None), Patient.mrd_number != "WALKIN"),
            or_(Patient.registration_status.is_(None), Patient.registration_status == "active"),
        )
        .all()
    )
    for patient in registered:
        if patient.id in seen or patient.date_registered is None:
            continue
        seen.add(patient.id)
        rows.append(TodayConsult(
            patient_id=patient.id,
            patient_name=patient.name,
            patient_mrd=patient.mrd_number,
            patient_age=patient.age,
            patient_sex=patient.sex,
            scheduled_at=as_kolkata(patient.date_registered).replace(tzinfo=None),
            status="arrived",
            channel="walk_in",
            kind=_kind(patient.id, prior, None, None),
            complaint="Registered today",
        ))

    due = (
        visits_for_clinic(db, user)
        .options(joinedload(Visit.patient))
        .filter(Visit.follow_up_date == today)
        .all()
    )
    for visit in due:
        if visit.patient_id in seen or (visit.patient and (visit.patient.mrd_number == "WALKIN" or (visit.patient.registration_status or "") == "cancelled")):
            continue
        from app.services.appointment_service import follow_up_calendar_outcome
        if follow_up_calendar_outcome(db, visit) in {"cancelled", "done"}:
            continue
        patient = visit.patient
        seen.add(visit.patient_id)
        rows.append(TodayConsult(
            visit_id=visit.id,
            patient_id=visit.patient_id,
            patient_name=patient.name if patient else "",
            patient_mrd=patient.mrd_number if patient else None,
            patient_age=patient.age if patient else None,
            patient_sex=patient.sex if patient else None,
            scheduled_at=datetime.combine(today, time(10, 0)),
            status="due",
            channel="in_clinic",
            kind="revisit",
            complaint=visit.follow_up_notes or visit.diagnosis,
        ))

    def sort_key(row: TodayConsult):
        return (row.scheduled_at or datetime.max, row.token_number or 9999, row.patient_name)

    rows.sort(key=sort_key)
    open_rows = [row for row in rows if row.status not in {"registration_cancelled", "appointment_cancelled"}]
    return TodayBoard(
        date=today.isoformat(),
        consultations=rows,
        booked=sum(1 for row in rows if row.status == "scheduled"),
        waiting=sum(1 for row in rows if row.status in {"arrived", "due"}),
        in_consult=sum(1 for row in rows if row.status == "in_consult"),
        done=sum(1 for row in rows if row.status == "completed"),
        new=sum(1 for row in open_rows if row.kind == "new"),
        revisit=sum(1 for row in open_rows if row.kind == "revisit"),
        walk_in=sum(1 for row in open_rows if row.channel == "walk_in"),
        online=sum(1 for row in open_rows if row.channel == "online"),
    )


@router.get("", response_model=DashboardResponse)
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recent = (
        visits_for_clinic(db, user)
        .options(joinedload(Visit.patient))
        .order_by(Visit.visit_date.desc())
        .limit(8)
        .all()
    )
    stats = DashboardStats(
        total_patients=patients_query(db, user).count(),
        total_visits=visits_for_clinic(db, user).count(),
        total_drugs=db.query(GenericDrug).count(),
        total_brands=db.query(BrandMedication).count(),
    )
    recent_items = [
        RecentVisitItem(
            id=v.id,
            visit_date=v.visit_date,
            visit_type=v.visit_type,
            diagnosis=v.diagnosis,
            chief_complaints=v.chief_complaints,
            patient_id=v.patient_id,
            patient_name=v.patient.name,
            patient_mrd=v.patient.mrd_number,
        )
        for v in recent
    ]
    return DashboardResponse(stats=stats, recent_visits=recent_items, today=today_consultations(db, user))
