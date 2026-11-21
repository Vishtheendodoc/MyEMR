"""WhatsApp / reminder helpers for appointments and follow-ups."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import quote

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models import Appointment, Patient, ReminderLog, User, Visit  # Patient used in clinic joins


def normalize_phone(raw: str | None, default_country: str = "91") -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if len(digits) == 10:
        return f"{default_country}{digits}"
    if digits.startswith("0") and len(digits) == 11:
        return f"{default_country}{digits[1:]}"
    if digits.startswith(default_country) and len(digits) >= 12:
        return digits
    return digits


def whatsapp_link(phone: str | None, message: str) -> str | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    return f"https://wa.me/{normalized}?text={quote(message)}"


def plain_doctor_name(name: str | None) -> str:
    text = (name or "").strip()
    if text.lower().startswith("dr."):
        text = text[3:].strip()
    elif text.lower().startswith("dr "):
        text = text[3:].strip()
    return text


def reminder_names(db: Session, clinic_id: int | None, fallback_doctor: str | None) -> tuple[str, str]:
    from app.models import ClinicProfile

    row = db.get(ClinicProfile, clinic_id) if clinic_id else None
    clinic = ""
    doctor = ""
    if row:
        clinic = (row.reminder_clinic_name or row.name or "").strip()
        doctor = plain_doctor_name(row.reminder_doctor_name)
    if not clinic:
        clinic = settings.clinic_name or "the clinic"
    if not doctor:
        doctor = plain_doctor_name(fallback_doctor) or "the doctor"
    return clinic, doctor


def reminder_is_cancelled(db: Session, source_type: str, source_id: int) -> bool:
    return (
        db.query(ReminderLog)
        .filter(
            ReminderLog.source_type == source_type,
            ReminderLog.source_id == source_id,
            ReminderLog.status == "cancelled",
        )
        .first()
        is not None
    )


def format_appt_message(patient_name: str, doctor_name: str, when: datetime, notes: str | None = None, clinic: str | None = None) -> str:
    clinic = clinic or settings.clinic_name or "clinic"
    doctor_name = plain_doctor_name(doctor_name) or "the doctor"
    stamp = when.strftime("%d %b %Y, %I:%M %p")
    msg = (
        f"Namaste {patient_name},\n"
        f"This is a reminder for your appointment with Dr. {doctor_name} "
        f"on {stamp} at {clinic}.\n"
        f"Please arrive 10 minutes early. Reply if you need to reschedule."
    )
    if notes:
        msg += f"\nNote: {notes}"
    return msg


def format_followup_message(patient_name: str, doctor_name: str, due: date, diagnosis: str | None = None, clinic: str | None = None) -> str:
    clinic = clinic or settings.clinic_name or "clinic"
    doctor_name = plain_doctor_name(doctor_name) or "the doctor"
    stamp = due.strftime("%d %b %Y")
    msg = (
        f"Namaste {patient_name},\n"
        f"This is a reminder that your follow-up with Dr. {doctor_name} "
        f"is due on {stamp} at {clinic}."
    )
    if diagnosis:
        msg += f"\nRegarding: {diagnosis}"
    msg += "\nPlease call the clinic to confirm your slot."
    return msg


def twilio_configured() -> bool:
    return bool(
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_whatsapp_from
    )


def send_whatsapp_twilio(to_phone: str, message: str) -> tuple[bool, str | None]:
    """Send via Twilio WhatsApp API when configured. Returns (ok, error)."""
    if not twilio_configured():
        return False, "Twilio WhatsApp is not configured"
    try:
        from urllib.request import Request, urlopen
        import base64
        import json as _json

        to = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:+{to_phone}"
        frm = settings.twilio_whatsapp_from
        if not frm.startswith("whatsapp:"):
            frm = f"whatsapp:{frm}"

        body = f"To={quote(to)}&From={quote(frm)}&Body={quote(message)}"
        auth = base64.b64encode(
            f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode()
        ).decode()
        req = Request(
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
            data=body.encode(),
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urlopen(req, timeout=20) as resp:
            payload = _json.loads(resp.read().decode())
            sid = payload.get("sid")
            return True, sid
    except Exception as exc:  # noqa: BLE001 — surface to UI
        return False, str(exc)


def appointment_reminder_date(appt_day: date) -> date:
    """Remind 1 day prior; Monday appointments are reminded on Friday."""
    if appt_day.weekday() == 0:  # Monday
        return appt_day - timedelta(days=3)  # Friday
    return appt_day - timedelta(days=1)


def recent_reminder(
    db: Session,
    doctor_id: int,
    source_type: str,
    source_id: int,
    within_hours: int = 72,
) -> ReminderLog | None:
    cutoff = datetime.utcnow() - timedelta(hours=within_hours)
    return (
        db.query(ReminderLog)
        .filter(
            ReminderLog.doctor_id == doctor_id,
            ReminderLog.source_type == source_type,
            ReminderLog.source_id == source_id,
            ReminderLog.status.in_(["sent", "opened", "queued"]),
            ReminderLog.sent_at.isnot(None),
            ReminderLog.sent_at >= cutoff,
        )
        .order_by(ReminderLog.sent_at.desc())
        .first()
    )


def build_reminder_queue(db: Session, doctor_id: int, doctor_name: str, days_ahead: int = 3, clinic_id: int | None = None) -> list[dict]:
    today = date.today()
    # Include Mon appointments reminded on Friday (up to +3 days from reminder day)
    horizon = today + timedelta(days=max(days_ahead, 3))
    items: list[dict] = []
    clinic_label, doctor_label = reminder_names(db, clinic_id, doctor_name)

    appt_q = (
        db.query(Appointment)
        .options(joinedload(Appointment.patient))
        .join(Patient, Appointment.patient_id == Patient.id)
        .filter(
            Appointment.status == "scheduled",
            Appointment.scheduled_at >= datetime.combine(today, datetime.min.time()),
            Appointment.scheduled_at < datetime.combine(horizon + timedelta(days=1), datetime.min.time()),
        )
    )
    if clinic_id is not None:
        appt_q = appt_q.filter(Patient.clinic_id == clinic_id)
    else:
        appt_q = appt_q.filter(Appointment.doctor_id == doctor_id)
    appts = appt_q.order_by(Appointment.scheduled_at.asc()).all()
    covered_visits: set[int] = set()
    for a in appts:
        match = re.search(r"Follow-up from visit #(\d+)", a.notes or "")
        if match:
            covered_visits.add(int(match.group(1)))
        if a.patient and (a.patient.registration_status or "") == "cancelled":
            continue
        if reminder_is_cancelled(db, "appointment", a.id):
            continue
        phone = a.patient.contact if a.patient else None
        message = format_appt_message(a.patient.name if a.patient else "Patient", doctor_label, a.scheduled_at, a.notes, clinic_label)
        last = recent_reminder(db, doctor_id, "appointment", a.id)
        rem_on = appointment_reminder_date(a.scheduled_at.date())
        items.append({
            "id": f"appt-{a.id}",
            "source_type": "appointment",
            "source_id": a.id,
            "visit_id": int(match.group(1)) if match else None,
            "patient_id": a.patient_id,
            "patient_name": a.patient.name if a.patient else "",
            "patient_mrd": a.patient.mrd_number if a.patient else None,
            "patient_contact": phone,
            "due_at": a.scheduled_at.isoformat(),
            "remind_on": rem_on.isoformat(),
            "auto_due_today": rem_on == today,
            "label": "Appointment",
            "detail": a.notes,
            "message": message,
            "whatsapp_url": whatsapp_link(phone, message),
            "already_reminded": last is not None,
            "last_reminded_at": last.sent_at.isoformat() if last and last.sent_at else None,
        })

    visit_q = (
        db.query(Visit)
        .options(joinedload(Visit.patient))
        .join(Patient, Visit.patient_id == Patient.id)
        .filter(
            Visit.follow_up_date.isnot(None),
            Visit.follow_up_date <= horizon,
        )
    )
    if clinic_id is not None:
        visit_q = visit_q.filter(Patient.clinic_id == clinic_id)
    else:
        visit_q = visit_q.filter(Visit.doctor_id == doctor_id)
    visits = visit_q.order_by(Visit.follow_up_date.asc()).all()
    for v in visits:
        if v.patient and (v.patient.registration_status or "") == "cancelled":
            continue
        if reminder_is_cancelled(db, "follow_up", v.id):
            continue
        from app.services.appointment_service import follow_up_calendar_outcome
        if follow_up_calendar_outcome(db, v) in {"cancelled", "done"}:
            continue
        if v.id in covered_visits:
            continue
        phone = v.patient.contact if v.patient else None
        message = format_followup_message(
            v.patient.name if v.patient else "Patient",
            doctor_label,
            v.follow_up_date,
            v.diagnosis,
            clinic_label,
        )
        last = recent_reminder(db, doctor_id, "follow_up", v.id)
        rem_on = appointment_reminder_date(v.follow_up_date)
        items.append({
            "id": f"fu-{v.id}",
            "source_type": "follow_up",
            "source_id": v.id,
            "patient_id": v.patient_id,
            "patient_name": v.patient.name if v.patient else "",
            "patient_mrd": v.patient.mrd_number if v.patient else None,
            "patient_contact": phone,
            "due_at": v.follow_up_date.isoformat(),
            "remind_on": rem_on.isoformat(),
            "auto_due_today": rem_on == today,
            "label": "Follow-up",
            "detail": v.follow_up_notes or v.diagnosis,
            "message": message,
            "whatsapp_url": whatsapp_link(phone, message),
            "already_reminded": last is not None,
            "last_reminded_at": last.sent_at.isoformat() if last and last.sent_at else None,
        })

    items.sort(key=lambda x: (not x.get("auto_due_today"), x["due_at"]))
    return items


def process_due_auto_reminders(db: Session) -> dict:
    """Send (or queue) appointment reminders due today for all doctors.

    Rule: 1 day before appointment; Monday appointments → Friday reminder.
    Uses Twilio when configured; otherwise logs queued items for staff WhatsApp click.
    """
    today = date.today()
    doctors = db.query(User).filter(User.role.in_(["doctor", "admin"])).all()
    if not doctors:
        doctors = db.query(User).all()

    sent = 0
    queued = 0
    failed = 0
    skipped = 0
    details: list[dict] = []

    # Look ahead far enough to catch Monday appts when today is Friday
    window_end = today + timedelta(days=4)

    for doctor in doctors:
        appts = (
            db.query(Appointment)
            .options(joinedload(Appointment.patient))
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.status == "scheduled",
                Appointment.scheduled_at >= datetime.combine(today, datetime.min.time()),
                Appointment.scheduled_at < datetime.combine(window_end + timedelta(days=1), datetime.min.time()),
            )
            .all()
        )
        for appt in appts:
            rem_on = appointment_reminder_date(appt.scheduled_at.date())
            if rem_on != today:
                continue
            if reminder_is_cancelled(db, "appointment", appt.id):
                skipped += 1
                continue
            if recent_reminder(db, doctor.id, "appointment", appt.id, within_hours=72):
                skipped += 1
                continue
            patient = appt.patient
            if not patient or (patient.registration_status or "") == "cancelled":
                failed += 1
                continue
            clinic_label, doctor_label = reminder_names(db, patient.clinic_id, doctor.doctor_name)
            message = format_appt_message(patient.name, doctor_label, appt.scheduled_at, appt.notes, clinic_label)
            auto = twilio_configured()
            result = log_and_send_reminder(
                db,
                doctor=doctor,
                patient=patient,
                source_type="appointment",
                source_id=appt.id,
                message=message,
                auto_send=auto,
                scheduled_for=appt.scheduled_at,
            )
            if result["status"] == "sent":
                sent += 1
            elif result["status"] in ("opened", "queued"):
                queued += 1
            else:
                failed += 1
            details.append({
                "appointment_id": appt.id,
                "patient_name": patient.name,
                "remind_on": rem_on.isoformat(),
                "appointment_at": appt.scheduled_at.isoformat(),
                "status": result["status"],
                "whatsapp_url": result.get("whatsapp_url"),
            })

    return {
        "date": today.isoformat(),
        "auto_send_available": twilio_configured(),
        "sent": sent,
        "queued": queued,
        "failed": failed,
        "skipped": skipped,
        "details": details,
    }


def log_and_send_reminder(
    db: Session,
    *,
    doctor: User,
    patient: Patient,
    source_type: str,
    source_id: int,
    message: str,
    channel: str = "whatsapp",
    auto_send: bool = False,
    scheduled_for: datetime | None = None,
) -> dict:
    phone = normalize_phone(patient.contact)
    link = whatsapp_link(patient.contact, message)
    status = "opened"
    error = None
    channel_used = channel

    if auto_send and twilio_configured() and phone:
        ok, err = send_whatsapp_twilio(phone, message)
        if ok:
            status = "sent"
            channel_used = "whatsapp_api"
        else:
            status = "failed"
            error = err
            channel_used = "whatsapp_api"
    elif auto_send and not twilio_configured():
        # No API keys — queue for staff to open WhatsApp click-to-chat
        status = "queued"
        channel_used = "whatsapp"
        error = "Queued for WhatsApp click-to-chat (Twilio not configured)"

    log = ReminderLog(
        doctor_id=doctor.id,
        patient_id=patient.id,
        source_type=source_type,
        source_id=source_id,
        channel=channel_used,
        status=status,
        phone=phone,
        message=message,
        error=error,
        scheduled_for=scheduled_for,
        sent_at=datetime.utcnow() if status in ("sent", "opened", "queued") else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return {
        "id": log.id,
        "status": log.status,
        "channel": log.channel,
        "whatsapp_url": link,
        "phone": phone,
        "message": message,
        "error": error,
        "auto_send_available": twilio_configured(),
    }


def video_caption(clinic: str, patient_name: str, message: str, video_title: str) -> str:
    name = (patient_name or "there").strip()
    note = (message or "").strip().replace("{name}", name).replace("{clinic}", clinic)
    lines = [f"Namaste {name},"]
    title = (video_title or "").strip()
    if title:
        lines.append(title)
    if note:
        lines.append(note)
    lines.append(f"— {clinic}")
    return "\n".join(lines)


def render_broadcast(kind: str, clinic: str, patient_name: str, message: str, video_title: str, video_url: str, as_file: bool = False) -> str:
    name = (patient_name or "there").strip()
    note = (message or "").strip()
    if kind == "video" and as_file:
        return video_caption(clinic, name, note, video_title)
    if kind == "video":
        title = (video_title or "").strip()
        heading = f"Namaste {name},\n{clinic} has shared a short video"
        if title:
            heading += f": {title}"
        text = f"{heading}\n{video_url.strip()}"
        if note:
            text += f"\n{note}"
        return text
    body = note or f"Warm wishes from {clinic}. We hope you are keeping well."
    body = body.replace("{name}", name).replace("{clinic}", clinic)
    if name.lower() not in body.lower():
        body = f"Namaste {name},\n{body}"
    if clinic.lower() not in body.lower():
        body += f"\n— {clinic}"
    return body


def broadcast_registered(db: Session, user, kind: str, message: str, video_title: str, video_url: str, deliver: bool, as_file: bool = False, audience: str = "patients") -> dict:
    """Greeting, note, or video. The test list never includes patient mobiles."""
    from app.models import MessageContact
    from app.services.clinic_scope import clinic_id_of, patients_query

    clinic = settings.clinic_name or "the clinic"
    clinic_id = clinic_id_of(user)
    people: list[tuple[int | None, str, str]] = []
    seen: set[str] = set()
    items = []
    skipped = 0
    delivered = 0
    failed = 0
    use_api = deliver and twilio_configured() and not as_file
    test_only = audience == "test"
    if not test_only:
        rows = patients_query(db, user).order_by(Patient.name.asc()).all()
        for patient in rows:
            mrd = (patient.mrd_number or "").upper()
            if mrd == "WALKIN" or mrd.startswith("TMP-") or (patient.registration_status or "") == "temporary":
                continue
            phone = normalize_phone(patient.contact)
            if not phone:
                skipped += 1
                continue
            seen.add(phone)
            people.append((patient.id, patient.name, phone))
    saved = (
        db.query(MessageContact)
        .filter(
            MessageContact.clinic_id == clinic_id,
            MessageContact.list_kind == ("test" if test_only else "saved"),
        )
        .order_by(MessageContact.name.asc())
        .all()
    )
    for contact in saved:
        phone = normalize_phone(contact.phone)
        if not phone or phone in seen:
            continue
        seen.add(phone)
        people.append((None, contact.name, phone))
    for patient_id, person_name, phone in people:
        text = render_broadcast(kind, clinic, person_name, message, video_title, video_url, as_file)
        link = None if as_file else whatsapp_link(phone, text)
        status = "queued"
        error = None
        if use_api:
            ok, detail = send_whatsapp_twilio(phone, text)
            status = "sent" if ok else "failed"
            error = None if ok else detail
            if ok:
                delivered += 1
            else:
                failed += 1
        items.append({
            "patient_id": patient_id,
            "name": person_name,
            "phone": phone,
            "whatsapp_url": link,
            "status": status,
        })
    db.commit()
    return {
        "audience": len(items),
        "skipped_without_phone": skipped,
        "delivered": delivered,
        "failed": failed,
        "twilio": twilio_configured(),
        "items": items,
    }
