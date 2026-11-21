"""Copy existing measurements into ClinicalObservation without a second copy.

Each lab, CGM reading, and visit vital is keyed by its source record.
Running the sync again updates that row instead of inserting another one.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.models import CgmReading, ClinicalObservation, LabResult, Visit
from app.services.patient_360 import PARAM_BY_CODE, canonical_code, parse_numeric

SOURCE_LAB = "lab_result"
SOURCE_CGM = "cgm_reading"
SOURCE_VISIT = "visit"

VITALS = (
    ("height", "Height", "cm"),
    ("weight", "Weight", "kg"),
    ("bmi", "BMI", "kg/m²"),
    ("bp_systolic", "Systolic blood pressure", "mmHg"),
    ("bp_diastolic", "Diastolic blood pressure", "mmHg"),
    ("pulse", "Pulse", "/min"),
    ("temperature", "Temperature", "°C"),
    ("spo2", "Oxygen saturation", "%"),
)


def code_for_test_name(test_name: str) -> str:
    known = canonical_code(test_name)
    if known:
        return known
    slug = re.sub(r"[^a-z0-9]+", "_", (test_name or "").lower()).strip("_")
    return f"text_{slug[:60] or 'unspecified'}"


def name_for_code(code: str, fallback: str) -> str:
    spec = PARAM_BY_CODE.get(code)
    return spec.name if spec else fallback


def parse_reference_bounds(text: str | None) -> tuple[float | None, float | None]:
    raw = (text or "").strip().replace("–", "-").replace("—", "-")
    if not raw:
        return None, None
    below = re.match(r"^<\s*(-?\d+(?:\.\d+)?)$", raw)
    if below:
        return None, float(below.group(1))
    above = re.match(r"^>\s*(-?\d+(?:\.\d+)?)$", raw)
    if above:
        return float(above.group(1)), None
    span = re.match(r"^(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)$", raw)
    if span:
        return float(span.group(1)), float(span.group(2))
    return None, None


def as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def date_as_utc_midnight(value: date) -> datetime:
    return datetime(value.year, value.month, value.day)


def _format_number(value: float) -> str:
    return f"{value:g}"


def _index_for_patient(db: Session, patient_id: int) -> dict[tuple, ClinicalObservation]:
    rows = (
        db.query(ClinicalObservation)
        .filter(
            ClinicalObservation.patient_id == patient_id,
            ClinicalObservation.source_record_type.isnot(None),
            ClinicalObservation.source_record_id.isnot(None),
        )
        .all()
    )
    return {
        (row.source_record_type, row.source_record_id, row.observation_code): row
        for row in rows
    }


def _upsert(db: Session, index: dict[tuple, ClinicalObservation] | None, fields: dict) -> ClinicalObservation:
    key = (fields["source_record_type"], fields["source_record_id"], fields["observation_code"])
    row = None
    if index is not None:
        row = index.get(key)
    else:
        row = (
            db.query(ClinicalObservation)
            .filter_by(
                source_record_type=fields["source_record_type"],
                source_record_id=fields["source_record_id"],
                observation_code=fields["observation_code"],
            )
            .one_or_none()
        )
    if row:
        for name, value in fields.items():
            setattr(row, name, value)
        return row
    row = ClinicalObservation(**fields, verification_status="recorded")
    db.add(row)
    if index is not None:
        index[key] = row
    return row


def _drop_missing_vitals(db: Session, visit: Visit, present_codes: set[str]) -> None:
    rows = (
        db.query(ClinicalObservation)
        .filter_by(source_record_type=SOURCE_VISIT, source_record_id=visit.id)
        .all()
    )
    for row in rows:
        if row.observation_code not in present_codes:
            db.delete(row)


def sync_lab_observation(db: Session, lab: LabResult, index: dict | None = None) -> ClinicalObservation:
    code = code_for_test_name(lab.test_name)
    low, high = parse_reference_bounds(lab.reference_range)
    observed = lab.result_date or date.today()
    return _upsert(db, index, {
        "patient_id": lab.patient_id,
        "visit_id": lab.visit_id,
        "observation_code": code,
        "observation_name": name_for_code(code, lab.test_name),
        "value_numeric": parse_numeric(lab.value),
        "value_text": (lab.value or "").strip()[:100],
        "unit": lab.unit,
        "reference_range_low": low,
        "reference_range_high": high,
        "reference_range": (lab.reference_range or None),
        "observed_at": date_as_utc_midnight(observed),
        "source": "laboratory",
        "source_record_type": SOURCE_LAB,
        "source_record_id": lab.id,
    })


def sync_cgm_observation(db: Session, reading: CgmReading, index: dict | None = None) -> ClinicalObservation:
    observed = as_naive_utc(reading.reading_time or datetime.utcnow())
    return _upsert(db, index, {
        "patient_id": reading.patient_id,
        "visit_id": None,
        "observation_code": "cgm_glucose",
        "observation_name": "CGM glucose",
        "value_numeric": float(reading.glucose_mg_dl),
        "value_text": _format_number(float(reading.glucose_mg_dl)),
        "unit": "mg/dL",
        "reference_range_low": None,
        "reference_range_high": None,
        "reference_range": None,
        "observed_at": observed,
        "source": "cgm",
        "source_record_type": SOURCE_CGM,
        "source_record_id": reading.id,
    })


def sync_visit_observations(db: Session, visit: Visit, index: dict | None = None) -> None:
    present: set[str] = set()
    observed = as_naive_utc(visit.visit_date or datetime.utcnow())
    for code, label, unit in VITALS:
        raw = getattr(visit, code)
        if raw is None:
            continue
        present.add(code)
        number = float(raw)
        _upsert(db, index, {
            "patient_id": visit.patient_id,
            "visit_id": visit.id,
            "observation_code": code,
            "observation_name": label,
            "value_numeric": number,
            "value_text": _format_number(number),
            "unit": unit,
            "reference_range_low": None,
            "reference_range_high": None,
            "reference_range": None,
            "observed_at": observed,
            "source": "examination",
            "source_record_type": SOURCE_VISIT,
            "source_record_id": visit.id,
        })
    _drop_missing_vitals(db, visit, present)
    if index is not None:
        for key, row in list(index.items()):
            if key[0] == SOURCE_VISIT and key[1] == visit.id and key[2] not in present:
                index.pop(key, None)

    labs = db.query(LabResult).filter_by(visit_id=visit.id).all()
    for lab in labs:
        sync_lab_observation(db, lab, index)


def remove_sourced_observations(db: Session, source_type: str, source_id: int) -> None:
    (
        db.query(ClinicalObservation)
        .filter_by(source_record_type=source_type, source_record_id=source_id)
        .delete(synchronize_session=False)
    )


def sync_patient_observations(db: Session, patient_id: int) -> int:
    """Insert or update observations for one patient. Returns the number of source rows seen."""
    index = _index_for_patient(db, patient_id)
    labs = db.query(LabResult).filter_by(patient_id=patient_id).all()
    readings = db.query(CgmReading).filter_by(patient_id=patient_id).all()
    visits = db.query(Visit).filter_by(patient_id=patient_id).all()
    lab_ids = {lab.id for lab in labs}
    cgm_ids = {reading.id for reading in readings}
    visit_ids = {visit.id for visit in visits}

    for key, row in list(index.items()):
        source_type, source_id, _code = key
        missing = (
            (source_type == SOURCE_LAB and source_id not in lab_ids)
            or (source_type == SOURCE_CGM and source_id not in cgm_ids)
            or (source_type == SOURCE_VISIT and source_id not in visit_ids)
        )
        if missing:
            db.delete(row)
            index.pop(key, None)

    for lab in labs:
        sync_lab_observation(db, lab, index)
    for reading in readings:
        sync_cgm_observation(db, reading, index)
    for visit in visits:
        sync_visit_observations(db, visit, index)
    return len(labs) + len(readings) + len(visits)


def _coerce_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return as_naive_utc(value)
    if isinstance(value, date):
        return date_as_utc_midnight(value)
    if isinstance(value, str) and value.strip():
        cleaned = value.strip().replace("Z", "")
        try:
            return datetime.fromisoformat(cleaned[:19])
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


def backfill_connection(connection) -> int:
    """Idempotent copy used by Alembic. Reads only columns the migrations guarantee."""
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if "clinical_observation" not in tables:
        return 0
    existing = {
        (row[0], row[1], row[2])
        for row in connection.execute(text(
            "SELECT source_record_type, source_record_id, observation_code "
            "FROM clinical_observation "
            "WHERE source_record_type IS NOT NULL AND source_record_id IS NOT NULL"
        ))
    }
    inserted = 0

    def add_row(fields: dict) -> None:
        nonlocal inserted
        key = (fields["source_record_type"], fields["source_record_id"], fields["observation_code"])
        if key in existing or fields["source_record_id"] is None:
            return
        connection.execute(text(
            "INSERT INTO clinical_observation ("
            "patient_id, visit_id, observation_code, observation_name, value_numeric, value_text, "
            "unit, reference_range_low, reference_range_high, reference_range, observed_at, source, "
            "source_record_type, source_record_id, verification_status, verified_by, created_at"
            ") VALUES ("
            ":patient_id, :visit_id, :observation_code, :observation_name, :value_numeric, :value_text, "
            ":unit, :reference_range_low, :reference_range_high, :reference_range, :observed_at, :source, "
            ":source_record_type, :source_record_id, :verification_status, :verified_by, :created_at)"
        ), fields)
        existing.add(key)
        inserted += 1

    now = datetime.utcnow()
    if "lab_result" in tables:
        for row in connection.execute(text(
            "SELECT id, patient_id, visit_id, test_name, value, unit, reference_range, result_date FROM lab_result"
        )):
            code = code_for_test_name(row[3] or "")
            low, high = parse_reference_bounds(row[6])
            add_row({
                "patient_id": row[1],
                "visit_id": row[2],
                "observation_code": code,
                "observation_name": name_for_code(code, row[3] or code),
                "value_numeric": parse_numeric(row[4]),
                "value_text": str(row[4] or "").strip()[:100],
                "unit": row[5],
                "reference_range_low": low,
                "reference_range_high": high,
                "reference_range": row[6],
                "observed_at": _coerce_timestamp(row[7]),
                "source": "laboratory",
                "source_record_type": SOURCE_LAB,
                "source_record_id": row[0],
                "verification_status": "recorded",
                "verified_by": None,
                "created_at": now,
            })

    if "cgm_reading" in tables:
        for row in connection.execute(text(
            "SELECT id, patient_id, reading_time, glucose_mg_dl FROM cgm_reading"
        )):
            glucose = float(row[3])
            add_row({
                "patient_id": row[1],
                "visit_id": None,
                "observation_code": "cgm_glucose",
                "observation_name": "CGM glucose",
                "value_numeric": glucose,
                "value_text": f"{glucose:g}",
                "unit": "mg/dL",
                "reference_range_low": None,
                "reference_range_high": None,
                "reference_range": None,
                "observed_at": _coerce_timestamp(row[2]),
                "source": "cgm",
                "source_record_type": SOURCE_CGM,
                "source_record_id": row[0],
                "verification_status": "recorded",
                "verified_by": None,
                "created_at": now,
            })

    if "visit" in tables:
        columns = {col["name"] for col in inspector.get_columns("visit")}
        vital_columns = [code for code, _label, _unit in VITALS if code in columns]
        if "id" in columns and "patient_id" in columns and vital_columns:
            selected = ["id", "patient_id", "visit_date" if "visit_date" in columns else "id"]
            selected.extend(vital_columns)
            for row in connection.execute(text(f"SELECT {', '.join(selected)} FROM visit")).mappings():
                observed = _coerce_timestamp(row.get("visit_date"))
                for code, label, unit in VITALS:
                    if code not in vital_columns or row.get(code) is None:
                        continue
                    number = float(row[code])
                    add_row({
                        "patient_id": row["patient_id"],
                        "visit_id": row["id"],
                        "observation_code": code,
                        "observation_name": label,
                        "value_numeric": number,
                        "value_text": f"{number:g}",
                        "unit": unit,
                        "reference_range_low": None,
                        "reference_range_high": None,
                        "reference_range": None,
                        "observed_at": observed,
                        "source": "examination",
                        "source_record_type": SOURCE_VISIT,
                        "source_record_id": row["id"],
                        "verification_status": "recorded",
                        "verified_by": None,
                        "created_at": now,
                    })
    return inserted


def backfill_all(db: Session) -> int:
    patient_ids = {
        pid
        for (pid,) in db.query(LabResult.patient_id).distinct()
    }
    patient_ids.update(pid for (pid,) in db.query(CgmReading.patient_id).distinct())
    patient_ids.update(pid for (pid,) in db.query(Visit.patient_id).distinct())
    total = 0
    for patient_id in sorted(pid for pid in patient_ids if pid is not None):
        total += sync_patient_observations(db, patient_id)
    return total
