from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import BrandMedication, Prescription, User, Visit
from app.schemas.prescription import PrescriptionCreate, PrescriptionCreateResponse, PrescriptionResponse
from app.services.clinical_safety import check_drug_comorbidity_interactions
from app.services.visit_service import ensure_visit_editable
from app.services.instruction_translations import format_bilingual_instructions
from app.services.prescription_utils import (
    ensure_mg_unit,
    enrich_prescription_response,
    get_or_create_manual_entry_brand,
)

router = APIRouter(tags=["prescriptions"])


@router.post("/visits/{visit_id}/prescriptions", response_model=PrescriptionCreateResponse, status_code=201)
def add_prescription(
    visit_id: int,
    data: PrescriptionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = db.get(Visit, visit_id)
    if not visit or visit.doctor_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    ensure_visit_editable(visit)

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
        visit_id=visit_id,
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
    db.commit()
    db.refresh(prescription)

    return PrescriptionCreateResponse(
        success=True,
        prescription_id=prescription.id,
        warnings=warnings,
    )


@router.delete("/prescriptions/{prescription_id}", status_code=204)
def delete_prescription(
    prescription_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prescription = db.get(Prescription, prescription_id)
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")
    visit = db.get(Visit, prescription.visit_id)
    if not visit or visit.doctor_id != user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    ensure_visit_editable(visit)
    db.delete(prescription)
    db.commit()
