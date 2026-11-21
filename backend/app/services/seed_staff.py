"""Seed desk staff accounts (idempotent) into the same clinic as the doctor."""

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Patient, User
from app.services.clinic_scope import DEFAULT_CLINIC_ID, primary_doctor

STAFF = [
    {
        "email": "registration@clinic.com",
        "display_name": "Registration Desk",
        "role": "registration",
        "password": "password123",
    },
    {
        "email": "billing@clinic.com",
        "display_name": "Billing Desk",
        "role": "billing",
        "password": "password123",
    },
    {
        "email": "pharmacy@clinic.com",
        "display_name": "Pharmacy Desk",
        "role": "pharmacy",
        "password": "password123",
    },
]


def seed_staff_users(db: Session) -> int:
    clinic_id = DEFAULT_CLINIC_ID
    # Ensure primary doctor is on clinic 1
    for doc in db.query(User).filter(User.role == "doctor").all():
        if not getattr(doc, "clinic_id", None):
            doc.clinic_id = clinic_id

    created = 0
    for row in STAFF:
        email = row["email"].lower()
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            changed = False
            if existing.role != row["role"]:
                existing.role = row["role"]
                changed = True
            if getattr(existing, "clinic_id", None) != clinic_id:
                existing.clinic_id = clinic_id
                changed = True
            if changed:
                db.commit()
            continue
        db.add(User(
            username=email,
            email=email,
            display_name=row["display_name"],
            password=hash_password(row["password"]),
            role=row["role"],
            clinic_id=clinic_id,
        ))
        created += 1
    if created:
        db.commit()

    # Unify patients into clinic and attach clinical ownership to the doctor
    owner = primary_doctor(db, clinic_id)
    patients = db.query(Patient).all()
    dirty = False
    for p in patients:
        if getattr(p, "clinic_id", None) != clinic_id:
            p.clinic_id = clinic_id
            dirty = True
        if owner and p.doctor_id and p.doctor_id != owner.id:
            creator = db.get(User, p.doctor_id)
            if creator and creator.role != "doctor":
                p.doctor_id = owner.id
                dirty = True
        elif owner and not p.doctor_id:
            p.doctor_id = owner.id
            dirty = True
    if dirty:
        db.commit()
    return created
