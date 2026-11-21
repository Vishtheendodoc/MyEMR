import json
import re
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models import Appointment, Bill, BillPayment, DayClose, Patient, PatientAdvance, Prescription, ReminderLog, User, Visit
from app.schemas.extended import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
    BillCreate,
    BillPaymentOut,
    BillResponse,
    BillUpdate,
    DebitNoteIn,
    ReminderSendRequest,
)
from app.services.appointment_service import appointment_counts_by_month, create_appointment_from_follow_up, normalize_channel
from app.services.patient_service import is_temporary_mrd, next_clinic_mrd
from app.services.clinic_time import clinic_day, clinic_period_utc, clinic_wall_now
from app.services.commerce import (
    add_debit_note,
    annotate_bill,
    apply_patient_advance,
    issue_credit_note,
    record_dispensed,
    record_payment,
    resolve_place_of_supply,
)
from app.services.invoice_series import next_document_number, rupee_round
from app.services.audit import write_audit
from app.services.clinic_scope import (
    clinic_id_of,
    desk_doctor_id,
    DESK_ROLES,
    ensure_patient_access,
    ensure_visit_access,
    owning_doctor_id,
    registration_doctor,
    visits_for_clinic,
)
from app.services.opd_visit import ensure_opd_visit_for_day
from app.services.reminder_service import (
    broadcast_registered,
    build_reminder_queue,
    format_appt_message,
    format_followup_message,
    log_and_send_reminder,
    process_due_auto_reminders,
    twilio_configured,
    whatsapp_link,
)
from app.services.prescription_utils import enrich_prescription_response
from app.schemas.prescription import PrescriptionResponse

router = APIRouter(tags=["operations"])


def _split_tests(text: str) -> list[str]:
    parts = [
        line.strip(" -\t*")
        for line in re.split(r"[\r\n,;•]+", text or "")
        if line.strip(" -\t*")
    ]
    return parts or ([text.strip()] if (text or "").strip() else [])


def _bill_lines(bill: Bill) -> list[dict]:
    if bill.line_items:
        try:
            return json.loads(bill.line_items)
        except json.JSONDecodeError:
            return []
    return [{
        "description": bill.description,
        "procedure_code": bill.procedure_code,
        "quantity": 1,
    }]


def _day_is_closed(db: Session, clinic_id: int, day: date) -> DayClose | None:
    return (
        db.query(DayClose)
        .filter(DayClose.clinic_id == clinic_id, DayClose.close_date == day)
        .first()
    )


def _ensure_bill_day_editable(db: Session, user, bill: Bill) -> None:
    day = clinic_day(bill.created_at or datetime.utcnow())
    if _day_is_closed(db, clinic_id_of(user), day):
        raise HTTPException(status_code=400, detail="This day's collections are locked. Re-open day close to edit.")


def _is_later_receipt(data: BillUpdate, bill: Bill) -> bool:
    """Money received against an existing balance. It does not change the closed day's invoice."""
    if data.refund_amount or data.payment_status == "cancelled":
        return False
    if data.description is not None and data.description != (bill.description or ""):
        return False
    if _payment_parts(data):
        return True
    if data.amount_paid is not None and float(data.amount_paid) + 0.009 >= float(bill.amount_paid or 0):
        return True
    return data.payment_status == "paid"


def _appt_response(a: Appointment) -> AppointmentResponse:
    raw = {c.name: getattr(a, c.name) for c in Appointment.__table__.columns}
    return AppointmentResponse(
        **raw,
        patient_name=a.patient.name if a.patient else None,
        patient_contact=a.patient.contact if a.patient else None,
        patient_mrd=a.patient.mrd_number if a.patient else None,
        registration_status=a.patient.registration_status if a.patient else None,
    )


def _next_invoice_number(db: Session, clinic_id: int) -> str:
    return next_document_number(db, clinic_id, "INV")


def _finish_total(exact: float) -> tuple[float, float]:
    payable, round_off = rupee_round(exact)
    if payable <= 0:
        raise HTTPException(status_code=400, detail="Invoice total must be greater than zero")
    return payable, round_off


def _ensure_appt_access(db: Session, appt_id: int, user) -> Appointment:
    appt = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient))
        .filter_by(id=appt_id)
        .first()
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    ensure_patient_access(db, appt.patient_id, user)
    return appt


def _bill_response(bill: Bill, patient: Patient | None) -> BillResponse:
    raw = {c.name: getattr(bill, c.name) for c in Bill.__table__.columns}
    stored = raw.pop("line_items", None)
    lines = None
    if stored:
        try:
            lines = json.loads(stored)
        except json.JSONDecodeError:
            lines = None
    raw["discount_amount"] = raw.get("discount_amount") or 0
    raw["refund_amount"] = raw.get("refund_amount") or 0
    paid = raw.get("amount_paid") or 0
    if raw.get("payment_status") == "paid" and paid <= 0:
        paid = raw.get("amount") or 0
    raw["amount_paid"] = paid
    raw["gst_percent"] = raw.get("gst_percent") or 0
    raw["gst_amount"] = raw.get("gst_amount") or 0
    raw["round_off"] = raw.get("round_off") or 0
    raw["advance_applied"] = raw.get("advance_applied") or 0
    raw["cgst_amount"] = raw.get("cgst_amount") or 0
    raw["sgst_amount"] = raw.get("sgst_amount") or 0
    raw["igst_amount"] = raw.get("igst_amount") or 0
    return BillResponse(
        **raw,
        line_items=lines,
        patient_name=patient.name if patient else None,
        patient_mrd=patient.mrd_number if patient else None,
        patient_age=patient.age if patient else None,
        patient_sex=patient.sex if patient else None,
    )


def _compose_bill(data: BillCreate) -> dict:
    """Price one invoice. Line items become a single bill with a stored breakdown."""
    if data.line_items:
        lines = []
        base_sum = 0.0
        gst_sum = 0.0
        for item in data.line_items:
            rate = item.rate if item.rate is not None else item.base_amount
            if rate is None:
                raise HTTPException(status_code=400, detail=f"Enter a price for {item.description}")
            qty = item.quantity or 1
            line_base = round(float(qty) * float(rate), 2)
            gst = round(line_base * float(item.gst_percent or 0) / 100, 2)
            base_sum += line_base
            gst_sum += gst
            stored = {
                "description": item.description.strip(),
                "procedure_code": item.procedure_code,
                "quantity": qty,
                "rate": float(rate),
                "base_amount": line_base,
                "gst_percent": float(item.gst_percent or 0),
                "gst_amount": gst,
            }
            if item.batch_id:
                stored["batch_id"] = item.batch_id
            if (item.note or "").strip():
                stored["note"] = item.note.strip()
            lines.append(stored)
        gross = round(base_sum + gst_sum, 2)
        discount = min(round(float(data.discount_amount or 0), 2), gross)
        total, round_off = _finish_total(gross - discount)
        paid = float(data.amount_paid or 0)
        if data.payment_status == "paid":
            paid = total
        paid = min(max(paid, 0.0), total)
        status = "paid" if paid >= total - 0.009 else ("partial" if paid > 0 else "pending")
        label = ", ".join(line["description"] for line in lines)[:300]
        return {
            "description": (data.description or label)[:300],
            "amount": total,
            "base_amount": round(base_sum, 2),
            "gst_percent": 0,
            "gst_amount": round(gst_sum, 2),
            "procedure_code": lines[0]["procedure_code"] if len(lines) == 1 else None,
            "payment_status": status,
            "payment_method": data.payment_method,
            "discount_amount": discount,
            "amount_paid": round(paid, 2),
            "line_items": json.dumps(lines),
            "round_off": round_off,
        }

    if data.amount is None or data.amount <= 0:
        raise HTTPException(status_code=400, detail="Enter a valid amount")
    base = data.base_amount if data.base_amount is not None else data.amount
    gst_amount = data.gst_amount
    if data.gst_percent > 0 and gst_amount == 0:
        gst_amount = round(base * data.gst_percent / 100, 2)
    total = float(data.amount)
    if data.gst_percent > 0 and abs(total - (base + gst_amount)) > 0.05:
        total = round(base + gst_amount, 2)
    discount = min(round(float(data.discount_amount or 0), 2), total)
    total, round_off = _finish_total(total - discount)
    paid = total if data.payment_status == "paid" else min(float(data.amount_paid or 0), total)
    status = "paid" if paid >= total - 0.009 else ("partial" if paid > 0 else (data.payment_status or "pending"))
    return {
        "description": data.description[:300],
        "amount": total,
        "base_amount": base,
        "gst_percent": data.gst_percent,
        "gst_amount": gst_amount,
        "procedure_code": data.procedure_code,
        "payment_status": status,
        "payment_method": data.payment_method,
        "discount_amount": discount,
        "amount_paid": round(paid, 2),
        "line_items": None,
        "round_off": round_off,
    }


