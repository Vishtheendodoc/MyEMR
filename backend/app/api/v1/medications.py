import os

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import BrandMedication, GenericDrug, User
from app.schemas.medication import (
    BrandResponse,
    GenericDrugResponse,
    GenericSearchResult,
    MedicationStatsResponse,
    MedicationUploadResponse,
)
from app.services.medication_service import process_medication_rows
from app.services.prescription_utils import (
    build_prescription_stats,
    format_brand_label,
    get_brand_prescription_counts,
    get_custom_prescription_counts,
    is_insulin_brand,
    suggest_prescription_dosage,
)

router = APIRouter(prefix="/medications", tags=["medications"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=list[GenericDrugResponse])
def list_medications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    drugs = (
        db.query(GenericDrug)
        .options(joinedload(GenericDrug.brands))
        .order_by(GenericDrug.generic_name)
        .all()
    )
    result = []
    for drug in drugs:
        brands = [
            BrandResponse(
                id=b.id,
                brand_name=b.brand_name,
                display_label=format_brand_label(b),
                manufacturer=b.manufacturer,
                strength=b.strength,
                formulation=b.formulation,
                price=b.price,
                is_insulin=is_insulin_brand(b),
                suggested_dosage=suggest_prescription_dosage(b),
            )
            for b in drug.brands
            if b.brand_name != "Manual Entry"
        ]
        result.append(GenericDrugResponse(
            id=drug.id,
            generic_name=drug.generic_name,
            drug_class=drug.drug_class,
            indication=drug.indication,
            created_at=drug.created_at,
            brands=brands,
        ))
    return result


@router.get("/stats", response_model=MedicationStatsResponse)
def medication_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    drugs = db.query(GenericDrug).options(joinedload(GenericDrug.brands)).all()
    brand_counts = get_brand_prescription_counts(db, user.id)
    custom_counts = get_custom_prescription_counts(db, user.id)
    stats = build_prescription_stats(drugs, brand_counts, custom_counts)
    return MedicationStatsResponse(**stats)


@router.get("/search", response_model=list[GenericSearchResult])
def search_medications(
    q: str = Query("", min_length=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(q) < 2:
        return []
    results = []
    drugs = db.query(GenericDrug).filter(GenericDrug.generic_name.ilike(f"%{q}%")).limit(10).all()
    for drug in drugs:
        results.append(GenericSearchResult(
            type="generic", id=drug.id, generic_name=drug.generic_name,
            drug_class=drug.drug_class, indication=drug.indication,
        ))
    brand_matches = (
        db.query(BrandMedication)
        .options(joinedload(BrandMedication.generic_drug))
        .filter(BrandMedication.brand_name.ilike(f"%{q}%"))
        .limit(10)
        .all()
    )
    seen = set()
    for brand in brand_matches:
        if brand.id in seen:
            continue
        seen.add(brand.id)
        results.append(GenericSearchResult(
            type="brand",
            id=brand.generic_drug_id,
            brand_id=brand.id,
            generic_name=brand.generic_drug.generic_name,
            brand_name=brand.brand_name,
            display_label=format_brand_label(brand),
            is_insulin=is_insulin_brand(brand),
            strength=brand.strength,
            formulation=brand.formulation,
            suggested_dosage=suggest_prescription_dosage(brand),
            drug_class=brand.generic_drug.drug_class,
        ))
    return results[:15]


@router.get("/brands/{generic_id}", response_model=list[BrandResponse])
def get_brands(
    generic_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    brands = db.query(BrandMedication).filter_by(generic_drug_id=generic_id).all()
    return [
        BrandResponse(
            id=b.id,
            brand_name=b.brand_name,
            display_label=format_brand_label(b),
            manufacturer=b.manufacturer,
            strength=b.strength,
            formulation=b.formulation,
            price=b.price,
            is_insulin=is_insulin_brand(b),
            suggested_dosage=suggest_prescription_dosage(b),
        )
        for b in brands
    ]


@router.post("/upload", response_model=MedicationUploadResponse)
async def upload_medications(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    filepath = os.path.join(UPLOAD_DIR, file.filename or "upload.csv")
    with open(filepath, "wb") as f:
        f.write(content)
    try:
        if filepath.endswith(".csv"):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        result = process_medication_rows(db, df.to_dict("records"))
        return MedicationUploadResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
