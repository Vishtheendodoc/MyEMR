from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models import Appointment, Bill, Patient, User, Visit
from app.schemas.patient import PatientCreate, PatientDetailResponse, PatientResponse, PatientUpdate, VisitSummary
from app.schemas.patient_360 import Patient360Response
from app.services.patient_360 import build_patient_360
from app.services.audit import write_audit
from app.services.clinic_scope import (
    DESK_ROLES,
    clinic_id_of,
    ensure_patient_access,
    patients_query,
    registration_doctor,
)
from app.services.opd_visit import appointment_vitals_for_patient_day
from app.services.patient_service import (
    ensure_mrd_available,
    ensure_mobile_available,
    find_duplicate_patients,
    is_temporary_mrd,
    next_clinic_mrd,
    next_temp_mrd,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientResponse])
def list_patients(
    q: str | None = None,
    search_type: str = Query("name", pattern="^(name|mrd|phone|diagnosis)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = patients_query(db, user)
    if q:
        if search_type == "name":
            query = query.filter(Patient.name.ilike(f"%{q}%"))
        elif search_type == "mrd":
            query = query.filter(Patient.mrd_number.ilike(f"%{q}%"))
        elif search_type == "phone":
            digits = "".join(ch for ch in q if ch.isdigit()) or q.strip()
            query = query.filter(Patient.contact.ilike(f"%{digits}%"))
        elif search_type == "diagnosis":
            if user.role not in {"doctor", "nurse", "admin"}:
                raise HTTPException(status_code=403, detail="Diagnosis search is for the doctor")
            patient_ids = (
                db.query(Visit.patient_id)
                .join(Patient, Visit.patient_id == Patient.id)
                .filter(Patient.clinic_id == clinic_id_of(user), Visit.diagnosis.ilike(f"%{q}%"))
                .distinct()
                .all()
            )
            ids = [pid[0] for pid in patient_ids]
            query = query.filter(Patient.id.in_(ids))
    return query.order_by(Patient.date_registered.desc()).all()


@router.get("/duplicates")
def check_duplicates(
    name: str = "",
    contact: str | None = None,
    exclude_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = None if user.role == "registration" else clinic_id_of(user)
    return find_duplicate_patients(db, scope, name, contact, exclude_id)


@router.post("", response_model=PatientResponse, status_code=201)
def create_patient(
    data: PatientCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = data.model_dump()
    temporary = bool(payload.pop("temporary", False))
    doctor = registration_doctor(db, user, payload.pop("doctor_id", None))
    clinic_id = doctor.clinic_id if user.role in DESK_ROLES else clinic_id_of(user)
    if temporary:
        payload["mrd_number"] = next_temp_mrd(db, clinic_id)
        registration_status = "temporary"
    else:
        payload["mrd_number"] = ensure_mrd_available(
            db,
            payload.get("mrd_number"),
            clinic_id=clinic_id,
            auto_assign=True,
        )
        registration_status = "active"
    ensure_mobile_available(db, clinic_id, payload.get("contact"))
    patient = Patient(
        **payload,
        clinic_id=clinic_id,
        doctor_id=doctor.id,
        registration_status=registration_status,
    )
    db.add(patient)
    db.flush()
    write_audit(
        db,
        user_id=user.id,
        action="patient.create",
        entity_type="patient",
        entity_id=patient.id,
        details=patient.mrd_number,
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}/queue-vitals")
def queue_vitals(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_patient_access(db, patient_id, user)
    return appointment_vitals_for_patient_day(db, patient_id)


@router.get("/{patient_id}/patient-360", response_model=Patient360Response)
def patient_360(
    patient_id: int,
    user: User = Depends(require_role("doctor")),
    db: Session = Depends(get_db),
):
    """Longitudinal chart for the treating doctor. Desk roles are rejected."""
    patient = ensure_patient_access(db, patient_id, user)
    payload = build_patient_360(db, patient)
    write_audit(
        db,
        user_id=user.id,
        action="patient.view_360",
        entity_type="patient",
        entity_id=patient.id,
    )
    db.commit()
    return payload


@router.get("/{patient_id}", response_model=PatientDetailResponse)
def get_patient(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = ensure_patient_access(db, patient_id, user)
    write_audit(
        db,
        user_id=user.id,
        action="patient.view",
        entity_type="patient",
        entity_id=patient.id,
        details=patient.mrd_number,
    )
    db.commit()
    visits = (
        db.query(Visit)
        .filter_by(patient_id=patient_id)
        .order_by(Visit.visit_date.desc())
        .all()
    )
    visits_out = []
    for visit in visits:
        summary = VisitSummary.model_validate(visit)
        if user.role not in {"doctor", "nurse", "admin"}:
            summary.diagnosis = None
            summary.chief_complaints = None
        visits_out.append(summary)
    return PatientDetailResponse(
        **{c.name: getattr(patient, c.name) for c in Patient.__table__.columns},
        visits=visits_out,
    )


@router.patch("/{patient_id}", response_model=PatientResponse)
def update_patient(
    patient_id: int,
    data: PatientUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient = ensure_patient_access(db, patient_id, user)
    updates = data.model_dump(exclude_unset=True)
    if "mrd_number" in updates:
        updates["mrd_number"] = ensure_mrd_available(
            db,
            updates["mrd_number"],
            exclude_patient_id=patient_id,
            clinic_id=clinic_id_of(user),
            auto_assign=False,
        )
        if updates["mrd_number"] and not is_temporary_mrd(updates["mrd_number"]):
            patient.registration_status = "active"
    if "contact" in updates:
        ensure_mobile_available(db, clinic_id_of(user), updates.get("contact"), exclude_id=patient.id)
    for key, value in updates.items():
        setattr(patient, key, value)
    write_audit(
        db,
        user_id=user.id,
        action="patient.update",
        entity_type="patient",
        entity_id=patient.id,
        details=",".join(updates.keys()),
    )
    db.commit()
    db.refresh(patient)
    return patient


def _registration_is_locked(db: Session, patient_id: int) -> str | None:
    """A printed prescription, or a locked visit, keeps the registration."""
    visits = db.query(Visit).filter_by(patient_id=patient_id).all()
    for visit in visits:
        if visit.pdf_generated_at:
            return "A prescription has been printed, so this registration cannot be cancelled"
        if visit.finalized_at or (visit.status or "") in {"locked", "finalized"}:
            return "This visit is locked and finalised, so this registration cannot be cancelled"
    return None


@router.post("/{patient_id}/assign-mrd", response_model=PatientResponse)
def assign_permanent_mrd(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replace a temporary booking id with the next permanent MRD."""
    patient = ensure_patient_access(db, patient_id, user)
    if (patient.registration_status or "") == "cancelled":
        raise HTTPException(status_code=400, detail="This registration is cancelled")
    if not is_temporary_mrd(patient.mrd_number) and (patient.registration_status or "active") != "temporary":
        return patient
    previous = patient.mrd_number
    patient.mrd_number = next_clinic_mrd(db, clinic_id_of(user))
    patient.registration_status = "active"
    write_audit(
        db,
        user_id=user.id,
        action="patient.assign_mrd",
        entity_type="patient",
        entity_id=patient.id,
        details=f"{previous} -> {patient.mrd_number}",
    )
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/cancel", response_model=PatientResponse)
def cancel_registration(
    patient_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a registration until a prescription is printed or the visit is locked."""
    patient = ensure_patient_access(db, patient_id, user)
    if (patient.registration_status or "") == "cancelled":
        return patient
    locked = _registration_is_locked(db, patient.id)
    if locked:
        raise HTTPException(status_code=400, detail=locked)
    for visit in db.query(Visit).filter_by(patient_id=patient.id).all():
        if (visit.status or "") not in {"locked", "finalized"} and not visit.finalized_at:
            visit.status = "cancelled"
    for appt in db.query(Appointment).filter_by(patient_id=patient.id).all():
        if appt.status != "cancelled":
            appt.status = "cancelled"
    patient.registration_status = "cancelled"
    patient.mrd_number = None
    write_audit(
        db,
        user_id=user.id,
        action="patient.cancel",
        entity_type="patient",
        entity_id=patient.id,
        details=patient.mrd_number,
    )
    db.commit()
    db.refresh(patient)
    return patient
