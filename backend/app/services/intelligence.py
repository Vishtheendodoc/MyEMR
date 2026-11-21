"""Build versioned review alerts from stored observations. Does not diagnose or prescribe."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ClinicalAlert, ClinicalObservation, ClinicalRule, Patient, Prescription, Visit
from app.services.observation_sync import sync_patient_observations

LOW_GLUCOSE_CODES = ("cgm_glucose", "glucose", "fbs", "rbs")
RENAL_CREATININE = "creatinine"
LEVOTHYROXINE_WORDS = ("levothyroxine", "thyroxine", "eltroxin", "thyronorm")


def _stamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _series(grouped: dict[str, list[ClinicalObservation]], code: str | None) -> list[ClinicalObservation]:
    if not code:
        return []
    return grouped.get(code, [])


def _latest(grouped: dict[str, list[ClinicalObservation]], code: str | None) -> ClinicalObservation | None:
    rows = _series(grouped, code)
    return rows[-1] if rows else None


def _payload(row: ClinicalObservation) -> dict:
    return {
        "code": row.observation_code,
        "name": row.observation_name,
        "value": row.value_numeric,
        "text": row.value_text,
        "unit": row.unit,
        "observed_at": _stamp(row.observed_at),
    }


def _previous(rows: list[ClinicalObservation], current: ClinicalObservation) -> str:
    earlier = [row for row in rows if row.id != current.id]
    return json.dumps([_payload(row) for row in earlier[-3:]])


def _hit(rule: ClinicalRule, rows: list[dict], previous: str) -> dict:
    return {
        "rule": rule,
        "triggering_parameters": json.dumps(rows),
        "previous_values": previous,
    }


def _high(rule: ClinicalRule, grouped: dict[str, list[ClinicalObservation]]) -> dict | None:
    row = _latest(grouped, rule.observation_code)
    if row is None or row.value_numeric is None or rule.threshold_high is None:
        return None
    if row.value_numeric < rule.threshold_high:
        return None
    return _hit(rule, [_payload(row)], _previous(_series(grouped, rule.observation_code), row))


def _low(rule: ClinicalRule, grouped: dict[str, list[ClinicalObservation]]) -> dict | None:
    row = _latest(grouped, rule.observation_code)
    if row is None or row.value_numeric is None or rule.threshold_low is None:
        return None
    if row.value_numeric > rule.threshold_low:
        return None
    return _hit(rule, [_payload(row)], _previous(_series(grouped, rule.observation_code), row))


def _hba1c_rise(rule: ClinicalRule, grouped: dict[str, list[ClinicalObservation]]) -> dict | None:
    rows = _series(grouped, "hba1c")
    if len(rows) < 2 or rule.threshold_high is None:
        return None
    previous, latest = rows[-2], rows[-1]
    if previous.value_numeric is None or latest.value_numeric is None:
        return None
    if latest.value_numeric - previous.value_numeric < rule.threshold_high:
        return None
    return _hit(rule, [_payload(previous), _payload(latest)], json.dumps([_payload(previous)]))


def _hypoglycemia(rule: ClinicalRule, grouped: dict[str, list[ClinicalObservation]]) -> dict | None:
    cutoff = datetime.utcnow() - timedelta(days=14)
    level = rule.threshold_low if rule.threshold_low is not None else 70.0
    found: list[dict] = []
    for code in LOW_GLUCOSE_CODES:
        for row in _series(grouped, code):
            if row.value_numeric is None or row.observed_at < cutoff:
                continue
            if row.value_numeric < level:
                found.append(_payload(row))
    if not found:
        return None
    return _hit(rule, found[-5:], json.dumps([]))


def _renal(rule: ClinicalRule, grouped: dict[str, list[ClinicalObservation]]) -> dict | None:
    egfr = _latest(grouped, "egfr")
    creatinine = _latest(grouped, RENAL_CREATININE)
    rows: list[dict] = []
    if egfr and egfr.value_numeric is not None and rule.threshold_low is not None and egfr.value_numeric < rule.threshold_low:
        rows.append(_payload(egfr))
    if (
        creatinine
        and creatinine.value_numeric is not None
        and rule.threshold_high is not None
        and creatinine.value_numeric > rule.threshold_high
    ):
        rows.append(_payload(creatinine))
    if not rows:
        return None
    return _hit(rule, rows, json.dumps([]))


def _text_has(patient: Patient, visits: list[Visit], words: tuple[str, ...]) -> bool:
    chunks = [patient.problem_list or ""]
    chunks.extend((visit.diagnosis or "") for visit in visits)
    chunks.extend((visit.history or "") for visit in visits)
    blob = " ".join(chunks).lower()
    return any(word in blob for word in words)


def _med_names(db: Session, patient_id: int) -> str:
    rows = (
        db.query(Prescription)
        .join(Visit, Prescription.visit_id == Visit.id)
        .filter(Visit.patient_id == patient_id)
        .all()
    )
    parts: list[str] = []
    for row in rows:
        parts.append(row.custom_drug_name or "")
        parts.append(row.custom_generic_name or "")
        if row.brand_medication and row.brand_medication.generic_drug:
            parts.append(row.brand_medication.generic_drug.generic_name or "")
            parts.append(row.brand_medication.brand_name or "")
    return " ".join(parts).lower()


def _screening_gap(rule: ClinicalRule, grouped, patient: Patient, visits: list[Visit]) -> dict | None:
    if not _text_has(patient, visits, ("diabetes",)):
        return None
    days = int(rule.threshold_high or 365)
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = [row for row in _series(grouped, "uacr") if row.observed_at >= cutoff]
    if recent:
        return None
    return _hit(rule, [{"code": "uacr", "value": None, "text": "no result in the review window"}], json.dumps([]))


def _tsh_on_treatment(rule: ClinicalRule, grouped, db: Session, patient_id: int) -> dict | None:
    row = _latest(grouped, "tsh")
    if row is None or row.value_numeric is None or rule.threshold_low is None:
        return None
    if row.value_numeric >= rule.threshold_low:
        return None
    if not any(word in _med_names(db, patient_id) for word in LEVOTHYROXINE_WORDS):
        return None
    return _hit(rule, [_payload(row)], _previous(_series(grouped, "tsh"), row))


def _pregnancy_tsh(rule: ClinicalRule, grouped, patient: Patient, visits: list[Visit]) -> dict | None:
    if not _text_has(patient, visits, ("pregnan",)):
        return None
    row = _latest(grouped, "tsh")
    if row is None or row.value_numeric is None or rule.threshold_high is None:
        return None
    if row.value_numeric <= rule.threshold_high:
        return None
    return _hit(rule, [_payload(row)], _previous(_series(grouped, "tsh"), row))


def _pcos_weight(rule: ClinicalRule, grouped, patient: Patient, visits: list[Visit]) -> dict | None:
    if not _text_has(patient, visits, ("pcos", "polycystic")):
        return None
    rows = [row for row in _series(grouped, "weight") if row.value_numeric]
    if len(rows) < 2 or rule.threshold_high is None:
        return None
    first, last = rows[0], rows[-1]
    if not first.value_numeric:
        return None
    change = (last.value_numeric - first.value_numeric) / first.value_numeric * 100
    if change < rule.threshold_high:
        return None
    return _hit(rule, [_payload(first), _payload(last)], json.dumps([_payload(first)]))


def _evaluate_rule(db: Session, rule: ClinicalRule, grouped, patient: Patient, visits: list[Visit]) -> dict | None:
    if rule.direction == "high":
        return _high(rule, grouped)
    if rule.direction == "low":
        return _low(rule, grouped)
    if rule.code == "hba1c_rise":
        return _hba1c_rise(rule, grouped)
    if rule.code == "hypoglycemia_review":
        return _hypoglycemia(rule, grouped)
    if rule.code == "renal_review":
        return _renal(rule, grouped)
    if rule.code == "screening_gap":
        return _screening_gap(rule, grouped, patient, visits)
    if rule.code == "tsh_on_levothyroxine":
        return _tsh_on_treatment(rule, grouped, db, patient.id)
    if rule.code == "pregnancy_tsh":
        return _pregnancy_tsh(rule, grouped, patient, visits)
    if rule.code == "pcos_weight_rise":
        return _pcos_weight(rule, grouped, patient, visits)
    return None


def refresh_alerts(db: Session, patient: Patient) -> list[ClinicalAlert]:
    sync_patient_observations(db, patient.id)
    observations = (
        db.query(ClinicalObservation)
        .filter(
            ClinicalObservation.patient_id == patient.id,
            ClinicalObservation.verification_status.in_(("recorded", "verified")),
        )
        .order_by(ClinicalObservation.observed_at.asc(), ClinicalObservation.id.asc())
        .all()
    )
    grouped: dict[str, list[ClinicalObservation]] = defaultdict(list)
    for row in observations:
        grouped[row.observation_code].append(row)
    visits = db.query(Visit).filter_by(patient_id=patient.id).order_by(Visit.visit_date.asc()).all()
    rules = db.query(ClinicalRule).filter_by(active=True).all()
    fired: set[str] = set()
    now = datetime.utcnow()
    for rule in rules:
        outcome = _evaluate_rule(db, rule, grouped, patient, visits)
        existing = (
            db.query(ClinicalAlert)
            .filter_by(patient_id=patient.id, rule_code=rule.code, status="open")
            .first()
        )
        if outcome is None:
            if existing:
                existing.status = "resolved"
                existing.updated_at = now
            continue
        fired.add(rule.code)
        if existing:
            existing.rule_version = rule.version
            existing.title = rule.title
            existing.explanation = rule.explanation
            existing.triggering_parameters = outcome["triggering_parameters"]
            existing.previous_values = outcome["previous_values"]
            existing.recommended_review = rule.recommended_review
            existing.guideline_reference = rule.guideline_reference
            existing.severity = rule.severity
            existing.updated_at = now
            continue
        db.add(ClinicalAlert(
            patient_id=patient.id,
            clinic_id=patient.clinic_id or 1,
            rule_code=rule.code,
            rule_version=rule.version,
            title=rule.title,
            explanation=rule.explanation,
            triggering_parameters=outcome["triggering_parameters"],
            previous_values=outcome["previous_values"],
            recommended_review=rule.recommended_review,
            guideline_reference=rule.guideline_reference,
            severity=rule.severity,
            status="open",
            created_at=now,
            updated_at=now,
        ))
    db.flush()
    return (
        db.query(ClinicalAlert)
        .filter_by(patient_id=patient.id, status="open")
        .order_by(ClinicalAlert.severity.desc(), ClinicalAlert.id.desc())
        .all()
    )
