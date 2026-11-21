"""Typeahead suggestions learned from clinic charting history."""

import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import BrandMedication, DiagnosisMaster, Patient, Prescription, Visit
from app.services.clinic_scope import clinic_id_of

router = APIRouter(tags=["suggestions"])

VISIT_FIELDS = {
    "diagnosis": Visit.diagnosis,
    "chief_complaints": Visit.chief_complaints,
    "history": Visit.history,
    "examination": Visit.examination,
    "comorbidities": Visit.comorbidities,
    "investigation": Visit.investigation,
    "ordered_investigations": Visit.ordered_investigations,
    "follow_up_notes": Visit.follow_up_notes,
}


@router.get("/suggestions")
def field_suggestions(
    field: str = Query(..., min_length=1),
    q: str = "",
    limit: int = Query(12, ge=1, le=40),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinic_id = clinic_id_of(user)
    needle = (q or "").strip()
    out: list[dict] = []
    seen: set[str] = set()

    def add(value: str | None, source: str):
        text = (value or "").strip()
        if not text:
            return
        key = text.lower()
        if key in seen:
            return
        if needle and needle.lower() not in key:
            return
        seen.add(key)
        out.append({"value": text, "source": source})

    if field in VISIT_FIELDS:
        col = VISIT_FIELDS[field]
        query = (
            db.query(distinct(col))
            .join(Patient, Visit.patient_id == Patient.id)
            .filter(Patient.clinic_id == clinic_id, col.isnot(None), col != "")
        )
        if needle:
            query = query.filter(col.ilike(f"%{needle}%"))
        for (value,) in query.order_by(col.asc()).limit(80).all():
            # Split multi-line ordered investigations into line suggestions
            if field == "ordered_investigations" and value and ("\n" in value or ";" in value):
                for part in re.split(r"[\n;]+", value):
                    add(part.strip(" -•\t"), "clinic")
            else:
                add(value, "clinic")

        if field == "diagnosis":
            dq = db.query(DiagnosisMaster.diagnosis_name)
            if needle:
                dq = dq.filter(DiagnosisMaster.diagnosis_name.ilike(f"%{needle}%"))
            for (name,) in dq.order_by(DiagnosisMaster.diagnosis_name.asc()).limit(40).all():
                add(name, "master")

    elif field in {"drug", "custom_drug_name", "medicine"}:
        # Custom names used in this clinic
        cq = (
            db.query(distinct(Prescription.custom_drug_name))
            .join(Visit, Prescription.visit_id == Visit.id)
            .join(Patient, Visit.patient_id == Patient.id)
            .filter(
                Patient.clinic_id == clinic_id,
                Prescription.custom_drug_name.isnot(None),
                Prescription.custom_drug_name != "",
            )
        )
        if needle:
            cq = cq.filter(Prescription.custom_drug_name.ilike(f"%{needle}%"))
        for (name,) in cq.order_by(Prescription.custom_drug_name.asc()).limit(40).all():
            add(name, "clinic")

        bq = (
            db.query(distinct(BrandMedication.brand_name))
            .join(Prescription, Prescription.brand_medication_id == BrandMedication.id)
            .join(Visit, Prescription.visit_id == Visit.id)
            .join(Patient, Visit.patient_id == Patient.id)
            .filter(Patient.clinic_id == clinic_id)
        )
        if needle:
            bq = bq.filter(BrandMedication.brand_name.ilike(f"%{needle}%"))
        for (name,) in bq.order_by(BrandMedication.brand_name.asc()).limit(40).all():
            add(name, "clinic")

    # Prefer starts-with matches, then shorter labels
    needle_l = needle.lower()
    out.sort(
        key=lambda item: (
            0 if item["value"].lower().startswith(needle_l) else 1,
            0 if item["source"] == "clinic" else 1,
            len(item["value"]),
            item["value"].lower(),
        )
    )
    return out[:limit]
