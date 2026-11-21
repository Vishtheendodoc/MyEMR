"""Patient longitudinal timeline aggregation."""

from sqlalchemy.orm import Session

from app.models import LabResult, Visit
from app.services.clinic_time import clinic_day


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
            "date": clinic_day(v.visit_date).isoformat(),
            "weight": v.weight,
            "bmi": v.bmi,
            "height": v.height,
            "bp_systolic": v.bp_systolic,
            "bp_diastolic": v.bp_diastolic,
        })

    from app.services.patient_360 import PARAM_BY_CODE, canonical_code

    lab_series: dict[str, list] = {}
    for lab in labs:
        code = canonical_code(lab.test_name)
        key = PARAM_BY_CODE[code].name if code else lab.test_name.strip()
        points = lab_series.setdefault(key, [])
        try:
            val = float("".join(c for c in lab.value if c.isdigit() or c == ".") or "0")
        except ValueError:
            val = None
        point = {
            "date": lab.result_date.isoformat(),
            "value": val if val else lab.value,
            "unit": lab.unit,
        }
        if points and points[-1]["date"] == point["date"]:
            points[-1] = point
        else:
            points.append(point)

    return {
        "vitals": vitals_series,
        "labs": lab_series,
        "visit_count": len(visits),
    }
