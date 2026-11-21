"""Read-only Patient 360 snapshot built from records the EMR already stores.

This does not create observations, change visits, or copy laboratory rows.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session, selectinload

from app.models import (
    Appointment,
    Bill,
    BrandMedication,
    CgmReading,
    ImagingResult,
    LabResult,
    Patient,
    Prescription,
    Visit,
)
from app.schemas.patient_360 import (
    CgmPoint,
    ClinicalParameter,
    DiagnosisItem,
    MedicationChange,
    MedicationLine,
    NumericChange,
    ParameterValue,
    Patient360Response,
    PatientOverview,
    ReviewPrompt,
    TimelineEvent,
    TrendGroup,
    TrendPoint,
    TrendSeries,
    VisitComparison,
)
from app.services.calculators import EgfrInput, calculate_egfr
from app.services.growth_charts import parse_patient_age
from app.services.prescription_utils import (
    format_prescription_drug_name,
    format_prescription_generic_name,
)

try:
    KOLKATA = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    KOLKATA = timezone(timedelta(hours=5, minutes=30))

DISCLAIMER = (
    "Patient 360 summarizes records already stored for this person. "
    "Review prompts compare those records with fixed display thresholds. "
    "They are not a diagnosis, an order, or treatment advice."
)
COMPARISON_DISCLAIMER = (
    "The later visit is compared with the visit before it. "
    "A higher or lower value describes the recorded number only."
)

# Display thresholds for this screen. They are not cited guidelines.
HBA1C_REVIEW_AT = 9.0
EGFR_REVIEW_BELOW = 60.0
TSH_LOW = 0.1
TSH_HIGH = 10.0
HBA1C_GAP_DAYS = 180
UACR_GAP_DAYS = 365
TSH_GAP_DAYS = 365

ALIASES: dict[str, str] = {
    "hba1c": "hba1c",
    "hb a1c": "hba1c",
    "a1c": "hba1c",
    "glycated haemoglobin": "hba1c",
    "glycated hemoglobin": "hba1c",
    "fbs": "fbs",
    "fasting blood sugar": "fbs",
    "fasting glucose": "fbs",
    "fasting plasma glucose": "fbs",
    "ppbs": "ppbs",
    "postprandial blood sugar": "ppbs",
    "post prandial blood sugar": "ppbs",
    "pp blood sugar": "ppbs",
    "tsh": "tsh",
    "ft4": "ft4",
    "free t4": "ft4",
    "ft3": "ft3",
    "free t3": "ft3",
    "creatinine": "creatinine",
    "serum creatinine": "creatinine",
    "egfr": "egfr",
    "gfr": "egfr",
    "uacr": "uacr",
    "urine microalbumin": "uacr",
    "microalbumin": "uacr",
    "urine albumin creatinine ratio": "uacr",
    "albumin creatinine ratio": "uacr",
    "total cholesterol": "total_cholesterol",
    "cholesterol": "total_cholesterol",
    "ldl": "ldl",
    "ldl cholesterol": "ldl",
    "hdl": "hdl",
    "hdl cholesterol": "hdl",
    "triglycerides": "triglycerides",
    "triglyceride": "triglycerides",
    "calcium": "calcium",
    "serum calcium": "calcium",
    "phosphorus": "phosphorus",
    "phosphate": "phosphorus",
    "serum phosphorus": "phosphorus",
    "pth": "pth",
    "intact pth": "pth",
    "parathyroid hormone": "pth",
    "vitamin d": "vitamin_d",
    "vit d": "vitamin_d",
    "25 oh vitamin d": "vitamin_d",
    "25 hydroxy vitamin d": "vitamin_d",
    "prolactin": "prolactin",
    "prl": "prolactin",
    "cortisol": "cortisol",
    "8am cortisol": "cortisol",
    "morning cortisol": "cortisol",
    "random cortisol": "cortisol",
    "igf 1": "igf1",
    "igf1": "igf1",
    "insulin like growth factor 1": "igf1",
}

UNIT_TOKENS = {"mg", "dl", "ng", "ml", "pg", "miu", "l", "mmol", "g", "percent", "u", "iu", "mlmin"}

VITAL_FIELDS = (
    ("weight", "Weight", "kg", 0.5),
    ("bmi", "BMI", "kg/m²", 0.3),
    ("bp_systolic", "Systolic BP", "mmHg", 5),
    ("bp_diastolic", "Diastolic BP", "mmHg", 5),
    ("pulse", "Pulse", "/min", 5),
)

LAB_DIRECTION_EPSILON = {
    "hba1c": 0.3,
    "fbs": 10,
    "ppbs": 10,
    "tsh": 0.5,
    "ft4": 0.15,
    "ft3": 0.2,
    "creatinine": 0.1,
    "egfr": 5,
    "uacr": 5,
    "total_cholesterol": 10,
    "ldl": 10,
    "hdl": 5,
    "triglycerides": 15,
    "calcium": 0.2,
    "phosphorus": 0.2,
    "pth": 10,
    "vitamin_d": 5,
    "prolactin": 5,
    "cortisol": 2,
    "igf1": 20,
}


@dataclass(frozen=True)
class ParamSpec:
    code: str
    name: str
    group: str
    unit: str | None
    reference_range: str | None
    chart: str | None


PARAMETERS: tuple[ParamSpec, ...] = (
    ParamSpec("hba1c", "HbA1c", "Glycemic", "%", "<7.0", "hba1c"),
    ParamSpec("fbs", "FBS", "Glycemic", "mg/dL", "70–100", None),
    ParamSpec("ppbs", "PPBS", "Glycemic", "mg/dL", "<140", None),
    ParamSpec("tsh", "TSH", "Thyroid", "mIU/L", "0.4–4.5", "thyroid"),
    ParamSpec("ft4", "FT4", "Thyroid", "ng/dL", "0.8–1.8", "thyroid"),
    ParamSpec("ft3", "FT3", "Thyroid", "pg/mL", "2.3–4.2", "thyroid"),
    ParamSpec("creatinine", "Creatinine", "Renal", "mg/dL", "0.6–1.2", "renal"),
    ParamSpec("egfr", "eGFR", "Renal", "mL/min/1.73m²", ">60", "renal"),
    ParamSpec("uacr", "Urine albumin-creatinine ratio", "Renal", "mg/g", "<30", None),
    ParamSpec("total_cholesterol", "Total cholesterol", "Lipids", "mg/dL", "<200", "lipids"),
    ParamSpec("ldl", "LDL", "Lipids", "mg/dL", "<100", "lipids"),
    ParamSpec("hdl", "HDL", "Lipids", "mg/dL", ">40", "lipids"),
    ParamSpec("triglycerides", "Triglycerides", "Lipids", "mg/dL", "<150", "lipids"),
    ParamSpec("calcium", "Calcium", "Bone", "mg/dL", "8.5–10.5", "bone"),
    ParamSpec("phosphorus", "Phosphorus", "Bone", "mg/dL", "2.5–4.5", "bone"),
    ParamSpec("pth", "PTH", "Bone", "pg/mL", "15–65", "bone"),
    ParamSpec("vitamin_d", "Vitamin D", "Bone", "ng/mL", "30–100", None),
    ParamSpec("prolactin", "Prolactin", "Pituitary", "ng/mL", "4–23", None),
    ParamSpec("cortisol", "Cortisol", "Adrenal", "mcg/dL", "5–25", None),
    ParamSpec("igf1", "IGF-1", "Pituitary", "ng/mL", "age-adjusted", None),
    ParamSpec("weight", "Weight", "Vitals", "kg", None, "weight"),
    ParamSpec("bmi", "BMI", "Vitals", "kg/m²", None, "weight"),
    ParamSpec("bp", "Blood pressure", "Vitals", "mmHg", None, "bp"),
)

PARAM_BY_CODE = {item.code: item for item in PARAMETERS}

CHART_TITLES = {
    "hba1c": "HbA1c",
    "thyroid": "Thyroid function",
    "weight": "Weight and BMI",
    "renal": "Renal function",
    "lipids": "Lipids",
    "bone": "Calcium and PTH",
    "bp": "Blood pressure",
}


def norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def canonical_code(test_name: str | None) -> str | None:
    key = norm(test_name)
    if not key:
        return None
    if key in ALIASES:
        return ALIASES[key]
    tokens = key.split()
    while len(tokens) > 1 and tokens[-1] in UNIT_TOKENS:
        tokens.pop()
        candidate = " ".join(tokens)
        if candidate in ALIASES:
            return ALIASES[candidate]
    return None


def parse_numeric(value: str | None) -> float | None:
    text = (value or "").strip().replace(",", "")
    if not text or text[0] in "<>":
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def clip(text: str | None, limit: int = 180) -> str | None:
    if not text or not str(text).strip():
        return None
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def split_items(text: str | None) -> list[str]:
    if not text:
        return []
    return [part.strip() for part in re.split(r"[\n,;]+", text) if part.strip()]


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_utc(value).isoformat().replace("+00:00", "Z")


def kolkata_date(value: datetime) -> str:
    return as_utc(value).astimezone(KOLKATA).date().isoformat()


def today_kolkata() -> date:
    return datetime.now(KOLKATA).date()


def direction(previous: float | None, current: float | None, epsilon: float) -> str:
    if previous is None or current is None:
        return "unknown"
    delta = current - previous
    if abs(delta) < epsilon:
        return "similar"
    return "higher" if delta > 0 else "lower"


def _meaningful_generic(generic: str | None) -> str | None:
    cleaned = (generic or "").strip()
    if not cleaned or cleaned in {"-", "Custom / Manual Entry"}:
        return None
    return cleaned


def medication_identity(drug_name: str, generic_name: str | None) -> str:
    generic = _meaningful_generic(generic_name)
    return norm(generic or drug_name) or norm(drug_name)


def medication_signature(parts: dict) -> str:
    doses = []
    if parts.get("dose_morning") or parts.get("dose_afternoon") or parts.get("dose_evening"):
        doses.append(
            f"{parts.get('dose_morning') or '-'} / {parts.get('dose_afternoon') or '-'} / {parts.get('dose_evening') or '-'}"
        )
    chunks = [parts.get("dosage"), *doses, parts.get("frequency"), parts.get("timing"), parts.get("duration")]
    return " · ".join(str(chunk).strip() for chunk in chunks if chunk and str(chunk).strip())


def diff_medications(previous: list[dict], current: list[dict]) -> list[dict]:
    """Compare two prescription lists. Identity prefers the generic name."""
    before = {row["identity"]: row for row in previous if row.get("identity")}
    after = {row["identity"]: row for row in current if row.get("identity")}
    changes: list[dict] = []
    for key in after:
        if key not in before:
            changes.append({
                "change": "added",
                "drug_name": after[key]["drug_name"],
                "generic_name": after[key].get("generic_name"),
                "previous": None,
                "current": after[key].get("signature") or None,
            })
        elif (before[key].get("signature") or "") != (after[key].get("signature") or ""):
            changes.append({
                "change": "changed",
                "drug_name": after[key]["drug_name"],
                "generic_name": after[key].get("generic_name"),
                "previous": before[key].get("signature") or None,
                "current": after[key].get("signature") or None,
            })
    for key in before:
        if key not in after:
            changes.append({
                "change": "stopped",
                "drug_name": before[key]["drug_name"],
                "generic_name": before[key].get("generic_name"),
                "previous": before[key].get("signature") or None,
                "current": None,
            })
    order = {"added": 0, "changed": 1, "stopped": 2}
    changes.sort(key=lambda row: (order.get(row["change"], 9), row["drug_name"].lower()))
    return changes


def _point_value(point: dict | None) -> ParameterValue | None:
    if not point:
        return None
    return ParameterValue(
        date=point["date"],
        value_text=point["value_text"],
        value_numeric=point.get("value_numeric"),
        unit=point.get("unit"),
        source=point["source"],
    )


def _latest_and_previous(points: list[dict]) -> tuple[dict | None, dict | None]:
    if not points:
        return None, None
    ordered = sorted(points, key=lambda row: (row["date"], row.get("sort_id", 0)))
    latest = ordered[-1]
    previous = None
    for row in reversed(ordered[:-1]):
        if row["date"] != latest["date"]:
            previous = row
            break
    if previous is None and len(ordered) > 1:
        previous = ordered[-2]
    return latest, previous


def _as_of(points: list[dict], on_or_before: str) -> dict | None:
    eligible = [row for row in points if row["date"] <= on_or_before]
    if not eligible:
        return None
    return sorted(eligible, key=lambda row: (row["date"], row.get("sort_id", 0)))[-1]


def _days_since(point: dict | None, today: date) -> int | None:
    if not point:
        return None
    try:
        recorded = date.fromisoformat(point["date"][:10])
    except ValueError:
        return None
    return (today - recorded).days


def _egfr(creatinine: float, age_years: float | None, sex: str) -> float | None:
    if creatinine <= 0 or age_years is None:
        return None
    age = int(age_years)
    if age < 1 or age > 120:
        return None
    try:
        result = calculate_egfr(EgfrInput(creatinine_mg_dl=creatinine, age=age, sex=sex or "Male"))
    except Exception:
        return None
    value = result.get("egfr")
    return float(value) if value is not None else None


def _rx_line(visit: Visit, rx: Prescription) -> dict:
    generic = _meaningful_generic(format_prescription_generic_name(rx))
    drug_name = format_prescription_drug_name(rx)
    payload = {
        "visit_id": visit.id,
        "visit_date": kolkata_date(visit.visit_date),
        "drug_name": drug_name,
        "generic_name": generic,
        "dosage": rx.dosage,
        "frequency": rx.frequency,
        "timing": rx.timing,
        "duration": rx.duration,
        "dose_morning": rx.dose_morning,
        "dose_afternoon": rx.dose_afternoon,
        "dose_evening": rx.dose_evening,
    }
    payload["signature"] = medication_signature(payload)
    payload["identity"] = medication_identity(drug_name, generic)
    return payload


def _public_med(line: dict) -> MedicationLine:
    return MedicationLine(**{key: line.get(key) for key in MedicationLine.model_fields})


def _numeric_change(code: str, name: str, unit: str | None, previous: dict | None, current: dict | None, epsilon: float) -> NumericChange | None:
    if not previous and not current:
        return None
    prev_num = previous.get("value_numeric") if previous else None
    curr_num = current.get("value_numeric") if current else None
    if previous and current and previous.get("value_text") == current.get("value_text") and previous.get("date") == current.get("date"):
        return None
    return NumericChange(
        code=code,
        name=name,
        unit=unit,
        previous_value=previous.get("value_text") if previous else None,
        current_value=current.get("value_text") if current else None,
        previous_date=previous.get("date") if previous else None,
        current_date=current.get("date") if current else None,
        direction=direction(prev_num, curr_num, epsilon),
    )


def _investigation_text(visit: Visit) -> str | None:
    parts = [clip(visit.ordered_investigations, 400), clip(visit.investigation, 400)]
    text = " · ".join(part for part in parts if part)
    return text or None


def build_patient_360(db: Session, patient: Patient) -> Patient360Response:
    visits = (
        db.query(Visit)
        .options(
            selectinload(Visit.prescriptions)
            .selectinload(Prescription.brand_medication)
            .selectinload(BrandMedication.generic_drug)
        )
        .filter(Visit.patient_id == patient.id)
        .order_by(Visit.visit_date.asc(), Visit.id.asc())
        .all()
    )
    labs = (
        db.query(LabResult)
        .filter(LabResult.patient_id == patient.id)
        .order_by(LabResult.result_date.asc(), LabResult.id.asc())
        .all()
    )
    imaging = (
        db.query(ImagingResult)
        .filter(ImagingResult.patient_id == patient.id)
        .order_by(ImagingResult.report_date.asc(), ImagingResult.id.asc())
        .all()
    )
    bills = (
        db.query(Bill)
        .filter(Bill.patient_id == patient.id)
        .order_by(Bill.created_at.asc(), Bill.id.asc())
        .all()
    )
    appointments = (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient.id)
        .order_by(Appointment.scheduled_at.asc(), Appointment.id.asc())
        .all()
    )
    cgm_rows = (
        db.query(CgmReading)
        .filter(CgmReading.patient_id == patient.id)
        .order_by(CgmReading.reading_time.asc(), CgmReading.id.asc())
        .all()
    )

    lab_points: dict[str, list[dict]] = defaultdict(list)
    seen_labs: set[tuple] = set()
    for lab in labs:
        code = canonical_code(lab.test_name)
        if not code or code not in PARAM_BY_CODE:
            continue
        token = (code, lab.result_date.isoformat(), (lab.value or "").strip())
        if token in seen_labs:
            continue
        seen_labs.add(token)
        spec = PARAM_BY_CODE[code]
        lab_points[code].append({
            "date": lab.result_date.isoformat(),
            "value_text": (lab.value or "").strip(),
            "value_numeric": parse_numeric(lab.value),
            "unit": lab.unit or spec.unit,
            "source": "lab",
            "sort_id": lab.id,
            "reference_range": lab.reference_range,
        })

    age_years = parse_patient_age(patient.age)
    calculated_egfr: list[dict] = []
    for point in lab_points.get("creatinine", []):
        if point.get("value_numeric") is None:
            continue
        value = _egfr(point["value_numeric"], age_years, patient.sex)
        if value is None:
            continue
        calculated_egfr.append({
            "date": point["date"],
            "value_text": f"{value:.1f}",
            "value_numeric": value,
            "unit": "mL/min/1.73m²",
            "source": "calculated",
            "sort_id": point["sort_id"],
            "reference_range": ">60",
        })

    vital_points: dict[str, list[dict]] = defaultdict(list)
    for visit in visits:
        visit_day = kolkata_date(visit.visit_date)
        if visit.weight is not None:
            vital_points["weight"].append({
                "date": visit_day,
                "value_text": f"{visit.weight:g}",
                "value_numeric": float(visit.weight),
                "unit": "kg",
                "source": "visit",
                "sort_id": visit.id,
            })
        if visit.bmi is not None:
            vital_points["bmi"].append({
                "date": visit_day,
                "value_text": f"{visit.bmi:g}",
                "value_numeric": float(visit.bmi),
                "unit": "kg/m²",
                "source": "visit",
                "sort_id": visit.id,
            })
        if visit.bp_systolic is not None or visit.bp_diastolic is not None:
            systolic = visit.bp_systolic
            diastolic = visit.bp_diastolic
            text = "/".join([
                str(systolic) if systolic is not None else "—",
                str(diastolic) if diastolic is not None else "—",
            ])
            vital_points["bp"].append({
                "date": visit_day,
                "value_text": text,
                "value_numeric": float(systolic) if systolic is not None else None,
                "unit": "mmHg",
                "source": "visit",
                "sort_id": visit.id,
                "diastolic": float(diastolic) if diastolic is not None else None,
            })

    egfr_note = None
    if lab_points.get("egfr"):
        egfr_points = lab_points["egfr"]
    else:
        egfr_points = calculated_egfr
        if calculated_egfr:
            egfr_note = (
                "Calculated from creatinine with CKD-EPI using the age and sex on the chart. "
                "The age is the current recorded age, not the age on the day of the test. "
                "A race coefficient is not applied."
            )

    parameters: list[ClinicalParameter] = []
    for spec in PARAMETERS:
        if spec.code == "egfr":
            points = egfr_points
            note = egfr_note
        elif spec.code in vital_points:
            points = vital_points[spec.code]
            note = None
        else:
            points = lab_points.get(spec.code, [])
            note = None
        latest, previous = _latest_and_previous(points)
        reference = None
        if latest and latest.get("reference_range"):
            reference = latest["reference_range"]
        parameters.append(ClinicalParameter(
            code=spec.code,
            name=spec.name,
            group=spec.group,
            unit=spec.unit,
            reference_range=reference or spec.reference_range,
            note=note,
            latest=_point_value(latest),
            previous=_point_value(previous),
        ))

    meds_by_visit = {visit.id: [_rx_line(visit, rx) for rx in visit.prescriptions] for visit in visits}
    current_visit = next((visit for visit in reversed(visits) if meds_by_visit[visit.id]), None)
    current_lines = meds_by_visit[current_visit.id] if current_visit else []

    diagnoses: list[DiagnosisItem] = []
    seen_dx: set[str] = set()
    for visit in reversed(visits):
        for part in split_items(visit.diagnosis):
            key = norm(part)
            if not key or key in seen_dx:
                continue
            seen_dx.add(key)
            diagnoses.append(DiagnosisItem(text=part, visit_id=visit.id, visit_date=kolkata_date(visit.visit_date)))
            if len(diagnoses) >= 12:
                break
        if len(diagnoses) >= 12:
            break

    comorbidities = next((visit.comorbidities.strip() for visit in reversed(visits) if (visit.comorbidities or "").strip()), None)
    today = today_kolkata()
    prompts = _prompts(
        patient=patient,
        visits=visits,
        labs=labs,
        lab_points=lab_points,
        egfr_points=egfr_points,
        comorbidities=comorbidities,
        today=today,
    )

    registered = iso_utc(patient.date_registered) or today.isoformat()
    overview = PatientOverview(
        id=patient.id,
        name=patient.name,
        mrd_number=patient.mrd_number,
        age=patient.age,
        sex=patient.sex,
        contact=patient.contact,
        address=patient.address,
        date_of_birth=patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        date_registered=registered,
        allergies=(patient.allergies or "").strip() or None,
        problem_list=(patient.problem_list or "").strip() or None,
        comorbidities=comorbidities,
        visit_count=len(visits),
        active_diagnoses=diagnoses,
        current_medications=[_public_med(line) for line in current_lines],
        current_medications_visit_id=current_visit.id if current_visit else None,
        current_medications_visit_date=kolkata_date(current_visit.visit_date) if current_visit else None,
        prompts=prompts,
    )

    trends = _trends(lab_points, vital_points, egfr_points, bool(lab_points.get("egfr")))
    cgm = _cgm(cgm_rows)
    timeline = _timeline(patient, visits, meds_by_visit, labs, imaging, bills, appointments)
    comparison = _comparison(visits, meds_by_visit, lab_points, egfr_points)

    return Patient360Response(
        generated_at=iso_utc(datetime.now(timezone.utc)) or "",
        disclaimer=DISCLAIMER,
        overview=overview,
        parameters=parameters,
        trends=trends,
        cgm=cgm,
        timeline=timeline,
        comparison=comparison,
    )


def _prompts(
    *,
    patient: Patient,
    visits: list[Visit],
    labs: list[LabResult],
    lab_points: dict[str, list[dict]],
    egfr_points: list[dict],
    comorbidities: str | None,
    today: date,
) -> list[ReviewPrompt]:
    prompts: list[ReviewPrompt] = []
    if (patient.allergies or "").strip():
        prompts.append(ReviewPrompt(
            code="allergy",
            severity="info",
            title="Allergy recorded",
            explanation="An allergy is on the patient chart. Check it before prescribing or dispensing.",
            triggering=[patient.allergies.strip()],
        ))

    if visits:
        latest_visit = max(visits, key=lambda visit: (visit.visit_date, visit.id))
        if latest_visit.follow_up_date and latest_visit.follow_up_date < today:
            prompts.append(ReviewPrompt(
                code="follow_up_overdue",
                severity="review",
                title="Follow-up date has passed",
                explanation="The latest visit has a follow-up date earlier than today. This does not book or change the interval.",
                triggering=[latest_visit.follow_up_date.isoformat()],
            ))
        ordered = (latest_visit.ordered_investigations or "").strip()
        if ordered:
            visit_day = kolkata_date(latest_visit.visit_date)
            has_lab = any(lab.result_date.isoformat() >= visit_day for lab in labs)
            if not has_lab:
                prompts.append(ReviewPrompt(
                    code="investigations_unmatched",
                    severity="review",
                    title="Investigations listed without a later result",
                    explanation=(
                        "The latest visit lists investigations, and no laboratory result is dated on or after that visit. "
                        "Confirm whether they are still pending."
                    ),
                    triggering=[clip(ordered, 240) or ordered],
                ))

    corpus = " ".join(
        part
        for part in [
            patient.problem_list or "",
            comorbidities or "",
            *(visit.diagnosis or "" for visit in visits),
            *(visit.comorbidities or "" for visit in visits),
        ]
        if part
    ).lower()
    has_diabetes = any(word in corpus for word in ("diabetes", "diabetic", "t2dm", "t1dm"))
    has_thyroid = any(word in corpus for word in ("thyroid", "hypothyroid", "hyperthyroid"))

    hba1c_latest, _ = _latest_and_previous(lab_points.get("hba1c", []))
    if hba1c_latest and hba1c_latest.get("value_numeric") is not None and hba1c_latest["value_numeric"] >= HBA1C_REVIEW_AT:
        prompts.append(ReviewPrompt(
            code="hba1c_high",
            severity="review",
            title="HbA1c is at or above the review threshold",
            explanation=(
                f"The latest recorded HbA1c is {hba1c_latest['value_text']}%. "
                f"This screen flags values at or above {HBA1C_REVIEW_AT:g}%. It does not diagnose or change treatment."
            ),
            triggering=[f"HbA1c {hba1c_latest['value_text']}% on {hba1c_latest['date']}"],
        ))

    egfr_latest, _ = _latest_and_previous(egfr_points)
    if egfr_latest and egfr_latest.get("value_numeric") is not None and egfr_latest["value_numeric"] < EGFR_REVIEW_BELOW:
        prompts.append(ReviewPrompt(
            code="egfr_low",
            severity="review",
            title="eGFR is below the review threshold",
            explanation=(
                f"The latest eGFR on this chart is {egfr_latest['value_text']} {egfr_latest.get('unit') or ''}. "
                f"Values below {EGFR_REVIEW_BELOW:g} are flagged so renal function can be reviewed before renally cleared medicines."
            ),
            triggering=[f"eGFR {egfr_latest['value_text']} on {egfr_latest['date']} ({egfr_latest['source']})"],
        ))

    tsh_latest, _ = _latest_and_previous(lab_points.get("tsh", []))
    if tsh_latest and tsh_latest.get("value_numeric") is not None and (
        tsh_latest["value_numeric"] < TSH_LOW or tsh_latest["value_numeric"] > TSH_HIGH
    ):
        prompts.append(ReviewPrompt(
            code="tsh_wide",
            severity="review",
            title="TSH is outside a wide review range",
            explanation=(
                f"The latest TSH is {tsh_latest['value_text']} {tsh_latest.get('unit') or ''}. "
                f"This screen flags TSH below {TSH_LOW:g} or above {TSH_HIGH:g} so mildly out-of-range results do not raise an alert."
            ),
            triggering=[f"TSH {tsh_latest['value_text']} on {tsh_latest['date']}"],
        ))

    if has_diabetes:
        gap = _days_since(hba1c_latest, today)
        if gap is None or gap > HBA1C_GAP_DAYS:
            prompts.append(ReviewPrompt(
                code="screening_hba1c",
                severity="review",
                title="No recent HbA1c on file",
                explanation=(
                    "A diabetes-related diagnosis or problem is recorded, and there is no HbA1c from the last "
                    f"{HBA1C_GAP_DAYS} days. This is a review prompt, not an order to test."
                ),
                triggering=["diabetes recorded on the chart"],
            ))
        uacr_latest, _ = _latest_and_previous(lab_points.get("uacr", []))
        uacr_gap = _days_since(uacr_latest, today)
        if uacr_gap is None or uacr_gap > UACR_GAP_DAYS:
            prompts.append(ReviewPrompt(
                code="screening_uacr",
                severity="review",
                title="No recent urine albumin-creatinine ratio on file",
                explanation=(
                    "A diabetes-related diagnosis or problem is recorded, and there is no urine albumin-creatinine ratio from the last "
                    f"{UACR_GAP_DAYS} days. This is a review prompt, not an order to test."
                ),
                triggering=["diabetes recorded on the chart"],
            ))

    if has_thyroid:
        gap = _days_since(tsh_latest, today)
        if gap is None or gap > TSH_GAP_DAYS:
            prompts.append(ReviewPrompt(
                code="screening_tsh",
                severity="review",
                title="No recent TSH on file",
                explanation=(
                    "A thyroid-related diagnosis or problem is recorded, and there is no TSH from the last "
                    f"{TSH_GAP_DAYS} days. This is a review prompt, not an order to test."
                ),
                triggering=["thyroid recorded on the chart"],
            ))
    return prompts


def _series_from_points(spec: ParamSpec, points: list[dict]) -> TrendSeries | None:
    numeric = [
        TrendPoint(date=row["date"], value=row["value_numeric"])
        for row in sorted(points, key=lambda item: (item["date"], item.get("sort_id", 0)))
        if row.get("value_numeric") is not None
    ]
    deduped: list[TrendPoint] = []
    seen: set[str] = set()
    for point in numeric:
        if point.date in seen:
            deduped[-1] = point
        else:
            seen.add(point.date)
            deduped.append(point)
    if not deduped:
        return None
    return TrendSeries(code=spec.code, name=spec.name, unit=spec.unit, points=deduped)


def _trends(
    lab_points: dict[str, list[dict]],
    vital_points: dict[str, list[dict]],
    egfr_points: list[dict],
    egfr_is_recorded: bool,
) -> list[TrendGroup]:
    grouped: dict[str, list[TrendSeries]] = defaultdict(list)
    for spec in PARAMETERS:
        if not spec.chart or spec.code == "bp":
            continue
        if spec.code == "egfr":
            points = egfr_points
            series = _series_from_points(spec, points)
            if series and not egfr_is_recorded:
                series = series.model_copy(update={"name": "eGFR (calculated)"})
        elif spec.code in vital_points:
            series = _series_from_points(spec, vital_points[spec.code])
        else:
            series = _series_from_points(spec, lab_points.get(spec.code, []))
        if series:
            grouped[spec.chart].append(series)

    bp_sys = []
    bp_dia = []
    for row in sorted(vital_points.get("bp", []), key=lambda item: (item["date"], item.get("sort_id", 0))):
        if row.get("value_numeric") is not None:
            bp_sys.append(TrendPoint(date=row["date"], value=row["value_numeric"]))
        if row.get("diastolic") is not None:
            bp_dia.append(TrendPoint(date=row["date"], value=row["diastolic"]))
    if bp_sys:
        grouped["bp"].append(TrendSeries(code="bp_systolic", name="Systolic", unit="mmHg", points=_dedupe_trend(bp_sys)))
    if bp_dia:
        grouped["bp"].append(TrendSeries(code="bp_diastolic", name="Diastolic", unit="mmHg", points=_dedupe_trend(bp_dia)))

    groups = []
    for chart_id, title in CHART_TITLES.items():
        series = grouped.get(chart_id) or []
        if series:
            groups.append(TrendGroup(id=chart_id, title=title, series=series))
    return groups


def _dedupe_trend(points: list[TrendPoint]) -> list[TrendPoint]:
    deduped: list[TrendPoint] = []
    seen: set[str] = set()
    for point in points:
        if point.date in seen:
            deduped[-1] = point
        else:
            seen.add(point.date)
            deduped.append(point)
    return deduped


def _cgm(rows: list[CgmReading]) -> list[CgmPoint]:
    if not rows:
        return []
    end = as_utc(rows[-1].reading_time)
    start = end - timedelta(days=14)
    window = [row for row in rows if as_utc(row.reading_time) >= start]
    if len(window) > 500:
        window = window[-500:]
    return [
        CgmPoint(time=iso_utc(row.reading_time) or "", glucose=float(row.glucose_mg_dl))
        for row in window
        if iso_utc(row.reading_time)
    ]


def _timeline(
    patient: Patient,
    visits: list[Visit],
    meds_by_visit: dict[int, list[dict]],
    labs: list[LabResult],
    imaging: list[ImagingResult],
    bills: list[Bill],
    appointments: list[Appointment],
) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    if patient.date_registered:
        events.append(TimelineEvent(
            at=iso_utc(patient.date_registered) or patient.date_registered.date().isoformat(),
            kind="registration",
            title="Registered",
            detail=patient.mrd_number,
        ))

    for visit in visits:
        events.append(TimelineEvent(
            at=iso_utc(visit.visit_date) or kolkata_date(visit.visit_date),
            kind="consultation",
            title=f"{visit.visit_type} ({visit.status})",
            detail=clip(visit.diagnosis or visit.chief_complaints),
            ref_type="visit",
            ref_id=visit.id,
        ))
        meds = meds_by_visit.get(visit.id) or []
        if meds:
            names = ", ".join(line["drug_name"] for line in meds)
            events.append(TimelineEvent(
                at=iso_utc(visit.visit_date) or kolkata_date(visit.visit_date),
                kind="prescription",
                title="Prescription",
                detail=clip(names, 240),
                ref_type="visit",
                ref_id=visit.id,
            ))
        if visit.follow_up_date:
            events.append(TimelineEvent(
                at=visit.follow_up_date.isoformat(),
                kind="follow_up",
                title="Follow-up",
                detail=clip(visit.follow_up_notes),
                ref_type="visit",
                ref_id=visit.id,
            ))

    labs_by_day: dict[str, list[str]] = defaultdict(list)
    for lab in labs:
        day = lab.result_date.isoformat()
        if lab.test_name not in labs_by_day[day]:
            labs_by_day[day].append(lab.test_name)
    for day, names in labs_by_day.items():
        if len(names) > 8:
            detail = ", ".join(names[:8]) + f" +{len(names) - 8} more"
        else:
            detail = ", ".join(names)
        events.append(TimelineEvent(at=day, kind="laboratory", title="Laboratory results", detail=detail))

    for study in imaging:
        events.append(TimelineEvent(
            at=study.report_date.isoformat(),
            kind="imaging",
            title=study.study_type,
            detail=clip(study.findings),
        ))

    for bill in bills:
        pharmacy = (bill.category or "") == "pharmacy" or (bill.description or "").lower().startswith("pharmacy")
        events.append(TimelineEvent(
            at=iso_utc(bill.created_at) or "",
            kind="pharmacy" if pharmacy else "bill",
            title="Pharmacy dispensing" if pharmacy else "Bill",
            detail=clip(f"{bill.description} · ₹{bill.amount:g} · {bill.payment_status}"),
            ref_type="bill",
            ref_id=bill.id,
        ))

    for appointment in appointments:
        token = f"Token {appointment.token_number}" if appointment.token_number else None
        detail = " · ".join(part for part in [appointment.status, token, clip(appointment.notes, 120)] if part)
        events.append(TimelineEvent(
            at=iso_utc(appointment.scheduled_at) or "",
            kind="appointment",
            title="Appointment",
            detail=detail or None,
            ref_type="appointment",
            ref_id=appointment.id,
        ))

    events.sort(key=lambda event: event.at or "", reverse=True)
    unique: list[TimelineEvent] = []
    seen: set[tuple] = set()
    for event in events:
        # Repeated visit saves can insert the same imaging or lab day more than once.
        # Collapse identical display rows without deleting the stored records.
        if event.kind in {"laboratory", "imaging"}:
            token = (event.kind, (event.at or "")[:10], event.title, event.detail)
        else:
            token = (event.kind, event.at, event.title, event.detail, event.ref_type, event.ref_id)
        if token in seen:
            continue
        seen.add(token)
        unique.append(event)
    return unique[:250]


def _comparison(
    visits: list[Visit],
    meds_by_visit: dict[int, list[dict]],
    lab_points: dict[str, list[dict]],
    egfr_points: list[dict],
) -> VisitComparison:
    if len(visits) < 2:
        return VisitComparison(available=False, disclaimer=COMPARISON_DISCLAIMER)

    current = visits[-1]
    previous = visits[-2]
    current_day = kolkata_date(current.visit_date)
    previous_day = kolkata_date(previous.visit_date)
    current_meds = meds_by_visit.get(current.id) or []
    previous_meds = meds_by_visit.get(previous.id) or []

    if not current_meds and previous_meds:
        medication_note = (
            "The later visit has no prescription recorded. "
            "Medicines from the earlier visit are not marked as stopped."
        )
        medication_changes: list[MedicationChange] = []
    elif not current_meds and not previous_meds:
        medication_note = "Neither visit has a prescription recorded."
        medication_changes = []
    else:
        medication_note = None
        medication_changes = [MedicationChange(**row) for row in diff_medications(previous_meds, current_meds)]

    parameter_changes: list[NumericChange] = []
    for spec in PARAMETERS:
        if spec.code in {"weight", "bmi", "bp"}:
            continue
        points = egfr_points if spec.code == "egfr" else lab_points.get(spec.code, [])
        change = _numeric_change(
            spec.code,
            spec.name,
            spec.unit,
            _as_of(points, previous_day),
            _as_of(points, current_day),
            LAB_DIRECTION_EPSILON.get(spec.code, 0.1),
        )
        if change and change.previous_value != change.current_value:
            parameter_changes.append(change)

    vital_changes: list[NumericChange] = []
    for code, name, unit, epsilon in VITAL_FIELDS:
        prev_raw = getattr(previous, code)
        curr_raw = getattr(current, code)
        if prev_raw is None and curr_raw is None:
            continue
        vital_changes.append(NumericChange(
            code=code,
            name=name,
            unit=unit,
            previous_value=None if prev_raw is None else f"{prev_raw:g}" if isinstance(prev_raw, float) else str(prev_raw),
            current_value=None if curr_raw is None else f"{curr_raw:g}" if isinstance(curr_raw, float) else str(curr_raw),
            previous_date=previous_day,
            current_date=current_day,
            direction=direction(
                float(prev_raw) if prev_raw is not None else None,
                float(curr_raw) if curr_raw is not None else None,
                epsilon,
            ),
        ))

    previous_dx = split_items(previous.diagnosis)
    current_dx = split_items(current.diagnosis)
    previous_keys = {norm(item): item for item in previous_dx}
    current_keys = {norm(item): item for item in current_dx}

    return VisitComparison(
        available=True,
        disclaimer=COMPARISON_DISCLAIMER,
        previous_visit_id=previous.id,
        current_visit_id=current.id,
        previous_visit_date=previous_day,
        current_visit_date=current_day,
        previous_visit_status=previous.status,
        current_visit_status=current.status,
        medication_note=medication_note,
        medication_changes=medication_changes,
        parameter_changes=parameter_changes,
        vital_changes=vital_changes,
        diagnosis_previous=clip(previous.diagnosis, 400),
        diagnosis_current=clip(current.diagnosis, 400),
        diagnoses_added=[current_keys[key] for key in current_keys if key not in previous_keys],
        diagnoses_removed=[previous_keys[key] for key in previous_keys if key not in current_keys],
        investigations_previous=_investigation_text(previous),
        investigations_current=_investigation_text(current),
    )
