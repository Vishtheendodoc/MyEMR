from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import BrandMedication, Patient, Prescription, User, Visit
from app.schemas.prescription import PrescriptionCreate, PrescriptionCreateResponse, PrescriptionResponse
from app.services.clinical_safety import check_drug_comorbidity_interactions
from app.services.clinic_scope import ensure_patient_access, ensure_visit_access
from app.services.visit_service import ensure_visit_editable
from app.services.instruction_translations import format_bilingual_instructions
from app.services.prescription_utils import (
    ensure_mg_unit,
    enrich_prescription_response,
    get_or_create_manual_entry_brand,
)

router = APIRouter(tags=["prescriptions"])


def _add_one_prescription(db: Session, visit: Visit, data: PrescriptionCreate) -> PrescriptionCreateResponse:
    custom_drug_name = (data.custom_drug_name or "").strip()
    has_insulin_doses = any([data.dose_morning, data.dose_afternoon, data.dose_evening])

    if custom_drug_name:
        brand = get_or_create_manual_entry_brand(db)
        brand_id = brand.id
    else:
        if not data.brand_id:
            raise HTTPException(status_code=400, detail="Please select a brand or enter a custom drug name")
        brand = db.get(BrandMedication, data.brand_id)
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        brand_id = brand.id

    dosage = (data.dosage or "").strip() or None
    if dosage and brand and not custom_drug_name:
        formulation = (brand.formulation or "").strip().lower()
        if formulation in ("tablet", "capsule"):
            dosage = ensure_mg_unit(dosage)

    if not has_insulin_doses and not dosage:
        raise HTTPException(status_code=400, detail="Enter dosage or insulin doses")
    if not has_insulin_doses and not data.frequency:
        raise HTTPException(status_code=400, detail="Frequency is required when insulin doses are not used")

    warnings = []
    if visit.comorbidities and not custom_drug_name and brand:
        comorbidities_list = [c.strip() for c in visit.comorbidities.split(",") if c.strip()]
        warnings = check_drug_comorbidity_interactions(db, brand.generic_drug_id, comorbidities_list)

    warning_text = None
    if warnings:
        warning_text = "; ".join(w["recommendation"] for w in warnings if w.get("recommendation")) or None

    prescription = Prescription(
        visit_id=visit.id,
        brand_medication_id=brand_id,
        custom_drug_name=custom_drug_name or None,
        custom_generic_name=(data.custom_generic_name or "").strip() or None,
        dosage=dosage,
        dose_morning=(data.dose_morning or "").strip() or None,
        dose_afternoon=(data.dose_afternoon or "").strip() or None,
        dose_evening=(data.dose_evening or "").strip() or None,
        frequency=data.frequency or ("Insulin dosing" if has_insulin_doses else None),
        timing=(data.timing or "").strip() or None,
        duration=data.duration,
        instructions=format_bilingual_instructions((data.instructions or "").strip()),
        warnings=warning_text,
    )
    db.add(prescription)
    db.flush()
    return PrescriptionCreateResponse(success=True, prescription_id=prescription.id, warnings=warnings)


@router.get("/patients/{patient_id}/last-prescriptions")
def last_prescriptions(
    patient_id: int,
    exclude_visit_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_patient_access(db, patient_id, user)

    q = (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date.desc(), Visit.id.desc())
    )
    if exclude_visit_id:
        q = q.filter(Visit.id != exclude_visit_id)

    source = None
    for visit in q.limit(20).all():
        count = db.query(Prescription).filter_by(visit_id=visit.id).count()
        if count:
            source = visit
            break
    if not source:
        return {"source_visit_id": None, "visit_date": None, "prescriptions": []}

    rows = (
        db.query(Prescription)
        .options(joinedload(Prescription.brand_medication).joinedload(BrandMedication.generic_drug))
        .filter_by(visit_id=source.id)
        .all()
    )
    rx_list = []
    for p in rows:
        base = PrescriptionResponse.model_validate(p)
        rx_list.append(base.model_copy(update=enrich_prescription_response(p)))
    return {
        "source_visit_id": source.id,
        "visit_date": source.visit_date.isoformat(),
        "prescriptions": rx_list,
    }


@router.post("/visits/{visit_id}/prescriptions/repeat/{source_visit_id}")
def repeat_prescriptions(
    visit_id: int,
    source_visit_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = ensure_visit_access(db, visit_id, user)
    ensure_visit_editable(visit)

    source = ensure_visit_access(db, source_visit_id, user)
    if source.patient_id != visit.patient_id:
        raise HTTPException(status_code=404, detail="Source visit not found")

    rows = db.query(Prescription).filter_by(visit_id=source_visit_id).all()
    if not rows:
        raise HTTPException(status_code=400, detail="Source visit has no prescriptions")

    created = []
    all_warnings: list[dict] = []
    for rx in rows:
        payload = PrescriptionCreate(
            brand_id=None if rx.custom_drug_name else rx.brand_medication_id,
            custom_drug_name=rx.custom_drug_name,
            custom_generic_name=rx.custom_generic_name,
            dosage=rx.dosage,
            dose_morning=rx.dose_morning,
            dose_afternoon=rx.dose_afternoon,
            dose_evening=rx.dose_evening,
            frequency=rx.frequency,
            timing=rx.timing,
            duration=rx.duration or "30 days",
            instructions=rx.instructions,
        )
        res = _add_one_prescription(db, visit, payload)
        created.append(res.prescription_id)
        all_warnings.extend(res.warnings)

    db.commit()
    return {
        "success": True,
        "copied": len(created),
        "prescription_ids": created,
        "warnings": all_warnings,
    }


@router.post("/visits/{visit_id}/prescriptions", response_model=PrescriptionCreateResponse, status_code=201)
def add_prescription(
    visit_id: int,
    data: PrescriptionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == "nurse":
        raise HTTPException(status_code=403, detail="Prescribing stays with the doctor")
    visit = ensure_visit_access(db, visit_id, user)
    ensure_visit_editable(visit)
    result = _add_one_prescription(db, visit, data)
    from app.services.audit import write_audit

    write_audit(db, user_id=user.id, action="prescription.create", entity_type="prescription", entity_id=result.prescription_id)
    db.commit()
    return result


@router.delete("/prescriptions/{prescription_id}", status_code=204)
def delete_prescription(
    prescription_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prescription = db.get(Prescription, prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    visit = ensure_visit_access(db, prescription.visit_id, user)
    ensure_visit_editable(visit)
    from app.services.audit import write_audit

    write_audit(db, user_id=user.id, action="prescription.delete", entity_type="prescription", entity_id=prescription.id)
    db.delete(prescription)
    db.commit()