@router.get("/appointments/calendar")
def appointments_calendar(
    year: int,
    month: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1–12")
    return appointment_counts_by_month(db, clinic_id_of(user), year, month)


@router.get("/appointments", response_model=list[AppointmentResponse])
def list_appointments(
    day: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Appointment)
        .join(Patient, Appointment.patient_id == Patient.id)
        .options(joinedload(Appointment.patient))
        .filter(Patient.clinic_id == clinic_id_of(user))
    )
    chosen = desk_doctor_id(user)
    if chosen:
        q = q.filter(or_(Patient.doctor_id == chosen, Patient.doctor_id.is_(None)))
    if day:
        try:
            d = date.fromisoformat(day)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="day must be YYYY-MM-DD") from exc
        start = datetime.combine(d, time.min)
        end = start + timedelta(days=1)
        q = q.filter(Appointment.scheduled_at >= start, Appointment.scheduled_at < end)
    appts = q.order_by(Appointment.scheduled_at.asc()).all()
    return [_appt_response(a) for a in appts]


@router.get("/patients/{patient_id}/appointments", response_model=list[AppointmentResponse])
def patient_appointments(
    patient_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_patient_access(db, patient_id, user)
    rows = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient))
        .filter(Appointment.patient_id == patient_id)
        .order_by(Appointment.scheduled_at.desc())
        .all()
    )
    return [_appt_response(a) for a in rows]


class QueueCheckIn(BaseModel):
    patient_id: int
    channel: str = "walk_in"
    kind: str = "new"
    doctor_id: int | None = None


def _next_token(db: Session, clinic_id: int, day: date) -> int:
    start = datetime.combine(day, time.min)
    end = start + timedelta(days=1)
    numbers = (
        db.query(Appointment.token_number)
        .join(Patient, Appointment.patient_id == Patient.id)
        .filter(
            Patient.clinic_id == clinic_id,
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at < end,
        )
        .all()
    )
    return max([n[0] or 0 for n in numbers] or [0]) + 1


@router.post("/queue/check-in")
def check_in_patient(data: QueueCheckIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Registration puts someone on the chosen doctor's list for today."""
    doctor = registration_doctor(db, user, data.doctor_id) if user.role in DESK_ROLES else None
    if user.role in DESK_ROLES:
        patient = db.get(Patient, data.patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        if doctor and patient.clinic_id != doctor.clinic_id:
            if user.role != "registration":
                raise HTTPException(status_code=400, detail="This chart belongs to another doctor's clinic")
            from app.services.patient_service import ensure_mobile_available
            ensure_mobile_available(db, doctor.clinic_id, patient.contact, exclude_id=patient.id)
            patient.clinic_id = doctor.clinic_id
    else:
        patient = ensure_patient_access(db, data.patient_id, user)
    if (patient.registration_status or "") == "cancelled":
        raise HTTPException(status_code=400, detail="This registration is cancelled")
    owner_id = doctor.id if doctor else owning_doctor_id(db, user)
    today = clinic_day(datetime.utcnow())
    start = datetime.combine(today, time.min)
    end = start + timedelta(days=1)
    kind = "revisit" if (data.kind or "").strip().lower() == "revisit" else "new"
    channel = normalize_channel(data.channel)
    visit_type = "Revisit" if kind == "revisit" else "New Visit"
    existing = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id,
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at < end,
            Appointment.status != "cancelled",
        )
        .order_by(Appointment.id.desc())
        .first()
    )
    if existing is None:
        existing = Appointment(
            patient_id=patient.id,
            doctor_id=owner_id,
            scheduled_at=clinic_wall_now(),
            duration_minutes=15,
            status="arrived",
            channel=channel,
            notes="Revisit" if kind == "revisit" else "New",
        )
        db.add(existing)
        db.flush()
    else:
        existing.doctor_id = owner_id
        existing.channel = channel
        existing.notes = "Revisit" if kind == "revisit" else "New"
        if existing.status == "scheduled":
            existing.status = "arrived"
    if existing.status == "arrived" and not existing.token_number:
        existing.token_number = _next_token(db, patient.clinic_id, today)
    if is_temporary_mrd(patient.mrd_number) or (patient.registration_status or "") == "temporary":
        previous = patient.mrd_number
        patient.mrd_number = next_clinic_mrd(db, patient.clinic_id)
        patient.registration_status = "active"
        write_audit(
            db,
            user_id=user.id,
            action="patient.assign_mrd",
            entity_type="patient",
            entity_id=patient.id,
            details=f"{previous} -> {patient.mrd_number}",
        )
    if doctor:
        patient.doctor_id = doctor.id
    visit = ensure_opd_visit_for_day(
        db,
        patient_id=patient.id,
        doctor_id=owner_id,
        day=today,
        visit_type=visit_type,
        appt=existing,
    )
    if (visit.status or "draft") == "draft":
        visit.visit_type = visit_type
    db.commit()
    return {
        "appointment_id": existing.id,
        "visit_id": visit.id,
        "token_number": existing.token_number,
        "status": existing.status,
        "channel": existing.channel,
        "kind": kind,
    }


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
def create_appointment(data: AppointmentCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_patient_access(db, data.patient_id, user)
    payload = data.model_dump()
    payload["channel"] = normalize_channel(payload.get("channel"))
    appt = Appointment(doctor_id=owning_doctor_id(db, user), **payload)
    db.add(appt)
    db.commit()
    appt = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient))
        .filter_by(id=appt.id)
        .first()
    )
    return _appt_response(appt)


@router.patch("/appointments/{appt_id}", response_model=AppointmentResponse)
def update_appointment(
    appt_id: int,
    data: AppointmentUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appt = _ensure_appt_access(db, appt_id, user)
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(appt, key, value)
    if "scheduled_at" in payload:
        from app.services.appointment_service import sync_follow_up_date_from_appointment

        sync_follow_up_date_from_appointment(db, appt)
    db.commit()
    appt = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient))
        .filter_by(id=appt_id)
        .first()
    )
    return _appt_response(appt)


