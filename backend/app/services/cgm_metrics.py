"""CGM summaries use the ambulatory glucose profile conventions: 70–180 mg/dL in range."""

from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session, joinedload

from app.models import CgmReading, ImagingResult, Patient, Prescription, Visit
from app.services.clinic_time import clinic_day

try:
    KOLKATA = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    KOLKATA = timezone(timedelta(hours=5, minutes=30))

TIR_LOW = 70.0
TIR_HIGH = 180.0
BASAL_WORDS = ("glargine", "degludec", "detemir", "nph", "basal")
BOLUS_WORDS = ("aspart", "lispro", "glulisine", "regular", "bolus", "actrapid", "novorapid")
INSULIN_WORDS = ("insulin",) + BASAL_WORDS + BOLUS_WORDS
SGLT2_WORDS = ("empagliflozin", "dapagliflozin", "canagliflozin", "ertugliflozin")
GLP1_WORDS = ("semaglutide", "liraglutide", "dulaglutide", "exenatide", "tirzepatide")


def _local(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(KOLKATA)


def _number(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = "".join(ch if ch.isdigit() or ch == "." else " " for ch in raw)
    parts = [part for part in cleaned.split() if part]
    if not parts:
        return None
    try:
        return float(parts[0])
    except ValueError:
        return None


def _label(rx: Prescription) -> str:
    parts = [rx.custom_drug_name or "", rx.custom_generic_name or ""]
    if rx.brand_medication:
        parts.append(rx.brand_medication.brand_name or "")
        if rx.brand_medication.generic_drug:
            parts.append(rx.brand_medication.generic_drug.generic_name or "")
    return " ".join(parts).lower()


def _contains(label: str, words: tuple[str, ...]) -> bool:
    return any(word in label for word in words)


def cgm_summary(readings: list[CgmReading]) -> dict:
    values = [row.glucose_mg_dl for row in readings]
    count = len(values)
    if count == 0:
        return {
            "reading_count": 0,
            "time_in_range": None,
            "time_above_range": None,
            "time_below_range": None,
            "time_below_54": None,
            "gmi": None,
            "coefficient_of_variation": None,
            "average_glucose": None,
            "glucose_sd": None,
            "ranges_mg_dl": {"in_range": [TIR_LOW, TIR_HIGH], "below": TIR_LOW, "above": TIR_HIGH},
        }
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if count > 1 else 0.0
    return {
        "reading_count": count,
        "time_in_range": round(sum(TIR_LOW <= value <= TIR_HIGH for value in values) / count * 100, 1),
        "time_above_range": round(sum(value > TIR_HIGH for value in values) / count * 100, 1),
        "time_below_range": round(sum(value < TIR_LOW for value in values) / count * 100, 1),
        "time_below_54": round(sum(value < 54 for value in values) / count * 100, 1),
        "gmi": round(3.31 + 0.02392 * mean, 2),
        "coefficient_of_variation": round(sd / mean * 100, 1) if mean else None,
        "average_glucose": round(mean, 1),
        "glucose_sd": round(sd, 1),
        "ranges_mg_dl": {"in_range": [TIR_LOW, TIR_HIGH], "below": TIR_LOW, "above": TIR_HIGH},
    }


def agp_profile(readings: list[CgmReading]) -> list[dict]:
    buckets: dict[int, list[float]] = {hour: [] for hour in range(24)}
    for row in readings:
        buckets[_local(row.reading_time).hour].append(row.glucose_mg_dl)
    profile = []
    for hour, values in buckets.items():
        if not values:
            profile.append({"hour": hour, "p10": None, "p50": None, "p90": None, "count": 0})
            continue
        ordered = sorted(values)

        def percentile(rank: float) -> float:
            index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * rank)))
            return round(ordered[index], 1)

        profile.append({
            "hour": hour,
            "p10": percentile(0.10),
            "p50": percentile(0.50),
            "p90": percentile(0.90),
            "count": len(values),
        })
    return profile


