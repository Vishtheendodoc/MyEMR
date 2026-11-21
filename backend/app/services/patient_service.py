"""Patient registration helpers."""

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Patient
from app.services.clinic_time import clinic_wall_now


def normalize_mrd(mrd: str | None) -> str | None:
    if mrd is None:
        return None
    cleaned = mrd.strip().upper()
    return cleaned or None


def is_temporary_mrd(mrd: str | None) -> bool:
    return bool(mrd and str(mrd).upper().startswith("TMP-"))


def _next_serial(db: Session, clinic_id: int, prefix: str) -> str:
    """Lowest free yearly number. A cancelled registration gives its number back."""
    rows = (
        db.query(Patient.mrd_number)
        .filter(Patient.mrd_number.like(f"{prefix}%"))
        .all()
    )
    used = set()
    for (number,) in rows:
        tail = str(number)[len(prefix):]
        if tail.isdigit():
            used.add(int(tail))
    seq = 1
    while True:
        if seq not in used:
            candidate = f"{prefix}{seq:05d}"
            held = db.query(Patient).filter(Patient.mrd_number == candidate).first()
            if not held:
                return candidate
        seq += 1


def next_clinic_mrd(db: Session, clinic_id: int) -> str:
    """Permanent MRD, the usual Indian clinic form: MRD-year-serial."""
    prefix = f"MRD-{clinic_wall_now().year}-"
    return _next_serial(db, clinic_id, prefix)


def next_temp_mrd(db: Session, clinic_id: int) -> str:
    """Temporary id for a booking made before the patient reaches the desk."""
    prefix = f"TMP-{clinic_wall_now().year}-"
    return _next_serial(db, clinic_id, prefix)


def ensure_mrd_available(
    db: Session,
    mrd: str | None,
    *,
    exclude_patient_id: int | None = None,
    clinic_id: int | None = None,
    auto_assign: bool = False,
) -> str | None:
    """Return normalized MRD or raise if already registered. Auto-assign when blank."""
    normalized = normalize_mrd(mrd)
    if not normalized:
        if auto_assign and clinic_id is not None:
            return next_clinic_mrd(db, clinic_id)
        return None
    query = db.query(Patient).filter(Patient.mrd_number == normalized)
    if exclude_patient_id:
        query = query.filter(Patient.id != exclude_patient_id)
    existing = query.first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"MRD number '{normalized}' is already registered for {existing.name}",
        )
    return normalized


def mobile_digits(raw: str | None) -> str | None:
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def patient_with_mobile(db: Session, clinic_id: int | None, contact: str | None, exclude_id: int | None = None) -> Patient | None:
    ten = mobile_digits(contact)
    if not ten:
        return None
    query = db.query(Patient).filter(
        Patient.contact.isnot(None),
        Patient.contact.contains(ten),
        or_(Patient.registration_status.is_(None), Patient.registration_status != "cancelled"),
    )
    if clinic_id is not None:
        query = query.filter(Patient.clinic_id == clinic_id)
    rows = query.all()
    for row in rows:
        if exclude_id and row.id == exclude_id:
            continue
        if mobile_digits(row.contact) == ten:
            return row
    return None


def ensure_mobile_available(db: Session, clinic_id: int, contact: str | None, exclude_id: int | None = None) -> None:
    existing = patient_with_mobile(db, clinic_id, contact, exclude_id)
    if not existing:
        return
    label = existing.mrd_number or "no MRD"
    raise HTTPException(
        status_code=400,
        detail=f"This mobile is already registered for {existing.name} ({label})",
    )


def find_duplicate_patients(db: Session, clinic_id: int | None, name: str, contact: str | None, exclude_id: int | None = None):
    hits = []
    q = db.query(Patient)
    if clinic_id is not None:
        q = q.filter(Patient.clinic_id == clinic_id)
    if exclude_id:
        q = q.filter(Patient.id != exclude_id)
    existing = patient_with_mobile(db, clinic_id, contact, exclude_id)
    if existing:
        hits.append({"id": existing.id, "name": existing.name, "mrd_number": existing.mrd_number, "contact": existing.contact, "match": "mobile"})
    stem = (name or "").strip().lower()
    if len(stem) >= 3:
        for p in q.filter(Patient.name.ilike(f"%{stem}%")).limit(8).all():
            if any(h["id"] == p.id for h in hits):
                continue
            hits.append({"id": p.id, "name": p.name, "mrd_number": p.mrd_number, "contact": p.contact, "match": "name"})
    return hits[:8]
