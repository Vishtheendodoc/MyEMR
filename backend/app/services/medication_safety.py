"""Prescription safety checks. Nothing here rewrites a prescription."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models import Bill, ClinicalObservation, DrugPairInteraction, Prescription, SubstitutionRequest, Visit
from app.services.clinical_safety import check_drug_comorbidity_interactions

RENAL_REVIEW = ("metformin", "empagliflozin", "dapagliflozin", "canagliflozin", "ertugliflozin")


def _label(rx: Prescription) -> tuple[str, str]:
    generic = (rx.custom_generic_name or "").strip()
    brand = (rx.custom_drug_name or "").strip()
    if rx.brand_medication:
        brand = brand or (rx.brand_medication.brand_name or "")
        if rx.brand_medication.generic_drug and not generic:
            generic = rx.brand_medication.generic_drug.generic_name or ""
    molecule = generic or brand
    return molecule.lower(), brand or molecule


def _duration_days(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.search(r"(\d+)", raw)
    if not match:
        return None
    count = int(match.group(1))
    text = raw.lower()
    if "week" in text:
        return count * 7
    if "month" in text:
        return count * 30
    return count


def _latest_visits(db: Session, patient_id: int) -> list[Visit]:
    return (
        db.query(Visit)
        .options(joinedload(Visit.prescriptions).joinedload(Prescription.brand_medication))
        .filter_by(patient_id=patient_id)
        .order_by(Visit.visit_date.desc(), Visit.id.desc())
        .limit(2)
        .all()
    )


def medication_safety(db: Session, patient_id: int, allergies: str | None) -> dict:
    visits = _latest_visits(db, patient_id)
    current = visits[0] if visits else None
    previous = visits[1] if len(visits) > 1 else None
    current_rows = list(current.prescriptions) if current else []
    previous_rows = list(previous.prescriptions) if previous else []
    lines = []
    molecules: dict[str, list[str]] = {}
    for rx in current_rows:
        molecule, display = _label(rx)
        molecules.setdefault(molecule, []).append(display)
        lines.append({
            "prescription_id": rx.id,
            "display": display,
            "molecule": molecule,
            "duration_days": _duration_days(rx.duration),
        })
    duplicates = [
        {"molecule": molecule, "names": names}
        for molecule, names in molecules.items()
        if molecule and len(names) > 1
    ]
    previous_molecules = {_label(rx)[0] for rx in previous_rows}
    current_molecules = {line["molecule"] for line in lines}
    added = sorted(current_molecules - previous_molecules)
    stopped = sorted(molecule for molecule in previous_molecules - current_molecules if molecule)
    pairs = db.query(DrugPairInteraction).all()
    interactions = []
    blob = " ".join(current_molecules)
    for pair in pairs:
        if pair.generic_a in blob and pair.generic_b in blob:
            interactions.append({
                "drugs": [pair.generic_a, pair.generic_b],
                "severity": pair.severity,
                "recommendation": pair.recommendation,
            })
    comorbidity = []
    if current and current.comorbidities:
        names = [part.strip() for part in current.comorbidities.split(",") if part.strip()]
        for rx in current_rows:
            if rx.brand_medication:
                comorbidity.extend(check_drug_comorbidity_interactions(db, rx.brand_medication.generic_drug_id, names))
    egfr = (
        db.query(ClinicalObservation)
        .filter_by(patient_id=patient_id, observation_code="egfr")
        .order_by(ClinicalObservation.observed_at.desc())
        .first()
    )
    renal = []
    if egfr and egfr.value_numeric is not None and egfr.value_numeric < 45:
        for line in lines:
            if any(word in line["molecule"] for word in RENAL_REVIEW):
                renal.append({
                    "medicine": line["display"],
                    "egfr": egfr.value_numeric,
                    "recommendation": "Review the renal dose. The prescription was not changed.",
                })
    allergy_text = (allergies or "").lower()
    allergy_hits = []
    if allergy_text.strip():
        for line in lines:
            token = line["molecule"]
            display_hit = bool(line["display"] and line["display"].lower() in allergy_text)
            if (token and token in allergy_text) or display_hit:
                allergy_hits.append({"medicine": line["display"], "allergy": allergies})
    since = datetime.utcnow() - timedelta(days=90)
    bills = (
        db.query(Bill)
        .filter(Bill.patient_id == patient_id, Bill.created_at >= since)
        .all()
    )
    pharmacy_text = " ".join((bill.description or "") + " " + (bill.line_items or "") for bill in bills if (bill.category or "") == "pharmacy").lower()
    if not any((bill.category or "") == "pharmacy" for bill in bills):
        dispensed = {"compared": False, "note": "No pharmacy bill in the last 90 days, so dispensed items were not compared.", "missing": []}
    else:
        missing = [line["display"] for line in lines if line["display"].lower() not in pharmacy_text and line["molecule"] not in pharmacy_text]
        dispensed = {"compared": True, "note": "Compared with pharmacy bill text. A missing name is a prompt to review, not proof it was not supplied.", "missing": missing}
    refills = [
        {"prescription_id": line["prescription_id"], "display": line["display"], "duration_days": line["duration_days"]}
        for line in lines
        if line["duration_days"]
    ]
    return {
        "current_visit_id": current.id if current else None,
        "previous_visit_id": previous.id if previous else None,
        "current": lines,
        "added_since_previous": added,
        "stopped_since_previous": stopped,
        "duplicates": duplicates,
        "drug_interactions": interactions,
        "comorbidity_warnings": comorbidity,
        "renal_review": renal,
        "allergy_warnings": allergy_hits,
        "dispensed": dispensed,
        "refills": refills,
        "substitutions_do_not_change_the_prescription": True,
    }


def request_substitution(
    db: Session,
    *,
    patient_id: int,
    prescription: Prescription,
    requested_brand: str,
    reason: str | None,
    user_id: int,
) -> SubstitutionRequest:
    _, display = _label(prescription)
    row = SubstitutionRequest(
        patient_id=patient_id,
        prescription_id=prescription.id,
        current_label=display,
        requested_brand=requested_brand.strip(),
        status="pending",
        reason=reason,
        requested_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def decide_substitution(db: Session, row: SubstitutionRequest, status: str, user_id: int) -> SubstitutionRequest:
    row.status = status
    row.decided_by = user_id
    row.decided_at = datetime.utcnow()
    db.flush()
    return row