def daily_profiles(readings: list[CgmReading]) -> list[dict]:
    days: dict[str, list[float]] = {}
    for row in readings:
        key = _local(row.reading_time).date().isoformat()
        days.setdefault(key, []).append(row.glucose_mg_dl)
    rows = []
    for day, values in sorted(days.items()):
        rows.append({
            "date": day,
            "average": round(statistics.fmean(values), 1),
            "minimum": round(min(values), 1),
            "maximum": round(max(values), 1),
            "count": len(values),
        })
    return rows


def nocturnal_hypoglycemia(readings: list[CgmReading]) -> dict:
    events = []
    for row in readings:
        local = _local(row.reading_time)
        if 0 <= local.hour < 6 and row.glucose_mg_dl < TIR_LOW:
            events.append({"time": local.isoformat(), "glucose": row.glucose_mg_dl})
    return {"count": len(events), "window_local": "00:00-06:00 Asia/Kolkata", "below_mg_dl": TIR_LOW, "events": events[:20]}


def postprandial_windows(readings: list[CgmReading]) -> dict:
    windows = {
        "morning_08_10": (8, 10),
        "afternoon_13_15": (13, 15),
        "evening_20_22": (20, 22),
    }
    summary = {}
    for name, (start, end) in windows.items():
        values = [row.glucose_mg_dl for row in readings if start <= _local(row.reading_time).hour < end]
        summary[name] = {
            "average": round(statistics.fmean(values), 1) if values else None,
            "count": len(values),
        }
    return {
        "note": "Meal times are not stored. These are clock windows in Asia/Kolkata, not confirmed post-meal readings.",
        "windows": summary,
    }


def _visit_insulin(visit: Visit) -> dict | None:
    basal = 0.0
    bolus = 0.0
    names: list[str] = []
    found = False
    for rx in visit.prescriptions:
        label = _label(rx)
        if not _contains(label, INSULIN_WORDS):
            continue
        found = True
        names.append(rx.custom_drug_name or (rx.brand_medication.brand_name if rx.brand_medication else label))
        doses = [_number(rx.dose_morning), _number(rx.dose_afternoon), _number(rx.dose_evening), _number(rx.dosage)]
        amount = sum(value for value in doses if value is not None)
        if _contains(label, BOLUS_WORDS) and not _contains(label, BASAL_WORDS):
            bolus += amount
        else:
            basal += amount
    if not found:
        return None
    return {
        "visit_date": clinic_day(visit.visit_date).isoformat(),
        "names": names,
        "basal_units": round(basal, 2),
        "bolus_units": round(bolus, 2),
        "total_daily_units": round(basal + bolus, 2),
    }


def insulin_history(db: Session, patient_id: int) -> dict:
    visits = (
        db.query(Visit)
        .options(joinedload(Visit.prescriptions).joinedload(Prescription.brand_medication))
        .filter_by(patient_id=patient_id)
        .order_by(Visit.visit_date.asc())
        .all()
    )
    rows = [row for row in (_visit_insulin(visit) for visit in visits) if row]
    weight = next((visit.weight for visit in reversed(visits) if visit.weight), None)
    latest = rows[-1] if rows else None
    previous = rows[-2] if len(rows) > 1 else None
    per_kg = None
    if latest and weight:
        per_kg = round(latest["total_daily_units"] / weight, 2)
    change = None
    if latest and previous:
        change = round(latest["total_daily_units"] - previous["total_daily_units"], 2)
    return {
        "regimens": rows[-8:],
        "latest_total_daily_units": latest["total_daily_units"] if latest else None,
        "units_per_kg": per_kg,
        "weight_kg": weight,
        "titration_change_units": change,
    }


def medicine_flags(db: Session, patient_id: int) -> dict:
    visits = (
        db.query(Visit)
        .options(joinedload(Visit.prescriptions).joinedload(Prescription.brand_medication))
        .filter_by(patient_id=patient_id)
        .all()
    )
    sglt2: list[str] = []
    glp1: list[str] = []
    for visit in visits:
        for rx in visit.prescriptions:
            label = _label(rx)
            display = rx.custom_drug_name or (rx.brand_medication.brand_name if rx.brand_medication else label)
            if _contains(label, SGLT2_WORDS):
                sglt2.append(display)
            if _contains(label, GLP1_WORDS):
                glp1.append(display)
    return {"sglt2_inhibitor": sorted(set(sglt2)), "glp1_receptor_agonist": sorted(set(glp1))}


