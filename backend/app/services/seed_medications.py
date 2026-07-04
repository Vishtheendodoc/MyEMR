"""Upsert clinic-specific medication brands (idempotent on every startup)."""

from sqlalchemy.orm import Session

from app.models import GenericDrug
from app.services.medication_service import upsert_brand_from_row

CLINIC_MEDICATIONS = [
    {
        "generic_name": "Vildagliptin + Metformin",
        "brand_name": "Vildanex M",
        "drug_class": "Antidiabetic Combination",
        "indication": "Type 2 Diabetes",
        "strength": "50/500 mg",
        "formulation": "Tablet",
    },
    {
        "generic_name": "Dapagliflozin + Linagliptin + Metformin",
        "brand_name": "Linaray DM Forte",
        "drug_class": "Antidiabetic Combination",
        "indication": "Type 2 Diabetes",
        "strength": "5/10/1000 mg",
        "formulation": "Tablet",
    },
    {
        "generic_name": "Rosuvastatin",
        "brand_name": "Roseloy",
        "drug_class": "Statin",
        "indication": "Hyperlipidemia",
        "manufacturer": "Lupin Ltd",
        "strength": "10mg",
        "formulation": "Tablet",
    },
    {
        "generic_name": "Rosuvastatin + Fenofibrate",
        "brand_name": "Roseloy F",
        "drug_class": "Lipid-lowering Combination",
        "indication": "Hyperlipidemia",
        "manufacturer": "Lupin Ltd",
        "strength": "10/160 mg",
        "formulation": "Tablet",
    },
    {
        "generic_name": "Cilnidipine",
        "brand_name": "Cilnpress",
        "drug_class": "Calcium Channel Blocker",
        "indication": "Hypertension",
        "manufacturer": "Macleods",
        "strength": "10mg",
        "formulation": "Tablet",
    },
    {
        "generic_name": "Cilnidipine + Telmisartan",
        "brand_name": "Cilipress T",
        "drug_class": "Antihypertensive Combination",
        "indication": "Hypertension",
        "manufacturer": "Macleods",
        "strength": "40/10 mg",
        "formulation": "Tablet",
    },
]


def seed_clinic_medications(db: Session) -> int:
    """Insert or update clinic brand rows; returns count of new brands added."""
    added = 0
    for row in CLINIC_MEDICATIONS:
        generic_name = row["generic_name"]
        generic = db.query(GenericDrug).filter_by(generic_name=generic_name).first()
        if not generic:
            generic = GenericDrug(
                generic_name=generic_name,
                drug_class=row.get("drug_class", ""),
                indication=row.get("indication", ""),
            )
            db.add(generic)
            db.flush()
        if upsert_brand_from_row(db, generic, row):
            added += 1
    db.commit()
    return added
