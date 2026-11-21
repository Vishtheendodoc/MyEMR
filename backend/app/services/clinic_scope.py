"""Each doctor has a separate setup. Desk staff work in the doctor they have selected."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, Query

from app.models import Patient, User, Visit


DEFAULT_CLINIC_ID = 1


DESK_ROLES = {"registration", "billing", "pharmacy"}


def clinic_id_of(user: User) -> int:
    if getattr(user, "role", None) in DESK_ROLES:
        acting = getattr(user, "acting_clinic_id", None)
        if acting:
            return int(acting)
    return getattr(user, "clinic_id", None) or DEFAULT_CLINIC_ID


def registration_doctor(db: Session, user: User, doctor_id: int | None) -> User:
    """Doctor a desk registration is filed under. A doctor files under themselves."""
    if user.role == "doctor":
        return user
    if user.role not in DESK_ROLES:
        if doctor_id:
            chosen = db.get(User, doctor_id)
            if chosen and chosen.role == "doctor" and chosen.is_active is not False:
                return chosen
        return user
    if not doctor_id:
        doctor_id = desk_doctor_id(user)
    if not doctor_id:
        raise HTTPException(status_code=400, detail="Choose the doctor this patient is registering under")
    doctor = db.get(User, doctor_id)
    if not doctor or doctor.role != "doctor" or doctor.is_active is False:
        raise HTTPException(status_code=400, detail="Choose a doctor")
    return doctor


def desk_doctor_id(user: User) -> int | None:
    """The doctor a desk is working for. Doctors keep their own full clinic."""
    if getattr(user, "role", None) in DESK_ROLES:
        acting = getattr(user, "acting_doctor_id", None)
        if acting:
            return int(acting)
    return None


def _for_desk_doctor(query: Query, user: User) -> Query:
    doctor_id = desk_doctor_id(user)
    if doctor_id:
        query = query.filter(or_(Patient.doctor_id == doctor_id, Patient.doctor_id.is_(None)))
    return query


def primary_doctor(db: Session, clinic_id: int) -> User | None:
    return (
        db.query(User)
        .filter(User.clinic_id == clinic_id, User.role == "doctor")
        .order_by(User.id.asc())
        .first()
    )


def owning_doctor_id(db: Session, user: User) -> int:
    """Clinical owner for new patients, bills, and dispenses."""
    if user.role == "doctor":
        return user.id
    chosen = desk_doctor_id(user)
    if chosen:
        return chosen
    doc = primary_doctor(db, clinic_id_of(user))
    return doc.id if doc else user.id


def patients_query(db: Session, user: User) -> Query:
    query = db.query(Patient).filter(
        or_(Patient.registration_status.is_(None), Patient.registration_status != "cancelled"),
    )
    if user.role == "registration":
        return query
    query = query.filter(Patient.clinic_id == clinic_id_of(user))
    return _for_desk_doctor(query, user)


def ensure_patient_access(db: Session, patient_id: int, user: User) -> Patient:
    patient = db.get(Patient, patient_id)
    if user.role == "registration":
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        return patient
    if not patient or (patient.clinic_id or DEFAULT_CLINIC_ID) != clinic_id_of(user):
        raise HTTPException(status_code=404, detail="Patient not found")
    doctor_id = desk_doctor_id(user)
    if doctor_id and patient.doctor_id and patient.doctor_id != doctor_id:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def ensure_visit_access(db: Session, visit_id: int, user: User) -> Visit:
    visit = db.get(Visit, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    ensure_patient_access(db, visit.patient_id, user)
    return visit


def visits_for_clinic(db: Session, user: User) -> Query:
    query = (
        db.query(Visit)
        .join(Patient, Visit.patient_id == Patient.id)
        .filter(Patient.clinic_id == clinic_id_of(user))
    )
    return _for_desk_doctor(query, user)