def _has_diabetes(patient: Patient, visits: list[Visit]) -> bool:
    blob = " ".join([patient.problem_list or ""] + [(visit.diagnosis or "") for visit in visits]).lower()
    return "diabetes" in blob


def screening_status(db: Session, patient: Patient) -> list[dict]:
    visits = db.query(Visit).filter_by(patient_id=patient.id).order_by(Visit.visit_date.desc()).all()
    if not _has_diabetes(patient, visits):
        return []
    today = datetime.utcnow().date()

    def overdue(found: datetime | None, days: int = 365) -> dict:
        if found is None:
            return {"last_on": None, "overdue": True}
        last = found.date() if isinstance(found, datetime) else found
        return {"last_on": last.isoformat(), "overdue": (today - last).days > days}

    imaging = (
        db.query(ImagingResult)
        .filter(ImagingResult.patient_id == patient.id)
        .order_by(ImagingResult.report_date.desc())
        .all()
    )
    retina = next((row.report_date for row in imaging if any(word in (row.study_type or "").lower() for word in ("retina", "fundus", "eye"))), None)
    from app.models import ClinicalObservation

    def latest_day(codes: set[str]):
        from app.models import LabResult
        from app.services.patient_360 import canonical_code

        found: list[date] = []
        for lab in db.query(LabResult).filter_by(patient_id=patient.id).all():
            if canonical_code(lab.test_name) in codes and lab.result_date:
                found.append(lab.result_date)
        rows = (
            db.query(ClinicalObservation)
            .filter(
                ClinicalObservation.patient_id == patient.id,
                ClinicalObservation.observation_code.in_(codes),
            )
            .all()
        )
        for row in rows:
            if row.observed_at:
                found.append(row.observed_at.date() if isinstance(row.observed_at, datetime) else row.observed_at)
        return max(found) if found else None

    kidney = latest_day({"uacr"})
    lipids = latest_day({"ldl", "hdl", "triglycerides", "total_cholesterol", "cholesterol"})
    foot = next((visit.visit_date for visit in visits if "foot" in (visit.examination or "").lower()), None)
    bp = next((visit.visit_date for visit in visits if visit.bp_systolic), None)
    return [
        {"item": "retinopathy", **overdue(datetime.combine(retina, datetime.min.time()) if retina else None)},
        {"item": "nephropathy", **overdue(datetime.combine(kidney, datetime.min.time()) if kidney else None)},
        {"item": "foot_examination", **overdue(foot)},
        {"item": "blood_pressure", **overdue(bp)},
        {"item": "lipids", **overdue(datetime.combine(lipids, datetime.min.time()) if lipids else None)},
    ]


def build_diabetes_intelligence(db: Session, patient_id: int, days: int) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=max(1, min(days, 90)))
    readings = (
        db.query(CgmReading)
        .filter(CgmReading.patient_id == patient_id, CgmReading.reading_time >= cutoff)
        .order_by(CgmReading.reading_time.asc())
        .all()
    )
    patient = db.get(Patient, patient_id)
    low_count = sum(1 for row in readings if row.glucose_mg_dl < TIR_LOW)
    return {
        "cgm_period_days": days,
        "cgm_metrics": cgm_summary(readings),
        "agp": agp_profile(readings),
        "daily_glucose": daily_profiles(readings),
        "nocturnal_hypoglycemia": nocturnal_hypoglycemia(readings),
        "postprandial": postprandial_windows(readings),
        "insulin": insulin_history(db, patient_id),
        "diabetes_medicines": medicine_flags(db, patient_id),
        "hypoglycemia_events_in_period": low_count,
        "screening": screening_status(db, patient) if patient else [],
    }
