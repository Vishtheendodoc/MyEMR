"""Clinic analytics. Consultation, pharmacy, and laboratory money are counted in separate buckets."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Bill, ClinicalObservation, ImagingResult, Patient, StockBatch, Visit
from app.services.clinic_scope import clinic_id_of


def _bucket(bill: Bill) -> str:
    category = (bill.category or "").lower()
    description = (bill.description or "").lower()
    if category == "pharmacy" or description.startswith("pharmacy"):
        return "pharmacy"
    if category in {"lab", "laboratory"} or description.startswith("lab"):
        return "laboratory"
    return "consultation"


def _percent(part: int, whole: int) -> float | None:
    if whole == 0:
        return None
    return round(part / whole * 100, 1)


def _diabetes_ids(db: Session, clinic_id: int) -> set[int]:
    rows = (
        db.query(Visit.patient_id, Visit.diagnosis, Patient.problem_list)
        .join(Patient, Visit.patient_id == Patient.id)
        .filter(Patient.clinic_id == clinic_id)
        .all()
    )
    found = set()
    for patient_id, diagnosis, problems in rows:
        blob = f"{diagnosis or ''} {problems or ''}".lower()
        if "diabetes" in blob:
            found.add(patient_id)
    return found


def _latest_code(db: Session, patient_ids: set[int], code: str, since: datetime | None = None) -> set[int]:
    if not patient_ids:
        return set()
    query = db.query(ClinicalObservation.patient_id).filter(
        ClinicalObservation.patient_id.in_(patient_ids),
        ClinicalObservation.observation_code == code,
        ClinicalObservation.verification_status.in_(("recorded", "verified")),
    )
    if since is not None:
        query = query.filter(ClinicalObservation.observed_at >= since)
    return {row[0] for row in query.distinct().all()}


def practice_analytics(db: Session, user) -> dict:
    clinic_id = clinic_id_of(user)
    today = date.today()
    month_start = datetime(today.year, today.month, 1)
    year_ago = datetime.utcnow() - timedelta(days=365)
    bills = db.query(Bill).join(Patient, Bill.patient_id == Patient.id).filter(Patient.clinic_id == clinic_id).all()
    totals = {"consultation": 0.0, "pharmacy": 0.0, "laboratory": 0.0}
    medication_sales: dict[str, dict] = {}
    for bill in bills:
        bucket = _bucket(bill)
        totals[bucket] += bill.amount or 0
        if bucket == "pharmacy":
            key = bill.description or "Pharmacy"
            slot = medication_sales.setdefault(key, {"description": key, "amount": 0.0, "count": 0})
            slot["amount"] += bill.amount or 0
            slot["count"] += 1

    visits = db.query(Visit).join(Patient, Visit.patient_id == Patient.id).filter(Patient.clinic_id == clinic_id).all()
    consultations_today = sum(1 for visit in visits if visit.visit_date.date() == today)
    month_visits = [visit for visit in visits if visit.visit_date >= month_start]
    first_visit: dict[int, datetime] = {}
    for visit in visits:
        current = first_visit.get(visit.patient_id)
        if current is None or visit.visit_date < current:
            first_visit[visit.patient_id] = visit.visit_date
    month_patients = {visit.patient_id for visit in month_visits}
    new_patients = sum(1 for patient_id in month_patients if first_visit[patient_id] >= month_start)
    returning = len(month_patients) - new_patients

    diabetes_ids = _diabetes_ids(db, clinic_id)
    hba1c_rows = (
        db.query(ClinicalObservation)
        .join(Patient, ClinicalObservation.patient_id == Patient.id)
        .filter(
            Patient.clinic_id == clinic_id,
            ClinicalObservation.observation_code == "hba1c",
            ClinicalObservation.value_numeric.isnot(None),
            ClinicalObservation.verification_status.in_(("recorded", "verified")),
        )
        .order_by(ClinicalObservation.observed_at.desc())
        .all()
    )
    latest_hba1c: dict[int, float] = {}
    for row in hba1c_rows:
        latest_hba1c.setdefault(row.patient_id, row.value_numeric)
    hba1c_values = list(latest_hba1c.values())
    at_target = sum(1 for value in hba1c_values if value < 7)

    screened_kidney = _latest_code(db, diabetes_ids, "uacr", year_ago)
    thyroid_ids = set()
    osteo_ids = set()
    for visit in visits:
        blob = (visit.diagnosis or "").lower()
        if "thyroid" in blob or "hypothyroid" in blob:
            thyroid_ids.add(visit.patient_id)
        if "osteoporosis" in blob:
            osteo_ids.add(visit.patient_id)
    thyroid_recent = _latest_code(db, thyroid_ids, "tsh", year_ago)
    dexa_patients = {
        row[0]
        for row in db.query(ImagingResult.patient_id)
        .join(Patient, ImagingResult.patient_id == Patient.id)
        .filter(Patient.clinic_id == clinic_id, ImagingResult.study_type.ilike("%dexa%"))
        .all()
    }
    tscore_patients = _latest_code(db, osteo_ids, "t_score")
    osteo_monitored = (dexa_patients | tscore_patients) & osteo_ids

    weights: dict[int, list[tuple[datetime, float]]] = {}
    for visit in visits:
        if visit.weight:
            weights.setdefault(visit.patient_id, []).append((visit.visit_date, visit.weight))
    weight_loss = 0
    for series in weights.values():
        series.sort(key=lambda item: item[0])
        if series[-1][1] <= series[0][1] - 1:
            weight_loss += 1

    prior_patients = {patient_id for patient_id, first in first_visit.items() if first < year_ago}
    retained = 0
    for patient_id in prior_patients:
        recent = any(visit.patient_id == patient_id and visit.visit_date >= year_ago for visit in visits)
        if recent:
            retained += 1
    follow_ups = [visit for visit in visits if visit.follow_up_date]
    attended = 0
    for visit in follow_ups:
        later = any(
            other.patient_id == visit.patient_id and other.id != visit.id and other.visit_date.date() >= visit.follow_up_date
            for other in visits
        )
        if later:
            attended += 1

    soon = today + timedelta(days=90)
    expiring = (
        db.query(StockBatch)
        .filter(
            StockBatch.clinic_id == clinic_id,
            StockBatch.quantity > 0,
            StockBatch.expiry_date.isnot(None),
            StockBatch.expiry_date <= soon,
        )
        .all()
    )
    recent_bill_text = " ".join((bill.description or "").lower() for bill in bills if bill.created_at and bill.created_at >= datetime.utcnow() - timedelta(days=180))
    stock = db.query(StockBatch).filter(StockBatch.clinic_id == clinic_id, StockBatch.quantity > 0).all()
    if not recent_bill_text.strip():
        dead = []
        dead_note = "No bill text in the last 180 days, so dead stock was not inferred."
    else:
        dead = [
            {"item_name": row.item_name, "quantity": row.quantity}
            for row in stock
            if row.item_name.lower() not in recent_bill_text
        ]
        dead_note = None

    return {
        "clinical": {
            "patients_with_hba1c": len(hba1c_values),
            "average_hba1c": round(sum(hba1c_values) / len(hba1c_values), 2) if hba1c_values else None,
            "percent_below_general_adult_target": _percent(at_target, len(hba1c_values)),
            "target_note": "The 7% level is a general adult reference on this screen. It is not each person's own target.",
            "percent_diabetes_with_urine_albumin": _percent(len(screened_kidney), len(diabetes_ids)),
            "percent_diabetes_with_retinopathy_imaging": _percent(
                len({
                    row[0]
                    for row in db.query(ImagingResult.patient_id)
                    .filter(ImagingResult.patient_id.in_(diabetes_ids or {0}), ImagingResult.study_type.ilike("%retina%"))
                    .all()
                }) if diabetes_ids else 0,
                len(diabetes_ids),
            ),
            "percent_thyroid_with_recent_tsh": _percent(len(thyroid_recent), len(thyroid_ids)),
            "percent_osteoporosis_with_density_result": _percent(len(osteo_monitored), len(osteo_ids)),
            "patients_with_weight_loss": weight_loss,
        },
        "business": {
            "consultations_today": consultations_today,
            "consultations_this_month": len(month_visits),
            "new_patients_this_month": new_patients,
            "returning_patients_this_month": returning,
            "consultation_revenue": round(totals["consultation"], 2),
            "pharmacy_turnover": round(totals["pharmacy"], 2),
            "pharmacy_gross_margin": None,
            "pharmacy_margin_note": "Purchase cost is not stored, so gross margin is not calculated.",
            "medication_sales": sorted(medication_sales.values(), key=lambda item: item["amount"], reverse=True)[:15],
            "laboratory_revenue": round(totals["laboratory"], 2),
            "stock_expiring_within_90_days": [
                {"item_name": row.item_name, "expiry_date": row.expiry_date.isoformat(), "quantity": row.quantity}
                for row in expiring
            ],
            "dead_stock": dead,
            "dead_stock_note": dead_note,
            "follow_up_conversion_percent": _percent(attended, len(follow_ups)),
            "retention_percent": _percent(retained, len(prior_patients)),
            "revenue_note": "Each bill is placed in one bucket. The three revenue figures are not added together here.",
        },
    }


def revenue_buckets_sum_to_bills(db: Session, user) -> bool:
    report = practice_analytics(db, user)
    business = report["business"]
    clinic_id = clinic_id_of(user)
    total = (
        db.query(func.coalesce(func.sum(Bill.amount), 0))
        .join(Patient, Bill.patient_id == Patient.id)
        .filter(Patient.clinic_id == clinic_id)
        .scalar()
    )
    split = business["consultation_revenue"] + business["pharmacy_turnover"] + business["laboratory_revenue"]
    return abs(float(total or 0) - split) < 0.01