@router.patch("/appointments/{appt_id}/status")
def update_appointment_status(appt_id: int, status: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    appt = _ensure_appt_access(db, appt_id, user)
    allowed = {"scheduled", "arrived", "in_consult", "completed", "cancelled", "no_show"}
    if status == "done":
        status = "completed"
    if user.role == "registration" and not (status == "cancelled" and appt.status == "scheduled"):
        raise HTTPException(status_code=403, detail="Registration desk can only cancel a booked appointment")
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Unknown queue status")
    appt.status = status
    if status == "cancelled" and appt.scheduled_at:
        day = appt.scheduled_at.date()
        start = datetime.combine(day, time.min)
        end = start + timedelta(days=1)
        same_day = (
            db.query(Visit)
            .filter(Visit.patient_id == appt.patient_id, Visit.visit_date >= start, Visit.visit_date < end)
            .all()
        )
        for visit in same_day:
            if visit.pdf_generated_at or visit.finalized_at or (visit.status or "") in {"locked", "finalized"}:
                continue
            visit.status = "cancelled"
    if status == "arrived":
        day = appt.scheduled_at.date() if appt.scheduled_at else date.today()
        if not appt.token_number:
            start = datetime.combine(day, time.min)
            end = start + timedelta(days=1)
            clinic_id = appt.patient.clinic_id if appt.patient else clinic_id_of(user)
            numbers = (
                db.query(Appointment.token_number)
                .join(Patient, Appointment.patient_id == Patient.id)
                .filter(
                    Patient.clinic_id == clinic_id,
                    Appointment.scheduled_at >= start,
                    Appointment.scheduled_at < end,
                )
                .all()
            )
            appt.token_number = max([n[0] or 0 for n in numbers] or [0]) + 1
        ensure_opd_visit_for_day(
            db,
            patient_id=appt.patient_id,
            doctor_id=owning_doctor_id(db, user),
            day=day,
            visit_type="OPD",
            appt=appt,
        )
    db.commit()
    return {"success": True, "token_number": appt.token_number, "status": appt.status}


@router.patch("/visits/{visit_id}/follow-up")
def reschedule_follow_up(
    visit_id: int,
    follow_up_date: date = Query(...),
    follow_up_notes: str | None = None,
    follow_up_time: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = ensure_visit_access(db, visit_id, user)
    if follow_up_date < clinic_day(datetime.utcnow()) and follow_up_date != visit.follow_up_date:
        raise HTTPException(status_code=400, detail="Choose today or a later date")
    at = time(10, 0)
    if follow_up_time:
        try:
            hour, minute = follow_up_time.strip().split(":")
            at = time(int(hour), int(minute))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Time must be HH:MM") from exc
    visit.follow_up_date = follow_up_date
    if follow_up_notes is not None:
        visit.follow_up_notes = follow_up_notes
    db.query(ReminderLog).filter(
        ReminderLog.source_type == "follow_up",
        ReminderLog.source_id == visit.id,
        ReminderLog.status == "cancelled",
    ).delete(synchronize_session=False)
    moved = create_appointment_from_follow_up(db, visit, owning_doctor_id(db, user), at=at)
    db.commit()
    return {
        "success": True,
        "visit_id": visit.id,
        "follow_up_date": visit.follow_up_date.isoformat(),
        "follow_up_notes": visit.follow_up_notes,
        "appointment_id": moved.id if moved else None,
        "scheduled_at": moved.scheduled_at.isoformat() if moved else None,
    }


def _reminder_fallback_doctor(db: Session, user) -> str:
    from app.services.clinic_scope import primary_doctor

    if user.role == "doctor":
        return user.doctor_name
    doctor = primary_doctor(db, clinic_id_of(user))
    return doctor.doctor_name if doctor else user.doctor_name


@router.get("/reminders/status")
def reminders_status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.reminder_service import reminder_names

    clinic, doctor = reminder_names(db, clinic_id_of(user), _reminder_fallback_doctor(db, user))
    return {
        "auto_send_available": twilio_configured(),
        "channel_default": "whatsapp_api" if twilio_configured() else "whatsapp_link",
        "clinic_name": clinic,
        "doctor_name": doctor,
        "rule": "1 day before appointment; Monday appointments reminded on Friday",
    }


class ReminderNamesIn(BaseModel):
    clinic_name: str
    doctor_name: str


@router.patch("/reminders/names")
def save_reminder_names(
    data: ReminderNamesIn,
    user=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    from app.models import ClinicProfile
    from app.services.reminder_service import plain_doctor_name, reminder_names

    clinic_name = (data.clinic_name or "").strip()
    doctor_name = plain_doctor_name(data.doctor_name)
    if len(clinic_name) < 2:
        raise HTTPException(status_code=400, detail="Enter the clinic name")
    if len(doctor_name) < 2:
        raise HTTPException(status_code=400, detail="Enter the doctor name")
    clinic_id = clinic_id_of(user)
    row = db.get(ClinicProfile, clinic_id)
    if not row:
        row = ClinicProfile(clinic_id=clinic_id, name=clinic_name)
        db.add(row)
    row.reminder_clinic_name = clinic_name
    row.reminder_doctor_name = doctor_name
    db.commit()
    clinic, doctor = reminder_names(db, clinic_id, doctor_name)
    return {"clinic_name": clinic, "doctor_name": doctor}


@router.post("/reminders/cancel")
def cancel_reminder(
    data: ReminderSendRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.reminder_service import reminder_is_cancelled

    from app.services.appointment_service import linked_follow_up_appointments

    if data.source_type == "appointment":
        appt = _ensure_appt_access(db, data.source_id, user)
        patient_id = appt.patient_id
        if appt.status in {"scheduled", "arrived", "in_consult"}:
            appt.status = "cancelled"
    elif data.source_type == "follow_up":
        visit = ensure_visit_access(db, data.source_id, user)
        patient_id = visit.patient_id
        linked = linked_follow_up_appointments(db, visit)
        active = [row for row in linked if (row.status or "") in {"scheduled", "arrived", "in_consult"}]
        for row in active:
            row.status = "cancelled"
        if not linked and visit.follow_up_date:
            db.add(Appointment(
                patient_id=visit.patient_id,
                doctor_id=owning_doctor_id(db, user),
                scheduled_at=datetime.combine(visit.follow_up_date, time(10, 0)),
                duration_minutes=15,
                status="cancelled",
                channel="in_clinic",
                notes=f"Follow-up from visit #{visit.id}",
            ))
    else:
        raise HTTPException(status_code=400, detail="source_type must be appointment or follow_up")
    if reminder_is_cancelled(db, data.source_type, data.source_id):
        db.commit()
        return {"success": True}
    db.add(ReminderLog(
        doctor_id=owning_doctor_id(db, user),
        patient_id=patient_id,
        source_type=data.source_type,
        source_id=data.source_id,
        channel="whatsapp",
        status="cancelled",
        message="Cancelled",
        sent_at=datetime.utcnow(),
    ))
    db.commit()
    return {"success": True}


class BroadcastIn(BaseModel):
    kind: str = "greeting"
    message: str = ""
    video_title: str = ""
    video_url: str = ""
    deliver: bool = False
    as_file: bool = False
    audience: str = "patients"


@router.post("/messages/broadcast")
def broadcast_message(
    data: BroadcastIn,
    user=Depends(require_role("registration")),
    db: Session = Depends(get_db),
):
    from urllib.parse import urlparse

    kind = (data.kind or "greeting").strip().lower()
    if kind not in {"greeting", "message", "video"}:
        raise HTTPException(status_code=400, detail="Choose a greeting, a message, or a video")
    if kind == "video":
        parsed = urlparse((data.video_url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Upload a video or paste a video link")
    elif kind == "message" and len((data.message or "").strip()) < 3:
        raise HTTPException(status_code=400, detail="Write the message to send")
    if len(data.message or "") > 800:
        raise HTTPException(status_code=400, detail="Keep the message under 800 characters")
    audience = (data.audience or "patients").strip().lower()
    if audience not in {"patients", "test"}:
        raise HTTPException(status_code=400, detail="Choose the test list or the patient list")
    return broadcast_registered(
        db,
        user,
        kind,
        data.message,
        data.video_title,
        data.video_url,
        data.deliver,
        data.as_file,
        audience,
    )


class MessageContactIn(BaseModel):
    name: str
    phone: str
    list_kind: str = "saved"


class SendTextIn(BaseModel):
    phone: str
    name: str = ""
    kind: str = "greeting"
    message: str = ""
    video_title: str = ""
    video_url: str = ""


class SendVideoIn(BaseModel):
    phone: str
    name: str = ""
    token: str
    message: str = ""
    video_title: str = ""


def _ten_digit_phone(raw: str) -> str:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10:
        raise HTTPException(status_code=400, detail="Enter a 10-digit mobile number")
    return digits


@router.get("/messages/contacts")
def list_message_contacts(user=Depends(require_role("registration")), db: Session = Depends(get_db)):
    from app.models import MessageContact

    rows = (
        db.query(MessageContact)
        .filter(MessageContact.clinic_id == clinic_id_of(user))
        .order_by(MessageContact.name.asc())
        .all()
    )
    return [{"id": row.id, "name": row.name, "phone": row.phone, "list_kind": row.list_kind or "saved"} for row in rows]


@router.post("/messages/contacts", status_code=201)
def save_message_contact(data: MessageContactIn, user=Depends(require_role("registration")), db: Session = Depends(get_db)):
    from app.models import MessageContact

    name = (data.name or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Enter the person's name")
    list_kind = (data.list_kind or "saved").strip().lower()
    if list_kind not in {"saved", "test"}:
        raise HTTPException(status_code=400, detail="Choose the test list or the saved list")
    phone = _ten_digit_phone(data.phone)
    clinic_id = clinic_id_of(user)
    if list_kind != "test":
        from app.services.patient_service import patient_with_mobile

        owner = patient_with_mobile(db, clinic_id, phone)
        if owner:
            label = owner.mrd_number or "no MRD"
            raise HTTPException(status_code=400, detail=f"This mobile is already registered for {owner.name} ({label})")
    row = db.query(MessageContact).filter_by(clinic_id=clinic_id, phone=phone).first()
    if row:
        where = "the test list" if (row.list_kind or "saved") == "test" else "the saved list"
        raise HTTPException(status_code=400, detail=f"This mobile is already on {where} for {row.name}")
    row = MessageContact(clinic_id=clinic_id, name=name, phone=phone, list_kind=list_kind)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "phone": row.phone, "list_kind": row.list_kind}


@router.delete("/messages/contacts/{contact_id}")
def delete_message_contact(contact_id: int, user=Depends(require_role("registration")), db: Session = Depends(get_db)):
    from app.models import MessageContact

    row = db.get(MessageContact, contact_id)
    if not row or row.clinic_id != clinic_id_of(user):
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(row)
    db.commit()
    return {"success": True}


@router.post("/messages/send-text")
def send_text_to_whatsapp(data: SendTextIn, user=Depends(require_role("registration"))):
    from urllib.parse import urlparse

    from app.core.config import settings
    from app.services.reminder_service import normalize_phone, render_broadcast
    from app.services.whatsapp_file import send_text_message

    kind = (data.kind or "greeting").strip().lower()
    if kind not in {"greeting", "message", "video"}:
        raise HTTPException(status_code=400, detail="Choose a greeting, a message, or a video")
    if kind == "video":
        parsed = urlparse((data.video_url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Upload a video or paste a video link")
    elif kind == "message" and len((data.message or "").strip()) < 3:
        raise HTTPException(status_code=400, detail="Write the message to send")
    phone = normalize_phone(data.phone)
    if not phone or len(phone) < 12:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")
    text = render_broadcast(
        kind,
        settings.clinic_name or "the clinic",
        data.name,
        data.message,
        data.video_title,
        data.video_url,
    )
    send_text_message(phone, text)
    return {"status": "sent", "phone": phone}


@router.post("/messages/send-video")
def send_video_to_whatsapp(data: SendVideoIn, user=Depends(require_role("registration"))):
    from app.core.config import settings
    from app.services.education_videos import resolve_video
    from app.services.reminder_service import normalize_phone, video_caption
    from app.services.whatsapp_file import send_video_file

    path, _media, stored_title = resolve_video(data.token)
    phone = normalize_phone(data.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")
    caption = video_caption(settings.clinic_name or "the clinic", data.name, data.message, data.video_title or stored_title)
    send_video_file(phone, path, caption)
    return {"status": "sent", "phone": phone}


@router.post("/messages/videos", status_code=201)
async def upload_education_video(
    file: UploadFile = File(...),
    title: str = Form(""),
    user=Depends(require_role("registration")),
):
    from app.services.education_videos import save_video

    original = file.filename or "video.mp4"

    def chunks():
        while True:
            block = file.file.read(1024 * 1024)
            if not block:
                break
            yield block

    return save_video(original, chunks(), title)


@router.get("/messages/videos/{token}")
def play_education_video(token: str):
    from app.services.education_videos import resolve_video

    path, media_type, label = resolve_video(token)
    return FileResponse(path, media_type=media_type, filename=f"{label}{path.suffix}")


@router.post("/reminders/auto-run")
def reminders_auto_run(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Process appointment reminders due today (Mon→Fri rule). Doctor or any staff."""
    return process_due_auto_reminders(db)


@router.get("/reminders/queue")
def reminders_queue(
    days: int = 3,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doctor = user if user.role == "doctor" else None
    from app.services.clinic_scope import primary_doctor
    from app.services.reminder_service import reminder_names
    chosen = desk_doctor_id(user)
    owner = db.get(User, chosen) if chosen else None
    owner = owner or doctor or primary_doctor(db, clinic_id_of(user)) or user
    _clinic, doctor_label = reminder_names(db, clinic_id_of(user), owner.doctor_name)
    items = build_reminder_queue(
        db,
        owner.id,
        doctor_label,
        days_ahead=days,
        clinic_id=clinic_id_of(user),
    )
    if chosen:
        allowed = {
            row.id for row in db.query(Patient.id).filter(
                Patient.id.in_([item["patient_id"] for item in items] or [0]),
                or_(Patient.doctor_id == chosen, Patient.doctor_id.is_(None)),
            )
        }
        items = [item for item in items if item["patient_id"] in allowed]
    return items


@router.post("/reminders/send")
def send_reminder(
    data: ReminderSendRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.reminder_service import reminder_is_cancelled
    if data.source_type in {"appointment", "follow_up"} and reminder_is_cancelled(db, data.source_type, data.source_id):
        raise HTTPException(status_code=400, detail="This reminder was cancelled")
    if data.source_type == "appointment":
        appt = _ensure_appt_access(db, data.source_id, user)
        patient = appt.patient
        from app.services.reminder_service import reminder_names
        clinic_label, doctor_label = reminder_names(db, clinic_id_of(user), _reminder_fallback_doctor(db, user))
        message = data.message or format_appt_message(patient.name, doctor_label, appt.scheduled_at, appt.notes, clinic_label)
        scheduled_for = appt.scheduled_at
    elif data.source_type == "follow_up":
        visit = ensure_visit_access(db, data.source_id, user)
        visit = (
            db.query(Visit)
            .options(joinedload(Visit.patient))
            .filter_by(id=visit.id)
            .first()
        )
        if not visit or not visit.follow_up_date:
            raise HTTPException(status_code=404, detail="Follow-up not found")
        patient = visit.patient
        from app.services.reminder_service import reminder_names
        clinic_label, doctor_label = reminder_names(db, clinic_id_of(user), _reminder_fallback_doctor(db, user))
        message = data.message or format_followup_message(
            patient.name, doctor_label, visit.follow_up_date, visit.diagnosis, clinic_label
        )
        scheduled_for = datetime.combine(visit.follow_up_date, time(10, 0))
    else:
        raise HTTPException(status_code=400, detail="source_type must be appointment or follow_up")

    if not patient.contact:
        raise HTTPException(status_code=400, detail="Patient has no contact number")

    # Log against clinic primary doctor so reminder ownership stays clinic-wide.
    from app.services.clinic_scope import primary_doctor
    doctor = primary_doctor(db, clinic_id_of(user)) or user
    result = log_and_send_reminder(
        db,
        doctor=doctor,
        patient=patient,
        source_type=data.source_type,
        source_id=data.source_id,
        message=message,
        auto_send=data.auto_send,
        scheduled_for=scheduled_for,
    )
    if not result.get("whatsapp_url") and result["status"] != "sent":
        raise HTTPException(status_code=400, detail="Could not build WhatsApp link — check phone number")
    return result


@router.get("/reminders/history")
def reminder_history(limit: int = 50, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(ReminderLog)
        .join(Patient, ReminderLog.patient_id == Patient.id)
        .filter(
            Patient.clinic_id == clinic_id_of(user),
            ReminderLog.source_type != "broadcast",
        )
        .order_by(ReminderLog.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    out = []
    for r in rows:
        patient = db.get(Patient, r.patient_id)
        out.append({
            "id": r.id,
            "patient_id": r.patient_id,
            "patient_name": patient.name if patient else None,
            "source_type": r.source_type,
            "source_id": r.source_id,
            "channel": r.channel,
            "status": r.status,
            "phone": r.phone,
            "message": r.message,
            "error": r.error,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


@router.get("/bills", response_model=list[BillResponse])
def list_bills(user=Depends(get_current_user), db: Session = Depends(get_db)):
    bill_q = (
        db.query(Bill)
        .join(Patient, Bill.patient_id == Patient.id)
        .options(joinedload(Bill.visit))
        .filter(Patient.clinic_id == clinic_id_of(user))
    )
    chosen = desk_doctor_id(user)
    if chosen:
        bill_q = bill_q.filter(or_(Patient.doctor_id == chosen, Patient.doctor_id.is_(None)))
    bills = bill_q.order_by(Bill.created_at.desc()).all()
    result = []
    for b in bills:
        patient = db.get(Patient, b.patient_id)
        result.append(_bill_response(b, patient))
    return result


@router.get("/bills/{bill_id}", response_model=BillResponse)
def get_bill(bill_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Invoice not found")
    patient = ensure_patient_access(db, bill.patient_id, user)
    saved = _bill_response(bill, patient)
    payments = db.query(BillPayment).filter_by(bill_id=bill.id).order_by(BillPayment.id.asc()).all()
    saved.receipts = [
        BillPaymentOut(
            amount=payment.amount,
            method=payment.method,
            kind=payment.kind or "collection",
            note=payment.note,
            created_at=payment.created_at,
        )
        for payment in payments
    ]
    return saved


@router.get("/billing/visit-options")
def billing_visit_options(user=Depends(get_current_user), db: Session = Depends(get_db)):
    visits = (
        visits_for_clinic(db, user)
        .options(joinedload(Visit.patient))
        .order_by(Visit.visit_date.desc(), Visit.id.desc())
        .limit(80)
        .all()
    )
    return [
        {
            "visit_id": v.id,
            "patient_id": v.patient_id,
            "patient_name": v.patient.name,
            "patient_mrd": v.patient.mrd_number,
            "visit_date": v.visit_date.isoformat(),
            "visit_type": v.visit_type,
            "diagnosis": v.diagnosis,
            "investigation": v.investigation,
        }
        for v in visits
    ]


def _visit_investigation_billed(db: Session, visit: Visit) -> bool:
    names = {n.lower() for n in _split_tests(visit.ordered_investigations or "")}
    if not names:
        return False
    bills = (
        db.query(Bill)
        .filter(Bill.visit_id == visit.id, Bill.payment_status != "cancelled")
        .all()
    )
    for bill in bills:
        for line in _bill_lines(bill):
            desc = (line.get("description") or "").strip().lower()
            code = str(line.get("procedure_code") or bill.procedure_code or "")
            if desc and any(desc == n or n in desc or desc in n for n in names):
                return True
            if code in {"999316", "999313", "999317"} and any(
                n in (bill.description or "").lower() for n in names
            ):
                return True
    return False


def _visit_pharmacy_billed(db: Session, visit_id: int) -> bool:
    bills = (
        db.query(Bill)
        .filter(Bill.visit_id == visit_id, Bill.payment_status != "cancelled")
        .all()
    )
    for bill in bills:
        if bill.category == "pharmacy" or (bill.description or "").lower().startswith("pharmacy"):
            return True
        if any(str(line.get("procedure_code") or "") == "300490" for line in _bill_lines(bill)):
            return True
    return False


@router.get("/billing/orders")
def billing_lab_orders(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Investigations ordered by doctor — for billing desk to raise lab/procedure bills."""
    visits = (
        visits_for_clinic(db, user)
        .options(joinedload(Visit.patient))
        .filter(Visit.ordered_investigations.isnot(None), Visit.ordered_investigations != "")
        .order_by(Visit.visit_date.desc(), Visit.id.desc())
        .limit(60)
        .all()
    )
    items = []
    for v in visits:
        items.append({
            "visit_id": v.id,
            "patient_id": v.patient_id,
            "patient_name": v.patient.name if v.patient else "",
            "patient_mrd": v.patient.mrd_number if v.patient else None,
            "visit_date": v.visit_date.isoformat(),
            "diagnosis": v.diagnosis,
            "investigation": v.ordered_investigations,
            "billed": _visit_investigation_billed(db, v),
        })
    return items


@router.get("/pharmacy/prescriptions")
def pharmacy_prescriptions(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Drugs prescribed by doctor — for pharmacy desk to raise medicine bills."""
    rows = (
        db.query(Prescription)
        .join(Visit, Prescription.visit_id == Visit.id)
        .join(Patient, Visit.patient_id == Patient.id)
        .options(
            joinedload(Prescription.brand_medication),
            joinedload(Prescription.visit).joinedload(Visit.patient),
        )
        .filter(Patient.clinic_id == clinic_id_of(user))
    )
    chosen = desk_doctor_id(user)
    if chosen:
        rows = rows.filter(or_(Patient.doctor_id == chosen, Patient.doctor_id.is_(None)))
    rows = (
        rows
        .order_by(Prescription.created_at.desc())
        .limit(120)
        .all()
    )
    # Group by visit
    by_visit: dict[int, dict] = {}
    for rx in rows:
        visit = rx.visit
        if not visit:
            continue
        bucket = by_visit.get(visit.id)
        if not bucket:
            bucket = {
                "visit_id": visit.id,
                "patient_id": visit.patient_id,
                "patient_name": visit.patient.name if visit.patient else "",
                "patient_mrd": visit.patient.mrd_number if visit.patient else None,
                "visit_date": visit.visit_date.isoformat(),
                "diagnosis": visit.diagnosis,
                "billed": _visit_pharmacy_billed(db, visit.id),
                "prescriptions": [],
            }
            by_visit[visit.id] = bucket
        extra = enrich_prescription_response(rx)
        base = PrescriptionResponse.model_validate(rx).model_copy(update=extra)
        bucket["prescriptions"].append(base.model_dump(mode="json"))
    result = []
    for bucket in by_visit.values():
        lines = bucket["prescriptions"]
        notes = [line.get("dispense_note") for line in lines if line.get("dispense_note")]
        bucket["declined"] = bool(lines) and all((line.get("dispense_status") or "") == "declined" for line in lines)
        bucket["dispense_note"] = notes[-1] if notes else None
        result.append(bucket)
    return result


class DispenseDecline(BaseModel):
    visit_id: int
    note: str


@router.post("/pharmacy/prescriptions/decline")
def decline_dispense(
    data: DispenseDecline,
    user=Depends(require_role("pharmacy")),
    db: Session = Depends(get_db),
):
    """Patient did not buy these medicines at the clinic."""
    note = (data.note or "").strip()
    if len(note) < 3:
        raise HTTPException(status_code=400, detail="Add a short note for why the medicines were not dispensed")
    visit = ensure_visit_access(db, data.visit_id, user)
    rows = db.query(Prescription).filter(Prescription.visit_id == visit.id).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No prescription to decline")
    open_lines = [
        row for row in rows
        if (row.dispense_status or "pending") != "declined" and float(row.dispensed_quantity or 0) <= 0
    ]
    if not open_lines:
        raise HTTPException(status_code=400, detail="These medicines are already dispensed or declined")
    for row in open_lines:
        row.dispense_status = "declined"
        row.dispense_note = note
    db.commit()
    return {"success": True, "visit_id": visit.id, "declined": len(open_lines), "note": note}


def _payment_parts(data) -> list[tuple[str, float]] | None:
    parts = getattr(data, "payments", None) or None
    if not parts:
        return None
    rows: list[tuple[str, float]] = []
    for part in parts:
        amount = round(float(part.amount or 0), 2)
        if amount <= 0:
            continue
        rows.append(((part.method or "Cash").strip() or "Cash", amount))
    return rows or None


def _take_payments(db: Session, bill: Bill, parts: list[tuple[str, float]], user_id: int | None, cap: float) -> float:
    recorded = 0.0
    methods: list[str] = []
    room = round(max(float(cap or 0), 0), 2)
    for method, amount in parts:
        take = round(min(amount, room - recorded), 2)
        if take <= 0.009:
            break
        record_payment(db, bill, take, method, user_id)
        recorded = round(recorded + take, 2)
        methods.append(method)
    if methods:
        bill.payment_method = " + ".join(dict.fromkeys(methods))
    return recorded


def _paid_status(paid: float, total: float) -> str:
    if paid >= float(total or 0) - 0.009 and float(total or 0) > 0:
        return "paid"
    if paid > 0:
        return "partial"
    return "pending"


def _merge_visit_bill(db: Session, visit, data: BillCreate, user):
    existing = (
        db.query(Bill)
        .filter(
            Bill.visit_id == visit.id,
            Bill.payment_status.notin_(["cancelled", "refunded"]),
        )
        .order_by(Bill.id.desc())
        .first()
    )
    if not existing:
        return None
    # A closed day cannot be edited. A later pharmacy or lab sale opens a new invoice.
    if existing.created_at and _day_is_closed(db, clinic_id_of(user), clinic_day(existing.created_at)):
        return None
    _ensure_bill_day_editable(db, user, existing)
    from app.api.v1.clinic_admin import consume_lines

    priced = _compose_bill(data)
    new_lines = json.loads(priced["line_items"] or "[]")
    old_lines = json.loads(existing.line_items or "[]")
    if not old_lines:
        old_lines = [{
            "description": existing.description,
            "procedure_code": existing.procedure_code,
            "quantity": 1,
            "rate": existing.base_amount or existing.amount,
            "base_amount": existing.base_amount or existing.amount,
            "gst_percent": existing.gst_percent or 0,
            "gst_amount": existing.gst_amount or 0,
        }]
    lines = old_lines + new_lines
    consume_lines(db, clinic_id_of(user), new_lines)
    base = round(sum(float(line.get("base_amount") or 0) for line in lines), 2)
    gst = round(sum(float(line.get("gst_amount") or 0) for line in lines), 2)
    discount = min(
        round(float(existing.discount_amount or 0) + float(priced["discount_amount"] or 0), 2),
        base + gst,
    )
    total, round_off = _finish_total(max(base + gst - discount, 0))
    existing.base_amount = base
    existing.gst_amount = gst
    existing.discount_amount = discount
    existing.amount = total
    existing.round_off = round_off
    existing.line_items = json.dumps(lines)
    existing.description = ", ".join(line.get("description") or "" for line in lines)[:300]
    existing.category = "visit"
    if data.payment_method:
        existing.payment_method = data.payment_method
    previous_paid = float(existing.amount_paid or 0)
    parts = _payment_parts(data)
    if parts:
        recorded = _take_payments(db, existing, parts, user.id, round(total - previous_paid, 2))
        paid = round(previous_paid + recorded, 2)
    else:
        paid = min(round(previous_paid + float(priced.get("amount_paid") or 0), 2), total)
    existing.amount_paid = paid
    existing.payment_status = _paid_status(paid, total)
    annotate_bill(db, user, existing)
    if not parts:
        record_payment(db, existing, round(paid - previous_paid, 2), data.payment_method, user.id)
    record_dispensed(db, visit.id, new_lines)
    db.commit()
    db.refresh(existing)
    patient = db.get(Patient, visit.patient_id)
    return _bill_response(existing, patient)


@router.post("/bills", response_model=BillResponse, status_code=201)
def create_bill(data: BillCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "nurse":
        raise HTTPException(status_code=403, detail="Billing stays with the billing desk")
    visit = ensure_visit_access(db, data.visit_id, user)
    # One open invoice per visit: always append when an open bill exists
    merged = _merge_visit_bill(db, visit, data, user)
    if merged:
        return merged
    if _day_is_closed(db, clinic_id_of(user), clinic_day(datetime.utcnow())):
        raise HTTPException(status_code=400, detail="Today's collections are locked.")
    priced = _compose_bill(data)
    from app.api.v1.clinic_admin import consume_lines
    draft = data.payment_status == "draft"
    if draft:
        priced["payment_status"] = "draft"
        priced["amount_paid"] = 0
    else:
        lines = json.loads(priced["line_items"] or "[]")
        consume_lines(db, clinic_id_of(user), lines)
        if priced.get("line_items") is not None:
            priced["line_items"] = json.dumps(lines)

    bill = Bill(
        visit_id=data.visit_id,
        patient_id=visit.patient_id,
        doctor_id=owning_doctor_id(db, user),
        invoice_number=data.invoice_number or _next_invoice_number(db, clinic_id_of(user)),
        category=(data.category or "visit"),
        place_of_supply=resolve_place_of_supply(db, user, data.place_of_supply),
        **priced,
    )
    db.add(bill)
    db.flush()
    annotate_bill(db, user, bill)
    if not draft and data.advance_applied:
        room = round(float(bill.amount or 0) - float(bill.amount_paid or 0), 2)
        applied = apply_patient_advance(db, clinic_id_of(user), visit.patient_id, min(float(data.advance_applied), room))
        if applied > 0:
            bill.advance_applied = applied
            bill.amount_paid = round(float(bill.amount_paid or 0) + applied, 2)
            bill.payment_status = _paid_status(float(bill.amount_paid or 0), float(bill.amount or 0))
            record_payment(db, bill, applied, "Advance", user.id, kind="advance_apply", note="Patient advance")
    parts = _payment_parts(data)
    if not draft and parts:
        room = round(float(bill.amount or 0) - float(bill.advance_applied or 0), 2)
        recorded = _take_payments(db, bill, parts, user.id, room)
        bill.amount_paid = round(float(bill.advance_applied or 0) + recorded, 2)
        bill.payment_status = _paid_status(float(bill.amount_paid or 0), float(bill.amount or 0))
    elif not draft:
        record_payment(db, bill, float(priced.get("amount_paid") or 0), bill.payment_method, user.id)
    if not draft:
        record_dispensed(db, visit.id, json.loads(priced["line_items"] or "[]"))
    write_audit(
        db,
        user_id=user.id,
        action="bill.create",
        entity_type="bill",
        entity_id=None,
        details=f"visit={visit.id} amount={priced.get('amount')}",
    )
    db.commit()
    db.refresh(bill)
    patient = db.get(Patient, visit.patient_id)
    return _bill_response(bill, patient)


@router.patch("/bills/{bill_id}", response_model=BillResponse)
def update_bill(bill_id: int, data: BillUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    ensure_patient_access(db, bill.patient_id, user)
    if bill.payment_status == "cancelled":
        raise HTTPException(status_code=400, detail="This invoice is cancelled")
    invoice_day = clinic_day(bill.created_at or datetime.utcnow())
    clinic_id = clinic_id_of(user)
    if _day_is_closed(db, clinic_id, invoice_day) and not _is_later_receipt(data, bill):
        raise HTTPException(status_code=400, detail="This day's collections are locked. Re-open day close to edit.")
    if _day_is_closed(db, clinic_id, clinic_day(datetime.utcnow())):
        raise HTTPException(status_code=400, detail="Today's collections are locked. Re-open day close to record this receipt.")
    from app.api.v1.clinic_admin import restore_lines

    if data.refund_amount:
        if not (data.refund_reason or "").strip():
            raise HTTPException(status_code=400, detail="Enter a reason for the refund")
        refund = min(float(data.refund_amount), float(bill.amount_paid or 0))
        bill.refund_amount = round(float(bill.refund_amount or 0) + refund, 2)
        bill.refund_reason = data.refund_reason.strip()
        bill.amount_paid = round(max(float(bill.amount_paid or 0) - refund, 0), 2)
        bill.payment_status = "refunded" if bill.amount_paid <= 0 else "partial"
        if bill.payment_status == "refunded":
            restore_lines(db, clinic_id_of(user), _bill_lines(bill))
        write_audit(
            db,
            user_id=user.id,
            action="bill.refund",
            entity_type="bill",
            entity_id=bill.id,
            details=f"refund={refund} reason={bill.refund_reason}",
        )
        record_payment(db, bill, -refund, bill.payment_method, user.id, kind="refund", note=bill.refund_reason)
        issue_credit_note(db, user, bill, refund, bill.refund_reason or "")
        db.commit()
        db.refresh(bill)
        patient = db.get(Patient, bill.patient_id)
        return _bill_response(bill, patient)
    if data.payment_status == "cancelled":
        bill.payment_status = "cancelled"
        restore_lines(db, clinic_id_of(user), _bill_lines(bill))
        issue_credit_note(db, user, bill, float(bill.amount or 0), data.refund_reason or "Invoice cancelled")
        write_audit(
            db,
            user_id=user.id,
            action="bill.cancel",
            entity_type="bill",
            entity_id=bill.id,
            details=bill.invoice_number,
        )
    else:
        previous_paid = float(bill.amount_paid or 0)
        parts = _payment_parts(data)
        if parts:
            recorded = _take_payments(db, bill, parts, user.id, round(float(bill.amount or 0) - previous_paid, 2))
            bill.amount_paid = round(previous_paid + recorded, 2)
            bill.payment_status = _paid_status(float(bill.amount_paid or 0), float(bill.amount or 0))
        elif data.amount_paid is not None:
            paid = min(max(float(data.amount_paid), 0.0), float(bill.amount))
            bill.amount_paid = round(paid, 2)
            bill.payment_status = _paid_status(paid, float(bill.amount or 0))
        elif data.payment_status == "paid":
            bill.amount_paid = bill.amount
            bill.payment_status = "paid"
        elif data.payment_status is not None:
            bill.payment_status = data.payment_status
        if data.description is not None:
            bill.description = data.description
        if not parts:
            if data.payment_method is not None:
                bill.payment_method = data.payment_method
            delta = round(float(bill.amount_paid or 0) - previous_paid, 2)
            if delta > 0:
                record_payment(db, bill, delta, bill.payment_method, user.id)
            elif delta < 0:
                record_payment(db, bill, delta, bill.payment_method, user.id, kind="refund")
    db.commit()
    db.refresh(bill)
    patient = db.get(Patient, bill.patient_id)
    return _bill_response(bill, patient)


@router.post("/bills/{bill_id}/debit-note", response_model=BillResponse)
def create_debit_note(bill_id: int, data: DebitNoteIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    ensure_patient_access(db, bill.patient_id, user)
    if bill.payment_status in {"cancelled", "draft"}:
        raise HTTPException(status_code=400, detail="This invoice cannot take a debit note")
    if _day_is_closed(db, clinic_id_of(user), clinic_day(bill.created_at or datetime.utcnow())):
        raise HTTPException(status_code=400, detail="This day's collections are locked. Re-open day close to edit.")
    add_debit_note(db, user, bill, data.amount, data.gst_percent, data.reason)
    write_audit(db, user_id=user.id, action="bill.debit_note", entity_type="bill", entity_id=bill.id, details=bill.debit_note_number)
    db.commit()
    db.refresh(bill)
    return _bill_response(bill, db.get(Patient, bill.patient_id))


@router.post("/bills/{bill_id}/whatsapp")
def whatsapp_invoice(bill_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    patient = ensure_patient_access(db, bill.patient_id, user)
    due = max(float(bill.amount or 0) - float(bill.amount_paid or 0), 0)
    message = (
        f"Invoice {bill.invoice_number or bill.id} for {patient.name}: "
        f"₹{bill.amount:.0f} (paid ₹{float(bill.amount_paid or 0):.0f}, due ₹{due:.0f}). "
        f"Thank you."
    )
    link = whatsapp_link(patient.contact, message)
    return {"success": True, "whatsapp_url": link, "message": message}


def _closed_day_totals(row: DayClose) -> dict:
    """Figures stored when the day was locked. A later receipt does not rewrite them."""
    cash = round(float(row.cash_total or 0), 2)
    upi = round(float(row.upi_total or 0), 2)
    card = round(float(row.card_total or 0), 2)
    other = round(float(row.other_total or 0), 2)
    billed = round(float(row.billed_total or 0), 2)
    collected = round(float(row.collected_total or 0), 2)
    return {
        "date": row.close_date.isoformat(),
        "close_date": row.close_date.isoformat(),
        "cash": cash,
        "upi": upi,
        "card": card,
        "bank": 0,
        "other": other,
        "billed": billed,
        "collected": collected,
        "cash_total": cash,
        "upi_total": upi,
        "card_total": card,
        "other_total": other,
        "billed_total": billed,
        "collected_total": collected,
        "invoice_count": 0,
    }


def _day_close_totals(db: Session, clinic_id: int, day: date) -> dict:
    opening, closing = clinic_period_utc(day, day)
    bills = (
        db.query(Bill)
        .join(Patient, Bill.patient_id == Patient.id)
        .filter(
            Patient.clinic_id == clinic_id,
            Bill.created_at >= opening,
            Bill.created_at < closing,
            Bill.payment_status != "cancelled",
        )
        .all()
    )
    payments = (
        db.query(BillPayment)
        .filter(
            BillPayment.clinic_id == clinic_id,
            BillPayment.created_at >= opening,
            BillPayment.created_at < closing,
        )
        .all()
    )
    cash = upi = card = bank = other = 0.0
    billed = collected = 0.0

    def add_mode(method: str | None, amount: float) -> None:
        nonlocal cash, upi, card, bank, other
        label = (method or "").strip().lower()
        if "cash" in label:
            cash += amount
        elif "upi" in label:
            upi += amount
        elif "card" in label:
            card += amount
        elif "bank" in label or "transfer" in label:
            bank += amount
        else:
            other += amount

    for payment in payments:
        if (payment.kind or "") == "advance_apply":
            continue
        amount = float(payment.amount or 0)
        collected += amount
        add_mode(payment.method, amount)
    advances = (
        db.query(PatientAdvance)
        .filter(
            PatientAdvance.clinic_id == clinic_id,
            PatientAdvance.created_at >= opening,
            PatientAdvance.created_at < closing,
        )
        .all()
    )
    for advance in advances:
        collected += float(advance.amount or 0)
        add_mode(advance.method, float(advance.amount or 0))
    bill_ids = [bill.id for bill in bills]
    paid_bill_ids = set()
    if bill_ids:
        paid_bill_ids = {
            row[0]
            for row in db.query(BillPayment.bill_id).filter(BillPayment.bill_id.in_(bill_ids)).all()
        }
    for bill in bills:
        billed += float(bill.amount or 0)
        if bill.id in paid_bill_ids:
            continue
        paid = max(float(bill.amount_paid or 0) - float(bill.refund_amount or 0), 0)
        collected += paid
        add_mode(bill.payment_method, paid)
    return {
        "date": day.isoformat(),
        "close_date": day.isoformat(),
        "cash": round(cash, 2),
        "upi": round(upi, 2),
        "card": round(card, 2),
        "bank": round(bank, 2),
        "other": round(other, 2),
        "billed": round(billed, 2),
        "collected": round(collected, 2),
        "cash_total": round(cash, 2),
        "upi_total": round(upi, 2),
        "card_total": round(card, 2),
        "other_total": round(other, 2),
        "billed_total": round(billed, 2),
        "collected_total": round(collected, 2),
        "invoice_count": len(bills),
    }


@router.get("/day-close")
def day_close_summary(
    day: date | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    day = day or clinic_day(datetime.utcnow())
    clinic_id = clinic_id_of(user)
    locked = _day_is_closed(db, clinic_id, day)
    totals = _closed_day_totals(locked) if locked else _day_close_totals(db, clinic_id, day)
    totals["locked"] = locked is not None
    totals["locked_at"] = locked.closed_at.isoformat() if locked and locked.closed_at else None
    totals["notes"] = locked.notes if locked else None
    totals["opening_cash"] = round(float(locked.opening_cash or 0), 2) if locked else 0
    totals["closing_cash"] = round(float(locked.closing_cash or 0), 2) if locked else 0
    return totals


class DayCloseLockRequest(BaseModel):
    notes: str | None = None
    day: date | None = None
    opening_cash: float = 0
    closing_cash: float | None = None


@router.post("/day-close")
def lock_day_close(
    payload: DayCloseLockRequest = Body(default_factory=DayCloseLockRequest),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    day = payload.day or clinic_day(datetime.utcnow())
    notes = payload.notes
    opening = round(float(payload.opening_cash or 0), 2)
    if opening < 0:
        raise HTTPException(status_code=400, detail="Opening cash cannot be negative")
    clinic_id = clinic_id_of(user)
    existing = _day_is_closed(db, clinic_id, day)
    if existing:
        raise HTTPException(status_code=400, detail="This day is already locked")
    totals = _day_close_totals(db, clinic_id, day)
    row = DayClose(
        clinic_id=clinic_id,
        close_date=day,
        cash_total=totals["cash_total"],
        upi_total=totals["upi_total"],
        card_total=totals["card_total"],
        other_total=totals["other_total"],
        billed_total=totals["billed_total"],
        collected_total=totals["collected_total"],
        opening_cash=opening,
        closing_cash=round(float(payload.closing_cash), 2) if payload.closing_cash is not None else round(opening + totals["cash"], 2),
        closed_by=user.id,
        notes=notes,
    )
    if row.closing_cash < 0:
        raise HTTPException(status_code=400, detail="Closing cash cannot be negative")
    db.add(row)
    write_audit(
        db,
        user_id=user.id,
        action="day_close.lock",
        entity_type="day_close",
        entity_id=None,
        details=day.isoformat(),
    )
    db.commit()
    db.refresh(row)
    return {
        **totals,
        "locked": True,
        "id": row.id,
        "locked_at": row.closed_at.isoformat() if row.closed_at else None,
        "notes": notes,
        "opening_cash": row.opening_cash,
        "closing_cash": row.closing_cash,
    }


class DayCloseReopenRequest(BaseModel):
    day: date | None = None


@router.post("/day-close/reopen")
def reopen_day_close(
    payload: DayCloseReopenRequest = Body(default_factory=DayCloseReopenRequest),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in ("doctor", "admin"):
        raise HTTPException(status_code=403, detail="Only an admin or doctor can open a locked day")
    day = payload.day or clinic_day(datetime.utcnow())
    clinic_id = clinic_id_of(user)
    row = _day_is_closed(db, clinic_id, day)
    if not row:
        raise HTTPException(status_code=404, detail="This day is not locked")
    db.delete(row)
    write_audit(
        db,
        user_id=user.id,
        action="day_close.reopen",
        entity_type="day_close",
        entity_id=row.id,
        details=day.isoformat(),
    )
    db.commit()
    totals = _day_close_totals(db, clinic_id, day)
    totals["locked"] = False
    totals["locked_at"] = None
    totals["notes"] = None
    totals["opening_cash"] = 0
    totals["closing_cash"] = 0
    return totals


@router.get("/day-close/locks")
def list_locked_days(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(DayClose)
        .filter(DayClose.clinic_id == clinic_id_of(user))
        .order_by(DayClose.close_date.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "date": row.close_date.isoformat(),
            "locked_at": row.closed_at.isoformat() if row.closed_at else None,
            "notes": row.notes,
        }
        for row in rows
    ]


@router.get("/analytics")
def analytics(user=Depends(require_role()), db: Session = Depends(get_db)):
    from collections import Counter
    from sqlalchemy import func, extract
    from app.models import BrandMedication

    visits = visits_for_clinic(db, user).all()
    diag_counter = Counter()
    for v in visits:
        if v.diagnosis:
            diag_counter[v.diagnosis.split(",")[0].strip()] += 1

    monthly = (
        db.query(extract("month", Visit.visit_date).label("month"), func.count(Visit.id))
        .join(Patient, Visit.patient_id == Patient.id)
        .filter(Patient.clinic_id == clinic_id_of(user))
        .group_by("month")
        .all()
    )

    rx_counts = (
        db.query(Prescription.brand_medication_id, func.count(Prescription.id))
        .join(Visit)
        .join(Patient, Visit.patient_id == Patient.id)
        .filter(Patient.clinic_id == clinic_id_of(user))
        .group_by(Prescription.brand_medication_id)
        .order_by(func.count(Prescription.id).desc())
        .limit(10)
        .all()
    )
    top_meds = []
    for brand_id, count in rx_counts:
        brand = db.get(BrandMedication, brand_id)
        top_meds.append({"drug": brand.brand_name if brand else str(brand_id), "count": count})

    bills = (
        db.query(Bill)
        .join(Patient, Bill.patient_id == Patient.id)
        .filter(Patient.clinic_id == clinic_id_of(user))
        .all()
    )
    total = sum(b.amount for b in bills)
    paid = sum(b.amount for b in bills if b.payment_status == "paid")
    gst_collected = sum(b.gst_amount or 0 for b in bills if b.payment_status == "paid")

    payload = {
        "diagnosis_distribution": [{"diagnosis": k, "count": v} for k, v in diag_counter.most_common(10)],
        "visit_volume_by_month": [{"month": int(m), "count": c} for m, c in monthly],
        "top_medications": top_meds,
        "revenue_summary": {"total_billed": total, "total_paid": paid, "pending": total - paid, "gst_collected": gst_collected},
    }
    from app.services.practice_analytics import practice_analytics

    payload["practice"] = practice_analytics(db, user)
    return payload
