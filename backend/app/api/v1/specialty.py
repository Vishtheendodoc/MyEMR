from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
import csv
import io
import json
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models import CgmReading, Patient, Visit
from app.schemas.extended import CgmReadingCreate, CgmReadingResponse
from app.services.clinic_scope import ensure_patient_access
from app.services.observation_sync import sync_cgm_observation
from app.services.clinic_time import clinic_day
from app.services.growth_charts import growth_chart_data, parse_patient_age
from app.services.specialty_templates import (
    FIELD_LABELS,
    get_template_field_list,
    list_template_options,
    suggest_template_from_diagnosis,
)

router = APIRouter(tags=["specialty"])


def _patient(db: Session, pid: int, user):
    return ensure_patient_access(db, pid, user)


@router.get("/patients/{patient_id}/diabetes-dashboard")
def diabetes_dashboard(
    patient_id: int,
    days: int = Query(14, ge=1, le=90),
    user=Depends(require_role()),
    db: Session = Depends(get_db),
):
    _patient(db, patient_id, user)
    from app.models import LabResult
    from app.services.patient_360 import PARAM_BY_CODE, canonical_code

    stored = (
        db.query(LabResult)
        .filter_by(patient_id=patient_id)
        .order_by(LabResult.result_date.asc(), LabResult.id.asc())
        .all()
    )
    hba1c = [row for row in stored if canonical_code(row.test_name) == "hba1c"][-12:]
    latest: dict[str, LabResult] = {}
    for row in stored:
        code = canonical_code(row.test_name)
        label = PARAM_BY_CODE[code].name if code else (row.test_name or "").strip()
        if label:
            latest[label] = row
    cgm = (
        db.query(CgmReading)
        .filter_by(patient_id=patient_id)
        .order_by(CgmReading.reading_time.desc())
        .limit(200)
        .all()
    )
    visits = (
        db.query(Visit)
        .options(joinedload(Visit.prescriptions))
        .filter_by(patient_id=patient_id)
        .order_by(Visit.visit_date.desc())
        .limit(10)
        .all()
    )
    insulin_doses = []
    for v in visits:
        for rx in v.prescriptions:
            if rx.dose_morning or rx.dose_afternoon or rx.dose_evening:
                insulin_doses.append({
                    "visit_date": clinic_day(v.visit_date).isoformat(),
                    "drug": rx.custom_drug_name or (rx.brand_medication.brand_name if rx.brand_medication else ""),
                    "morning": rx.dose_morning,
                    "afternoon": rx.dose_afternoon,
                    "evening": rx.dose_evening,
                })
    payload = {
        "hba1c_trend": [{"date": l.result_date.isoformat(), "value": l.value, "unit": l.unit} for l in hba1c],
        "recent_labs": [
            {
                "test_name": label,
                "value": row.value,
                "unit": row.unit,
                "result_date": row.result_date.isoformat(),
            }
            for label, row in sorted(latest.items())
        ],
        "cgm_readings": [{"time": c.reading_time.isoformat(), "glucose": c.glucose_mg_dl} for c in reversed(cgm)],
        "insulin_dosing": insulin_doses,
    }
    from app.services.cgm_metrics import build_diabetes_intelligence

    payload.update(build_diabetes_intelligence(db, patient_id, days))
    return payload


@router.post("/patients/{patient_id}/cgm", response_model=CgmReadingResponse, status_code=201)
def add_cgm(patient_id: int, data: CgmReadingCreate, user=Depends(require_role()), db: Session = Depends(get_db)):
    _patient(db, patient_id, user)
    reading = CgmReading(patient_id=patient_id, **data.model_dump())
    db.add(reading)
    db.flush()
    sync_cgm_observation(db, reading)
    db.commit()
    db.refresh(reading)
    return reading


@router.post("/patients/{patient_id}/cgm/upload")
async def upload_cgm_csv(patient_id: int, file: UploadFile = File(...), user=Depends(require_role()), db: Session = Depends(get_db)):
    _patient(db, patient_id, user)
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode()))
    count = 0
    for row in reader:
        glucose = float(row.get("glucose") or row.get("glucose_mg_dl") or 0)
        if glucose <= 0:
            continue
        ts = row.get("time") or row.get("reading_time")
        reading_time = datetime.fromisoformat(ts) if ts else datetime.utcnow()
        reading = CgmReading(patient_id=patient_id, glucose_mg_dl=glucose, reading_time=reading_time, source="csv")
        db.add(reading)
        db.flush()
        sync_cgm_observation(db, reading)
        count += 1
    db.commit()
    return {"imported": count}


@router.get("/patients/{patient_id}/growth-chart")
def growth_chart(patient_id: int, user=Depends(require_role()), db: Session = Depends(get_db)):
    patient = _patient(db, patient_id, user)
    age_years = parse_patient_age(patient.age) or 10.0
    visits = (
        db.query(Visit)
        .filter_by(patient_id=patient_id)
        .order_by(Visit.visit_date.asc())
        .all()
    )
    mph_visits = [v for v in visits if v.mid_parental_height]
    mid_parental_height = mph_visits[-1].mid_parental_height if mph_visits else None
    return growth_chart_data(age_years, patient.sex, visits, mid_parental_height)


@router.get("/specialty-templates")
def list_templates():
    return {
        template: get_template_field_list(template)
        for template in FIELD_LABELS
    }


@router.get("/specialty-template-options")
def template_options():
    return list_template_options()


@router.get("/specialty-templates/suggest")
def suggest_template(diagnosis: str = Query("")):
    template = suggest_template_from_diagnosis(diagnosis)
    fields = get_template_field_list(template) if template else []
    return {"template": template, "fields": fields}
