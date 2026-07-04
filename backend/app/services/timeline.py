"""Patient longitudinal timeline aggregation."""

from sqlalchemy.orm import Session

from app.models import LabResult, Visit


def build_patient_timeline(db: Session, patient_id: int) -> dict:
    visits = (
        db.query(Visit)
        .filter_by(patient_id=patient_id)
        .order_by(Visit.visit_date.asc())
        .all()
    )
    labs = (
        db.query(LabResult)
        .filter_by(patient_id=patient_id)
        .order_by(LabResult.result_date.asc())
        .all()
    )

    vitals_series = []
    for v in visits:
        vitals_series.append({
            "date": v.visit_date.date().isoformat(),
            "weight": v.weight,
            "bmi": v.bmi,
            "height": v.height,
            "bp_systolic": v.bp_systolic,
            "bp_diastolic": v.bp_diastolic,
        })

    lab_series: dict[str, list] = {}
    for lab in labs:
        key = lab.test_name.strip()
        if key not in lab_series:
            lab_series[key] = []
        try:
            val = float("".join(c for c in lab.value if c.isdigit() or c == ".") or "0")
        except ValueError:
            val = None
        lab_series[key].append({
            "date": lab.result_date.isoformat(),
            "value": val if val else lab.value,
            "unit": lab.unit,
        })

    return {
        "vitals": vitals_series,
        "labs": lab_series,
        "visit_count": len(visits),
    }
